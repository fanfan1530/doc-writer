"""AI Copilot API —— SSE 流式对话 + 会话管理。"""

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, func

from app.core.model_manager import ModelManager
from app.core.rag_retriever import RAGRetriever
from app.services.copilot_service import CopilotService
from app.services.document_service import DocumentService
from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models import Conversation, Message

router = APIRouter(prefix="/api/copilot", tags=["AI Copilot"])

model_manager = ModelManager()
rag = RAGRetriever()
doc_service = DocumentService(model_manager=model_manager, rag_retriever=rag)
copilot = CopilotService(model_manager=model_manager, rag_retriever=rag, doc_service=doc_service)


# ── 请求模型 ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., description="用户消息")
    conversation_id: int | None = Field(None, description="对话 ID，不传则创建新对话")
    doc_context: str = Field("", description="当前关联的文书全文")
    include_history: bool = Field(True, description="是否携带历史消息")


class ConversationTitleRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)


# ── 端点 ─────────────────────────────────────────────────

@router.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """SSE 流式对话 —— 发送消息并接收 AI 副驾驶的流式回复。

    事件类型:
    - thinking: AI 思考/工具调用中
    - tool_call: 调用工具
    - tool_result: 工具返回结果
    - chunk: 回复文本片段
    - error: 错误信息
    - done: 对话完成
    """
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    # 获取或创建会话
    conv_id = body.conversation_id
    if not conv_id:
        conv_id = await _create_conversation(user_id, body.message)

    # 加载历史
    history: list[dict] = []
    if body.include_history:
        history = await _load_history(conv_id)

    # 保存用户消息
    await _save_message(conv_id, "user", body.message)

    async def event_stream():
        full_reply = ""
        async for sse_data in copilot.stream_chat(
            user_message=body.message,
            history=history,
            doc_context=body.doc_context,
        ):
            # 解析 SSE 数据，提取文本
            if "event: chunk" in sse_data:
                import json as _json
                try:
                    data_part = sse_data.split("data: ")[1].strip()
                    chunk_data = _json.loads(data_part)
                    full_reply += chunk_data.get("text", "")
                except Exception:
                    pass
            yield sse_data

        # 保存 AI 回复 + 更新会话标题
        if full_reply:
            await _save_message(conv_id, "assistant", full_reply)
            await _auto_title(conv_id, body.message)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "X-Conversation-Id": str(conv_id),
        },
    )


@router.get("/conversations")
async def list_conversations(request: Request, limit: int = 20, offset: int = 0):
    """获取用户的对话历史列表。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(min(limit, 100))
        )
        rows = result.scalars().all()
        count = (await db.execute(
            select(func.count()).select_from(Conversation).where(Conversation.user_id == user_id)
        )).scalar()

        return {
            "conversations": [
                {
                    "id": r.id,
                    "title": r.title,
                    "doc_type": r.doc_type,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                    "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                }
                for r in rows
            ],
            "total": count,
        }


@router.get("/conversations/{conv_id}")
async def get_conversation(conv_id: int, request: Request):
    """获取指定对话的完整消息历史。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if not conv or conv.user_id != user_id:
            raise HTTPException(status_code=404, detail="对话不存在")

        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
        )
        messages = result.scalars().all()

        return {
            "id": conv.id,
            "title": conv.title,
            "doc_type": conv.doc_type,
            "doc_context": conv.doc_context,
            "messages": [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "tool_calls": m.tool_calls,
                    "doc_snapshot": m.doc_snapshot,
                    "created_at": m.created_at.isoformat() if m.created_at else "",
                }
                for m in messages
            ],
        }


@router.put("/conversations/{conv_id}/context")
async def update_doc_context(conv_id: int, body: dict, request: Request):
    """更新对话关联的文书上下文。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if not conv or conv.user_id != user_id:
            raise HTTPException(status_code=404, detail="对话不存在")

        conv.doc_context = body.get("doc_context", "")
        conv.doc_type = body.get("doc_type", conv.doc_type)
        await db.commit()
        return {"status": "ok"}


@router.put("/conversations/{conv_id}/title")
async def update_title(conv_id: int, body: ConversationTitleRequest, request: Request):
    """手动修改对话标题。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if not conv or conv.user_id != user_id:
            raise HTTPException(status_code=404, detail="对话不存在")
        conv.title = body.title[:256]
        await db.commit()
        return {"status": "ok"}


@router.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: int, request: Request):
    """删除对话及其所有消息。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if not conv or conv.user_id != user_id:
            raise HTTPException(status_code=404, detail="对话不存在")

        # 删除消息
        await db.execute(
            select(Message).where(Message.conversation_id == conv_id)
        )
        result = await db.execute(
            select(Message).where(Message.conversation_id == conv_id)
        )
        for m in result.scalars().all():
            await db.delete(m)
        await db.delete(conv)
        await db.commit()
        return {"status": "deleted"}


# ── 辅助 ─────────────────────────────────────────────────

async def _create_conversation(user_id: int, first_message: str) -> int:
    title = first_message[:50].replace("\n", " ")
    async with AsyncSessionLocal() as db:
        conv = Conversation(user_id=user_id, title=title)
        db.add(conv)
        await db.commit()
        await db.refresh(conv)
        return conv.id


async def _save_message(conv_id: int, role: str, content: str) -> None:
    async with AsyncSessionLocal() as db:
        db.add(Message(conversation_id=conv_id, role=role, content=content[:5000]))
        await db.commit()


async def _load_history(conv_id: int) -> list[dict]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(Message.created_at.asc())
            .limit(30)
        )
        return [
            {"role": m.role, "content": m.content}
            for m in result.scalars().all()
        ]


async def _auto_title(conv_id: int, first_msg: str) -> None:
    """用首条消息自动生成标题。"""
    title = first_msg[:50].replace("\n", " ")
    async with AsyncSessionLocal() as db:
        conv = (await db.execute(
            select(Conversation).where(Conversation.id == conv_id)
        )).scalar_one_or_none()
        if conv and conv.title == title:
            conv.title = title
            await db.commit()
