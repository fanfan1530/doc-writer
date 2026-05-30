#!/usr/bin/env python3
"""公安法律文书清洗工具 —— 从原始 .doc 到数据库就绪的结构化模板。

管道: 扫描 → 提取 → 清洗 → 拆分(刑事合集) → LLM字段提取 → Jinja2转换 → 验证 → 入库

用法:
  python doc_cleaner.py scan                          # 扫描源目录，统计文件
  python doc_cleaner.py process --category 行政        # 处理行政模板
  python doc_cleaner.py process --category 刑事        # 处理刑事模板(含合集拆分)
  python doc_cleaner.py process --all --dry-run        # 全部处理，仅预览不入库
  python doc_cleaner.py process --all --live           # 全部处理并入库
  python doc_cleaner.py process --doc-type "拘留证" --live  # 处理单个模板
  python doc_cleaner.py report                         # 输出当前数据库质量报告
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

sys.stdout.reconfigure(encoding='utf-8')

# ── 路径配置 ──────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "app" / "knowledge" / "data.db"
DOC_COLLECTION = (
    r"C:\Users\Lenovo\Desktop"
    r"\2024 GA刑事和行政法律文书电子word版-20241108(1)"
    r"\2024 GA刑事和行政法律文书电子word版-20241108"
)
ADMIN_DIR = os.path.join(DOC_COLLECTION, "2024版公安行政法律文书式样word版本-法度笔录-241108")
CRIMINAL_DIR = os.path.join(DOC_COLLECTION, "公安刑事法律文书式样(2022)")

# ── 文件 → 模板名映射 ──────────────────────────────────────────

ADMIN_FILE_MAP: dict[str, str | None] = {
    "1-行政案件立案登记表、接受证据清单（式样一）.doc": "行政案件立案登记表",
    "2-受案回执（式样二）2024年已删除.doc": None,
    "3-行政案件立案 不予立案告知书（式样三）（2024年新增）.doc": "行政案件立案/不予立案告知书",
    "4-移送案件通知书（式样四）.doc": "移送案件通知书",
    "5-传唤证（式样五）.doc": "传唤证",
    "6-询问 讯问笔录（式样六）.doc": "询问笔录",
    "7-检查证（式样七）.doc": "检查证",
    "8-勘验 检查 辨认 现场笔录（式样八）.doc": "勘验笔录",
    "9-调取证据通知书（式样九）.doc": "调取证据通知书",
    "10-调取证据清单（式样十）.doc": "调取证据清单",
    "11-鉴定聘请书（式样十一）.doc": "鉴定聘请书",
    "12-证据保全决定书、证据保全清单（式样十二）.doc": "证据保全决定书",
    "13-行政处罚告知笔录（式样十三）.doc": "行政处罚告知笔录",
    "14-不予受理听证通知书（式样十四）.doc": "不予受理听证通知书",
    "15-举行听证通知书（式样十五）.doc": "举行听证通知书",
    "16-听证笔录（式样十六）.doc": "听证笔录",
    "17-听证报告书（式样十七）.doc": "听证报告书",
    "18-治安调解协议书（式样十八）.doc": "治安调解协议书",
    "19-当场处罚决定书（式样十九）.doc": "当场处罚决定书",
    "20-不予行政处罚决定书（式样二十）.doc": "不予行政处罚决定书",
    "21-行政处罚决定书（式样二十一）.doc": "行政处罚决定书",
    "22-收缴、追缴物品清单（式样二十二）.doc": "收缴追缴物品清单",
    "23-责令___通知书（式样二十三）.doc": "责令通知书",
    "24-强制隔离戒毒、延长强制隔离戒毒决定书（式样二十四）.doc": "强制隔离戒毒决定书",
    "25-提前解除强制隔离戒毒决定书（式样二十五）.doc": "提前解除强制隔离戒毒决定书",
    "26-社区戒毒、社区康复决定书（式样二十六）.doc": "社区戒毒决定书",
    "27-解除社区戒毒、社区康复通知书（式样二十七）.doc": "解除社区戒毒通知书",
    "28-收容教育、延长收容教育决定书（式样二十八）（2020年已删除）.doc": None,
    "29-提前解除收容教育决定书（式样二十九）（2020年已删除）.doc": None,
    "30-解除收容教育证明书（式样三十）（2020年已删除）.doc": None,
    "31-拘留审查、延长拘留审查决定书（式样三十一）.doc": "拘留审查决定书",
    "32-解除拘留审查决定书（式样三十二）.doc": "解除拘留审查决定书",
    "33-限制活动范围决定书（式样三十三）.doc": "限制活动范围决定书",
    "34-遣送出境决定书（式样三十四）.doc": "遣送出境决定书",
    "35-驱逐出境决定书（式样三十五）.doc": "驱逐出境决定书",
    "36-催告书（式样三十六）.doc": "催告书",
    "37-行政强制执行决定书（式样三十七）.doc": "行政强制执行决定书",
    "38-代履行决定书（式样三十八）.doc": "代履行决定书",
    "39-强制执行申请书（式样三十九）.doc": "强制执行申请书",
    "40-暂缓执行行政拘留决定书（式样四十）.doc": "暂缓执行行政拘留决定书",
    "41-收取保证金通知书、收取保证金回执（式样四十一）.doc": "收取保证金通知书",
    "42-担保人保证书（式样四十二）.doc": "担保人保证书",
    "43-退还保证金通知书（式样四十三）.doc": "退还保证金通知书",
    "44-没收保证金决定书（式样四十四）.doc": "没收保证金决定书",
    "45-执行回执（式样四十五）.doc": "执行回执",
    "46-终止案件调查决定书（式样四十六）.doc": "终止案件调查决定书",
    "47-《冻结、延长冻结、解除冻结财产决定书》、《冻结、延长冻结、解除冻结财产通知书》（式样四十七）.doc": "冻结财产决定书",
    "48-约束、解除约束决定书（式样四十八）.doc": "约束决定书",
    "49-查询财产通知书（式样四十九）.doc": "查询财产通知书",
}

SKIP_FILES = {
    "001-1-公安行政法律文书式样目录.doc",
    "001-2-公安行政法律文书制作与使用说明.doc",
}

# ── 刑事模板列表（来自官方目录，108种）────────────────────────

CRIMINAL_TEMPLATE_NAMES = [
    # 立案、管辖、回避
    "受案登记表", "受案回执", "立案决定书", "不予立案通知书",
    "不立案理由说明书", "指定管辖决定书", "移送案件通知书",
    "回避/驳回申请回避决定书",
    # 律师参与刑事诉讼
    "提供法律援助通知书", "会见犯罪嫌疑人申请表",
    "准予会见犯罪嫌疑人决定书", "不准予会见犯罪嫌疑人决定书",
    # 强制措施
    "拘传证", "传讯通知书", "取保候审决定书", "被取保候审人义务告知书",
    "取保候审保证书", "收取保证金通知书", "保存证件清单",
    "退还保证金决定书", "没收保证金决定书", "对保证人罚款决定书",
    "责令具结悔过决定书", "解除取保候审决定书", "监视居住决定书",
    "指定居所监视居住通知书", "解除监视居住决定书", "拘留证",
    "拘留通知书", "延长拘留期限通知书", "提请批准逮捕书",
    "逮捕证", "逮捕通知书", "变更逮捕措施通知书",
    "不予释放/变更强制措施通知书",
    "提请批准延长侦查羁押期限意见书", "延长侦查羁押期限通知书",
    "计算/重新计算侦查羁押期限通知书",
    # 侦查取证
    "传唤证", "提讯提解证", "询问/讯问笔录",
    "犯罪嫌疑人诉讼权利义务告知书", "被害人诉讼权利义务告知书",
    "证人诉讼权利义务告知书", "未成年人法定代理人到场通知书",
    "询问通知书", "现场勘验笔录", "解剖尸体通知书",
    "调取证据通知书", "搜查证", "接受证据材料清单",
    "查封决定书", "扣押决定书", "扣押清单", "登记保存清单",
    "查封/解除查封清单", "协助查封/解除查封通知书", "发还清单",
    "随案移送清单", "销毁清单", "扣押/解除扣押邮件/电报通知书",
    "协助查询财产通知书", "协助冻结/解除冻结财产通知书",
    "鉴定聘请书", "鉴定意见通知书", "通缉令",
    "关于撤销通缉令的通知", "办案协作函",
    # 侦查终结
    "撤销案件决定书", "终止侦查决定书", "起诉意见书",
    "补充侦查报告书", "没收违法所得意见书", "强制医疗意见书",
    # 技术侦查
    "采取技术侦查措施决定书", "执行技术侦查措施通知书",
    "延长技术侦查措施期限决定书", "解除技术侦查措施决定书",
    # 执行
    "减刑/假释建议书", "假释证明书", "暂予监外执行决定书",
    "收监执行通知书", "准许拘役罪犯回家决定书", "刑满释放证明书",
    # 通用
    "呈请报告书", "复议决定书", "要求复议意见书", "提请复核意见书",
    "死亡通知书",
    # 入所
    "入所健康检查表", "换押证",
    # 卷宗
    "刑事侦查卷宗", "卷内文书目录", "告知书",
]


# ═══════════════════════════════════════════════════════════════
# Data Classes
# ═══════════════════════════════════════════════════════════════

@dataclass
class CleanJob:
    """单个模板的清洗任务。"""
    doc_type: str
    category: str           # "刑事" | "行政"
    filepath: str           # 源 .doc 路径
    raw_text: str = ""      # olefile 提取的原始文本
    cleaned_text: str = ""  # 去二进制残留后的文本
    template_text: str = "" # Jinja2 模板文本
    schema_fields: list = field(default_factory=list)
    usage_guide: str = ""
    description: str = ""
    quality_score: int = 0  # 0-100
    quality_issues: list = field(default_factory=list)
    stage: str = "pending"  # pending → extracted → cleaned → split → schema → jinja2 → validated → imported


@dataclass
class PipelineStats:
    """管道执行统计。"""
    total: int = 0
    extracted: int = 0
    cleaned: int = 0
    split: int = 0
    schema_ok: int = 0
    jinja2_ok: int = 0
    validated: int = 0
    imported: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════
# Stage 1: Text extraction (delegates to docfile_parser)
# ═══════════════════════════════════════════════════════════════

def extract_text(filepath: str) -> str:
    """从 .doc 提取文本（同步）。"""
    from app.services.docfile_parser import _extract_text_from_doc
    return _extract_text_from_doc(filepath)


# ═══════════════════════════════════════════════════════════════
# Stage 2: Binary cleaning
# ═══════════════════════════════════════════════════════════════

def clean_binary(text: str) -> str:
    """去 OLE 二进制残留，已在 extract_text 中完成。二次清理重复空白。"""
    if not text:
        return text
    # 合并过多空行
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    # 去除页码标记
    text = re.sub(r"PAGE\s+\\\*\s+MERGEFORMAT\s*\d+", "", text)
    # 去除表单控件残留
    text = re.sub(r"FORMCHECKBOX|FORMCHECKBOX", "", text)
    return text.strip()


# ═══════════════════════════════════════════════════════════════
# Stage 3: Criminal compound doc splitting
# ═══════════════════════════════════════════════════════════════

def _parse_criminal_toc(text: str) -> list[str]:
    """从刑事合集文本中解析目录，返回模板名称列表。"""
    # 目录位于 "目  录" 和第一个模板内容之间
    toc_match = re.search(r"目\s+录\s*\n(.*?)(?=\n\n(?:一式|第|\d+、))", text, re.DOTALL)
    if not toc_match:
        toc_match = re.search(r"目\s+录\s*\n([\s\S]{500,3000}?)(?=\n\s*\n)", text)

    if toc_match:
        toc_text = toc_match.group(1)
        # 解析目录行: "1、受案登记表*" 或 "13、拘传证"
        names = []
        for line in toc_text.split("\n"):
            line = line.strip()
            # 匹配编号+名称
            m = re.match(r"\d+[、,.]\s*(.+?)(?:\*|（\d{4}.*）)?$", line)
            if m:
                name = m.group(1).strip()
                if len(name) >= 2 and len(name) <= 30:
                    names.append(name)
        if len(names) >= 30:
            return names
    return []


def _locate_template_in_text(name: str, text: str) -> int:
    """在合集文本中查找模板的起始位置。支持多种标题格式。"""
    # 精确匹配
    pos = text.find(name)
    if pos >= 0:
        return pos
    # 去空格匹配（官方标题常用空格分隔，如"立 案 决 定 书"）
    spaced = " ".join(name)
    pos = text.find(spaced)
    if pos >= 0:
        return pos
    # 用正则：允许字符间有0-2个空格
    pattern = r"\s*".join(re.escape(c) for c in name)
    m = re.search(pattern, text)
    if m:
        return m.start()
    return -1


def _extract_template_section(text: str, name: str, next_name: str | None,
                               all_names: list[str]) -> str:
    """从合集文本中提取单个模板的文本段落。"""
    pos = _locate_template_in_text(name, text)
    if pos < 0:
        return ""

    # 找下一个模板的起始位置
    end_pos = len(text)
    if next_name:
        end_pos = _locate_template_in_text(next_name, text[pos+len(name):])
        if end_pos >= 0:
            end_pos = pos + len(name) + end_pos
        else:
            end_pos = len(text)
    else:
        # 最后一个模板：取到文本末尾或下一个明显的分割标记
        end_pos = len(text)

    # 限制单个模板最大长度（避免取到太多后面的内容）
    max_len = 8000
    section = text[pos:min(end_pos, pos + max_len)]
    return section.strip()


async def _extract_single_criminal_template(name: str, section_text: str, llm_chat_fn) -> dict | None:
    """用 LLM 从单个刑事模板文本中提取 schema + Jinja2。"""
    if len(section_text) < 50:
        return None

    prompt = """你是公安刑事法律文书专家。从以下刑事法律文书模板中提取结构化信息。

