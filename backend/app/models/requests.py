"""API 请求体模型。"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class DocumentInspectRequest(BaseModel):
    doc_type: str = Field(..., description="文书类型")
    fields: dict = Field(default_factory=dict, description="文书字段键值对")
    content: str = Field("", description="文书全文内容")
    case_number: str = Field("", description="案件编号")


class CrossDocumentInspectRequest(BaseModel):
    doc_type: str = Field(..., description="文书类型")
    fields: dict = Field(default_factory=dict)
    content: str = Field("", description="文书全文内容")
    case_number: str = Field("", description="案件编号")
    related_docs: list[dict] = Field(default_factory=list, description="关联文书列表")


class RulesOnlyRequest(BaseModel):
    doc_type: str = Field(..., description="文书类型")
    fields: dict = Field(default_factory=dict, description="文书字段键值对")
    case_number: str = Field("", description="案件编号")


class TableInspectRequest(BaseModel):
    table_type: str = Field(..., description="表格类型")
    fields: list[dict] = Field(default_factory=list, description="字段定义")
    rows: list[dict] = Field(default_factory=list, description="数据行")
    case_number: str = Field("", description="案件编号")


class TableFillRequest(BaseModel):
    table_type: str = Field("", description="表格类型")
    field_definitions: list[dict] = Field(default_factory=list, description="字段定义")
    input_text: str = Field(..., description="输入文本")


class TableBatchFillRequest(BaseModel):
    table_type: str = Field("", description="表格类型")
    field_definitions: list[dict] = Field(default_factory=list)
    input_texts: list[str] = Field(..., description="输入文本列表")


class DocumentGenerateRequest(BaseModel):
    doc_type: str = Field(..., description="文书类型")
    input_text: str = Field(..., description="输入案情描述")


class ExtractElementsRequest(BaseModel):
    input_text: str = Field(..., description="输入文本")
    doc_type: str = Field("", description="文书类型")


class PolishFactRequest(BaseModel):
    raw_fact: str = Field(..., description="原始事实描述")
    doc_type: str = Field("", description="文书类型")


class SuggestLawsRequest(BaseModel):
    fact: str = Field(..., description="案情描述")
    doc_type: str = Field("", description="文书类型")


class KnowledgeQARequest(BaseModel):
    question: str = Field(..., description="用户问题")
