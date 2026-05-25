"""
智能文书生成器 —— 基于要素抽取 + 模板填充 + LLM 润色的混合生成方案。
格式骨架由模板引擎保证，LLM 负责要素抽取和事实描述润色。
"""

from __future__ import annotations
import json
import logging
import re
from typing import Any

from openai import AsyncOpenAI

from app.config import get_settings
from app.core.rag_retriever import RAGRetriever

logger = logging.getLogger(__name__)


def _normalize_chinese_datetime(value: str) -> str:
    """将 ISO 格式时间转换为中文格式：2026-05-22 11:20 → 2026年5月22日11时20分
    也处理仅有日期的格式：2026-05-22 → 2026年5月22日
    """
    if not value:
        return value
    if "年" in value and "月" in value:
        return value
    # 带时间的完整 datetime：2026-05-22 11:20 或 2026-05-22T11:20
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})[\sT](\d{1,2}):(\d{2})", value)
    if m:
        y, mo, d, h, mi = m.groups()
        return f"{y}年{int(mo)}月{int(d)}日{int(h)}时{int(mi)}分"
    # 仅有日期：2026-05-22
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", value)
    if m:
        y, mo, d = m.groups()
        return f"{y}年{int(mo)}月{int(d)}日"
    return value


EXTRACTION_PROMPT = """你是一名公安文书处理专家。请从以下民警输入的案情描述中抽取关键信息要素。

## 输入内容
{input_text}

## 文书类型
{doc_type}

## 需要抽取的要素
{element_schema}

## 输出格式
请严格按照 JSON 格式输出，不要遗漏任何要素：
```json
{{
  "elements": {{
    "field_key": "抽取的值或null",
    ...
  }},
  "suggested_laws": ["建议引用的法条1", "建议引用的法条2"],
  "case_nature": "案件性质/案由"
}}
```

## 警务实战规则
1. 仅从输入信息中提取，严禁编造数据
2. 时间要素精确到分钟，格式必须为 YYYY-MM-DD HH:MM（如2026-05-21 20:00），严禁只输出日期。无精确时间的根据上下文合理推断
3. 涉案人员信息（姓名、身份证号、住址、联系方式）必须完整提取，缺项填null
4. 多人案件须提取全部涉案人员信息，以列表形式注明
5. 金额、数量等数值保持原始表述，不得四舍五入
6. 地点信息从大到小完整记录（省-市-区-详细地址）
7. 特别注意：检查笔录类文书必须有见证人信息，辨认笔录必须有陪衬对象数量
8. 交叉映射规则（输入来自询问/讯问笔录摘要时）：
   - "办案单位"→ police_station（公安机关名称），如"藤县公安局埌南派出所"
   - "询问时间"的起始时间 → inspection_time_start（检查开始时间）
   - "询问时间"的结束时间 → inspection_time_end（检查结束时间）
   - "询问地点"→ inspection_place（检查地点），如"XX派出所询问室"→"XX派出所检查室"
   - "被询问人"→ inspection_target（被检查人姓名）
   - "询问人"→ inspector_name（检查人姓名）
   - "询问人所属单位"→ inspector_unit（检查人工作单位）
   - "案由/案件性质"→ violation_type（违法性质）
   - 检查笔录的过程和结果日期应使用询问时间对应的年月日
9. 指认笔录交叉映射规则（输入来自询问/讯问笔录摘要时）：
   - "办案单位"→ police_station（公安机关名称）
   - "询问时间"的起始时间 → identification_time_start（指认开始时间）
   - "询问时间"的结束时间 → identification_time_end（指认结束时间）
   - "被询问人"→ identifier_name（指认人姓名）
   - "被询问人性别"→ identifier_gender（指认人性别）
   - "被询问人住址"→ identifier_address（指认人户籍地址）
   - "询问人"→ investigator_name（侦查人员姓名）
   - "询问人所属单位"→ investigator_unit（侦查人员单位）
   - "案由/案件性质"→ violation_type（案件性质/案由）
   - "案发地点"→ identification_place（指认地点）— 指认地点是被带到案发现场进行指认的实际位置，不是询问室
   - "案发地点"→ case_location（案发地点）
   - 指认对象应描述为"{案发日期}{案发地点}{案件性质}案发现场"
   - 案发日期从询问时间中提取，案发地点从案情描述中提取
   - case_description（案发经过简述）格式："伙同{同案犯姓名}在{案发地点}{违法行为简述}"，如"伙同聂材华、陈楚文、刘庆源在广西藤县埌南镇界垌村村委旁的工地内盗窃了电缆"
   - identification_confirmation（指认确认内容）格式："{指认对象}就是其{违法行为简述}的{场所/物品}"，如"该地方就是其盗窃电缆的现场和工棚"
10. 辨认笔录交叉映射规则（输入来自询问/讯问笔录摘要时）：
   - "办案单位"→ police_station（公安机关名称）
   - "询问时间"的起始时间 → identification_time_start（辨认开始时间）
   - "询问时间"的结束时间 → identification_time_end（辨认结束时间）
   - "询问地点"→ identification_place（辨认地点，默认为派出所询问室）
   - "被询问人"→ identifier_name（辨认人姓名）
   - "被询问人身份证号"→ identifier_id_number（辨认人证件号）
   - "被询问人在本案中的角色"→ identifier_role（辨认人身份，如"涉案人员之一"/"被害人"/"证人"）
   - "询问人"→ investigator_name（办案人员姓名）
   - "询问人所属单位"→ investigator_unit（办案人员单位）
   - "案由/案件性质"→ violation_type（案件性质/案由）
   - "案发日期"→ case_date
   - "案发地点"→ case_location
   - identification_target（辨认对象）规则：
     * 从输入中分析所有需要被辨认的涉案人员，按性别分为男、女两组
     * 每组各12张照片，描述为："N组十二张不同{性别}正面彩色免冠照片组"
     * 如有多组，用顿号连接，如："一组十二张不同男性正面彩色免冠照片组、二组十二张不同女性正面彩色免冠照片组"
     * 如仅有一组，描述为："一组十二张不同{男性/女性}正面彩色免冠照片组"
   - case_background（案件背景及辨认准备过程）格式：描述辨认人在本案中的角色、其陈述的案发经过（何时何地何人何事）、以及侦查人员准备了多少组辨认照片（每组12张）、告知了辨认人相关的权利义务
   - identification_results（辨认结果）格式：将输入中出现的每一个涉案人员逐行列出，每行一条，格式为"辨认照片N组中（X）号照片的人就是{姓名}"，其中N为照片组号（男性为第一组，女性为第二组），X为照片编号（未知时填X）。不得合并、省略或使用"分别辨认出"等概括性表述。每组结果的末尾须注明"该组照片中的其他人员均不是本案涉案人员"。重要：只能列出输入文本中明确出现的姓名，输入中未出现的姓名一律不得添加。若某组照片对应性别在输入中无涉案人员姓名，则该组写"该组照片中未辨认出涉案人员"
   - identification_operation、identification_conclusion、identification_confirmation 由系统自动生成
"""