文书名称: {name}
类别: 刑事

模板正文:
---
{section_text}
---

输出 JSON（只输出 JSON，不要解释）:
{{
  "doc_type": "{name}",
  "description": "文书用途（1句话）",
  "schema_fields": [
    {{
      "key": "snake_case英文key",
      "label": "中文标签",
      "type": "text/textarea/date/select/checkbox_group/composite/signature_block/document_number/table",
      "required": true/false,
      "dict_values": ["选项"],
      "placeholder": "填写提示"
    }}
  ],
  "template_text": "将所有填空空白(____、横线、〔〕、()等)替换为{{{{field_key}}}}的Jinja2模板，保留原文格式",
  "usage_guide": "填写说明（如有）"
}}

规则:
- template_text 必须保留全部原文格式（抬头、编号、正文、落款、日期等）
- 所有填空空白处必须替换为{{{{key}}}}，key必须与schema_fields中的key对应
- 文书编号（如X公[]字〔〕号） → 拆分为document_number类型
- 多签名+日期 → signature_block类型
- □ 选项 → checkbox_group类型，dict_values列出所有选项
- 文本段落（案情/事实） → textarea类型""".format(name=name, section_text=section_text[:6000])

    last_error = ""
    last_resp = ""
    for attempt in range(3):
        try:
            resp = await llm_chat_fn(prompt, max_tokens=8192)
            last_resp = resp
            resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL).strip()

            for marker in ("```json", "```"):
                if marker in resp:
                    parts = resp.split(marker)
                    if len(parts) >= 2:
                        inner = parts[1].split("```")
                        if inner:
                            resp = inner[0].strip()
                            break

            # DeepSeek可能先输出推理文本再输出JSON。找最后一个完整JSON块。
            # 优先找 ```json ``` 代码块，其次找 {"doc_type" 开头，最后找最后一个 {
            json_str = ""
            if "```json" in resp:
                parts = resp.split("```json")
                if len(parts) >= 2:
                    inner = parts[-1].split("```")
                    json_str = inner[0].strip()
            if not json_str:
                # 从末尾往前搜最后一个 {"doc_type"
                idx = resp.rfind('{"doc_type"')
                if idx < 0:
                    idx = resp.rfind('{\n  "doc_type"')
                if idx >= 0:
                    end = resp.rfind("}")
                    if end > idx:
                        json_str = resp[idx:end+1]
            if not json_str:
                # 回退：从最后一个 { 到最后一个 }
                idx = resp.rfind("{")
                end = resp.rfind("}")
                if idx >= 0 and end > idx:
                    json_str = resp[idx:end+1]

            if not json_str:
                last_error = f"no JSON found in: {resp[:300]}"
                continue

            # 尝试直接解析 → 修复后解析
            parse_ok = False
            for repair_pass in range(2):
                try:
                    result = json.loads(json_str)
                    if result.get("template_text") and result.get("schema_fields"):
                        return result
                    last_error = "missing template_text or schema_fields"
                    parse_ok = True
                except json.JSONDecodeError as e:
                    if repair_pass == 0:
                        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)
                        json_str = re.sub(r'([\{,]\s*)([a-zA-Z_][\w]*)\s*:', r'\1"\2":', json_str)
                    else:
                        last_error = f"JSON error: {str(e)[:120]}"
                except Exception as e:
                    last_error = f"{type(e).__name__}: {str(e)[:120]}"
                    break
            if parse_ok and last_error:
                continue  # try next attempt (missing fields, not JSON error)
        except Exception as e:
            last_error = f"API/network error: {type(e).__name__}: {str(e)[:120]}"

    if last_error:
        print(f"    [DEBUG] LLM失败原因: {last_error}")
        try:
            debug_path = PROJECT_ROOT / f"debug_llm_{name}.txt"
            debug_path.write_text(
                f"=== PROMPT (last 500 chars) ===\n{prompt[-500:]}\n\n"
                f"=== LAST RESPONSE ===\n{last_resp}",
                encoding='utf-8')
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════════════
# Stage 4: LLM schema extraction
# ═══════════════════════════════════════════════════════════════

SCHEMA_PROMPT = """你是公安法律文书专家。从以下文书模板中提取结构化信息，输出 JSON。

