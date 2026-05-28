"""知识库 API —— 法律法规 + 文书模板统一浏览检索。"""

from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/knowledge", tags=["知识库"])


# ── 法律法规 ─────────────────────────────────────────────

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

    filtered = []
    for law in all_laws:
        law_name = law.get("law_name", "")
        content = law.get("content", "")
        article = law.get("article_number", "")
        applicable = law.get("applicable_doc_types", [])

        if search:
            search_lower = search.lower()
            haystack = f"{law_name} {article} {content}".lower()
            if search_lower not in haystack:
                continue

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


@router.get("/stats")
async def get_knowledge_stats():
    """获取知识库统计信息。"""
    from app.core.rag_retriever import RAGRetriever
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select, func

    retriever = RAGRetriever()
    all_laws = retriever._laws if hasattr(retriever, "_laws") else []

    law_names: dict[str, int] = {}
    has_penalty = 0
    for law in all_laws:
        name = law.get("law_name", "未知")
        law_names[name] = law_names.get(name, 0) + 1
        if law.get("penalty_range"):
            has_penalty += 1

    async with AsyncSessionLocal() as db:
        total_templates = (
            await db.execute(select(func.count()).select_from(DocumentTemplate))
        ).scalar() or 0
        official = (
            await db.execute(
                select(func.count()).select_from(DocumentTemplate).where(
                    DocumentTemplate.is_official == True
                )
            )
        ).scalar() or 0

    return {
        "total_laws": len(all_laws),
        "law_categories": len(law_names),
        "with_penalty": has_penalty,
        "total_templates": total_templates,
        "official_templates": official,
        "top_laws": sorted(law_names.items(), key=lambda x: x[1], reverse=True)[:5],
    }


# ── 模板分类浏览 ──────────────────────────────────────────

@router.get("/templates")
async def list_templates(
    category: str = Query("", description="主分类: 刑事/行政"),
    subcategory: str = Query("", description="子分类"),
    keyword: str = Query("", description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    """分页浏览模板列表，支持分类筛选和关键词搜索。"""
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select, func, and_

    async with AsyncSessionLocal() as db:
        conditions = [DocumentTemplate.is_active == True]
        if category:
            conditions.append(DocumentTemplate.category == category)
        if subcategory:
            conditions.append(DocumentTemplate.subcategory == subcategory)

        base = select(DocumentTemplate).where(and_(*conditions))

        if keyword:
            kw = f"%{keyword}%"
            base = base.where(
                DocumentTemplate.name.contains(kw) |
                DocumentTemplate.doc_type.contains(kw) |
                DocumentTemplate.description.contains(kw)
            )

        count_stmt = select(func.count()).select_from(DocumentTemplate).where(and_(*conditions))
        if keyword:
            kw = f"%{keyword}%"
            count_stmt = count_stmt.where(
                DocumentTemplate.name.contains(kw) |
                DocumentTemplate.doc_type.contains(kw) |
                DocumentTemplate.description.contains(kw)
            )

        total = (await db.execute(count_stmt)).scalar() or 0
        offset = (page - 1) * page_size

        result = await db.execute(
            base.order_by(DocumentTemplate.category, DocumentTemplate.subcategory, DocumentTemplate.name)
                .offset(offset).limit(page_size)
        )
        rows = result.scalars().all()

        return {
            "templates": [r.to_api_dict() for r in rows],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


@router.get("/template-categories")
async def get_template_category_tree():
    """获取模板分类树（用于侧栏导航）。"""
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select, func, and_

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(
                DocumentTemplate.category,
                DocumentTemplate.subcategory,
                func.count(),
            )
            .where(DocumentTemplate.is_active == True)
            .group_by(DocumentTemplate.category, DocumentTemplate.subcategory)
            .order_by(DocumentTemplate.category, DocumentTemplate.subcategory)
        )

        tree: dict[str, dict[str, int]] = {}
        totals: dict[str, int] = {}
        for cat, subcat, cnt in result.all():
            cat_str = cat or "未分类"
            sub_str = subcat or "其他"
            if cat_str not in tree:
                tree[cat_str] = {}
                totals[cat_str] = 0
            tree[cat_str][sub_str] = cnt
            totals[cat_str] += cnt

        categories = []
        for cat_name in sorted(tree.keys()):
            children = [
                {"name": sub_name, "count": sub_count}
                for sub_name, sub_count in sorted(tree[cat_name].items())
            ]
            categories.append({
                "name": cat_name,
                "count": totals[cat_name],
                "children": children,
            })

        return {
            "categories": categories,
            "total_templates": sum(totals.values()),
        }


@router.get("/templates/{doc_type}")
async def get_template_detail(doc_type: str, category: str | None = None):
    """获取单个模板完整信息（含字段定义、模板文本、使用说明）。"""
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        q = select(DocumentTemplate).where(DocumentTemplate.doc_type == doc_type)
        if category:
            q = q.where(DocumentTemplate.category == category)
        result = await db.execute(q.limit(1))
        t = result.scalars().first()
        if not t:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"未找到模板: {doc_type}")
        return t.to_api_dict()


@router.get("/doc-types")
async def list_doc_types():
    """获取所有文书类型名称列表（用于下拉筛选器）。"""
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DocumentTemplate.doc_type, DocumentTemplate.name)
            .where(DocumentTemplate.is_active == True)
            .order_by(DocumentTemplate.doc_type)
        )
        return {
            "doc_types": [
                {"doc_type": dt, "name": name}
                for dt, name in result.all()
            ]
        }


