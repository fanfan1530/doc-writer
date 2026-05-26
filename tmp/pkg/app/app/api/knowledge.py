"""知识库 API —— 法律法规浏览检索。"""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


@router.get("/laws")
async def list_laws(
    search: str = Query("", description="搜索关键词"),
    doc_type: str = Query("", description="按文书类型筛选"),
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=100),
):
    """分页获取法律法规列表，支持关键词搜索和文书类型筛选。"""
    from app.core.rag_retriever import RAGRetriever
    retriever = RAGRetriever()
    all_laws = retriever._laws if hasattr(retriever, "_laws") else []

    # 搜索过滤
    filtered = []
    for law in all_laws:
        law_name = law.get("law_name", "")
        content = law.get("content", "")
        article = law.get("article_number", "")
        applicable = law.get("applicable_doc_types", [])

        # 关键词搜索
        if search:
            search_lower = search.lower()
            haystack = f"{law_name} {article} {content}".lower()
            if search_lower not in haystack:
                continue

        # 文书类型筛选
        if doc_type and applicable:
            if doc_type not in applicable:
                continue

        filtered.append({
            "id": law.get("id", hash(content) % 100000),
            "law_name": law_name,
            "article_number": article,
            "content": content[:500],
            "penalty_range": law.get("penalty_range", ""),
            "applicable_doc_types": applicable[:5],
        })

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "laws": filtered[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
