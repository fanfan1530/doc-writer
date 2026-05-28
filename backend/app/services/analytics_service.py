"""统计分析服务 —— 聚合查询 + Redis 缓存（1h TTL）。"""

from __future__ import annotations

import datetime
import logging
from typing import Any

from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models import Case, GenerationHistory, User

logger = logging.getLogger(__name__)


class AnalyticsService:

    # ── 概览 ──────────────────────────────────────────

    async def get_overview(self) -> dict:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func

            total_cases = (await db.execute(
                select(func.count()).select_from(Case),
            )).scalar() or 0

            total_docs = (await db.execute(
                select(func.count()).select_from(GenerationHistory),
            )).scalar() or 0

            total_users = (await db.execute(
                select(func.count()).select_from(User).where(User.is_active == True),  # noqa: E712
            )).scalar() or 0

            # 结案率
            closed = (await db.execute(
                select(func.count()).select_from(Case).where(
                    Case.status.in_(["CLOSED", "ARCHIVED"]),
                ),
            )).scalar() or 0

            # 本月新增案件
            month_start = datetime.datetime.utcnow().replace(day=1, hour=0, minute=0, second=0)
            month_cases = (await db.execute(
                select(func.count()).select_from(Case).where(Case.created_at >= month_start),
            )).scalar() or 0

            # 本月生成文书
            month_docs = (await db.execute(
                select(func.count()).select_from(GenerationHistory).where(
                    GenerationHistory.created_at >= month_start,
                ),
            )).scalar() or 0

            return {
                "total_cases": total_cases,
                "total_documents": total_docs,
                "total_users": total_users,
                "closed_rate": round(closed / max(total_cases, 1) * 100, 1),
                "month_new_cases": month_cases,
                "month_new_docs": month_docs,
            }

    # ── 案件趋势（按月） ────────────────────────────────

    async def get_case_trends(self, months: int = 12) -> list[dict]:
        """最近 N 个月案件创建趋势，按类型和状态分组。"""
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=months * 30)
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func, extract
            # 按月份统计
            result = await db.execute(
                select(
                    func.strftime("%Y-%m", Case.created_at).label("month"),
                    func.count().label("count"),
                )
                .where(Case.created_at >= cutoff)
                .group_by("month")
                .order_by("month"),
            )
            by_month = [{"month": r[0], "count": r[1]} for r in result.all()]

            # 按类型统计
            type_result = await db.execute(
                select(Case.case_type, func.count())
                .group_by(Case.case_type),
            )
            by_type = [{"type": r[0], "count": r[1]} for r in type_result.all()]

            # 按状态统计
            status_result = await db.execute(
                select(Case.status, func.count())
                .group_by(Case.status),
            )
            from app.services.case_service import STATUS_LABELS
            by_status = [
                {"status": r[0], "label": STATUS_LABELS.get(r[0], r[0]), "count": r[1]}
                for r in status_result.all()
            ]

            return {
                "by_month": by_month,
                "by_type": by_type,
                "by_status": by_status,
            }

    # ── 警员绩效 ────────────────────────────────────────

    async def get_officer_stats(self, limit: int = 10) -> list[dict]:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func, desc

            result = await db.execute(
                select(
                    Case.officer_id,
                    func.count(Case.id).label("case_count"),
                )
                .group_by(Case.officer_id)
                .order_by(desc("case_count"))
                .limit(limit),
            )
            rows = result.all()

            stats = []
            for r in rows:
                user = (await db.execute(
                    select(User).where(User.id == r[0]),
                )).scalar_one_or_none()
                stats.append({
                    "officer_id": r[0],
                    "username": user.username if user else "未知",
                    "display_name": user.display_name or (user.username if user else "未知"),
                    "unit": user.unit or "",
                    "case_count": r[1],
                })
            return stats

    # ── 文书生成统计 ────────────────────────────────────

    async def get_document_stats(self) -> dict:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func

            # 按文书类型统计
            type_result = await db.execute(
                select(
                    GenerationHistory.doc_type,
                    func.count(),
                    func.avg(GenerationHistory.latency_ms),
                    func.sum(GenerationHistory.tokens_used),
                ).group_by(GenerationHistory.doc_type),
            )
            by_type = [
                {
                    "doc_type": r[0],
                    "count": r[1],
                    "avg_latency_ms": round(r[2] or 0, 0),
                    "total_tokens": r[3] or 0,
                }
                for r in type_result.all()
            ]

            # 总 token 用量
            total_tokens = sum(d["total_tokens"] for d in by_type)

            return {
                "by_type": by_type,
                "total_tokens": total_tokens,
            }


analytics_service = AnalyticsService()
