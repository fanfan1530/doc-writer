"""类案检索 + 案件生命周期管理 API。"""

from fastapi import APIRouter, HTTPException, Request, status, Query, Depends
from pydantic import BaseModel, Field

from app.core.security import require_permission
from app.services.case_service import (
    search_cases, get_case_detail, seed_cases, case_service,
    STATUS_LABELS,
)
from app.services.notification_service import notification_service

router = APIRouter(prefix="/api/cases", tags=["类案检索 & 案件管理"])


# ── 请求模型 ─────────────────────────────────────────────

class CaseSearchRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000, description="案件描述文本")
    case_type: str | None = Field(None, pattern="^(刑事|行政|民事)$", description="案件类型筛选")
    limit: int = Field(10, ge=1, le=20)


class CreateCaseRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    case_type: str = Field("刑事", max_length=32)
    description: str = Field("", max_length=10000)
    unit: str = Field("", max_length=128)
    incident_date: str | None = Field(None)
    location: str = Field("", max_length=256)


class UpdateCaseRequest(BaseModel):
    title: str | None = Field(None, max_length=256)
    description: str | None = Field(None, max_length=10000)
    unit: str | None = Field(None, max_length=128)
    location: str | None = Field(None, max_length=256)


class TransitionRequest(BaseModel):
    target_status: str = Field(...)
    comment: str = Field("", max_length=500)


class SubmitDocumentRequest(BaseModel):
    document_id: int = Field(...)
    doc_type: str = Field(...)
    title: str = Field(...)


class ReviewDocumentRequest(BaseModel):
    action: str = Field(...)  # APPROVE / REJECT / RETURN
    comment: str = Field("", max_length=500)


# ── 类案检索（保持向后兼容）─────────────────────────────────

@router.post("/search")
async def search(request: CaseSearchRequest):
    """语义搜索相似案例。"""
    cases = search_cases(
        query=request.description,
        case_type=request.case_type,
        limit=request.limit,
    )
    return {"cases": cases, "total": len(cases), "query": request.description[:100]}


@router.get("/{case_id}")
async def get_case(case_id: str):
    """获取种子案例详情（以字符串 ID 标识的旧案例）。"""
    case = get_case_detail(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return case


@router.post("/seed")
async def seed():
    """初始化案例索引。"""
    count = seed_cases()
    return {"success": True, "count": count}


# ── 案件 CRUD ─────────────────────────────────────────────

@router.get("")
async def list_cases_db(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    case_type: str | None = Query(None),
    keyword: str = Query(""),
):
    """分页获取案件列表（数据库 ORM）。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    cases, total = await case_service.list_cases(
        limit=limit, offset=offset, status=status,
        case_type=case_type, keyword=keyword,
    )
    return {"cases": cases, "total": total, "statuses": [
        {"key": k, "label": v} for k, v in STATUS_LABELS.items()
    ]}


@router.post("")
async def create_case(
    body: CreateCaseRequest,
    request: Request,
    _=Depends(require_permission("cases:write")),
):
    """创建新案件（需 cases:write 权限）。"""
    user_id = getattr(request.state, "user_id", 0)
    result = await case_service.create_case(
        officer_id=user_id,
        title=body.title,
        case_type=body.case_type,
        description=body.description,
        unit=body.unit,
        incident_date=body.incident_date,
        location=body.location,
    )
    return result


@router.get("/db/{case_id}")
async def get_case_db(case_id: int, request: Request):
    """获取案件详情（ORM 版本）。"""
    user_id = getattr(request.state, "user_id", 0)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")

    case = await case_service.get_case_detail(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")
    return case


@router.put("/db/{case_id}")
async def update_case_db(
    case_id: int,
    body: UpdateCaseRequest,
    request: Request,
    _=Depends(require_permission("cases:write")),
):
    """更新案件信息。"""
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    case = await case_service.update_case(case_id, **updates)
    if not case:
        raise HTTPException(status_code=404, detail="案件不存在")
    return case


@router.post("/db/{case_id}/transition")
async def transition_case(
    case_id: int,
    body: TransitionRequest,
    request: Request,
    _=Depends(require_permission("cases:write")),
):
    """案件状态流转。"""
    user_id = getattr(request.state, "user_id", 0)
    try:
        result = await case_service.transition_status(
            case_id, body.target_status, user_id, body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not result:
        raise HTTPException(status_code=404, detail="案件不存在")
    return result


@router.post("/db/{case_id}/documents")
async def submit_document_to_case(
    case_id: int,
    body: SubmitDocumentRequest,
    request: Request,
    _=Depends(require_permission("documents:write")),
):
    """提交文书到案件。"""
    user_id = getattr(request.state, "user_id", 0)
    result = await case_service.submit_document(
        case_id=case_id,
        document_id=body.document_id,
        doc_type=body.doc_type,
        title=body.title,
        user_id=user_id,
    )
    # 创建通知给同单位领导
    await notification_service.create(
        user_id=user_id,  # 实际应发给审批人，此处简化
        ntype="DOCUMENT_SUBMITTED",
        title=f"文书待审: {body.title}",
        content=f"案件 {case_id} 提交了{body.doc_type}文书，等待审核",
        related_case_id=case_id,
    )
    return result


@router.post("/db/{case_id}/documents/{doc_id}/review")
async def review_document(
    case_id: int,
    doc_id: int,
    body: ReviewDocumentRequest,
    request: Request,
    _=Depends(require_permission("documents:approve")),
):
    """审核文书（需 documents:approve 权限）。"""
    user_id = getattr(request.state, "user_id", 0)
    try:
        result = await case_service.review_document(
            case_id, doc_id, user_id, body.action, body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 通知
    ntype = {
        "APPROVE": "DOCUMENT_APPROVED",
        "REJECT": "DOCUMENT_REJECTED",
        "RETURN": "DOCUMENT_REJECTED",
    }.get(body.action, "DOCUMENT_REJECTED")

    label = {"APPROVE": "通过", "REJECT": "驳回", "RETURN": "退回"}.get(body.action, body.action)
    await notification_service.create(
        user_id=user_id,
        ntype=ntype,
        title=f"文书审核{label}",
        content=f"文书 {doc_id} 已被{label}" + (f": {body.comment}" if body.comment else ""),
        related_case_id=case_id,
    )
    return result
