"""数据分析 API —— 概览统计 + 案件趋势 + 警员绩效 + 导出。"""

from fastapi import APIRouter, HTTPException, Query, Request, status, Depends
from app.core.security import require_permission
from app.services.analytics_service import analytics_service

router = APIRouter(prefix="/api/analytics", tags=["数据分析"])


@router.get("/overview")
async def overview(
    request: Request,
    _=Depends(require_permission("analytics:read")),
):
    """全局概览统计。"""
    data = await analytics_service.get_overview()
    return data


@router.get("/case-trends")
async def case_trends(
    request: Request,
    months: int = Query(12, ge=3, le=36),
    _=Depends(require_permission("analytics:read")),
):
    """案件趋势（按月/按类型/按状态）。"""
    data = await analytics_service.get_case_trends(months)
    return data


@router.get("/officer-stats")
async def officer_stats(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    _=Depends(require_permission("analytics:read")),
):
    """警员办案绩效排行。"""
    data = await analytics_service.get_officer_stats(limit)
    return {"officers": data}


@router.get("/document-stats")
async def document_stats(
    request: Request,
    _=Depends(require_permission("analytics:read")),
):
    """文书生成统计。"""
    data = await analytics_service.get_document_stats()
    return data
