"""
RAG 知识检索 —— 关键词检索 + 模板匹配。
当前为演示版本使用 JSON 文件知识库 + 简易关键词打分。
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
        self._load_knowledge()

    def _load_knowledge(self):
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

    def retrieve_laws(self, query: str, doc_type: str = "") -> str:
        results = self._keyword_search(self._laws, query, doc_type, top_k=5)
        if not results:
            return "未找到相关法条。"
        lines = []
        for r in results:
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
