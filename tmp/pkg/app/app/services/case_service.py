"""类案检索服务 —— 基于 ChromaDB 向量搜索的相似案例匹配。"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_CASES_COLLECTION = "doc_writer_cases"
_chroma_client = None


def _get_client():
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
        logger.warning("案例数据文件不存在: %s", cases_path)
        return []
    with open(cases_path, "r", encoding="utf-8") as f:
        return json.load(f)


def seed_cases() -> int:
    """将种子案例数据写入 ChromaDB 索引。幂等操作。"""
    client = _get_client()
    if client is None:
        return 0

    cases = _load_cases()
    if not cases:
        return 0

    try:
        # 检查是否已存在
        try:
            existing = client.get_collection(_CASES_COLLECTION)
            if existing.count() > 0:
                logger.info("案例索引已存在 (%d 条), 跳过初始化", existing.count())
                return existing.count()
        except Exception:
            pass

        # 删除旧索引（可能为空）
        try:
            client.delete_collection(_CASES_COLLECTION)
        except Exception:
            pass

        collection = client.create_collection(
            name=_CASES_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

        documents = []
        metadatas = []
        ids = []

        for case in cases:
            text = f"{case.get('title', '')} | {case.get('case_type', '')} | {case.get('key_facts', '')}"
            documents.append(text)
            metadatas.append({
                "case_id": case.get("id", ""),
                "title": case.get("title", ""),
                "case_type": case.get("case_type", ""),
                "key_facts": case.get("key_facts", ""),
                "penalty_outcome": case.get("penalty_outcome", ""),
                "laws": json.dumps(case.get("laws", [])),
                "evidence_list": json.dumps(case.get("evidence_list", [])),
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
    query: str,
    case_type: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """语义搜索相似案例。回退到关键词搜索。"""
    client = _get_client()

    # ChromaDB 向量搜索
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

                    items.append(_format_case(meta, score))
                    if len(items) >= limit:
                        break

            if items:
                return items
        except Exception as e:
            logger.warning("向量搜索失败，回退关键词: %s", str(e)[:100])

    # 回退：关键词搜索
    return _keyword_search(query, case_type, limit)


def get_case_detail(case_id: str) -> Optional[dict]:
    """获取案例详情。"""
    cases = _load_cases()
    for c in cases:
        if c.get("id") == case_id:
            return c
    return None


def _format_case(meta: dict, score: float) -> dict:
    laws = []
    try:
        laws = json.loads(meta.get("laws", "[]"))
    except (json.JSONDecodeError, TypeError):
        pass

    evidence = []
    try:
        evidence = json.loads(meta.get("evidence_list", "[]"))
    except (json.JSONDecodeError, TypeError):
        pass

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
    """关键词匹配搜索（ChromaDB 不可用时的回退方案）。"""
    cases = _load_cases()
    tokens = set(query.lower().split())

    scored = []
    for case in cases:
        if case_type and case.get("case_type") != case_type:
            continue
        text = f"{case.get('title', '')} {case.get('key_facts', '')} {case.get('case_type', '')}"
        text_lower = text.lower()
        score = sum(1 for t in tokens if t in text_lower)
        # 按 case_type 匹配加分
        if case_type and case.get("case_type") == case_type:
            score += 2
        if score > 0:
            scored.append((score, case))

    scored.sort(key=lambda x: x[0], reverse=True)

    max_score = max((s for s, _ in scored), default=1)
    return [
        _format_case_from_raw(c, s / max_score if max_score > 0 else 0)
        for s, c in scored[:limit]
    ]


def _format_case_from_raw(case: dict, score: float) -> dict:
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