POLISH_PROMPT = """你是一名公安文书撰写专家。请将以下事实描述润色为规范的公安法律文书语言。

## 原始描述
{raw_fact}

## 文书类型
{doc_type}

## 要求
1. 使用规范的公安法律文书用语，参照《公安机关刑事/行政法律文书式样》
2. 保持"七何要素"完整——何人、何时、何地、何事、何因、何果、何证据
3. 去除口语化表达、主观臆断词汇（如"可能""大概""好像""据说"等）
4. 保持事实准确，不添加、删减原始描述中没有的信息
5. 时间、地点、人名、身份证号、金额等关键信息不得改动
6. 行为动作使用确定性法律用语，如"击打"替代"打"，"口角"替代"吵架"
7. 多人多层级关系用"二人以上""多次"等明确表述
8. 涉及伤情的使用客观描述（部位、大小、颜色、形态），不主观定性
9. 证据列项标准化：编号+证据种类+来源+证明内容
10. 检查、搜查类过程的描述须按时间顺序，逐项记录

## 输出
直接输出润色后的事实描述段落，不要添加任何说明。
"""

CASE_SUMMARY_PROMPT = """你是一名公安案件分析专家。你的任务是对以下警务文书原文进行整理，输出一份结构化的案件摘要。

## 重要：你必须严格基于下面的「原文」来写摘要。原文是你唯一的事实来源。不得添加原文中没有的任何信息。

================================================================
                     ▼▼▼ 原 文 开 始 ▼▼▼
================================================================

{raw_text}

================================================================
                     ▲▲▲ 原 文 结 束 ▲▲▲
================================================================

## 核心原则 —— 优先级最高，违反即为严重错误

**严禁编造任何信息。**
- 原文中没有的信息，一律标注"不详"或"原文未记载"，绝对不得凭空补充
- 原文中不完整的信息（如只有姓没有名、只说"30多岁"没给准确年龄），如实转述，不得补全
- 原文中未明确的时间，不得"推断"，直接写"不详"
- 原文中没有的证据、物品、金额，不得列出
- 原文中未出现的涉案人员，不得添加
- 不要补充任何"合理推测""常见情况""惯例做法"

**如果你在摘要中写了原文没有的信息，那就是一个严重的错误。**

## 输出结构

### 一、案件基本信息
- 案发时间：原文中明确出现的事件发生时间（无则写"不详"）
- 案发地点：原文中明确出现的事件发生地点（无则写"不详"）
- 案件性质/案由：原文中涉及的违法行为或纠纷性质（无则写"不详"）

### 二、办案信息（询问/讯问笔录类文书必须提取此项）
- 办案单位：从"询问地点""讯问地点""办案单位""公安机关名称"或询问人/记录人所属单位中提取。例如"XX路派出所"或"XX县公安局XX派出所"。原文无明确记载则写"不详"
- 询问/讯问时间：原文中"询问时间""讯问时间"栏的内容，完整保留起止时间。例如"2026年5月20日14时30分至2026年5月20日16时00分"。无则写"不详"
- 询问/讯问地点：原文中"询问地点""讯问地点"栏的完整内容。无则写"不详"
- 询问人/讯问人：原文中记录的办案民警姓名及警号。无则写"不详"
- 记录人：原文中记录的记录人姓名及警号。无则写"不详"

### 三、涉案人员
- 逐人列出：姓名、性别、年龄、身份证号、住址、联系方式、在本案中的角色
- 以上字段，原文中有的就填，没有的就写"不详"
- 多人的内容不可合并或省略

### 四、案件事实经过
- 严格按原文时间顺序叙述
- 只写原文中明确记载的行为和事件
- 去掉程序性表述（告知权利义务、出示证件、告知回避权等）
- 去掉口语语气词和重复表述
- 行为动作可使用法律用语规范表述，但不得改变含义

### 五、证据情况
- 仅列举原文中明确提到的证据种类及来源
- 原文未提及证据则写"原文未记载"

### 六、涉案金额/物品
- 仅列举原文中明确的金额或物品名称、数量
- 原文未提及则写"原文未记载"

## 输出要求
- 使用自然流畅的案件叙述段落，但叙事必须完全忠实于原文
- 每项信息必须完整，不得省略原文中明确记载的内容
- 字数控制在300-1000字
- 直接输出案件摘要，不要添加任何解释说明
"""


