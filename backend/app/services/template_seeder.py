"""官方公安法律文书模板批量导入器。

从桌面 2024 版公安法律文书合集遍历 .doc 文件，
调用 docfile_parser 提取文本 + LLM 生成字段 schema，
写入 document_templates 表。

用法:
  python -m app.services.template_seeder --dry-run      # 预览
  python -m app.services.template_seeder --seed          # 执行导入
  python -m app.services.template_seeder --seed --max 5  # 只导入前5个
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────

DOC_COLLECTION = (
    r"C:\Users\Lenovo\Desktop"
    r"\2024 GA刑事和行政法律文书电子word版-20241108(1)"
    r"\2024 GA刑事和行政法律文书电子word版-20241108"
)

CRIMINAL_DIR = os.path.join(DOC_COLLECTION, "公安刑事法律文书式样(2022)")
ADMIN_DIR = os.path.join(DOC_COLLECTION, "2024版公安行政法律文书式样word版本-法度笔录-241108")

# 跳过的文件（目录、说明性文档）
SKIP_FILES = {
    "001-1-公安行政法律文书式样目录.doc",
    "001-2-公安行政法律文书制作与使用说明.doc",
    "刑事法律文书说明.txt",
}

# 行政类已有文件名 → doc_type 映射（从文件名推断）
ADMIN_FILE_MAP = {
    "1-行政案件立案登记表、接受证据清单（式样一）.doc": "行政案件立案登记表",
    "2-受案回执（式样二）2024年已删除.doc": None,  # 跳过已删除
    "3-行政案件立案 不予立案告知书（式样三）（2024年新增）.doc": "不予立案告知书",
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


def _find_doc_files() -> list[tuple[str, str, str | None]]:
    """扫描两个目录，返回 [(filepath, category, doc_type_override), ...]"""
    results: list[tuple[str, str, str | None]] = []

    # 行政类：每个文件是一个独立模板
    if os.path.isdir(ADMIN_DIR):
        for fname in sorted(os.listdir(ADMIN_DIR)):
            if not fname.endswith(".doc"):
                continue
            if fname in SKIP_FILES:
                continue
            override = ADMIN_FILE_MAP.get(fname)
            if override is None:
                logger.info("跳过已废弃: %s", fname)
                continue
            filepath = os.path.join(ADMIN_DIR, fname)
            results.append((filepath, "行政", override))

    # 刑事类：主文件包含 97 个模板，单独文件各一个
    if os.path.isdir(CRIMINAL_DIR):
        for fname in sorted(os.listdir(CRIMINAL_DIR)):
            if not fname.endswith(".doc"):
                continue
            filepath = os.path.join(CRIMINAL_DIR, fname)
            if fname == "01-刑事法律文书式样.doc":
                results.append((filepath, "刑事", None))  # 特殊处理
            else:
                name = Path(fname).stem
                results.append((filepath, "刑事", name))

    return results


async def _extract_text(filepath: str) -> str:
    """同步提取文本到线程池。"""
    from app.services.docfile_parser import _extract_text_from_doc

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _extract_text_from_doc, filepath)


# ── LLM schema 提取 ───────────────────────────────────────

SCHEMA_PROMPT = """你是公安法律文书专家。请从以下文书模板中提取结构化信息，输出 JSON。

文书文本:
---
{raw_text}
---

请输出以下 JSON（只输出 JSON，不要解释）:
{{
  "doc_type_short": "文书类型标识（如'行政处罚决定书'，用于系统内部匹配）",
  "name": "文书标准名称（如'公安行政处罚决定书'）",
  "description": "文书用途（1句话）",
  "category": "{category}",
  "schema_fields": [
    {{
      "key": "字段英文key（snake_case）",
      "label": "字段中文名",
      "type": "text/textarea/date/select/checkbox_group/composite",
      "required": true/false,
      "dict_values": ["可选值1"],
      "placeholder": "填写提示"
    }}
  ],
  "template_text": "将模板中的填空处(____、横线)替换为 {{{{field_key}}}} 格式的 Jinja2 模板，保留原格式和法律用语",
  "usage_guide": "制作说明摘要（提取文书后半部分的填写说明，最多500字）"
}}

