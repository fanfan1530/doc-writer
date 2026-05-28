"""智能生成 API —— 薄路由层，业务逻辑委托给 services 层。"""

import os
import re
import tempfile
import logging

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.file_parser import MAX_FILE_SIZE, parse_uploaded_file, validate_file
from app.core.model_manager import ModelManager
from app.core.rag_retriever import RAGRetriever
from app.core.security import sanitize_llm_input, rate_limiter, raise_rate_limited
from app.core.export.docx_exporter import file_response_from_docx
from app.services.document_service import DocumentService
from app.models.requests import (
    DocumentGenerateRequest,
    ExtractElementsRequest,
    PolishFactRequest,
    SuggestLawsRequest,
)

logger = logging.getLogger(__name__)

# ── 请求模型 ─────────────────────────────────────────────

class DocumentChainRequest(BaseModel):
    input_text: str = Field(..., description="案情描述")
    doc_types: list[str] = Field(..., description="需生成的多份文书类型列表")


class DeadlineCheckRequest(BaseModel):
    doc_type: str = Field(..., description="文书类型")
    fields: dict = Field(default_factory=dict, description="文书字段键值对")


class FillTemplateRequest(BaseModel):
    doc_type: str = Field(..., description="文书类型")
    fields: dict = Field(default_factory=dict, description="用户填写的字段键值对")


class ExportDocxRequest(BaseModel):
    content: str = Field(..., description="文书纯文本内容")
    doc_type: str = Field("", description="文书类型（用于生成文件名）")


# ── 初始化 ───────────────────────────────────────────────

router = APIRouter(prefix="/api/generation", tags=["智能生成"])

model_manager = ModelManager()
rag = RAGRetriever()
doc_service = DocumentService(model_manager=model_manager, rag_retriever=rag)


# ── 端点 ─────────────────────────────────────────────────

@router.post("/document")
async def generate_document(body: DocumentGenerateRequest, request: Request):
    """AI 智能文书生成：要素抽取 + 模板填充 + 法条推荐 + 事实润色。"""
    client_ip = request.client.host if request.client else "unknown"
    rl_info = await rate_limiter.check(client_ip)
    if not rl_info.allowed:
        raise_rate_limited(rl_info)

    sanitized = sanitize_llm_input(body.input_text)
    result = await doc_service.generate_document(body.doc_type, sanitized)
    return {
        "doc_type": body.doc_type,
        "elements": result["elements"],
        "suggested_laws": result["suggested_laws"],
        "case_nature": result["case_nature"],
        "content": result["content"],
    }


@router.post("/extract-elements")
async def extract_elements(body: ExtractElementsRequest):
    """要素抽取（不生成完整文书）。"""
    result = await doc_service.extract_elements(body.input_text, body.doc_type)
    return {
        "elements": result.get("elements", {}),
        "suggested_laws": result.get("suggested_laws", []),
        "case_nature": result.get("case_nature", ""),
    }


@router.post("/polish-fact")
async def polish_fact(body: PolishFactRequest):
    """事实描述润色：口语化 → 规范法律文书语言。"""
    polished = await doc_service.polish_fact(body.raw_fact, body.doc_type)
    return {"original": body.raw_fact, "polished": polished}


@router.post("/suggest-laws")
async def suggest_laws(body: SuggestLawsRequest):
    """根据案情推荐适用法条。"""
    laws = await doc_service.suggest_laws(body.fact, body.doc_type)
    return {"suggested_laws": laws}


@router.post("/fill-template")
async def fill_template(body: FillTemplateRequest, request: Request):
    """手动填写模板：用户逐项填写字段 → 模板填充 + 事实润色 + 法条推荐 + 期限预警。"""
    client_ip = request.client.host if request.client else "unknown"
    rl_info = await rate_limiter.check(client_ip)
    if not rl_info.allowed:
        raise_rate_limited(rl_info)

    fields = {k: sanitize_llm_input(str(v)) if v else v for k, v in body.fields.items()}
    try:
        result = await doc_service.fill_template(body.doc_type, fields)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/templates")
