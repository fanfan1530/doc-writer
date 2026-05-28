"""ORM 模型 —— 替代原先的 JSON 文件持久化。"""

import datetime
import uuid

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.sqlite import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


def _gen_id() -> str:
    return uuid.uuid4().hex[:10]


class ModelConfig(Base):
    """LLM 模型配置（替代 models.json）。"""
    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_gen_id)
    name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(64), default="自定义")
    base_url: Mapped[str] = mapped_column(String(512), default="")
    model_name: Mapped[str] = mapped_column(String(128), default="")
    model_name_large: Mapped[str] = mapped_column(String(128), default="")
    api_key: Mapped[str] = mapped_column(String(512), default="")
    api_type: Mapped[str] = mapped_column(String(32), default="openai")
    requires_key: Mapped[bool] = mapped_column(Boolean, default=True)
    temperature: Mapped[float] = mapped_column(Float, default=0.1)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    system_prompt: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
    )


class DocumentTemplate(Base):
    """文书模板（替代 templates.json）。"""
    __tablename__ = "document_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(64), unique=False, nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("doc_type", "category", name="uq_doc_type_category"),
    )
    name: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    schema_fields: Mapped[dict] = mapped_column(JSON, default=list)
    template_text: Mapped[str] = mapped_column(Text, default="")
    usage_guide: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(32), default="行政")
    subcategory: Mapped[str] = mapped_column(String(64), default="")
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )

    def to_api_dict(self) -> dict:
        return {
            "doc_type": self.doc_type,
            "name": self.name,
            "description": self.description,
            "schema_fields": self.schema_fields,
            "template_text": self.template_text,
            "usage_guide": self.usage_guide,
            "category": self.category,
            "subcategory": self.subcategory,
            "is_official": self.is_official,
            "version": self.version,
            "is_active": self.is_active,
        }


class Law(Base):
    """法条知识库（替代 laws.json 中的条目）。"""
    __tablename__ = "laws"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    law_name: Mapped[str] = mapped_column(String(256), default="", index=True)
    article_number: Mapped[str] = mapped_column(String(32), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    penalty_range: Mapped[str] = mapped_column(String(256), default="")
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    applicable_doc_types: Mapped[list] = mapped_column(JSON, default=list)


class ErrorPattern(Base):
    """错误模式库（替代 error_patterns.json）。"""
    __tablename__ = "error_patterns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    error_description: Mapped[str] = mapped_column(Text, default="")
    incorrect_example: Mapped[str] = mapped_column(Text, default="")
    correct_example: Mapped[str] = mapped_column(Text, default="")
    applicable_doc_types: Mapped[list] = mapped_column(JSON, default=list)


class GenerationHistory(Base):
    """文书生成历史记录。"""
    __tablename__ = "generation_history"
    __table_args__ = (
        Index("ix_history_doc_type_created", "doc_type", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_text: Mapped[str] = mapped_column(Text, default="")
    output_content: Mapped[str] = mapped_column(Text, default="")
    model_used: Mapped[str] = mapped_column(String(128), default="")
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    elements: Mapped[dict] = mapped_column(JSON, default=dict)
    suggested_laws: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, index=True,
    )


class User(Base):
    """系统用户。"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="user")
    display_name: Mapped[str] = mapped_column(String(64), default="")
    unit: Mapped[str] = mapped_column(String(128), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
    )


class AuditLog(Base):
    """操作审计日志。"""
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(64), default="")
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), default="")
    resource_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )


class Conversation(Base):
    """AI Copilot 对话会话。"""
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), default="新对话")
    doc_type: Mapped[str] = mapped_column(String(64), default="")
    doc_context: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, index=True,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
    )


class Message(Base):
    """对话消息（含工具调用追踪）。"""
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id"), nullable=False, index=True,
    )
    role: Mapped[str] = mapped_column(String(16), default="user")
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    doc_snapshot: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )


# ── 案件管理模型 (v2.1) ───────────────────────────────────

class Case(Base):
    """案件主表。"""
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_case_status_created", "status", "created_at"),
        Index("ix_case_officer", "officer_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True, default="",
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    case_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="刑事",
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="FILING", index=True,
    )
    officer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    unit: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    incident_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    location: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, index=True,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow,
    )


class CaseDocument(Base):
    """案件关联文书。"""
    __tablename__ = "case_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False, index=True,
    )
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("generation_history.id"), nullable=True,
    )
    doc_type: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(String(256), default="")
    status: Mapped[str] = mapped_column(
        String(32), default="DRAFT",
    )  # DRAFT / SUBMITTED / APPROVED / REJECTED
    submitted_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    submitted_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )


class CaseEvidence(Base):
    """案件证据。"""
    __tablename__ = "case_evidences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(256), default="")
    ev_type: Mapped[str] = mapped_column(String(64), default="")
    file_path: Mapped[str] = mapped_column(String(512), default="")
    uploaded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    uploaded_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )


class CaseTimeline(Base):
    """案件时间线事件。"""
    __tablename__ = "case_timelines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False, index=True,
    )
    event: Mapped[str] = mapped_column(String(256), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    occurred_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    recorded_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )


class ReviewRecord(Base):
    """文书审查记录。"""
    __tablename__ = "review_records"
    __table_args__ = (
        Index("ix_review_document", "document_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id"), nullable=False, index=True,
    )
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("case_documents.id"), nullable=False,
    )
    reviewer_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(32), nullable=False,
    )  # APPROVE / REJECT / RETURN
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )


# ── 通知模型 (v2.1) ──────────────────────────────────────

class Notification(Base):
    """系统通知。"""
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notif_user_read", "user_id", "is_read"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(256), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    related_case_id: Mapped[int] = mapped_column(Integer, ForeignKey("cases.id"), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow,
    )
