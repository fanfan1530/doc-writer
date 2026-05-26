"""Copilot 工具定义与实现 —— 每个工具对应一个后端能力。"""

from __future__ import annotations
from typing import Any

# ── 工具 Schema（供 LLM Function Calling） ──────────────────

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "search_laws",
        "description": "检索法律条文，用于回答法律依据、罪名构成、处罚幅度、立案标准等法律问题。返回相关法条全文。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "法律问题关键词，如'盗窃罪立案标准'、'故意伤害处罚'"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_procedures",
        "description": "检索公安机关办案程序规定，用于回答办案流程、审批要求、期限规定等程序性问题。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "程序问题关键词，如'行政案件延期审批'、'刑事拘留期限'"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "generate_document",
        "description": "根据案情描述自动生成公安法律文书（询问笔录、检查笔录、处罚决定书等）。返回完整文书内容。",
        "parameters": {
            "type": "object",
            "properties": {
                "doc_type": {"type": "string", "description": "文书类型，如'检查笔录'、'行政处罚决定书'、'辨认笔录'"},
                "input_text": {"type": "string", "description": "案情描述或案件基本事实"},
            },
            "required": ["doc_type", "input_text"],
        },
    },
    {
        "name": "polish_document",
        "description": "根据用户指令修改或润色文书内容。仅修改用户指定的部分，保持其他内容、格式、编号完全不变。返回修改后的完整文书。",
        "parameters": {
            "type": "object",
            "properties": {
                "current_text": {"type": "string", "description": "当前文书全文"},
                "instruction": {"type": "string", "description": "用户的修改要求"},
            },
            "required": ["current_text", "instruction"],
        },
    },
    {
        "name": "check_deadlines",
        "description": "检查案件的法定期限是否合规，返回期限预警信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "doc_type": {"type": "string", "description": "文书类型"},
                "fields": {"type": "object", "description": "案卷字段（日期、涉案人等）"},
            },
            "required": ["doc_type", "fields"],
        },
    },
    {
        "name": "analyze_case_nature",
        "description": "分析案件事实属于行政违法、刑事犯罪还是民事纠纷，给出初步定性意见和依据。",
        "parameters": {
            "type": "object",
            "properties": {
                "facts": {"type": "string", "description": "案件基本事实描述"},
            },
            "required": ["facts"],
        },
    },
    {
        "name": "evidence_checklist",
        "description": "根据案件类型推荐证据收集清单和取证要点。",
        "parameters": {
            "type": "object",
            "properties": {
                "case_type": {"type": "string", "description": "案件类型，如'盗窃'、'故意伤害'、'赌博'"},
            },
            "required": ["case_type"],
        },
    },
    {
        "name": "penalty_reference",
        "description": "查询违法行为的处罚幅度、裁量标准和相关依据。",
        "parameters": {
            "type": "object",
            "properties": {
                "violation": {"type": "string", "description": "违法行为描述，如'无证驾驶'、'殴打他人'"},
            },
            "required": ["violation"],
        },
    },
]


# ── 工具实现 ──────────────────────────────────────────────

class ToolExecutor:
    """工具执行器 —— 将 LLM 选择的工具调用映射到实际后端能力。"""

    def __init__(self, rag_retriever=None, doc_service=None):
        self._rag = rag_retriever
        self._doc = doc_service

    async def execute(self, tool_name: str, args: dict) -> str:
        handler = getattr(self, f"_tool_{tool_name}", None)
        if handler is None:
            return f"未知工具: {tool_name}"
        try:
            result = await handler(**args)
            return str(result)[:3000]
        except Exception as e:
            return f"工具执行失败: {str(e)[:200]}"

    async def _tool_search_laws(self, query: str) -> str:
        if not self._rag:
            return "法律检索服务暂不可用"
        return self._rag.retrieve_laws(query)

    async def _tool_search_procedures(self, query: str) -> str:
        if not self._rag:
            return "程序检索服务暂不可用"
        # 复用法律检索，法条库中包含程序规定
        results = self._rag.retrieve_laws(query, "")
        if results == "未找到相关法条。":
            return f"未找到与'{query}'相关的程序规定。建议咨询法制部门。"
        return results

    async def _tool_generate_document(self, doc_type: str, input_text: str) -> str:
        if not self._doc:
            return "文书生成服务暂不可用"
        result = await self._doc.generate_document(doc_type, input_text)
        return result.get("content", "") or "生成失败，请重试"

    async def _tool_polish_document(self, current_text: str, instruction: str) -> str:
        if not self._doc:
            return current_text
        # 构建精修 prompt
        prompt = f"""你是一名公安文书审核专家。以下是当前文书全文：

---
{current_text}
---

用户要求：{instruction}

请仅针对用户要求的部分进行修改，保持其他内容、格式、编号、段落结构完全不变。直接输出修改后的完整文书，不要加任何解释。"""
        return await self._doc._call_llm(prompt, max_tokens=4096)

    async def _tool_check_deadlines(self, doc_type: str, fields: dict) -> str:
        if not self._doc:
            return "期限检查服务暂不可用"
        warnings = self._doc.check_legal_deadlines(fields, doc_type)
        if not warnings:
            return "暂未发现期限问题。"
        lines = []
        for w in warnings:
            level = {"critical": "严重", "info": "提示"}.get(w.get("level", ""), "")
            lines.append(f"[{level}] {w.get('message', '')} (依据: {w.get('law_ref', '')})")
        return "\n".join(lines)

    async def _tool_analyze_case_nature(self, facts: str) -> str:
        prompt = f"""你是一名公安法制审核专家。请分析以下案件事实，判断属于行政违法、刑事犯罪还是民事纠纷。

案件事实：
{facts}

请从以下角度分析：
1. 案件性质判断（行政/刑事/民事）
2. 可能涉及的法律依据
3. 建议的下一步处理方向
4. 需要注意的风险点

回答应简明扼要，控制在300字以内。"""
        if self._doc:
            return await self._doc._call_llm(prompt, max_tokens=1024)
        return "案件分析服务暂不可用"

    async def _tool_evidence_checklist(self, case_type: str) -> str:
        prompt = f"""你是一名刑事侦查专家。针对"{case_type}"类案件，列出关键证据收集清单。

对于每类证据，说明：
1. 证据名称
2. 收集要点
3. 注意事项

请以清单格式输出，简明实用。"""
        if self._doc:
            return await self._doc._call_llm(prompt, max_tokens=1024)
        return "证据指引服务暂不可用"

    async def _tool_penalty_reference(self, violation: str) -> str:
        # 先检索法条
        laws = ""
        if self._rag:
            laws = self._rag.retrieve_laws(violation, "")
        prompt = f"""查询违法行为"{violation}"的处罚依据。

已检索到的相关法条：
{laws if laws and laws != '未找到相关法条。' else '（未找到直接关联法条）'}

请整理：
1. 违法行为定性
2. 处罚依据（引用具体法条）
3. 处罚幅度
4. 裁量考量因素（从轻/从重情节）

如检索结果不足，请基于法律常识给出参考建议。"""
        if self._doc:
            return await self._doc._call_llm(prompt, max_tokens=1024)
        return "处罚查询服务暂不可用"