async def list_templates(category: str = "", keyword: str = ""):
    """获取可用的文书模板列表（可按类别筛选 + 关键词搜索）。"""
    templates = rag._templates
    if category:
        templates = [t for t in templates if t.get("category", "") == category]
    if keyword:
        kw = keyword.lower()
        templates = [
            t for t in templates
            if kw in t.get("name", "").lower()
            or kw in t.get("doc_type", "").lower()
            or kw in t.get("description", "").lower()
            or kw in t.get("usage_guide", "").lower()
        ]
    return {
        "templates": [
            {
                "doc_type": t.get("doc_type", ""),
                "name": t.get("name", ""),
                "description": t.get("description", ""),
                "category": t.get("category", ""),
                "is_official": t.get("is_official", False),
                "version": t.get("version", 1),
            }
            for t in templates
        ],
        "total": len(templates),
    }


@router.get("/templates/categories")
async def list_template_categories():
    """获取模板分类列表及各类别数量。"""
    cats: dict[str, int] = {}
    for t in rag._templates:
        cat = t.get("category", "未分类")
        cats[cat] = cats.get(cat, 0) + 1
    return {
        "categories": [
            {"name": k, "count": v} for k, v in sorted(cats.items())
        ],
        "total_templates": len(rag._templates),
    }


@router.get("/templates/{doc_type}")
async def get_template(doc_type: str):
    """获取指定类型的文书模板（含字段定义）。"""
    template = rag.retrieve_template(doc_type)
    if not template:
        raise HTTPException(status_code=404, detail=f"未找到类型为 {doc_type} 的文书模板")
    return template


@router.post("/document-chain")
async def generate_document_chain(body: DocumentChainRequest):
    """批量文书链生成：从同一案情描述一键生成多份关联文书。"""
    if len(body.doc_types) > 8:
        raise HTTPException(status_code=400, detail="单次最多生成8份文书")
    results = await doc_service.generate_document_chain(body.input_text, body.doc_types)
    return {"results": results, "total": len(results)}


@router.post("/check-deadlines")
async def check_legal_deadlines(body: DeadlineCheckRequest):
    """法律期限预警：检查当前文书涉及的法定时限是否合规。"""
    warnings = doc_service.check_legal_deadlines(body.fields, body.doc_type)
    return {"doc_type": body.doc_type, "warnings": warnings, "total": len(warnings)}


class ExtractTimelineRequest(BaseModel):
    case_text: str = Field(..., min_length=1, max_length=10000)


@router.post("/extract-timeline")
async def extract_timeline(body: ExtractTimelineRequest):
    """从案情描述中提取时间序列事件，生成案件时间线。"""
    from app.core.llm.prompts import TIMELINE_EXTRACTION_PROMPT

    prompt = TIMELINE_EXTRACTION_PROMPT.format(case_text=body.case_text)

    try:
        result = await doc_service._call_llm(prompt, max_tokens=2048)
        import json as _json
        # 清理可能的 markdown 代码块
        text = result.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        events = _json.loads(text)
        if isinstance(events, dict):
            events = events.get("events", [])
        if not isinstance(events, list):
            events = []
        return {"events": events, "total": len(events)}
    except Exception as e:
        logger.warning("时间线提取失败: %s", str(e)[:100])
        return {"events": [], "total": 0, "error": str(e)[:200]}


@router.post("/summarize-case-file")
async def summarize_case_file(
    file: UploadFile = File(...),
    doc_type: str = Form(""),
):
    """上传 .doc/.docx 文书 → 解析提取文本 → LLM 整理为案件摘要。"""
    tmp_path = ""
    try:
        validate_file(file)

        content = await file.read()
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"文件过大，最大支持 {MAX_FILE_SIZE // 1024 // 1024} MB",
            )

        suffix = os.path.splitext(file.filename or ".docx")[1].lower()
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        raw_text = parse_uploaded_file(tmp_path, file.filename or "unknown")
        raw_text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]', '', raw_text)
        logger.info("文件解析完成: filename=%s, raw_len=%d", file.filename, len(raw_text))

        sanitized = sanitize_llm_input(raw_text)
        result = await doc_service.summarize_case_file_text(sanitized, doc_type)

        return {
            "success": True,
            "raw_text": raw_text,
            "raw_char_count": len(raw_text),
            "summary": result.get("summary", ""),
            "char_count": len(result.get("summary", "")),
            "warning": result.get("warning", ""),
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception:
        logger.exception("文件处理失败: %s", file.filename)
        raise HTTPException(status_code=500, detail="文件处理失败，请联系管理员")
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)
        except Exception:
            pass


