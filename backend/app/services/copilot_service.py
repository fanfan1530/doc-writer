"""AI Copilot 服务 —— 工具调用编排 + SSE 流式响应。"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator

from app.core.tools import TOOL_DEFINITIONS, ToolExecutor
from app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名资深公安法制审核专家，服务于一线民警的日常警务工作，精通刑法、治安管理处罚法、刑事诉讼法、公安机关办理案件程序规定等法律法规。

## 可用工具
1. search_laws —— 检索法律条文（刑法、治安管理处罚法等），返回具体法条全文
2. search_procedures —— 检索办案程序规定（办案期限、审批流程、证据规则等）
3. generate_document —— 根据案情自动生成公安法律文书（笔录、处罚决定书等）
4. polish_document —— 根据指令修改/润色指定的文书内容
5. check_deadlines —— 检查案件的法定办案期限是否超期
6. analyze_case_nature —— 分析案件属于行政违法、刑事犯罪还是民事纠纷
7. evidence_checklist —— 根据案件类型推荐证据收集清单和取证要点
8. penalty_reference —— 查询特定违法行为的处罚种类、幅度和裁量标准

## 工作原则（必须严格遵守）
- **强制工具使用**：凡是涉及法律条文、办案程序、处罚标准、案件定性、证据指引的问题，必须调用对应工具获取权威信息后再回答，禁止仅凭训练数据直接作答
- **法条引用**：引用法律条文时必须标注法律名称全称、条款编号和具体内容，不得编造或模糊引用
- **回答结构**：先给出结论要点，再展开法律依据和分析，最后给出实务建议
- **专业性**：使用规范的公安法律术语，保持严谨、准确、简洁的文风
- **诚实边界**：对于超出知识范围或工具无法解决的问题，明确告知并建议咨询法制部门
- **文书处理**：生成或修改文书后，完整输出文书全文，不要省略任何部分
- **上下文利用**：如果当前对话关联了文书全文（doc_context），修改文书时必须使用 polish_document 工具"""


class CopilotService:
    """警务 AI 副驾驶服务。"""

    def __init__(
        self,
        model_manager: "ModelManager | None" = None,
        rag_retriever: "RAGRetriever | None" = None,
        doc_service: "DocumentService | None" = None,
    ):
        self._model_manager = model_manager
        self._tools = ToolExecutor(rag_retriever=rag_retriever, doc_service=doc_service)
        self._doc = doc_service

    # ── 客户端/模型参数 ───────────────────────────────────

    def _get_client(self) -> LLMClient:
        if self._model_manager:
            return self._model_manager.get_client()
        from app.config import get_settings
        settings = get_settings()
        return LLMClient(
            api_type="openai",
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() or "sk-local",
        )

    def _get_model_name(self) -> str:
        if self._model_manager:
            return self._model_manager.get_active_config().get("model_name", "")
        from app.config import get_settings
        return get_settings().llm_model_small

    # ── 核心流式对话 ──────────────────────────────────────

    async def stream_chat(
        self,
        user_message: str,
        history: list[dict] | None = None,
        doc_context: str = "",
    ) -> AsyncGenerator[str, None]:
        """SSE 流式对话生成器。"""
        t0 = time.time()

        # 构建消息
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        if doc_context:
            messages.append({
                "role": "system",
                "content": f"当前文书全文（用户可能会要求修改此文书）：\n---\n{doc_context}\n---",
            })

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        model = self._get_model_name()
        client = self._get_client()

        # 第一轮：让 LLM 决定是否调用工具
        yield self._sse("thinking", {"message": "正在分析您的问题..."})

        try:
            # 先用非流式调用检查是否需要工具
            tool_response = await client.chat(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=512,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                timeout=60,
            )
        except Exception as e:
            logger.warning("LLM 工具选择失败: %s", str(e)[:100])
            yield self._sse("error", {"message": "AI 服务暂时不可用，请稍后重试"})
            yield self._sse("done", {"elapsed_ms": int((time.time() - t0) * 1000)})
            return

        # 解析工具调用
        tool_calls = self._parse_tool_calls(tool_response)

        if tool_calls:
            # 收集工具结果，用于构建最终回复
            tool_results_text = ""
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc.get("arguments", {})

                yield self._sse("thinking", {"message": f"正在调用: {tool_name}..."})
                yield self._sse("tool_call", {"tool": tool_name, "args": tool_args})

                tool_result = await self._tools.execute(tool_name, tool_args)
                # polish_document 完整返回，其他工具截断
                display_result = tool_result if tool_name == "polish_document" else tool_result[:500]
                yield self._sse("tool_result", {"tool": tool_name, "result": display_result})

                # polish_document 完成后通知前端替换文书
                if tool_name == "polish_document":
                    yield self._sse("doc_modified", {"content": tool_result})

                # 将工具结果整理为用户消息，避免 tool role 兼容性问题
                tool_results_text += f"\n\n[工具 {tool_name} 的返回结果]:\n{tool_result}"

            # 工具执行完毕后，将结果作为用户消息追加
            messages.append({
                "role": "user",
                "content": f"以下是工具调用的结果:{tool_results_text}\n\n请根据以上工具返回的信息，回答用户的问题。",
            })

            # 工具执行完毕后，生成最终回复
            yield self._sse("thinking", {"message": "正在整理回复..."})

        # 流式生成最终回复
        try:
            async for chunk in client.chat_stream(
                model=model,
                messages=messages,
                temperature=0.5,
                max_tokens=4096,
                timeout=90,
            ):
                text = self._extract_chunk_text(chunk)
                if text:
                    yield self._sse("chunk", {"text": text})
        except Exception as e:
            logger.warning("LLM 流式调用失败, 回退到非流式: %s", str(e)[:100])
            # 回退到非流式
            try:
                fallback = await client.chat(
                    model=model,
                    messages=messages,
                    temperature=0.5,
                    max_tokens=4096,
                    timeout=90,
                )
                yield self._sse("chunk", {"text": fallback})
            except Exception:
                yield self._sse("error", {"message": "回复生成失败，请重试"})

        yield self._sse("done", {"elapsed_ms": int((time.time() - t0) * 1000)})

    # ── 辅助方法 ──────────────────────────────────────────

    def _parse_tool_calls(self, response: Any) -> list[dict]:
        """从 LLM 响应中解析工具调用。"""
        if isinstance(response, dict):
            tcs = response.get("tool_calls", [])
            if tcs:
                return [
                    {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": json.loads(tc.get("function", {}).get("arguments", "{}")),
                    }
                    for tc in tcs
                ]
        return []

    def _extract_chunk_text(self, chunk: Any) -> str:
        """从流式 chunk 中提取文本。"""
        if isinstance(chunk, str):
            return chunk
        if isinstance(chunk, dict):
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                return delta.get("content", "") or ""
        return ""

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
