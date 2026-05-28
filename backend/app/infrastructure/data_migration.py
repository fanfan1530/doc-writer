"""首次启动时从 JSON 文件迁移数据到数据库（幂等：已有数据则跳过）。"""

import json
import logging
from pathlib import Path

from sqlalchemy import select, func

from app.infrastructure.database import AsyncSessionLocal
from app.infrastructure.models import (
    DocumentTemplate, ErrorPattern, Law, ModelConfig,
)

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


async def _ensure_schema_updates():
    """自动添加缺失的数据库列（开发环境 SQLite 兼容方案）。"""
    from app.infrastructure.database import engine, DATABASE_URL
    import sqlalchemy as sa

    if not DATABASE_URL.startswith("sqlite"):
        return

    # 各表缺失列定义
    _table_migrations: dict[str, list[tuple[str, str]]] = {
        "document_templates": [
            ("usage_guide", "TEXT DEFAULT ''"),
            ("category", "VARCHAR(32) DEFAULT '行政'"),
            ("subcategory", "VARCHAR(64) DEFAULT ''"),
            ("is_official", "BOOLEAN DEFAULT 0"),
            ("created_at", "TIMESTAMP"),
        ],
        "users": [
            ("display_name", "VARCHAR(64) DEFAULT ''"),
            ("unit", "VARCHAR(128) DEFAULT ''"),
            ("updated_at", "TIMESTAMP"),
        ],
    }

    try:
        async with engine.begin() as conn:
            for table, columns in _table_migrations.items():
                try:
                    existing = await conn.run_sync(
                        lambda sync_conn, t=table: [
                            row[1] for row in
                            sync_conn.execute(sa.text(f"PRAGMA table_info({t})")).fetchall()
                        ]
                    )
                except Exception:
                    continue  # 表可能尚未创建

                for col_name, col_type in columns:
                    if col_name not in existing:
                        await conn.execute(
                            sa.text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                        )
                        logger.info("已添加缺失列: %s.%s", table, col_name)
    except Exception:
        logger.debug("Schema 更新检查失败（可能是首次启动）", exc_info=True)


async def migrate_json_to_db():
    """从 JSON 文件导入数据到 DB（仅当 DB 为空时执行）。"""
    await _ensure_schema_updates()
    async with AsyncSessionLocal() as db:
        # 模型配置
        count = (await db.execute(select(func.count()).select_from(ModelConfig))).scalar()
        if count == 0:
            models_path = KNOWLEDGE_DIR / "models.json"
            if models_path.exists():
                try:
                    data = json.loads(models_path.read_text(encoding="utf-8"))
                    for p in data.get("providers", []):
                        p.setdefault("api_type", "openai")
                        db.add(ModelConfig(
                            id=p.get("id", ""),
                            name=p.get("name", ""),
                            provider=p.get("provider", "自定义"),
                            base_url=p.get("base_url", ""),
                            model_name=p.get("model_name", ""),
                            model_name_large=p.get("model_name_large", ""),
                            api_key=p.get("api_key", ""),
                            api_type=p.get("api_type", "openai"),
                            requires_key=p.get("requires_key", True),
                            temperature=p.get("temperature", 0.1),
                            max_tokens=p.get("max_tokens", 4096),
                            system_prompt=p.get("system_prompt", ""),
                            is_active=p.get("id") == data.get("active_model_id", ""),
                        ))
                    await db.commit()
                    logger.info("已从 models.json 导入 %d 条模型配置", len(data.get("providers", [])))
                except Exception:
                    logger.warning("models.json 迁移失败，将使用 DB 默认数据", exc_info=True)

        # 文书模板
        count = (await db.execute(select(func.count()).select_from(DocumentTemplate))).scalar()
        if count == 0:
            tmpl_path = KNOWLEDGE_DIR / "templates.json"
            if tmpl_path.exists():
                try:
                    templates = json.loads(tmpl_path.read_text(encoding="utf-8"))
                    for t in templates:
                        db.add(DocumentTemplate(
                            doc_type=t.get("doc_type", ""),
                            name=t.get("name", ""),
                            description=t.get("description", ""),
                            schema_fields=t.get("schema_fields", []),
                            template_text=t.get("template_text", ""),
                        ))
                    await db.commit()
                    logger.info("已从 templates.json 导入 %d 条模板", len(templates))
                except Exception:
                    logger.warning("templates.json 迁移失败", exc_info=True)

        # 法条库
        count = (await db.execute(select(func.count()).select_from(Law))).scalar()
        if count == 0:
            law_path = KNOWLEDGE_DIR / "laws.json"
            if law_path.exists():
                try:
                    laws = json.loads(law_path.read_text(encoding="utf-8"))
                    for l in laws:
                        db.add(Law(
                            law_name=l.get("law_name", ""),
                            article_number=l.get("article_number", ""),
                            content=l.get("content", ""),
                            penalty_range=l.get("penalty_range", ""),
                            keywords=l.get("keywords", []),
                            applicable_doc_types=l.get("applicable_doc_types", []),
                        ))
                    await db.commit()
                    logger.info("已从 laws.json 导入 %d 条法条", len(laws))
                except Exception:
                    logger.warning("laws.json 迁移失败", exc_info=True)

        # 错误模式
        count = (await db.execute(select(func.count()).select_from(ErrorPattern))).scalar()
        if count == 0:
            ep_path = KNOWLEDGE_DIR / "error_patterns.json"
            if ep_path.exists():
                try:
                    patterns = json.loads(ep_path.read_text(encoding="utf-8"))
                    for p in patterns:
                        db.add(ErrorPattern(
                            error_description=p.get("error_description", ""),
                            incorrect_example=p.get("incorrect_example", ""),
                            correct_example=p.get("correct_example", ""),
                            applicable_doc_types=p.get("applicable_doc_types", []),
                        ))
                    await db.commit()
                    logger.info("已从 error_patterns.json 导入 %d 条错误模式", len(patterns))
                except Exception:
                    logger.warning("error_patterns.json 迁移失败", exc_info=True)