@router.get("/history")
async def get_history(
    doc_type: str = "",
    keyword: str = "",
    since: str = "",
    before: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = 20,
    offset: int = 0,
):
    """获取文书生成历史记录（分页 + 搜索 + 时间筛选 + 服务端排序）。"""
    from datetime import datetime as _dt
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import GenerationHistory
    from sqlalchemy import select, func, and_, desc, asc

    SORT_COLUMNS: dict[str, object] = {
        "created_at": GenerationHistory.created_at,
        "doc_type": GenerationHistory.doc_type,
        "latency_ms": GenerationHistory.latency_ms,
        "id": GenerationHistory.id,
    }

    sort_col = SORT_COLUMNS.get(sort_by, GenerationHistory.created_at)
    sort_fn = desc if sort_order == "desc" else asc

    async with AsyncSessionLocal() as db:
        conditions = []
        if doc_type:
            conditions.append(GenerationHistory.doc_type == doc_type)
        if keyword:
            conditions.append(GenerationHistory.input_text.contains(keyword))
        if since:
            try:
                conditions.append(GenerationHistory.created_at >= _dt.fromisoformat(since))
            except ValueError:
                pass
        if before:
            try:
                conditions.append(GenerationHistory.created_at <= _dt.fromisoformat(before))
            except ValueError:
                pass

        base = select(GenerationHistory)
        if conditions:
            base = base.where(and_(*conditions))

        stmt = (
            base
            .order_by(sort_fn(sort_col))
            .offset(offset)
            .limit(min(limit, 100))
        )

        count_stmt = select(func.count()).select_from(GenerationHistory)
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))

        result = await db.execute(stmt)
        rows = result.scalars().all()
        total = (await db.execute(count_stmt)).scalar()

        return {
            "history": [
                {
                    "id": r.id,
                    "doc_type": r.doc_type,
                    "input_text": r.input_text[:200] if r.input_text else "",
                    "output_content": r.output_content[:500] if r.output_content else "",
                    "model_used": r.model_used,
                    "latency_ms": r.latency_ms,
                    "elements": r.elements,
                    "suggested_laws": r.suggested_laws,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }


@router.get("/history/{history_id}/export")
async def export_history_docx(history_id: int):
    """导出历史文书为 Word 文档（.docx），无需先获取详情。"""
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import GenerationHistory
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        stmt = select(GenerationHistory).where(GenerationHistory.id == history_id)
        result = await db.execute(stmt)
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="记录不存在")
        if not r.output_content.strip():
            raise HTTPException(status_code=400, detail="文书内容为空，无法导出")

        try:
            return file_response_from_docx(r.output_content, r.doc_type)
        except Exception:
            logger.exception("Word 导出失败")
            raise HTTPException(status_code=500, detail="Word 文档生成失败，请联系管理员")


@router.get("/history/{history_id}")
async def get_history_detail(history_id: int):
    """获取单条文书生成历史详情（含完整内容）。"""
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import GenerationHistory
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        stmt = select(GenerationHistory).where(GenerationHistory.id == history_id)
        result = await db.execute(stmt)
        r = result.scalar_one_or_none()
        if not r:
            raise HTTPException(status_code=404, detail="记录不存在")

        return {
            "id": r.id,
            "doc_type": r.doc_type,
            "input_text": r.input_text,
            "output_content": r.output_content,
            "model_used": r.model_used,
            "tokens_used": r.tokens_used,
            "latency_ms": r.latency_ms,
            "elements": r.elements,
            "suggested_laws": r.suggested_laws,
            "created_at": r.created_at.isoformat() if r.created_at else "",
        }


@router.post("/export-docx")
async def export_docx(body: ExportDocxRequest):
    """将生成的文书内容导出为规范公文格式的 Word 文档（.docx）。"""
    if not body.content.strip():
        raise HTTPException(status_code=400, detail="文书内容为空，无法导出")

    try:
        return file_response_from_docx(body.content, body.doc_type)
    except Exception:
        logger.exception("Word 导出失败")
        raise HTTPException(status_code=500, detail="Word 文档生成失败，请联系管理员")