class DocumentGenerator:
    """智能文书生成器。"""

    def __init__(self, retriever: RAGRetriever | None = None,
                 model_manager: "ModelManager | None" = None):
        self._model_manager = model_manager
        if model_manager is not None:
            self._client: AsyncOpenAI | None = None  # lazy init via _get_client()
        else:
            settings = get_settings()
            self._client = AsyncOpenAI(
                base_url=settings.llm_base_url,
                api_key=settings.llm_api_key.get_secret_value() or "sk-local",
            )
        self._model = None   # no longer used; kept for compat
        self._model_small = None
        self._retriever = retriever or RAGRetriever()

    def _get_client(self) -> AsyncOpenAI:
        """获取当前模型客户端（支持运行时切换）。"""
        if self._model_manager is not None:
            return self._model_manager.get_client()
        assert self._client is not None
        return self._client

    def _get_model_name(self) -> str:
        """获取当前使用的模型名。"""
        if self._model_manager is not None:
            return self._model_manager.get_active_config().get("model_name", "")
        return get_settings().llm_model_small

    def _get_temperature(self) -> float:
        """获取当前模型的推荐 temperature。"""
        if self._model_manager is not None:
            return self._model_manager.get_temperature()
        return 0.1

    def _get_max_tokens(self) -> int:
        """获取当前模型的推荐 max_tokens。"""
        if self._model_manager is not None:
            return self._model_manager.get_max_tokens()
        return 4096

    def _get_system_prompt(self) -> str:
        """获取当前模型的系统提示词。"""
        if self._model_manager is not None:
            return self._model_manager.get_system_prompt()
        return ""

    async def extract_elements(
        self, input_text: str, doc_type: str,
    ) -> dict[str, Any]:
        template = self._retriever.retrieve_template(doc_type)
        element_schema = json.dumps(
            template.get("schema_fields", []) if template else [],
            ensure_ascii=False,
        )

        prompt = EXTRACTION_PROMPT.replace("{input_text}", input_text).replace("{doc_type}", doc_type).replace("{element_schema}", element_schema)

        sys_prompt = self._get_system_prompt()
        temperature = self._get_temperature()
        max_tokens = self._get_max_tokens()

        messages = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = ""
        for attempt in range(3):
            try:
                response = await self._get_client().chat.completions.create(
                    model=self._get_model_name(),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=90,
                )
                text = response.choices[0].message.content or "{}"
                return self._parse_json(text)
            except Exception as e:
                last_error = str(e)[:200]
                logger.warning(
                    "要素抽取失败 (第%d次): %s", attempt + 1, last_error,
                )
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)

        logger.error("要素抽取最终失败: %s", last_error)
        return {"elements": {}, "suggested_laws": [], "case_nature": ""}

    async def polish_fact(self, raw_fact: str, doc_type: str = "") -> str:
        if not raw_fact.strip():
            return raw_fact
        sys_prompt = self._get_system_prompt()
        temperature = self._get_temperature()
        for attempt in range(3):
            try:
                messages = []
                if sys_prompt:
                    messages.append({"role": "system", "content": sys_prompt})
                messages.append({"role": "user", "content": POLISH_PROMPT.replace("{raw_fact}", raw_fact).replace("{doc_type}", doc_type or "公安法律文书")})
                response = await self._get_client().chat.completions.create(
                    model=self._get_model_name(),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=2048,
                    timeout=90,
                )
                return response.choices[0].message.content or raw_fact
            except Exception as e:
                logger.warning(
                    "事实润色失败 (第%d次): %s", attempt + 1, str(e)[:200],
                )
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)
        return raw_fact

    async def suggest_laws(self, fact_description: str, doc_type: str) -> list[dict]:
        law_text = self._retriever.retrieve_laws(fact_description, doc_type)
        if not law_text or law_text == "未找到相关法条。":
            return []
        results: list[dict] = []
        for block in law_text.split("\n\n"):
            if "】" in block and "条:" in block:
                results.append({"content": block.strip()})
        return results

    async def generate_document(
        self,
        doc_type: str,
        input_text: str,
        template: dict | None = None,
    ) -> dict[str, Any]:
        extracted = await self.extract_elements(input_text, doc_type)
        elements = extracted.get("elements", {})

        fact_keywords = ["illegal_fact", "case_brief", "case_fact", "fact_description",
                         "dispute_fact", "inspection_process", "inspection_findings",
                         "search_process", "investigation_summary", "case_summary",
                         "scene_description", "identification_process",
                         "case_background", "identification_results"]
        for kw in fact_keywords:
            if kw in elements and elements[kw]:
                polished = await self.polish_fact(str(elements[kw]), doc_type)
                elements[kw] = polished
                break

        # 检查笔录：自动计算派生字段（AI 模式同样需要）
        if doc_type == "检查笔录":
            # 时间格式规范化：ISO → 中文
            elements["inspection_time_start"] = _normalize_chinese_datetime(str(elements.get("inspection_time_start", "")))
            elements["inspection_time_end"] = _normalize_chinese_datetime(str(elements.get("inspection_time_end", "")))
            # inspection_date: 从 inspection_time_start 提取年月日
            time_str = str(elements.get("inspection_time_start", "") or "")
            date_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", time_str)
            if not date_match:
                date_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", time_str)
            if date_match:
                y, m, d = date_match.groups()
                elements["inspection_date"] = f"{y}年{int(m)}月{int(d)}日"
            elif time_str and time_str.lower() not in ("none", "null", ""):
                elements["inspection_date"] = time_str
            # 回退：从原始案情文本中提取日期
            if not elements.get("inspection_date"):
                for pattern in [r"(\d{4})年(\d{1,2})月(\d{1,2})日", r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})"]:
                    m = re.search(pattern, str(input_text))
                    if m:
                        y, mo, d = m.groups()
                        elements["inspection_date"] = f"{y}年{int(mo)}月{int(d)}日"
                        break

            # inspection_place: 默认为 {公安机关名称}检查室
            if not elements.get("inspection_place"):
                station = str(elements.get("police_station", "") or "")
                if station and station.lower() not in ("none", "null", ""):
                    elements["inspection_place"] = f"{station}检查室"

            # inspection_target_display: 检查对象应显示为"被检查人的身体"
            target = str(elements.get("inspection_target", ""))
            if target and not elements.get("inspection_target_display"):
                elements["inspection_target_display"] = f"{target}的身体"

            # violation_type: 去除 LLM 可能重复的"涉嫌"前缀（模板已含"涉嫌"）
            violation = str(elements.get("violation_type", ""))
            if violation.startswith("涉嫌"):
                violation = violation[2:]
                elements["violation_type"] = violation

            # inspection_reason: 收集{被检查人}是否有{违法性质}的证据
            if target and violation:
                elements["inspection_reason"] = f"收集{target}是否有{violation}的证据"

            # items_found: 默认"没有发现任何涉案物品"（笔录未体现则默认无）
            # 模板已含"身上"，需去除 LLM 返回的前缀避免"身上身上"重复
            items = str(elements.get("items_found", ""))
            if items.startswith("身上"):
                items = items[2:]
            if not items or items.lower() in ("null", "none", "无", "有", "是", "否", "未发现", "未", "发现", ""):
                elements["items_found"] = "没有发现任何涉案物品"
            else:
                elements["items_found"] = items

            # injury_found: 默认"无任何损伤"（笔录未体现则默认无）
            # 模板已含"身上"，需去除 LLM 返回的前缀避免"身上身上"重复
            injury = str(elements.get("injury_found", ""))
            if injury.startswith("身上"):
                injury = injury[2:]
            if not injury or injury.lower() in ("null", "none", "无", "有", "是", "否", "未发现", "未", "发现", ""):
                elements["injury_found"] = "无任何损伤"
            else:
                elements["injury_found"] = injury

        # 现场勘查笔录：时间格式转中文
        if doc_type == "现场勘查笔录":
            elements["crime_scene_time_start"] = _normalize_chinese_datetime(str(elements.get("crime_scene_time_start", "") or ""))
            elements["crime_scene_time_end"] = _normalize_chinese_datetime(str(elements.get("crime_scene_time_end", "") or ""))

        # 行政处罚告知笔录：默认值 + 时间格式规范化
        if doc_type == "行政处罚告知笔录":
            elements["notification_time"] = _normalize_chinese_datetime(str(elements.get("notification_time", "") or ""))
            if not str(elements.get("legal_representative", "")).strip() or str(elements.get("legal_representative", "")).lower() in ("null", "none", ""):
                elements["legal_representative"] = ""
            if not str(elements.get("evidence_list", "")).strip() or str(elements.get("evidence_list", "")).lower() in ("null", "none", ""):
                elements["evidence_list"] = "检查笔录、违法行为人的陈述和申辩，其他"
            if not str(elements.get("notified_person_statement", "")).strip() or str(elements.get("notified_person_statement", "")).lower() in ("null", "none", ""):
                elements["notified_person_statement"] = "我不提出陈述和申辩。"
            # 去除 proposed_penalty 末尾的"的处罚"避免与模板重复
            pp = str(elements.get("proposed_penalty", ""))
            if pp.endswith("的处罚"):
                elements["proposed_penalty"] = pp[:-3]
            # 处罚依据兜底
            if not str(elements.get("penalty_basis", "")).strip() or str(elements.get("penalty_basis", "")).lower() in ("null", "none", ""):
                search_text = " ".join([
                    str(elements.get(k, "")) for k in ["case_description", "violation_type"]
                    if str(elements.get(k, ""))
                ]) or input_text
                scored = []
                for law in self._retriever._laws:
                    score = 0
                    for kw in law.get("keywords", []):
                        if kw in search_text:
                            score += 1
                    if law.get("law_name", "") in search_text:
                        score += 3
                    if score > 0:
                        scored.append((score, law))
                scored.sort(key=lambda x: x[0], reverse=True)
                if scored:
                    top = scored[0][1]
                    elements["penalty_basis"] = f"《{top.get('law_name', '')}》第{top.get('article_number', '')}条"

        # 指认笔录：自动计算派生字段（AI 模式同样需要）
        if doc_type == "指认笔录":
            # 时间格式规范化：ISO → 中文
            elements["identification_time_start"] = _normalize_chinese_datetime(str(elements.get("identification_time_start", "")))
            elements["identification_time_end"] = _normalize_chinese_datetime(str(elements.get("identification_time_end", "")))
            # identification_date: 从 identification_time_start 提取年月日
            time_str = str(elements.get("identification_time_start", ""))
            date_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", time_str)
            if not date_match:
                date_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", time_str)
            if date_match:
                y, m, d = date_match.groups()
                elements["identification_date"] = f"{y}年{int(m)}月{int(d)}日"

            # case_date 格式规范化：ISO → 中文
            case_date_raw = str(elements.get("case_date", ""))
            if case_date_raw:
                cd_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", case_date_raw)
                if cd_match:
                    y, m, d = cd_match.groups()
                    date_str = f"{y}年{int(m)}月{int(d)}日"
                    if "凌晨" in case_date_raw:
                        date_str = date_str + "凌晨" + case_date_raw.split("凌晨")[-1].strip()
                    elements["case_date"] = date_str

            # identification_place: 默认为案发地点（指认是在案发现场进行的）
            if not elements.get("identification_place"):
                case_loc = str(elements.get("case_location", ""))
                if case_loc:
                    elements["identification_place"] = case_loc

            # identification_purpose: 让{指认人}指认{指认对象}，锁定案件证据
            identifier = str(elements.get("identifier_name", ""))
            target_obj = str(elements.get("identification_target", ""))
            if identifier and target_obj and not elements.get("identification_purpose"):
                elements["identification_purpose"] = f"让{identifier}指认{target_obj}，锁定案件证据"

            # case_description: 案发经过简述（如LLM未提取，则根据其他字段自动生成）
            if not elements.get("case_description"):
                loc = str(elements.get("case_location", ""))
                viol = str(elements.get("violation_type", ""))
                if identifier and loc and viol:
                    elements["case_description"] = f"伙同他人在{loc}{viol}了相关财物"

            # identification_confirmation: 指认确认内容（如LLM未提取，则自动生成）
            if not elements.get("identification_confirmation"):
                target = str(elements.get("identification_target", ""))
                viol = str(elements.get("violation_type", ""))
                if identifier and target and viol:
                    elements["identification_confirmation"] = f"该{target}就是其{viol}的现场"

        # 辨认笔录：自动计算派生字段（AI 模式同样需要）
        if doc_type == "辨认笔录":
            # 时间格式规范化：ISO → 中文
            elements["identification_time_start"] = _normalize_chinese_datetime(str(elements.get("identification_time_start", "")))
            elements["identification_time_end"] = _normalize_chinese_datetime(str(elements.get("identification_time_end", "")))

            # identification_place: 默认为 {公安机关名称}询问室
            if not elements.get("identification_place"):
                station = str(elements.get("police_station", ""))
                if station:
                    elements["identification_place"] = f"{station}询问室"

            # case_date 格式规范化：ISO → 中文
            case_date_raw = str(elements.get("case_date", ""))
            if case_date_raw:
                cd_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", case_date_raw)
                if cd_match:
                    y, m, d = cd_match.groups()
                    date_str = f"{y}年{int(m)}月{int(d)}日"
                    if "凌晨" in case_date_raw:
                        date_str = date_str + "凌晨" + case_date_raw.split("凌晨")[-1].strip()
                    elements["case_date"] = date_str

            identifier = str(elements.get("identifier_name", ""))
            case_date = str(elements.get("case_date", ""))
            case_loc = str(elements.get("case_location", ""))
            viol = str(elements.get("violation_type", ""))

            # identification_purpose: 让辨认人辨别确认照片中是否有在{案发日期}在{案发地点}{案件性质}的相关人员
            if not elements.get("identification_purpose"):
                if identifier and case_date and case_loc and viol:
                    elements["identification_purpose"] = f"让辨认人辨别确认照片中是否有在{case_date}在{case_loc}{viol}的相关人员。"

            # identification_operation: 辨认人X将所有照片认真仔细的审视了一遍，然后指出来
            if not elements.get("identification_operation"):
                if identifier:
                    elements["identification_operation"] = f"辨认人{identifier}将所有照片认真仔细的审视了一遍，然后指出来："

            # identification_conclusion: 至此，辨认结束
            if not elements.get("identification_conclusion"):
                elements["identification_conclusion"] = "至此，辨认结束。"

            # identification_confirmation: 以上笔录，X看过
            if not elements.get("identification_confirmation"):
                if identifier:
                    elements["identification_confirmation"] = f"以上笔录，{identifier}看过。"

            # identification_results: 当LLM未提取时，从输入中自动抽取涉案人员姓名逐行列出
            if not elements.get("identification_results"):
                suspect_names = self._extract_suspect_names(input_text, str(elements.get("identifier_name", "")))
                if suspect_names:
                    lines = []
                    for sn in suspect_names:
                        lines.append(f"辨认照片一组中（X）号照片的人就是{sn}")
                    lines.append("该组照片中的其他人员均不是本案涉案人员")
                    elements["identification_results"] = "\n".join(lines)

        # 行政处罚决定书：时间格式规范化 + 自动派生字段（AI 模式同样需要）
        if doc_type == "行政处罚决定书":
            elements["birth_date"] = _normalize_chinese_datetime(str(elements.get("birth_date", "") or ""))
            elements["case_occurrence_date"] = _normalize_chinese_datetime(str(elements.get("case_occurrence_date", "") or ""))
            elements["penalty_decision_date"] = _normalize_chinese_datetime(str(elements.get("penalty_decision_date", "") or ""))

            # 落款日期：转为中文大写数字格式（二○二六年五月十五日）
            chinese_digits = {"0": "○", "1": "一", "2": "二", "3": "三", "4": "四",
                              "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}
            def _to_chinese_num(n: int) -> str:
                if n <= 9:
                    return chinese_digits[str(n)]
                elif n == 10:
                    return "十"
                elif n < 20:
                    return "十" + chinese_digits[str(n % 10)]
                elif n % 10 == 0:
                    return chinese_digits[str(n // 10)] + "十"
                else:
                    return chinese_digits[str(n // 10)] + "十" + chinese_digits[str(n % 10)]

            raw_date = str(elements.get("penalty_decision_date", ""))
            stamp_match = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw_date)
            if stamp_match:
                y, m, d = stamp_match.groups()
                cy = "".join(chinese_digits.get(c, c) for c in y)
                cm = _to_chinese_num(int(m))
                cd = _to_chinese_num(int(d))
                elements["stamp_date"] = f"{cy}年{cm}月{cd}日"
            else:
                elements["stamp_date"] = raw_date

            # 默认值
            for fk in ["work_unit", "criminal_record"]:
                v = str(elements.get(fk, ""))
                if not v or v.lower() in ("null", "none", ""):
                    elements[fk] = "无"
            # 去除末尾句号防止与模板句号重复
            cr = str(elements.get("criminal_record", ""))
            if cr.endswith("。"):
                elements["criminal_record"] = cr.rstrip("。")
            if not str(elements.get("native_place", "")).strip() or str(elements.get("native_place", "")).lower() in ("null", "none", ""):
                elements["native_place"] = str(elements.get("household_register", ""))
            if not str(elements.get("household_register", "")).strip() or str(elements.get("household_register", "")).lower() in ("null", "none", ""):
                elements["household_register"] = str(elements.get("party_address", ""))

            # 行政复议机关 / 行政诉讼法院
            dept = str(elements.get("department", ""))
            county_match = re.match(r"(.+?县).+?公安", dept)
            gov_match = re.match(r"(.+?市).+?公安", dept)
            if not str(elements.get("reconsideration_org", "")).strip() or str(elements.get("reconsideration_org", "")).lower() in ("null", "none", ""):
                if county_match:
                    elements["reconsideration_org"] = f"{county_match.group(1)}人民政府"
                elif gov_match:
                    elements["reconsideration_org"] = f"{gov_match.group(1)}市人民政府"
                else:
                    fallback = re.match(r"(.+?[市县区])", dept)
                    elements["reconsideration_org"] = f"{fallback.group(1)}人民政府" if fallback else "XX人民政府"
            if not str(elements.get("lawsuit_court", "")).strip() or str(elements.get("lawsuit_court", "")).lower() in ("null", "none", ""):
                if county_match:
                    elements["lawsuit_court"] = f"{county_match.group(1)}人民法院"
                elif gov_match:
                    elements["lawsuit_court"] = f"{gov_match.group(1)}人民法院"
                else:
                    fallback = re.match(r"(.+?[市县区])", dept)
                    elements["lawsuit_court"] = f"{fallback.group(1)}人民法院" if fallback else "XX人民法院"

            # 去除 illegal_fact 末尾的证据列举句（模板已自动添加）
            ilf = str(elements.get("illegal_fact", ""))
            ilf = re.sub(r"[，,。]?以上事实有[^。]+等证据证实[。]?", "", ilf)
            ilf = re.sub(r"[，,。]?上述事实[^。]+证据[^。]证实[。]?", "", ilf)
            elements["illegal_fact"] = ilf

            # 处罚依据兜底：LLM 未提取时从法条库自动检索
            if not str(elements.get("penalty_basis", "")).strip() or str(elements.get("penalty_basis", "")).lower() in ("null", "none", ""):
                search_text = " ".join([
                    str(elements.get(k, "")) for k in ["illegal_fact", "violation_type", "case_nature"]
                    if str(elements.get(k, ""))
                ]) or input_text
                # 中文关键词匹配（按法条 keywords 在搜索文本中的命中数打分）
                scored = []
                for law in self._retriever._laws:
                    score = 0
                    for kw in law.get("keywords", []):
                        if kw in search_text:
                            score += 1
                    if law.get("law_name", "") in search_text:
                        score += 3
                    if score > 0:
                        scored.append((score, law))
                scored.sort(key=lambda x: x[0], reverse=True)
                if scored:
                    top = scored[0][1]
                    elements["penalty_basis"] = f"《{top.get('law_name', '')}》第{top.get('article_number', '')}条"
                    if not str(elements.get("penalty_content", "")).strip() or str(elements.get("penalty_content", "")).lower() in ("null", "none", ""):
                        fine = str(elements.get("fine_amount", ""))
                        if fine and fine not in ("null", "none", "", "0"):
                            elements["penalty_content"] = f"罚款{fine}元的处罚"
                        elif top.get("penalty_range"):
                            elements["penalty_content"] = top["penalty_range"]

            # 执行方式和期限
            if not str(elements.get("execution_detail", "")).strip() or str(elements.get("execution_detail", "")).lower() in ("null", "none", ""):
                elements["execution_detail"] = "收到决定书之日起15日内将罚款交到指定银行财政罚没专户。"

            # 文书编号
            if not str(elements.get("doc_number", "")).strip() or str(elements.get("doc_number", "")).lower() in ("null", "none", ""):
                cn = str(elements.get("case_number", ""))
                if cn and cn.lower() not in ("null", "none", ""):
                    elements["doc_number"] = cn
                else:
                    dept_abbr = dept.replace("公安局", "").replace("分局", "")[:6] if dept else "XX"
                    ds = str(elements.get("penalty_decision_date", "") or "")
                    year_match = re.search(r"(\d{4})", ds)
                    year = year_match.group(1) if year_match else "YYYY"
                    elements["doc_number"] = f"{dept_abbr}公行罚决字[{year}]NNN号"

        laws = await self.suggest_laws(input_text, doc_type)

        template_text = ""
        if template:
            template_text = template.get("template_text", "")
        elif not template:
            t = self._retriever.retrieve_template(doc_type)
            if t:
                template_text = t.get("template_text", "")

        content = self._fill_template(template_text, elements)

        return {
            "elements": elements,
            "suggested_laws": (
                [l["content"] for l in laws]
                or extracted.get("suggested_laws", [])
            ),
            "case_nature": extracted.get("case_nature", ""),
            "content": content or input_text,
            "template_used": template is not None,
        }

    def _fill_template(self, template_text: str, elements: dict[str, Any]) -> str:
        if not template_text:
            return ""
        result = template_text
        for key, value in elements.items():
            placeholder = "{{" + key + "}}"
            if value is None or value == "None" or value == "null":
                result = result.replace(placeholder, "")
            else:
                result = result.replace(placeholder, str(value))
        return result

    async def generate_document_chain(
        self,
        input_text: str,
        doc_types: list[str],
    ) -> list[dict[str, Any]]:
        """从同一案情描述批量生成多份关联文书（按办案流程顺序）。

        适用于一个案件中需要出具多份文书的情况，如：
        受案登记表 → 传唤证 → 询问笔录 → 行政处罚告知笔录 → 行政处罚决定书
        """
        results: list[dict[str, Any]] = []
        for doc_type in doc_types:
            result = await self.generate_document(doc_type, input_text)
            results.append(result)
        return results

    def check_legal_deadlines(self, fields: dict[str, Any], doc_type: str) -> list[dict]:
        """检查法律期限是否合规，返回超期风险提醒列表。

        基于现行法律规定检测：
        - 传唤询问查证时间不超过8/24小时
        - 行政案件办案期限不超过30日（可延长30日）
        - 扣押期限不超过30日（可延长30日）
        - 告知后3日内作出处罚决定
        - 送达期限7日等
        """
        warnings: list[dict] = []
        from datetime import datetime, timedelta

        try:
            if doc_type == "传唤证":
                summon_time = fields.get("summon_time")
                deadline = fields.get("summon_deadline")
                if summon_time and deadline:
                    t1 = self._parse_datetime(str(summon_time))
                    t2 = self._parse_datetime(str(deadline))
                    delta_hours = (t2 - t1).total_seconds() / 3600
                    if delta_hours > 8:
                        warnings.append({
                            "level": "critical",
                            "message": f"传唤询问查证时间 {delta_hours:.1f} 小时，超过8小时法定上限。" \
                                      "如需延长至24小时，须符合'可能适用行政拘留处罚'的法定条件并经批准。",
                            "law_ref": "《治安管理处罚法》第83条",
                            "field": "summon_deadline",
                        })

            elif doc_type == "行政处罚告知笔录":
                notif_time = fields.get("notification_time")
                if notif_time:
                    t1 = self._parse_datetime(str(notif_time))
                    deadline = t1 + timedelta(days=3)
                    warnings.append({
                        "level": "info",
                        "message": f"告知后应在 {deadline.strftime('%Y-%m-%d')} 前作出处罚决定。" \
                                  "当事人放弃陈述申辩的可在告知当日作出。",
                        "law_ref": "《行政处罚法》第62条",
                    })

            elif doc_type == "行政处罚决定书":
                filing_date = fields.get("filing_date") or fields.get("report_time")
                decision_date = fields.get("penalty_decision_date") or fields.get("notification_date")
                if filing_date and decision_date:
                    d1 = self._parse_date(str(filing_date))
                    d2 = self._parse_date(str(decision_date))
                    delta_days = (d2 - d1).days
                    if delta_days > 30:
                        warnings.append({
                            "level": "critical",
                            "message": f"办案期限 {delta_days} 日，超过30日法定上限。如需延长须经上一级公安机关批准。",
                            "law_ref": "《公安机关办理行政案件程序规定》第165条",
                            "field": "penalty_decision_date",
                        })

            elif doc_type == "扣押决定书":
                seizure_date = fields.get("seizure_date")
                if seizure_date:
                    d1 = self._parse_date(str(seizure_date))
                    deadline = d1 + timedelta(days=30)
                    warnings.append({
                        "level": "info",
                        "message": f"扣押期限至 {deadline.strftime('%Y-%m-%d')}（30日）。" \
                                  "与案件无关的物品应在三日内解除扣押并退还。",
                        "law_ref": "《治安管理处罚法》第89条",
                        "field": "seizure_date",
                    })

        except (ValueError, TypeError):
            pass
        return warnings

    async def summarize_case_file_text(
        self, raw_text: str, doc_type_hint: str = "",
    ) -> dict[str, str]:
        """将从文书文件中提取的原始文本整理为结构化案件摘要。

        用于上传 .doc/.docx 文书后自动生成案件摘要填入 AI 输入框。
        当 LLM 不可用或无法解析时，返回空摘要并附带错误提示，
        不允许将原始文本直接作为摘要返回。
        内置 3 次重试 + 指数退避，应对间歇性网络波动。
        """
        if not raw_text.strip():
            return {"summary": "", "warning": "提取的文本为空，请确认文件包含有效文字内容"}

        prompt = CASE_SUMMARY_PROMPT.replace("{raw_text}", raw_text)

        sys_prompt = self._get_system_prompt()
        temperature = self._get_temperature()
        max_tokens = self._get_max_tokens()

        messages = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": prompt})

        last_error = ""
        for attempt in range(3):
            try:
                response = await self._get_client().chat.completions.create(
                    model=self._get_model_name(),
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=90,
                )
                content = (response.choices[0].message.content or "").strip()
                if not content:
                    return {"summary": "", "warning": "AI 模型未能从文件中提取有效案情信息，请手动输入或更换模型后重试"}
                return {"summary": content, "warning": ""}
            except Exception as e:
                last_error = str(e)[:200]
                logger.warning(
                    "LLM 案件摘要生成失败 (第%d次): %s", attempt + 1, last_error,
                )
                if attempt < 2:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)

        logger.error("LLM 案件摘要生成最终失败: %s", last_error)
        return {"summary": "", "warning": f"AI 模型调用失败（重试3次后仍无法连接），请稍后重试或检查网络。错误: {last_error}"}

    def _parse_datetime(self, val: str) -> "datetime":
        from datetime import datetime
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {val}")

    def _parse_date(self, val: str) -> "date":
        return self._parse_datetime(val).date()

    def _extract_suspect_names(self, input_text: str, identifier_name: str) -> list[str]:
        """从案情描述中抽取除辨认人外的其他涉案人员姓名。

        识别模式：
        - "伙同A、B、C等人" / "伙同A、B、C等"
        - "与A、B、C一起" / "和A、B、C共同"
        """
        names: list[str] = []
        # 匹配 "伙同/与/及/和 X、Y、Z" 模式，直到遇到 "等" 或非名词语素
        pattern = r'(?:伙同|与|及|和|包括)\s*([一-龥]{2,4}(?:[、，][一-龥]{2,4})*)'
        for m in re.finditer(pattern, input_text):
            name_str = m.group(1)
            for part in re.split(r'[、，]', name_str):
                part = part.strip()
                # 去除可能尾随的"等"字
                part = re.sub(r'[等]+$', '', part)
                # 只接受2-3字的纯中文（中国姓名通常2-3字）
                if re.match(r'^[一-龥]{2,3}$', part):
                    # 排除非姓名语素
                    if part not in ('等人', '本案', '在场', '参与', '涉案', '其他',
                                    '一起', '共同', '多名', '若干', '其中', '上述'):
                        if part not in names and part != identifier_name:
                            names.append(part)
        return names

    def _parse_json(self, text: str) -> dict:
        text = text.strip()
        # 移除推理模型的思考标签（MiniMax等模型会在输出中嵌入 <think>...</think>）
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = text.strip()
        # 提取代码块内容
        for marker in ("```json", "```"):
            if marker in text:
                parts = text.split(marker)
                if len(parts) >= 2:
                    inner = parts[1].split("```")
                    if inner:
                        text = inner[0].strip()
                        break
        # 尝试在文本中查找 JSON 对象
        # 有些模型会在 JSON 前后加说明文字
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试修复常见格式问题
            try:
                # 移除尾随逗号
                fixed = re.sub(r",\s*}", "}", text)
                fixed = re.sub(r",\s*]", "]", fixed)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
        return {"elements": {}, "suggested_laws": [], "case_nature": ""}
