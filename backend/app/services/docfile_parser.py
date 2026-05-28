""".doc 文件解析器 —— WPS OLE 二进制格式文本提取 + LLM 字段识别。"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _is_ext_a(char: str) -> bool:
    """检查字符是否在 CJK Extension A 范围 (U+3400-U+4DBF)。"""
    return "㐀" <= char <= "䶿"


def _has_dense_ext_a(text: str, window: int = 15, threshold: int = 3) -> bool:
    """检查文本中是否有密集的 CJK Extension A 字符簇（二进制残留特征）。"""
    ext_a_count = 0
    for i, ch in enumerate(text):
        if _is_ext_a(ch):
            ext_a_count += 1
            if i >= window and _is_ext_a(text[i - window]):
                ext_a_count -= 1
            if ext_a_count >= threshold:
                return True
    return False


def _clean_binary_residue(text: str) -> str:
    """去除 .doc 提取文本中的 OLE 二进制残留垃圾。"""
    if not text:
        return text

    lines = text.split("\n")

    # 去除 OLE 二进制头部（第一行通常含 "袉倔卋卋" 等乱码）
    if lines and ("倔卋卋" in lines[0] or "袉倔" in lines[0] or "€" in lines[0]):
        for i, line in enumerate(lines[1:], 1):
            stripped = line.strip()
            if stripped and not _has_dense_ext_a(stripped, threshold=2):
                cjk_count = sum(1 for c in stripped if "一" <= c <= "鿿")
                if cjk_count >= 4:
                    lines = lines[i:]
                    break

    # 找到二进制垃圾的起始行（Ext-A 密度过高）
    first_garbage = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) < 4:
            continue
        ext_a_count = sum(1 for c in stripped if _is_ext_a(c))
        if ext_a_count / len(stripped) > 0.3:
            first_garbage = i
            break
        if _has_dense_ext_a(stripped, window=15, threshold=3):
            first_garbage = i
            break

    if first_garbage < len(lines):
        lines = lines[:first_garbage]

    return "\n".join(lines).strip()


def _extract_text_from_doc(filepath: str) -> str:
    """从 .doc (OLE 二进制格式) 中提取可读中文文本。"""
    try:
        import olefile
    except ImportError:
        logger.error("olefile 未安装，请执行: pip install olefile")
        return ""

    if not Path(filepath).exists():
        return ""

    try:
        ole = olefile.OleFileIO(filepath)
        data = ole.openstream("WordDocument").read()
    except Exception as e:
        logger.warning("无法打开 %s: %s", filepath, str(e)[:100])
        return ""

    chars: list[str] = []
    i = 0
    while i < len(data) - 1:
        lo = data[i]
        hi = data[i + 1]
        if hi == 0 and 0x20 <= lo <= 0x7e:
            chars.append(chr(lo))
        elif hi == 0 and lo == 0x0d:
            chars.append("\n")
        elif hi == 0 and lo == 0x09:
            chars.append("\t")
        elif hi > 0:
            char_val = lo | (hi << 8)
            if (0x4e00 <= char_val <= 0x9fff or
                0x3400 <= char_val <= 0x4dbf or
                0x3000 <= char_val <= 0x303f or
                0xff00 <= char_val <= 0xffef or
                0x2000 <= char_val <= 0x206f):
                chars.append(chr(char_val))
        i += 2

    text = "".join(chars)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 应用 Ext-A 密度检测清理二进制残留
    text = _clean_binary_residue(text)

    return text


def extract_document_info(filepath: str) -> dict:
    """解析 .doc 文件，返回 {name, category, text, usage_guide} 等基础信息。"""
    text = _extract_text_from_doc(filepath)
    if not text:
        return {"success": False, "error": "无法提取文本"}

    filename = Path(filepath).stem
    # 从文件名提取可能的文书名称（去除编号前缀）
    name_match = re.match(r"^\d+[-—]?(.+)", filename)
    doc_name = name_match.group(1) if name_match else filename

    # 分类：从路径判断
    is_criminal = "刑事" in str(filepath)
    category = "刑事" if is_criminal else "行政"

    # 粗略拆分：前半部分为模板，后半部分为使用说明
    lines = text.split("\n")
    usage_start = -1
    for i, line in enumerate(lines):
        if any(kw in line for kw in ["式样", "是公安机关", "使用", "制作", "说明", "填写"]):
            if i > len(lines) * 0.5:  # 后半部分出现的是说明
                usage_start = i
                break

    if usage_start > 0:
        template_text = "\n".join(lines[:usage_start]).strip()
        usage_guide = "\n".join(lines[usage_start:]).strip()
    else:
        template_text = text[: len(text) // 2]
        usage_guide = text[len(text) // 2 :]

    return {
        "success": True,
        "name": doc_name,
        "category": category,
        "raw_text": text[:5000],
        "template_text": template_text[:3000],
        "usage_guide": usage_guide[:2000],
        "filepath": filepath,
        "char_count": len(text),
    }


async def generate_template_schema(doc_info: dict, llm_chat_fn) -> dict:
    """用 LLM 从文档文本中提取字段 schema 和模板结构。

    llm_chat_fn: async (prompt: str, max_tokens: int) -> str
    """
    import json as _json

    prompt = f"""你是公安法律文书专家。请从以下文书模板中提取结构化信息，输出 JSON。

文书名称: {doc_info.get("name", "")}
类别: {doc_info.get("category", "")}

模板文本:
---
{doc_info.get("template_text", "")[:3000]}
---

使用说明:
---
{doc_info.get("usage_guide", "")[:2000]}
---

请输出以下 JSON（只输出 JSON，不要解释）:
{{
  "doc_type": "文书标准名称（如'行政处罚决定书'）",
  "doc_type_short": "简短标识（如'行政处罚决定书'）",
  "category": "刑事/行政",
  "description": "文书用途（1句话）",
  "schema_fields": [
    {{
      "key": "字段英文key（snake_case）",
      "label": "字段中文名",
      "type": "text/textarea/date/select/checkbox_group/composite",
      "required": true/false,
      "dict_values": ["可选值1","可选值2"],  // 仅 select/checkbox_group 类型
      "placeholder": "填写提示"
    }}
  ],
  "template_text": "将模板文本中的占位符替换为 {{field_key}} 格式的 Jinja2 模板，保留原格式和官方用语"
}}

规则:
- 填空处(____或横线) → text 类型字段
- 日期填空 → date 类型
- □ 多选项 → checkbox_group 类型
- 身份证件种类+号码 → composite 类型
- 长文本(案情描述/违法事实) → textarea 类型
- 下拉选项 → select 类型
- 模板文本中所有空白填空处必须替换为 {{field_key}}"""

    try:
        resp = await llm_chat_fn(prompt, max_tokens=4096)
        # 尝试从 LLM 回复中提取 JSON
        json_start = resp.find("{")
        json_end = resp.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            return _json.loads(resp[json_start:json_end])
    except Exception as e:
        logger.warning("LLM schema extraction failed for %s: %s", doc_info.get("name"), str(e)[:100])

    # 回退：返回基础结构
    return {
        "doc_type": doc_info.get("name", ""),
        "doc_type_short": doc_info.get("name", ""),
        "category": doc_info.get("category", "行政"),
        "description": "",
        "schema_fields": [],
        "template_text": doc_info.get("template_text", ""),
    }
