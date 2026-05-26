"""向量检索 RAG —— 使用 chromadb 进行语义搜索，增强关键词检索。

首次启动时自动从知识库构建向量索引。无 embedding 模型时回退到关键词搜索。
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "doc_writer_knowledge"
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
        logger.info("ChromaDB 客户端已初始化: %s", persist_dir)
        return _chroma_client
    except Exception as e:
        logger.warning("ChromaDB 初始化失败: %s", str(e)[:100])
        return None


def build_index(laws: list[dict], templates: list[dict]) -> bool:
    """从法条和模板构建向量索引。"""
    client = _get_client()
    if client is None:
        return False

    try:
        # 删除旧索引
        try:
            client.delete_collection(_COLLECTION_NAME)
        except Exception:
            pass

        collection = client.create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        documents: list[str] = []
        metadatas: list[dict] = []
        ids: list[str] = []

        for i, law in enumerate(laws):
            text = f"【{law.get('law_name', '')}】第{law.get('article_number', '')}条: {law.get('content', '')}"
            documents.append(text)
            metadatas.append({
                "type": "law",
                "law_name": law.get("law_name", ""),
                "article_number": law.get("article_number", ""),
                "doc_types": json.dumps(law.get("applicable_doc_types", [])),
            })
            ids.append(f"law-{i}")

        for i, tmpl in enumerate(templates):
            text = f"{tmpl.get('name', '')} - {tmpl.get('description', '')}"
            documents.append(text)
            metadatas.append({
                "type": "template",
                "doc_type": tmpl.get("doc_type", ""),
                "name": tmpl.get("name", ""),
            })
            ids.append(f"tmpl-{i}")

        # 分批添加
        batch_size = 50
        for start in range(0, len(documents), batch_size):
            end = start + batch_size
            collection.add(
                documents=documents[start:end],
                metadatas=metadatas[start:end],
                ids=ids[start:end],
            )

        logger.info("向量索引构建完成: %d 条文档", len(documents))
        return True
    except Exception as e:
        logger.warning("向量索引构建失败: %s", str(e)[:100])
        return False


def vector_search(query: str, n_results: int = 5) -> list[dict]:
    """语义搜索法条和模板。"""
    client = _get_client()
    if client is None:
        return []

    try:
        collection = client.get_collection(_COLLECTION_NAME)
        results = collection.query(query_texts=[query], n_results=n_results)

        items: list[dict] = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                doc = results["documents"][0][i] if results["documents"] else ""
                distance = (
                    results["distances"][0][i]
                    if results.get("distances") and results["distances"][0]
                    else 1.0
                )
                items.append({
                    "id": doc_id,
                    "type": meta.get("type", ""),
                    "content": doc,
                    "metadata": meta,
                    "score": max(0, 1 - distance),  # cosine distance → similarity
                })
        return items
    except Exception:
        return []