文书名称: {doc_type}
类别: {category}

模板文本:
---
{template_text}
---

使用说明:
---
{usage_guide}
---

输出 JSON（只输出 JSON）:
{{
  "doc_type": "标准名称",
  "description": "一句话用途",
  "schema_fields": [
    {{
      "key": "snake_case字段key",
      "label": "中文标签",
      "type": "text/textarea/date/select/checkbox_group/composite/signature_block/document_number",
      "required": true/false,
      "dict_values": ["选项1"],  // 仅select/checkbox_group
      "placeholder": "填写提示"
    }}
  ],
  "template_text": "将所有填空空白(____横线括号空白)替换为{{{{field_key}}}}的Jinja2模板，保留全文格式和法律用语",
  "usage_guide": "填写说明摘要"
}}

规则:
- 所有填空处(____、横线、括号空白、年  月  日) → 必须对应一个schema字段
- □ 多选项 → checkbox_group, dict_values列出所有选项
- 文书编号(如X公[]字〔〕号) → document_number类型
- 签名+日期+盖章 → signature_block类型
- 证件种类+号码 → composite类型
- 长文本(案情/事实/经过) → textarea类型
- template_text必须保留原格式，所有空白替换为{{{{key}}}}"""


async def llm_extract_schema(job: CleanJob, llm_chat_fn) -> bool:
    """用 LLM 提取字段 schema + 生成 Jinja2 模板。成功返回 True。"""
    truncated = job.cleaned_text[:8000] if len(job.cleaned_text) > 8000 else job.cleaned_text
    prompt = SCHEMA_PROMPT.format(
        doc_type=job.doc_type,
        category=job.category,
        template_text=truncated,
        usage_guide=job.usage_guide or "(无)",
    )

    for attempt in range(3):
        try:
            resp = await llm_chat_fn(prompt, max_tokens=8192)
            resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL)

            # 从 markdown 代码块提取
            for marker in ("```json", "```"):
                if marker in resp:
                    parts = resp.split(marker)
                    if len(parts) >= 2:
                        inner = parts[1].split("```")
                        if inner:
                            resp = inner[0].strip()
                            break

            json_start = resp.find("{")
            json_end = resp.rfind("}") + 1
            if json_start < 0 or json_end <= json_start:
                continue

            result = json.loads(resp[json_start:json_end])

            sf = result.get("schema_fields", [])
            tt = result.get("template_text", "")

            if sf and tt and "{{" in tt:
                job.schema_fields = sf
                job.template_text = tt
                job.usage_guide = result.get("usage_guide", job.usage_guide)
                job.description = result.get("description", "")
                job.stage = "schema"
                return True

        except (json.JSONDecodeError, KeyError) as e:
            if attempt < 2:
                await asyncio.sleep(1)
        except Exception as e:
            if attempt < 2:
                await asyncio.sleep(2)

    return False


# ═══════════════════════════════════════════════════════════════
# Stage 5: Quality validation
# ═══════════════════════════════════════════════════════════════

def validate_job(job: CleanJob) -> int:
    """验证模板质量，返回 0-100 的评分。"""
    score = 100
    job.quality_issues = []

    # 模板文本检查
    tt = job.template_text or ""
    if len(tt) < 100:
        score -= 40
        job.quality_issues.append(f"模板文本过短({len(tt)}字符)")
    elif len(tt) < 300:
        score -= 15
        job.quality_issues.append(f"模板文本偏短({len(tt)}字符)")

    # Jinja2 占位符检查
    placeholders = re.findall(r"\{\{(.*?)\}\}", tt)
    if len(placeholders) < 3:
        score -= 30
        job.quality_issues.append(f"Jinja2占位符过少({len(placeholders)}个)")
    elif len(placeholders) < 5:
        score -= 10
        job.quality_issues.append(f"Jinja2占位符偏少({len(placeholders)}个)")

    # 字段 schema 检查
    sf = job.schema_fields or []
    if len(sf) < 3:
        score -= 25
        job.quality_issues.append(f"schema_fields过少({len(sf)}个)")
    if len(sf) > 0:
        template_keys = set(re.findall(r"\{\{(.*?)\}\}", tt))
        schema_keys = {f.get("key", "") for f in sf}
        matched = template_keys & schema_keys
        if len(schema_keys) > 0 and len(matched) < len(schema_keys) * 0.5:
            score -= 20
            job.quality_issues.append(f"字段匹配率低({len(matched)}/{len(schema_keys)})")

    # 检查是否有原始空白残留
    blank_count = len(re.findall(r"_{3,}|〔\s*〕|\（\s*\）", tt))
    if blank_count > 5:
        score -= 10
        job.quality_issues.append(f"仍有{blank_count}处空白未替换为Jinja2")

    job.quality_score = max(0, score)
    job.stage = "validated"
    return job.quality_score


# ═══════════════════════════════════════════════════════════════
# Stage 6: Database import
# ═══════════════════════════════════════════════════════════════

def import_to_db(job: CleanJob, dry_run: bool = True) -> bool:
    """将清洗后的模板导入数据库。dry_run=True 时不写入。"""
    if dry_run:
        return True

    conn = sqlite3.connect(str(DB_PATH))
    try:
        cursor = conn.cursor()
        sf_json = json.dumps(job.schema_fields, ensure_ascii=False)

        existing = cursor.execute(
            "SELECT id, template_text, schema_fields FROM document_templates WHERE doc_type = ? AND category = ?",
            (job.doc_type, job.category),
        ).fetchone()

        if existing:
            cursor.execute(
                """UPDATE document_templates
                   SET template_text = ?, schema_fields = ?, usage_guide = ?,
                       description = ?, version = version + 1, is_official = 1, is_active = 1
                   WHERE doc_type = ? AND category = ?""",
                (job.template_text, sf_json, job.usage_guide, job.description,
                 job.doc_type, job.category),
            )
        else:
            cursor.execute(
                """INSERT INTO document_templates
                   (doc_type, name, description, schema_fields, template_text,
                    usage_guide, category, is_official, is_active, version)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 1, 1, 1)""",
                (job.doc_type, job.doc_type, job.description, sf_json,
                 job.template_text, job.usage_guide, job.category),
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"  [ERROR] 入库失败: {e}")
        return False
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════
# Pipeline Orchestrator
# ═══════════════════════════════════════════════════════════════

class DocCleaner:
    """文档清洗管道编排器。"""

    def __init__(self, llm_chat_fn, dry_run: bool = True):
        self.llm = llm_chat_fn
        self.dry_run = dry_run
        self.stats = PipelineStats()

    def discover_files(self, category: str | None = None) -> list[CleanJob]:
        """扫描源目录，返回待处理的清洗任务列表。"""
        jobs: list[CleanJob] = []

        # 行政模板
        if category is None or category == "行政":
            if os.path.isdir(ADMIN_DIR):
                for fname in sorted(os.listdir(ADMIN_DIR)):
                    if not fname.endswith(".doc") or fname in SKIP_FILES:
                        continue
                    doc_type = ADMIN_FILE_MAP.get(fname)
                    if doc_type is None:
                        continue
                    filepath = os.path.join(ADMIN_DIR, fname)
                    jobs.append(CleanJob(doc_type=doc_type, category="行政", filepath=filepath))

        # 刑事模板
        if category is None or category == "刑事":
            if os.path.isdir(CRIMINAL_DIR):
                for fname in sorted(os.listdir(CRIMINAL_DIR)):
                    if not fname.endswith(".doc"):
                        continue
                    filepath = os.path.join(CRIMINAL_DIR, fname)
                    if fname == "01-刑事法律文书式样.doc":
                        # 刑事合集，拆分为独立模板
                        for name in CRIMINAL_TEMPLATE_NAMES:
                            jobs.append(CleanJob(
                                doc_type=name, category="刑事",
                                filepath=filepath,
                                stage="pending",
                            ))
                    else:
                        # 独立刑事文件
                        name = Path(fname).stem
                        jobs.append(CleanJob(
                            doc_type=name, category="刑事", filepath=filepath,
                        ))

        self.stats.total = len(jobs)
        return jobs

    def filter_jobs(self, jobs: list[CleanJob], doc_type: str | None = None) -> list[CleanJob]:
        """按条件过滤任务。"""
        if doc_type:
            jobs = [j for j in jobs if j.doc_type == doc_type]
        return jobs

    async def run(self, jobs: list[CleanJob], limit: int = 0) -> PipelineStats:
        """执行完整的清洗管道。"""
        # 跳过数据库中已有Jinja2的模板
        conn = sqlite3.connect(str(DB_PATH))
        existing = set()
        for row in conn.execute(
            "SELECT doc_type FROM document_templates WHERE template_text LIKE '%{{%}}%'"
        ):
            existing.add(row[0])
        conn.close()

        skipped_existing = 0
        filtered_jobs = []
        for j in jobs:
            if j.doc_type in existing:
                skipped_existing += 1
            elif limit > 0 and len(filtered_jobs) >= limit:
                pass  # 超过limit，跳过
            else:
                filtered_jobs.append(j)
        jobs = filtered_jobs

        print(f"\n{'='*60}")
        print(f"文档清洗管道启动 — {len(jobs)} 个模板待处理（跳过{skipped_existing}个已有Jinja2）")
        if self.dry_run:
            print("模式: DRY RUN (仅预览，不写入数据库)")
        else:
            print("模式: LIVE (将写入数据库)")
        print(f"{'='*60}\n")

        # ── 处理刑事合集（如果有）──
        compound_jobs = [j for j in jobs if Path(j.filepath).name == "01-刑事法律文书式样.doc"]
        other_jobs = [j for j in jobs if j not in compound_jobs]

        if compound_jobs:
            await self._process_compound(compound_jobs[0].filepath, compound_jobs)

        # ── 处理独立文件 ──
        for i, job in enumerate(other_jobs):
            self._print_job_header(i + 1, len(other_jobs), job)

            # Stage 1-2: Extract + Clean
            if not await self._extract_and_clean(job):
                continue

            # Stage 3: LLM schema + Jinja2
            if not await self._schema_and_jinja2(job):
                continue

            # Stage 4: Validate
            score = validate_job(job)
            self._print_quality(job)

            # Stage 5: Import
            if score >= 40 or not self.dry_run:
                if import_to_db(job, self.dry_run):
                    self.stats.imported += 1
            else:
                print(f"  [SKIP] 质量评分过低({score})，跳过导入")

        self._print_summary()
        return self.stats

    async def _extract_and_clean(self, job: CleanJob) -> bool:
        """Stage 1-2: 提取文本 → 清洗。"""
        loop = asyncio.get_running_loop()
        try:
            job.raw_text = await loop.run_in_executor(None, extract_text, job.filepath)
        except Exception as e:
            print(f"  [ERROR] 文本提取失败: {e}")
            self.stats.errors.append(f"{job.doc_type}: {e}")
            return False

        if not job.raw_text.strip():
            print(f"  [SKIP] 提取文本为空")
            self.stats.skipped += 1
            return False

        job.cleaned_text = clean_binary(job.raw_text)
        job.stage = "cleaned"
        self.stats.extracted += 1
        print(f"  ✓ 提取 {len(job.raw_text)} 字符 → 清洗后 {len(job.cleaned_text)} 字符")
        return True

    async def _schema_and_jinja2(self, job: CleanJob) -> bool:
        """Stage 3: LLM 提取 schema + 生成 Jinja2。"""
        ok = await llm_extract_schema(job, self.llm)
        if ok:
            self.stats.schema_ok += 1
            self.stats.jinja2_ok += 1
            jinja_count = len(re.findall(r"\{\{.*?\}\}", job.template_text))
            print(f"  ✓ Schema: {len(job.schema_fields)} 字段, Jinja2: {jinja_count} 占位符")
            return True
        else:
            print(f"  [FAIL] LLM 字段提取失败 (3次重试后)")
            self.stats.errors.append(f"{job.doc_type}: LLM schema extraction failed")
            return False

    async def _process_compound(self, filepath: str, jobs: list[CleanJob]):
        """处理刑事合集文档：提取文本 → 跳过TOC+说明 → 按模板名定位段落 → 逐个LLM处理。"""
        print(f"\n── 处理刑事合集文档 ──")
        loop = asyncio.get_running_loop()
        raw = await loop.run_in_executor(None, extract_text, filepath)
        cleaned = clean_binary(raw)
        print(f"  提取 {len(raw)} 字符 → 清洗后 {len(cleaned)} 字符")

        # 找到模板正文的起始位置（跳过前面的通知、说明、目录）
        # 策略：从第一个 "一式两份" 或 "一式三份" 之后开始搜索
        body_start = 0
        for marker in ["一式两份", "一式三份"]:
            pos = cleaned.find(marker)
            if pos > 0 and (body_start == 0 or pos < body_start):
                body_start = pos

        # 反向查找：从 body_start 往前找 "目  录" 确认在 TOC 之后
        toc_pos = cleaned.find("目  录")
        if toc_pos < 0:
            toc_pos = cleaned.find("目录")
        if body_start > toc_pos + 500:
            print(f"  跳过前 {body_start} 字符（通知+说明+目录）")
        else:
            body_start = max(toc_pos, 0)

        body_text = cleaned[body_start:]
        print(f"  模板正文区域: {len(body_text)} 字符\n")

        sorted_jobs = sorted(jobs, key=lambda j: _locate_template_in_text(j.doc_type, body_text)
                             if _locate_template_in_text(j.doc_type, body_text) >= 0 else 999999)

        processed = 0
        for i, job in enumerate(sorted_jobs):
            if processed >= len(jobs):
                break

            # 在正文中定位
            section = _extract_template_section(
                body_text, job.doc_type,
                sorted_jobs[i+1].doc_type if i+1 < len(sorted_jobs) else None,
                [j.doc_type for j in sorted_jobs],
            )

            if not section or len(section) < 50:
                continue

            job.cleaned_text = section
            job.raw_text = section
            job.stage = "cleaned"
            self.stats.extracted += 1
            processed += 1

            print(f"[{processed}] {job.doc_type}: 定位到 {len(section)} 字符段落")

            # LLM 提取 schema + Jinja2
            result = await _extract_single_criminal_template(job.doc_type, section, self.llm)
            if result:
                job.schema_fields = result.get("schema_fields", [])
                job.template_text = result.get("template_text", "")
                job.usage_guide = result.get("usage_guide", "")
                job.description = result.get("description", "")
                job.stage = "schema"
                self.stats.schema_ok += 1
                self.stats.jinja2_ok += 1

                score = validate_job(job)
                jinja_count = len(re.findall(r"\{\{.*?\}\}", job.template_text))
                label = "✓" if score >= 70 else ("△" if score >= 40 else "✗")
                print(f"  {label} {len(job.schema_fields)}字段, {jinja_count}占位符, 评分{score}")

                if score >= 40 and not self.dry_run:
                    if import_to_db(job, self.dry_run):
                        self.stats.imported += 1
            else:
                print(f"  [SKIP] LLM 提取失败")

        print(f"\n  刑事合集: {processed} 个模板定位, {self.stats.schema_ok} 个Schema成功, "
              f"{self.stats.imported} 个入库")

    def _print_job_header(self, i: int, total: int, job: CleanJob):
        print(f"[{i}/{total}] [{job.category}] {job.doc_type}")
        print(f"  文件: {Path(job.filepath).name}")

    def _print_quality(self, job: CleanJob):
        label = "✓" if job.quality_score >= 70 else ("△" if job.quality_score >= 40 else "✗")
        print(f"  {label} 质量评分: {job.quality_score}/100")
        for issue in job.quality_issues:
            print(f"    - {issue}")

    def _print_summary(self):
        s = self.stats
        print(f"\n{'='*60}")
        print(f"管道完成: {s.total} 总数 | {s.extracted} 提取 | {s.schema_ok} Schema | "
              f"{s.jinja2_ok} Jinja2 | {s.imported} 导入 | {s.skipped} 跳过 | {len(s.errors)} 错误")
        if s.errors:
            print("错误列表:")
            for e in s.errors[:10]:
                print(f"  - {e}")
        print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════
# Database quality report
# ═══════════════════════════════════════════════════════════════

def print_db_report():
    """输出当前数据库模板质量报告。"""
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM document_templates WHERE is_official = 1 AND is_active = 1")
    total = cur.fetchone()[0]

    cur.execute("""
        SELECT category, COUNT(*),
               SUM(CASE WHEN template_text != '' THEN 1 ELSE 0 END) as has_text,
               SUM(CASE WHEN schema_fields != '' AND schema_fields != '[]' THEN 1 ELSE 0 END) as has_fields,
               SUM(CASE WHEN template_text LIKE '%{{%}}%' THEN 1 ELSE 0 END) as has_jinja2
        FROM document_templates WHERE is_official = 1 AND is_active = 1
        GROUP BY category
    """)
    print(f"\n{'='*60}")
    print(f"数据库模板质量报告 ({DB_PATH})")
    print(f"{'='*60}")
    print(f"{'类别':<6} {'总数':<6} {'有正文':<8} {'有Schema':<10} {'有Jinja2':<10}")
    print(f"{'-'*40}")
    for row in cur.fetchall():
        cat, cnt, has_text, has_fields, has_jinja2 = row
        print(f"{cat:<6} {cnt:<6} {has_text:<8} {has_fields:<10} {has_jinja2:<10}")
    print(f"{'-'*40}")

    # 刑事模板详情
    cur.execute("""
        SELECT doc_type,
               CASE WHEN template_text != '' THEN 'Y' ELSE 'N' END as has_text,
               CASE WHEN schema_fields != '' AND schema_fields != '[]' THEN 'Y' ELSE 'N' END as has_fields,
               CASE WHEN template_text LIKE '%{{%}}%' THEN 'Y' ELSE 'N' END as has_jinja2,
               LENGTH(template_text) as text_len
        FROM document_templates
        WHERE is_official = 1 AND is_active = 1 AND category = '刑事'
        ORDER BY doc_type
    """)
    criminal = cur.fetchall()
    ready = sum(1 for r in criminal if r[1] == 'Y' and r[2] == 'Y' and r[3] == 'Y')
    print(f"\n刑事模板: {len(criminal)} 总数, {ready} 完全就绪")

    if criminal:
        incomplete = [r for r in criminal if not (r[1] == 'Y' and r[2] == 'Y' and r[3] == 'Y')]
        if incomplete:
            print("\n未就绪的刑事模板:")
            for r in incomplete:
                issues = []
                if r[1] == 'N': issues.append("无正文")
                if r[2] == 'N': issues.append("无Schema")
                if r[3] == 'N': issues.append("无Jinja2")
                print(f"  - {r[0]}: {', '.join(issues)} (正文{r[4]}字)")

    conn.close()
    print(f"{'='*60}\n")


# ═══════════════════════════════════════════════════════════════
# LLM client factory
# ═══════════════════════════════════════════════════════════════

async def _create_llm_chat_fn():
    """创建 LLM 对话函数。"""
    from app.core.llm_client import LLMClient
    from app.config import get_settings

    settings = get_settings()
    client = LLMClient(
        api_type="openai",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value() or "sk-local",
    )

    async def chat(prompt: str, max_tokens: int = 4096) -> str:
        messages = [{"role": "user", "content": prompt}]
        return await client.chat(
            model=settings.llm_model_large,
            messages=messages,
            temperature=0.1,
            max_tokens=max_tokens,
        )

    return chat


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════

async def main():
    parser = argparse.ArgumentParser(
        description="公安法律文书清洗工具 — 从原始 .doc 到数据库就绪模板",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python doc_cleaner.py scan                     # 扫描源目录
  python doc_cleaner.py report                   # 数据库质量报告
  python doc_cleaner.py process --all --dry-run  # 全部处理(预览)
  python doc_cleaner.py process --category 行政 --live  # 处理行政并入库
  python doc_cleaner.py process --doc-type "拘留证" --live  # 处理单个模板
        """,
    )
    sub = parser.add_subparsers(dest="command", help="子命令")

    # scan
    sub.add_parser("scan", help="扫描源目录并统计文件")

    # report
    sub.add_parser("report", help="输出数据库质量报告")

    # process
    proc = sub.add_parser("process", help="执行清洗管道")
    proc.add_argument("--all", action="store_true", help="处理所有类别")
    proc.add_argument("--category", choices=["行政", "刑事"], help="按类别处理")
    proc.add_argument("--doc-type", type=str, help="处理指定模板名称")
    proc.add_argument("--dry-run", action="store_true", default=True, help="仅预览不入库(默认)")
    proc.add_argument("--live", action="store_true", help="实际写入数据库")
    proc.add_argument("--limit", type=int, default=0, help="限制处理数量")

    args = parser.parse_args()

    if args.command == "scan":
        cleaner = DocCleaner(None, dry_run=True)
        jobs = cleaner.discover_files()
        admin_count = sum(1 for j in jobs if j.category == "行政")
        criminal_count = sum(1 for j in jobs if j.category == "刑事")
        compound = sum(1 for j in jobs if Path(j.filepath).name == "01-刑事法律文书式样.doc")
        print(f"\n源目录扫描结果:")
        print(f"  行政模板: {admin_count} 个 (独立 .doc 文件)")
        print(f"  刑事模板: {criminal_count} 个 (其中 {compound} 个来自合集文档)")
        print(f"  总计: {len(jobs)} 个模板")
        print(f"\n源路径: {DOC_COLLECTION}")

    elif args.command == "report":
        print_db_report()

    elif args.command == "process":
        if not args.all and not args.category and not args.doc_type:
            print("请指定 --all、--category 或 --doc-type")
            return

        dry_run = not args.live
        llm_fn = await _create_llm_chat_fn()
        cleaner = DocCleaner(llm_fn, dry_run=dry_run)

        category = args.category if not args.all else None
        jobs = cleaner.discover_files(category=category)

        if args.doc_type:
            jobs = cleaner.filter_jobs(jobs, doc_type=args.doc_type)

        await cleaner.run(jobs, limit=args.limit)

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
