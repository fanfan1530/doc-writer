"""类案检索 API —— 语义搜索相似案例。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.case_service import search_cases, get_case_detail, seed_cases

router = APIRouter(prefix="/api/cases", tags=["类案检索"])


class CaseSearchRequest(BaseModel):
    description: str = Field(..., min_length=1, max_length=5000, description="案件描述文本")
    case_type: str | None = Field(None, pattern="^(刑事|行政|民事)$", description="案件类型筛选")
    limit: int = Field(10, ge=1, le=20)


class CaseSearchResponse(BaseModel):
    cases: list[dict]
    total: int
    query: str


@router.post("/search", response_model=CaseSearchResponse)
async def search(request: CaseSearchRequest):
    """语义搜索相似案例。"""
    cases = search_cases(
        query=request.description,
        case_type=request.case_type,
        limit=request.limit,
    )
    return CaseSearchResponse(cases=cases, total=len(cases), query=request.description[:100])


@router.get("/{case_id}")
async def get_case(case_id: str):
    """获取案例详情。"""
    case = get_case_detail(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="案例不存在")
    return case


@router.post("/seed")
async def seed():
    """初始化案例索引（幂等操作，已存在则跳过）。"""
    count = seed_cases()
    return {"success": True, "count": count, "message": f"已初始化 {count} 条案例"}