规则:
- 填空处(____或横线) → text 类型字段
- □ 多选项 → checkbox_group 类型
- 日期填空 → date 类型
- 身份证件种类+号码 → composite 类型
- 长文本(案情描述/违法事实) → textarea 类型
- 下拉选项 → select 类型（填 dict_values）
- 笔录类 QA 区 → qa_block 类型
- 签名区 → signature_block 类型
- template_text 必须保留原格式（空格、换行、公章位置等），所有空白填空处换为 {{{{field_key}}}}
- 文书编号（如 X公[]字〔〕号） → document_number 类型
- 一式N份说明 → distribution 类型"""


async def _llm_extract_schema(
    raw_text: str,
    category: str,
    llm_chat_fn: Callable[[str, int], Awaitable[str]],
    doc_type_override: str | None = None,
) -> dict | None:
    """用 LLM 从原始文本提取模板 schema。"""
    truncated = raw_text[:8000] if len(raw_text) > 8000 else raw_text

    prompt = SCHEMA_PROMPT.format(raw_text=truncated, category=category)
    if doc_type_override:
        prompt += f"\n注意：此文书的标准名称为「{doc_type_override}」。"

    try:
        resp = await llm_chat_fn(prompt, max_tokens=8192)
        # 移除 DeepSeek 思考标签
        resp = re.sub(r"<think>.*?</think>", "", resp, flags=re.DOTALL | re.IGNORECASE).strip()
        logger.debug("LLM response (first 300): %s", resp[:300])

        # 提取 JSON：优先从代码块提取
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
        if json_start >= 0 and json_end > json_start:
            json_str = resp[json_start:json_end]
            # 修复常见 JSON 问题
            json_str = re.sub(r",\s*}", "}", json_str)
            json_str = re.sub(r",\s*]", "]", json_str)
            result = json.loads(json_str)
            if doc_type_override and not result.get("doc_type_short"):
                result["doc_type_short"] = doc_type_override
            return result
        else:
            logger.warning("LLM response contains no JSON: %s", resp[:200])
    except json.JSONDecodeError as e:
        logger.warning("JSON parse error: %s", str(e)[:100])
    except Exception as e:
        logger.warning("LLM schema extraction failed: %s", str(e)[:100])

    return None


# ── 刑事合集处理 ──────────────────────────────────────────

CRIMINAL_TOC_PROMPT = """你是公安刑事法律文书专家。以下是从《公安机关刑事法律文书式样（2012版）》.doc 文件中提取的文本（含目录）。

请从目录中列出所有刑事法律文书名称，输出 JSON 数组:
["受案登记表", "受案回执", "立案决定书", ...]

只输出 JSON 数组，不要解释。

