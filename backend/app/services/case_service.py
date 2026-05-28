"""案件生命周期管理服务 —— ChromaDB 检索 + 状态机 + CRUD。"""

from __future__ import annotations

import datetime
import json as _json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models import (
    Case, CaseDocument, CaseEvidence, CaseTimeline, ReviewRecord,
)

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# ChromaDB 案例检索（保留向后兼容）
# ══════════════════════════════════════════════════════════

_CASES_COLLECTION = "doc_writer_cases"
_chroma_client = None


def _get_chroma():
    global _chroma_client
    if _chroma_client is not None:
        return _chroma_client
    try:
        import chromadb
        persist_dir = os.getenv(
            "CHROMA_PERSIST_DIR",
            str(Path(__file__).resolve().parent.parent / "knowledge" / "chroma_db"),
        )
        _chroma_client = chromadb.PersistentClient(path=persist_dir)
        return _chroma_client
    except Exception as e:
        logger.warning("ChromaDB 初始化失败: %s", str(e)[:100])
        return None


def _load_cases() -> list[dict]:
    cases_path = Path(__file__).resolve().parent.parent / "knowledge" / "cases.json"
    if not cases_path.exists():
        return []
    with open(cases_path, "r", encoding="utf-8") as f:
        return _json.load(f)


def seed_cases() -> int:
    """将种子案例数据写入 ChromaDB 索引。幂等操作。"""
    client = _get_chroma()
    if client is None:
        return 0
    cases = _load_cases()
    if not cases:
        return 0
    try:
        try:
            existing = client.get_collection(_CASES_COLLECTION)
            if existing.count() > 0:
                logger.info("案例索引已存在 (%d 条), 跳过初始化", existing.count())
                return existing.count()
        except Exception:
            pass
        try:
            client.delete_collection(_CASES_COLLECTION)
        except Exception:
            pass
        collection = client.create_collection(
            name=_CASES_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )
        documents, metadatas, ids = [], [], []
        for case in cases:
            text = f"{case.get('title', '')} | {case.get('case_type', '')} | {case.get('key_facts', '')}"
            documents.append(text)
            metadatas.append({
                "case_id": case.get("id", ""),
                "title": case.get("title", ""),
                "case_type": case.get("case_type", ""),
                "key_facts": case.get("key_facts", ""),
                "penalty_outcome": case.get("penalty_outcome", ""),
                "laws": _json.dumps(case.get("laws", [])),
                "evidence_list": _json.dumps(case.get("evidence_list", [])),
                "procedural_notes": case.get("procedural_notes", ""),
            })
            ids.append(case.get("id", f"case_{len(ids)}"))
        batch_size = 20
        for start in range(0, len(documents), batch_size):
            end = start + batch_size
            collection.add(
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                ids=ids[start:end],
            )
        logger.info("案例索引构建完成: %d 条案例", len(documents))
        return len(documents)
    except Exception as e:
        logger.warning("案例索引构建失败: %s", str(e)[:100])
        return 0


def search_cases(
    query: str, case_type: Optional[str] = None, limit: int = 10,
) -> list[dict]:
    """语义搜索相似案例。回退到关键词搜索。"""
    client = _get_chroma()
    if client is not None:
        try:
            collection = client.get_collection(_CASES_COLLECTION)
            n_results = limit + 5 if case_type else limit
            results = collection.query(query_texts=[query], n_results=n_results)
            items = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    meta = results["metadatas"][0][i] if results["metadatas"] else {}
                    distance = results["distances"][0][i] if results.get("distances") and results["distances"][0] else 1.0
                    score = max(0, 1 - distance)
                    if case_type and meta.get("case_type") != case_type:
                        continue
                    items.append(_format_chroma_case(meta, score))
                    if len(items) >= limit:
                        break
            if items:
                return items
        except Exception as e:
            logger.warning("向量搜索失败，回退关键词: %s", str(e)[:100])
    return _keyword_search(query, case_type, limit)


def get_case_detail(case_id: str) -> Optional[dict]:
    """获取 ChromaDB 案例详情（基于 cases.json）。"""
    cases = _load_cases()
    for c in cases:
        if c.get("id") == case_id:
            return c
    return None