@router.put("/templates/{doc_type}/toggle")
async def toggle_template(doc_type: str, category: str = "行政"):
    """启用/禁用模板。"""
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(DocumentTemplate).where(
                DocumentTemplate.doc_type == doc_type,
                DocumentTemplate.category == category,
            )
        )
        t = result.scalar_one_or_none()
        if not t:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"未找到模板: {doc_type}")
        t.is_active = not t.is_active
        await db.commit()
        return {"doc_type": doc_type, "is_active": t.is_active}


@router.get("/templates/{doc_type}/download")
async def download_template(doc_type: str, category: str | None = None):
    """下载模板 —— 优先返回原始 .doc 文件，否则生成 .docx。"""
    import os
    import tempfile
    from fastapi.responses import FileResponse
    from starlette.background import BackgroundTask

    # 1. 尝试查找原始 .doc 文件
    from app.services.docfile_finder import find_original_doc
    cat = category or "行政"
    original = find_original_doc(doc_type, cat)

    if original and os.path.isfile(original):
        safe_name = doc_type or "文书"
        return FileResponse(
            original,
            media_type="application/msword",
            filename=f"{safe_name}.doc".encode("utf-8").decode("latin-1"),
        )

    # 2. 回退: 从 DB 生成 .docx
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        q = select(DocumentTemplate).where(DocumentTemplate.doc_type == doc_type)
        if category:
            q = q.where(DocumentTemplate.category == category)
        result = await db.execute(q.limit(1))
        t = result.scalars().first()
        if not t:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"未找到模板: {doc_type}")

        lines = [f"《{t.doc_type}》", ""]
        lines.append(f"类别：{t.category or '未分类'}　　"
                     f"子分类：{t.subcategory or '未分类'}")
        lines.append("")

        if t.template_text:
            lines.append("━━━ 模板正文 ━━━")
            lines.append("")
            lines.append(t.template_text)
        elif t.schema_fields:
            lines.append("━━━ 模板字段 ━━━")
            lines.append("")
            for f in t.schema_fields:
                mark = "（必填）" if f.get("required") else ""
                lines.append(f"　□  {f.get('label', f.get('key', ''))}{mark}")
        else:
            lines.append("（此模板暂无模板正文，请参考原始 .doc 文件。）")

        if t.usage_guide:
            lines.append("")
            lines.append("━━━ 制作与使用说明 ━━━")
            lines.append("")
            lines.append(t.usage_guide)

        from app.core.export.docx_exporter import build_docx
        content = "\n".join(lines)
        buf = build_docx(content, t.doc_type)

        safe_name = t.doc_type or "文书"
        filename = f"{safe_name}.docx"

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".docx")
        try:
            tmp.write(buf.read())
            tmp_path = tmp.name
            tmp.close()
            return FileResponse(
                tmp_path,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=filename.encode("utf-8").decode("latin-1"),
                background=BackgroundTask(os.unlink, tmp_path),
            )
        except Exception:
            os.unlink(tmp.name)
            raise
