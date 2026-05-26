"""
RAG 知识检索 —— 关键词检索 + 模板匹配。
优先从 DB 读取知识库，DB 为空时回退到 JSON 文件。
生产环境替换为 Milvus/pgvector + BM25 + Cross-encoder 重排序。
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any

from app.config import get_settings


class RAGRetriever:
    """知识检索引擎。"""

    def __init__(self):
        settings = get_settings()
        self._knowledge_dir = Path(settings.knowledge_dir)
        self._laws: list[dict] = []
        self._templates: list[dict] = []
        self._error_patterns: list[dict] = []
        self._vector_ready = False
        self._load_knowledge()

    def _load_knowledge(self):
        """优先从 DB 加载，DB 为空时回退到 JSON 文件。"""
        if self._try_load_from_db():
            self._build_index()
            return
        self._load_from_json()
        self._build_index()

    def _build_index(self):
        try:
            from app.core.vector_rag import build_index
            self._vector_ready = build_index(self._laws, self._templates)
        except Exception:
            self._vector_ready = False

    def _load_from_json(self):
        for name, target in [
            ("laws.json", "_laws"),
            ("templates.json", "_templates"),
            ("error_patterns.json", "_error_patterns"),
        ]:
            path = self._knowledge_dir / name
            if path.exists():
                try:
                    setattr(self, target, json.loads(path.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, IOError):
                    pass

    def _try_load_from_db(self) -> bool:
        """尝试从 DB 加载知识库，成功返回 True。"""
        try:
            import asyncio
            from app.infrastructure.database import AsyncSessionLocal
            from app.infrastructure.models import DocumentTemplate, Law, ErrorPattern
            from sqlalchemy import select, func

            async def _load():
                async with AsyncSessionLocal() as db:
                    # 检查是否有数据
                    count = (await db.execute(select(func.count()).select_from(DocumentTemplate))).scalar()
                    if count == 0:
                        return False

                    # 加载模板
                    result = await db.execute(select(DocumentTemplate).where(DocumentTemplate.is_active == True))
                    self._templates = [r.to_api_dict() for r in result.scalars().all()]

                    # 加载法条
                    result = await db.execute(select(Law))
                    self._laws = [
                        {
                            "law_name": r.law_name,
                            "article_number": r.article_number,
                            "content": r.content,
                            "penalty_range": r.penalty_range,
                            "keywords": r.keywords,
                            "applicable_doc_types": r.applicable_doc_types,
                        }
                        for r in result.scalars().all()
                    ]

                    # 加载错误模式
                    result = await db.execute(select(ErrorPattern))
                    self._error_patterns = [
                        {
                            "error_description": r.error_description,
                            "incorrect_example": r.incorrect_example,
                            "correct_example": r.correct_example,
                            "applicable_doc_types": r.applicable_doc_types,
                        }
                        for r in result.scalars().all()
                    ]
                    return True

            try:
                loop = asyncio.get_running_loop()
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(_load(), loop)
                future.result(timeout=5)
            except RuntimeError:
                asyncio.run(_load())
            return bool(self._templates or self._laws)
        except Exception:
            return False

    def retrieve_laws(self, query: str, doc_type: str = "") -> str:
        # 根据文书类型预过滤：行政类文书排除刑事法律
        admin_doc_types = {
            "行政处罚决定书", "检查笔录", "行政处罚告知笔录",
            "治安调解协议书", "调解协议书", "扣押决定书",
        }
        if doc_type in admin_doc_types:
            candidates = [
                l for l in self._laws
                if "刑事诉讼法" not in l.get("law_name", "")
                and "刑法" not in l.get("law_name", "")
                and "刑事案件" not in l.get("law_name", "")
            ]
        else:
            candidates = self._laws

        # 优先向量检索，回退关键词
        results: list[dict] = []
        if self._vector_ready and query.strip():
            try:
                from app.core.vector_rag import vector_search
                vector_results = vector_search(query, n_results=8)
                law_ids = {vr["id"] for vr in vector_results if vr["type"] == "law"}
                if law_ids:
                    # 用原始 self._laws 的索引匹配向量检索的 ID
                    for i, law in enumerate(self._laws):
                        if f"law-{i}" in law_ids and law in candidates:
                            results.append(law)
                    # 向量搜索结果不够时关键词补充
                    if len(results) < 3:
                        extra = self._keyword_search(candidates, query, doc_type, top_k=5)
                        existing_ids = {id(r) for r in results}
                        for law in extra:
                            if id(law) not in existing_ids:
                                results.append(law)
            except Exception:
                pass

        if not results:
            results = self._keyword_search(candidates, query, doc_type, top_k=5)

        if not results:
            return "未找到相关法条。"
        lines = []
        for r in results[:5]:
            lines.append(
                f"【{r.get('law_name', '')}】第{r.get('article_number', '')}条: "
                f"{r.get('content', '')}" +
                (f" (处罚幅度: {r.get('penalty_range', '')})" if r.get('penalty_range') else "")
            )
        return "\n\n".join(lines)

    def retrieve_error_patterns(self, doc_type: str = "") -> str:
        candidates = self._error_patterns
        if doc_type:
            candidates = [
                p for p in candidates
                if doc_type in p.get("applicable_doc_types", [])
            ] or candidates
        results = candidates[:5]
        if not results:
            return "暂无历史错误记录。"
        lines = []
        for r in results:
            lines.append(
                f"- 错误: {r.get('error_description', '')}\n"
                f"  错误示例: {r.get('incorrect_example', '')}\n"
                f"  正确示例: {r.get('correct_example', '')}"
            )
        return "\n".join(lines)

    def retrieve_template(self, doc_type: str) -> dict | None:
        for t in self._templates:
            if t.get("doc_type") == doc_type:
                return t
        return None

    def retrieve_relevant_knowledge(self, query: str, top_k: int = 10) -> list[dict]:
        all_items = self._laws + self._error_patterns
        return self._keyword_search(all_items, query, "", top_k=top_k)

    def _keyword_search(
        self, items: list[dict], query: str, doc_type: str = "", top_k: int = 5,
    ) -> list[dict]:
        if not query and not doc_type:
            return items[:top_k]

        scored: list[tuple[float, dict]] = []
        query_lower = query.lower()
        for item in items:
            text = json.dumps(item, ensure_ascii=False).lower()
            score = 0.0
            for term in query_lower.split():
                if term in text:
                    score += 1.0
            if doc_type and doc_type in str(item.get("applicable_doc_types", [])):
                score += 2.0
            if doc_type and doc_type in item.get("doc_type", ""):
                score += 3.0
            if score > 0:
                scored.append((score, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:top_k]]