def _format_chroma_case(meta: dict, score: float) -> dict:
    try:
        laws = _json.loads(meta.get("laws", "[]"))
    except (_json.JSONDecodeError, TypeError):
        laws = []
    try:
        evidence = _json.loads(meta.get("evidence_list", "[]"))
    except (_json.JSONDecodeError, TypeError):
        evidence = []
    return {
        "id": meta.get("case_id", ""),
        "title": meta.get("title", ""),
        "case_type": meta.get("case_type", ""),
        "key_facts": meta.get("key_facts", ""),
        "penalty_outcome": meta.get("penalty_outcome", ""),
        "laws": laws,
        "evidence_list": evidence,
        "procedural_notes": meta.get("procedural_notes", ""),
        "similarity_score": round(score, 4),
    }


def _keyword_search(query: str, case_type: Optional[str] = None, limit: int = 10) -> list[dict]:
    cases = _load_cases()
    tokens = set(query.lower().split())
    scored = []
    for case in cases:
        if case_type and case.get("case_type") != case_type:
            continue
        text = f"{case.get('title', '')} {case.get('key_facts', '')} {case.get('case_type', '')}"
        text_lower = text.lower()
        s = sum(1 for t in tokens if t in text_lower)
        if case_type and case.get("case_type") == case_type:
            s += 2
        if s > 0:
            scored.append((s, case))
    scored.sort(key=lambda x: x[0], reverse=True)
    max_score = max((s for s, _ in scored), default=1)
    return [
        _format_chroma_case_from_raw(c, s / max_score if max_score > 0 else 0)
        for s, c in scored[:limit]
    ]


def _format_chroma_case_from_raw(case: dict, score: float) -> dict:
    return {
        "id": case.get("id", ""),
        "title": case.get("title", ""),
        "case_type": case.get("case_type", ""),
        "key_facts": case.get("key_facts", ""),
        "penalty_outcome": case.get("penalty_outcome", ""),
        "laws": case.get("laws", []),
        "evidence_list": case.get("evidence_list", []),
        "procedural_notes": case.get("procedural_notes", ""),
        "similarity_score": round(score, 4),
    }

# ── 状态机 ──────────────────────────────────────────────

CASE_STATUSES: list[str] = [
    "FILING", "INVESTIGATING", "REVIEWING", "APPROVED", "CLOSED", "ARCHIVED",
]

STATUS_LABELS: dict[str, str] = {
    "FILING": "立案中",
    "INVESTIGATING": "侦查中",
    "REVIEWING": "审核中",
    "APPROVED": "已批准",
    "CLOSED": "已结案",
    "ARCHIVED": "已归档",
}

VALID_TRANSITIONS: dict[str, list[str]] = {
    "FILING": ["INVESTIGATING"],
    "INVESTIGATING": ["REVIEWING", "FILING"],  # 可退回补充侦查
    "REVIEWING": ["APPROVED", "INVESTIGATING"],
    "APPROVED": ["CLOSED", "REVIEWING"],
    "CLOSED": ["ARCHIVED", "INVESTIGATING"],  # 可重新打开
    "ARCHIVED": [],  # 终态
}


def can_transition(current: str, target: str) -> bool:
    return target in VALID_TRANSITIONS.get(current, [])


# ── 案件服务 ────────────────────────────────────────────