目录文本:
---
{toc_text}
---"""


async def _extract_criminal_toc(
    full_text: str,
    llm_chat_fn: Callable[[str, int], Awaitable[str]],
) -> list[str]:
    """从刑事合集文本中提取目录（文书名称列表）。"""
    # 取包含目录的部分
    toc_section = full_text[:15000] if len(full_text) > 15000 else full_text

    try:
        resp = await llm_chat_fn(CRIMINAL_TOC_PROMPT.format(toc_text=toc_section), max_tokens=2048)
        json_start = resp.find("[")
        json_end = resp.rfind("]") + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(resp[json_start:json_end])
    except Exception as e:
        logger.warning("刑事目录提取失败: %s", str(e)[:100])

    # 回退：硬编码已知的刑事文书列表（从目录解析）
    return [
        "受案登记表", "受案回执", "立案决定书", "不予立案通知书",
        "不立案理由说明书", "指定管辖决定书", "移送案件通知书",
        "回避/驳回申请回避决定书", "提供法律援助通知书",
        "会见犯罪嫌疑人申请表", "准予会见犯罪嫌疑人决定书",
        "不准予会见犯罪嫌疑人决定书", "拘传证", "传讯通知书",
        "取保候审决定书", "被取保候审人义务告知书", "取保候审保证书",
        "收取保证金通知书", "保存证件清单", "退还保证金决定书",
        "没收保证金决定书", "对保证人罚款决定书", "责令具结悔过决定书",
        "解除取保候审决定书", "监视居住决定书", "指定居所监视居住通知书",
        "解除监视居住决定书", "拘留证", "拘留通知书",
        "延长拘留期限通知书", "提请批准逮捕书", "逮捕证", "逮捕通知书",
        "变更逮捕措施通知书", "不予释放/变更强制措施通知书",
        "提请批准延长侦查羁押期限意见书", "延长侦查羁押期限通知书",
        "计算/重新计算侦查羁押期限通知书", "入所健康检查表",
        "换押证", "释放通知书", "释放证明书", "传唤证", "提讯提解证",
        "询问/讯问笔录", "犯罪嫌疑人诉讼权利义务告知书",
        "被害人诉讼权利义务告知书", "证人诉讼权利义务告知书",
        "未成年人法定代理人到场通知书", "询问通知书", "现场勘验笔录",
        "解剖尸体通知书", "调取证据通知书", "搜查证", "接受证据材料清单",
        "查封决定书", "扣押决定书", "扣押清单", "登记保存清单",
        "查封/解除查封清单", "协助查封/解除查封通知书", "发还清单",
        "随案移送清单", "销毁清单", "扣押/解除扣押邮件/电报通知书",
        "协助查询财产通知书", "协助冻结/解除冻结财产通知书",
        "鉴定聘请书", "鉴定意见通知书", "通缉令", "办案协作函",
        "撤销案件决定书", "终止侦查决定书", "起诉意见书",
        "补充侦查报告书", "没收违法所得意见书", "强制医疗意见书",
        "采取技术侦查措施决定书", "执行技术侦查措施通知书",
        "延长技术侦查措施期限决定书", "解除技术侦查措施决定书",
        "减刑/假释建议书", "假释证明书", "暂予监外执行决定书",
        "收监执行通知书", "准许拘役罪犯回家决定书", "刑满释放证明书",
        "呈请报告书", "复议决定书", "要求复议意见书", "提请复核意见书",
        "死亡通知书", "刑事侦查卷宗", "卷内文书目录", "告知书",
    ]


# ── 主流程 ────────────────────────────────────────────────

async def seed_all(
    llm_chat_fn: Callable[[str, int], Awaitable[str]],
    dry_run: bool = True,
    max_templates: int = 0,
    start_offset: int = 0,
) -> dict:
    """批量导入所有官方模板到数据库。

    Args:
        llm_chat_fn: async (prompt: str, max_tokens: int) -> str
        dry_run: True 时只打印不写入
        max_templates: 限制导入数量（0 = 全部）
        start_offset: 跳过前 N 个文件
    """
    from app.infrastructure.database import AsyncSessionLocal
    from app.infrastructure.models import DocumentTemplate
    from sqlalchemy import select

    files = _find_doc_files()
    logger.info("找到 %d 个 .doc 文件", len(files))

    stats = {"total_files": len(files), "imported": 0, "skipped": 0, "errors": 0}
    processed = 0
    skipped_offset = 0

    for filepath, category, doc_type_override in files:
        if skipped_offset < start_offset:
            skipped_offset += 1
            continue
        if max_templates > 0 and processed >= max_templates:
            break

        fname = Path(filepath).name
        logger.info("[%d/%d] 处理: %s", processed + 1, len(files), fname)

        try:
            # 1. 提取文本
            raw_text = await _extract_text(filepath)
            if not raw_text.strip():
                logger.warning("  文本为空，跳过")
                stats["skipped"] += 1
                continue

            # 2. 刑事合集特殊处理：提取目录并创建基本条目
            if fname == "01-刑事法律文书式样.doc":
                toc_names = await _extract_criminal_toc(raw_text, llm_chat_fn)
                logger.info("  刑事合集包含 %d 个模板", len(toc_names))

                if not dry_run:
                    async with AsyncSessionLocal() as db:
                        for name in toc_names:
                            doc_type = name.strip()
                            existing = (
                                await db.execute(
                                    select(DocumentTemplate).where(
                                        DocumentTemplate.doc_type == doc_type,
                                    )
                                )
                            ).scalar_one_or_none()

                            if not existing:
                                db.add(DocumentTemplate(
                                    doc_type=doc_type,
                                    name=doc_type,
                                    description=f"《公安机关刑事法律文书式样（2012版）》- {doc_type}",
                                    schema_fields=[],
                                    template_text="",
                                    usage_guide="",
                                    category="刑事",
                                    is_official=True,
                                    version=1,
                                    is_active=True,
                                ))
                        await db.commit()
                stats["imported"] += len(toc_names)
                logger.info("  刑事合集: 导入 %d 个模板名称", len(toc_names))

            else:
                # 3. 独立文件：LLM 提取完整 schema
                schema = await _llm_extract_schema(
                    raw_text, category, llm_chat_fn, doc_type_override,
                )

                if schema:
                    doc_type = schema.get("doc_type_short") or doc_type_override or Path(filepath).stem

                    if not dry_run:
                        async with AsyncSessionLocal() as db:
                            existing = (
                                await db.execute(
                                    select(DocumentTemplate).where(
                                        DocumentTemplate.doc_type == doc_type,
                                    )
                                )
                            ).scalar_one_or_none()

                            if existing:
                                # 更新已有模板
                                existing.name = schema.get("name", existing.name)
                                existing.description = schema.get("description", existing.description)
                                existing.schema_fields = schema.get("schema_fields", [])
                                existing.template_text = schema.get("template_text", "")
                                existing.usage_guide = schema.get("usage_guide", "")
                                existing.category = schema.get("category", category)
                                existing.is_official = True
                                logger.info("  更新: %s", doc_type)
                            else:
                                db.add(DocumentTemplate(
                                    doc_type=doc_type,
                                    name=schema.get("name", doc_type),
                                    description=schema.get("description", ""),
                                    schema_fields=schema.get("schema_fields", []),
                                    template_text=schema.get("template_text", ""),
                                    usage_guide=schema.get("usage_guide", ""),
                                    category=schema.get("category", category),
                                    is_official=True,
                                    version=1,
                                    is_active=True,
                                ))
                                logger.info("  新增: %s", doc_type)
                            await db.commit()

                    stats["imported"] += 1
                    logger.info("  -> %s", schema.get("name", doc_type_override or fname))
                else:
                    logger.warning("  LLM 提取失败，跳过")
                    stats["skipped"] += 1

            processed += 1

        except Exception as e:
            logger.error("  错误: %s", str(e)[:200])
            stats["errors"] += 1

    logger.info(
        "导入完成: %d 导入, %d 跳过, %d 错误",
        stats["imported"], stats["skipped"], stats["errors"],
    )
    return stats


# ── 便捷入口（使用系统配置的 LLM） ─────────────────────────

async def _default_llm_chat(prompt: str, max_tokens: int) -> str:
    """使用系统配置的 LLM 客户端进行对话。"""
    from app.core.llm_client import LLMClient
    from app.config import get_settings

    settings = get_settings()
    client = LLMClient(
        api_type="openai",
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key.get_secret_value() or "sk-local",
    )

    messages = [{"role": "user", "content": prompt}]
    return await client.chat(
        model=settings.llm_model_small,
        messages=messages,
        temperature=0.1,
        max_tokens=max_tokens,
    )


async def run_seeder(dry_run: bool = True, max_templates: int = 0):
    """便捷函数：使用默认 LLM 运行导入。"""
    return await seed_all(_default_llm_chat, dry_run=dry_run, max_templates=max_templates)


# ── CLI ────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    dry_run = "--dry-run" in sys.argv or "--seed" not in sys.argv
    max_templates = 0
    for i, arg in enumerate(sys.argv):
        if arg == "--max" and i + 1 < len(sys.argv):
            max_templates = int(sys.argv[i + 1])

    asyncio.run(run_seeder(dry_run=dry_run, max_templates=max_templates))