class CaseService:

    async def create_case(
        self, officer_id: int, title: str, case_type: str,
        description: str = "", unit: str = "",
        incident_date: str | None = None, location: str = "",
    ) -> dict:
        async with AsyncSessionLocal() as db:
            case_number = await self._gen_case_number(db, case_type)
            case = Case(
                case_number=case_number,
                title=title,
                case_type=case_type,
                status="FILING",
                officer_id=officer_id,
                unit=unit,
                description=description,
                incident_date=datetime.datetime.fromisoformat(incident_date) if incident_date else None,
                location=location,
            )
            db.add(case)
            await db.commit()
            await db.refresh(case)

            # 记录时间线
            db.add(CaseTimeline(
                case_id=case.id,
                event="立案",
                description=f"案件「{title}」立案，编号 {case_number}",
                occurred_at=datetime.datetime.utcnow(),
                recorded_by=officer_id,
            ))
            await db.commit()

            return self._format_case(case)

    async def update_case(self, case_id: int, **kwargs: Any) -> dict | None:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
            if not case:
                return None
            for k, v in kwargs.items():
                if v is not None and hasattr(case, k):
                    setattr(case, k, v)
            await db.commit()
            await db.refresh(case)
            return self._format_case(case)

    async def transition_status(
        self, case_id: int, target_status: str, user_id: int, comment: str = "",
    ) -> dict | None:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
            if not case:
                return None

            if not can_transition(case.status, target_status):
                raise ValueError(
                    f"不允许从 {STATUS_LABELS.get(case.status, case.status)} "
                    f"转为 {STATUS_LABELS.get(target_status, target_status)}",
                )

            old_status = case.status
            case.status = target_status

            db.add(CaseTimeline(
                case_id=case.id,
                event=f"状态变更: {STATUS_LABELS.get(old_status, old_status)} → {STATUS_LABELS.get(target_status, target_status)}",
                description=comment or f"案件状态从 {old_status} 变更为 {target_status}",
                occurred_at=datetime.datetime.utcnow(),
                recorded_by=user_id,
            ))
            await db.commit()
            await db.refresh(case)
            return self._format_case(case)

    async def get_case_detail(self, case_id: int) -> dict | None:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            case = (await db.execute(select(Case).where(Case.id == case_id))).scalar_one_or_none()
            if not case:
                return None

            # 查询关联文书
            docs = (await db.execute(
                select(CaseDocument).where(CaseDocument.case_id == case_id),
            )).scalars().all()

            # 查询证据
            evidences = (await db.execute(
                select(CaseEvidence).where(CaseEvidence.case_id == case_id),
            )).scalars().all()

            # 查询时间线
            timelines = (await db.execute(
                select(CaseTimeline).where(CaseTimeline.case_id == case_id).order_by(CaseTimeline.created_at.desc()),
            )).scalars().all()

            # 查询审查记录
            reviews = (await db.execute(
                select(ReviewRecord).where(ReviewRecord.case_id == case_id).order_by(ReviewRecord.created_at.desc()),
            )).scalars().all()

            result = self._format_case(case)
            result["documents"] = [
                {
                    "id": d.id,
                    "document_id": d.document_id,
                    "doc_type": d.doc_type,
                    "title": d.title,
                    "status": d.status,
                    "submitted_by": d.submitted_by,
                    "submitted_at": d.submitted_at.isoformat() if d.submitted_at else "",
                    "created_at": d.created_at.isoformat() if d.created_at else "",
                }
                for d in docs
            ]
            result["evidences"] = [
                {
                    "id": e.id,
                    "name": e.name,
                    "ev_type": e.ev_type,
                    "file_path": e.file_path,
                    "uploaded_by": e.uploaded_by,
                    "uploaded_at": e.uploaded_at.isoformat() if e.uploaded_at else "",
                }
                for e in evidences
            ]
            result["timeline"] = [
                {
                    "id": t.id,
                    "event": t.event,
                    "description": t.description,
                    "occurred_at": t.occurred_at.isoformat() if t.occurred_at else "",
                    "recorded_by": t.recorded_by,
                }
                for t in timelines
            ]
            result["reviews"] = [
                {
                    "id": r.id,
                    "document_id": r.document_id,
                    "reviewer_id": r.reviewer_id,
                    "action": r.action,
                    "comment": r.comment,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in reviews
            ]
            return result

    async def list_cases(
        self, limit: int = 20, offset: int = 0,
        status: str | None = None, case_type: str | None = None,
        officer_id: int | None = None, keyword: str = "",
    ) -> tuple[list[dict], int]:
        async with AsyncSessionLocal() as db:
            from sqlalchemy import select, func, desc

            q = select(Case)
            count_q = select(func.count()).select_from(Case)

            if status:
                q = q.where(Case.status == status)
                count_q = count_q.where(Case.status == status)
            if case_type:
                q = q.where(Case.case_type == case_type)
                count_q = count_q.where(Case.case_type == case_type)
            if officer_id:
                q = q.where(Case.officer_id == officer_id)
                count_q = count_q.where(Case.officer_id == officer_id)
            if keyword:
                q = q.where(Case.title.contains(keyword) | Case.description.contains(keyword))
                count_q = count_q.where(Case.title.contains(keyword) | Case.description.contains(keyword))

            total = (await db.execute(count_q)).scalar() or 0
            result = await db.execute(
                q.order_by(desc(Case.updated_at)).offset(offset).limit(min(limit, 100)),
            )
            rows = result.scalars().all()
            return [self._format_case(c) for c in rows], total

    async def submit_document(
        self, case_id: int, document_id: int, doc_type: str, title: str, user_id: int,
    ) -> dict:
        async with AsyncSessionLocal() as db:
            cd = CaseDocument(
                case_id=case_id,
                document_id=document_id,
                doc_type=doc_type,
                title=title,
                status="SUBMITTED",
                submitted_by=user_id,
                submitted_at=datetime.datetime.utcnow(),
            )
            db.add(cd)
            db.add(CaseTimeline(
                case_id=case_id,
                event="文书提交",
                description=f"提交文书「{title}」({doc_type})",
                occurred_at=datetime.datetime.utcnow(),
                recorded_by=user_id,
            ))
            await db.commit()
            await db.refresh(cd)
            return {
                "id": cd.id,
                "case_id": cd.case_id,
                "doc_type": cd.doc_type,
                "title": cd.title,
                "status": cd.status,
            }

    async def review_document(
        self, case_id: int, doc_id: int, reviewer_id: int,
        action: str, comment: str = "",
    ) -> dict:
        """审核文书: APPROVE / REJECT / RETURN。"""
        if action not in ("APPROVE", "REJECT", "RETURN"):
            raise ValueError(f"无效的审核操作: {action}")

        async with AsyncSessionLocal() as db:
            from sqlalchemy import select
            doc = (await db.execute(
                select(CaseDocument).where(CaseDocument.id == doc_id, CaseDocument.case_id == case_id),
            )).scalar_one_or_none()
            if not doc:
                raise ValueError("文书不存在")

            doc.status = action + "ED" if action != "RETURN" else "DRAFT"

            record = ReviewRecord(
                case_id=case_id,
                document_id=doc_id,
                reviewer_id=reviewer_id,
                action=action,
                comment=comment,
            )
            db.add(record)

            action_label = {"APPROVE": "审批通过", "REJECT": "驳回", "RETURN": "退回修改"}.get(action, action)
            db.add(CaseTimeline(
                case_id=case_id,
                event=f"文书{action_label}",
                description=f"文书「{doc.title}」{action_label}" + (f": {comment}" if comment else ""),
                occurred_at=datetime.datetime.utcnow(),
                recorded_by=reviewer_id,
            ))
            await db.commit()
            return {
                "id": record.id,
                "action": record.action,
                "comment": record.comment,
                "document_status": doc.status,
            }

    # ── 辅助 ──────────────────────────────────────────

    @staticmethod
    def _format_case(c: Case) -> dict:
        return {
            "id": c.id,
            "case_number": c.case_number,
            "title": c.title,
            "case_type": c.case_type,
            "status": c.status,
            "status_label": STATUS_LABELS.get(c.status, c.status),
            "officer_id": c.officer_id,
            "unit": c.unit,
            "description": c.description,
            "incident_date": c.incident_date.isoformat() if c.incident_date else "",
            "location": c.location,
            "created_at": c.created_at.isoformat() if c.created_at else "",
            "updated_at": c.updated_at.isoformat() if c.updated_at else "",
        }

    @staticmethod
    async def _gen_case_number(db, case_type: str) -> str:
        from sqlalchemy import select, func
        today = datetime.date.today()
        prefix = {"刑事": "X", "行政": "XZ", "民事": "MS"}.get(case_type, "QT")
        date_str = today.strftime("%Y%m%d")
        base = f"{prefix}{date_str}"
        count = (await db.execute(
            select(func.count()).select_from(Case).where(Case.case_number.like(f"{base}%")),
        )).scalar() or 0
        return f"{base}{count + 1:04d}"


# 全局单例
case_service = CaseService()
