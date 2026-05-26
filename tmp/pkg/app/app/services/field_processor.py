"""字段处理器 — AI 模式与手动模式共享的字段后处理逻辑。

原先这些逻辑在 document_generator.py 和 generation.py 中各有一份完整拷贝，
现在统一到此模块，两个模式共用。
"""

from __future__ import annotations
import re
from typing import Any

from app.utils.date_utils import (
    normalize_chinese_datetime,
    extract_date_from_datetime,
    to_stamp_date,
    safe_str,
)


class FieldProcessor:
    """文书字段标准化后处理器。"""

    def __init__(self, law_retriever: "RAGRetriever | None" = None):
        self._law_retriever = law_retriever

    def process(
        self, doc_type: str, fields: dict[str, Any], input_text: str = "",
    ) -> dict[str, Any]:
        """统一入口：根据文书类型分派到对应的处理方法。"""
        fields = {k: safe_str(v) for k, v in fields.items()}

        if doc_type == "检查笔录":
            fields = self._process_inspection_record(fields, input_text)
        elif doc_type == "行政处罚决定书":
            fields = self._process_penalty_decision(fields, input_text)
        elif doc_type == "指认笔录":
            fields = self._process_identification_record(fields, input_text)
        elif doc_type == "辨认笔录":
            fields = self._process_lineup_record(fields, input_text)
        elif doc_type == "现场勘查笔录":
            fields = self._process_crime_scene_record(fields, input_text)
        elif doc_type == "行政处罚告知笔录":
            fields = self._process_penalty_notification(fields, input_text)

        return fields

    # ── 检查笔录 ──────────────────────────────────────────

    def _process_inspection_record(
        self, fields: dict[str, Any], input_text: str = "",
    ) -> dict[str, Any]:
        fields["inspection_time_start"] = normalize_chinese_datetime(
            fields.get("inspection_time_start", ""))
        fields["inspection_time_end"] = normalize_chinese_datetime(
            fields.get("inspection_time_end", ""))

        # inspection_date 从时间中提取
        if not fields.get("inspection_date"):
            date_val = extract_date_from_datetime(fields["inspection_time_start"])
            if not date_val:
                date_val = self._find_date_in_text(input_text)
            if date_val:
                fields["inspection_date"] = date_val

        # inspection_place 默认值
        if not fields.get("inspection_place"):
            station = fields.get("police_station", "")
            if station:
                fields["inspection_place"] = f"{station}检查室"

        # inspection_target_display
        target = fields.get("inspection_target", "")
        if target and not fields.get("inspection_target_display"):
            fields["inspection_target_display"] = f"{target}的身体"

        # 去除"涉嫌"前缀
        violation = fields.get("violation_type", "")
        if violation.startswith("涉嫌"):
            fields["violation_type"] = violation[2:]

        # inspection_reason 自动生成
        if target and violation and not fields.get("inspection_reason"):
            fields["inspection_reason"] = f"收集{target}是否有{violation}的证据"

        # items_found 清理和默认值
        items = fields.get("items_found", "")
        # 去除 LLM 可能添加的多余前缀
        for prefix in ["身上是，", "身上是。", "身上是", "是，", "是。", "身上发现，", "身上发现", "发现，", "发现。"]:
            if items.startswith(prefix):
                items = items[len(prefix):]
                break
        if not items or items.strip() in ("null", "none", "无", "有", "是", "否", "未发现", "未", "发现", ""):
            fields["items_found"] = "没有发现任何涉案物品"
        else:
            fields["items_found"] = items.strip()

        # injury_found 清理和默认值
        injury = fields.get("injury_found", "")
        for prefix in ["身上是，", "身上是。", "身上是", "是，", "是。", "身上发现，", "身上发现"]:
            if injury.startswith(prefix):
                injury = injury[len(prefix):]
                break
        if not injury or injury.strip() in ("null", "none", "无", "有", "是", "否", "未发现", "未", "发现", ""):
            fields["injury_found"] = "无任何损伤"
        else:
            fields["injury_found"] = injury.strip()

        return fields

    # ── 行政处罚决定书 ────────────────────────────────────

    def _process_penalty_decision(
        self, fields: dict[str, Any], input_text: str = "",
    ) -> dict[str, Any]:
        fields["birth_date"] = normalize_chinese_datetime(fields.get("birth_date", ""))
        fields["case_occurrence_date"] = normalize_chinese_datetime(
            fields.get("case_occurrence_date", ""))
        fields["penalty_decision_date"] = normalize_chinese_datetime(
            fields.get("penalty_decision_date", ""))

        # 落款日期转中文大写 —— 无值时用当前日期兜底
        raw_date = fields.get("penalty_decision_date", "")
        if raw_date:
            fields["stamp_date"] = to_stamp_date(raw_date)
        else:
            from datetime import date
            fields["stamp_date"] = to_stamp_date(date.today().isoformat())

        # 默认值
        for fk in ["work_unit", "criminal_record"]:
            v = fields.get(fk, "")
            if not v or v.lower() in ("null", "none", ""):
                fields[fk] = "无"

        cr = fields.get("criminal_record", "")
        if cr.endswith("。"):
            fields["criminal_record"] = cr.rstrip("。")

        if not fields.get("native_place"):
            fields["native_place"] = fields.get("household_register", "")
        if not fields.get("household_register"):
            fields["household_register"] = fields.get("party_address", "")

        # 行政复议机关 / 行政诉讼法院 从办案单位派生
        dept = fields.get("department", "")
        county_match = re.match(r"(.+?县).+?公安", dept)
        gov_match = re.match(r"(.+?市).+?公安", dept)

        if not fields.get("reconsideration_org"):
            fields["reconsideration_org"] = self._derive_gov_org(county_match, gov_match, dept, "人民政府")

        if not fields.get("lawsuit_court"):
            fields["lawsuit_court"] = self._derive_gov_org(county_match, gov_match, dept, "人民法院")

        # 去除 illegal_fact 中的文书前缀（模板中已包含）
        ilf = fields.get("illegal_fact", "")
        for prefix in ["现查明：", "现查明:", "现查明，", "现查明,", "现查明。", "现查明.", "现查明"]:
            if ilf.startswith(prefix):
                ilf = ilf[len(prefix):]
                break
        # 去除清理后开头的标点
        ilf = re.sub(r"^[，,。.、：:\s]+", "", ilf)
        # 去除末尾证据列举句
        ilf = re.sub(r"[，,。;；]?\s*以上事实有[^。；]+等证据证实[。;；]?", "", ilf)
        ilf = re.sub(r"[，,。;；]?\s*上述事实[^。；]+证据[^。；]证实[。;；]?", "", ilf)
        ilf = re.sub(r"[，,。;；]?\s*以上事实[^。；]{0,30}证据[^。；]{0,20}证实[。;；]?", "", ilf)
        fields["illegal_fact"] = ilf

        # 处罚依据兜底
        law_result = None
        if not fields.get("penalty_basis"):
            search_text = " ".join(
                fields.get(k, "") for k in ["illegal_fact", "violation_type", "case_nature"]
                if fields.get(k, "")
            ) or input_text
            law_result = self._fallback_law_search(search_text)
            if law_result:
                fields["penalty_basis"] = f"《{law_result[0]}》第{law_result[1]}条"
                if not fields.get("penalty_content"):
                    fine = fields.get("fine_amount", "")
                    if fine and fine not in ("null", "none", "", "0"):
                        fields["penalty_content"] = f"罚款{fine}元的处罚"
                    elif law_result[2]:
                        fields["penalty_content"] = f"{law_result[2]}的处罚"

        # 处罚内容最终兜底
        if not fields.get("penalty_content"):
            if law_result and law_result[2]:
                fields["penalty_content"] = f"{law_result[2]}的处罚（具体幅度需根据情节轻重确定）"
            else:
                fields["penalty_content"] = "⚠️[待填写具体处罚内容]"

        # 执行方式和期限
        if not fields.get("execution_detail"):
            fields["execution_detail"] = "收到决定书之日起15日内将罚款交到指定银行财政罚没专户。"

        # 文书编号
        if not fields.get("doc_number"):
            cn = fields.get("case_number", "")
            if cn:
                fields["doc_number"] = cn
            else:
                dept_abbr = dept.replace("公安局", "").replace("分局", "")[:6] if dept else "XX"
                from datetime import date
                year_match = re.search(r"(\d{4})", fields.get("penalty_decision_date", "") or str(date.today().year))
                year = year_match.group(1) if year_match else str(date.today().year)
                import time
                seq = str(int(time.time() * 1000))[-6:]
                fields["doc_number"] = f"{dept_abbr}公行罚决字[{year}]{seq}号"

        return fields

    # ── 指认笔录 ──────────────────────────────────────────

    def _process_identification_record(
        self, fields: dict[str, Any], input_text: str = "",
    ) -> dict[str, Any]:
        fields["identification_time_start"] = normalize_chinese_datetime(
            fields.get("identification_time_start", ""))
        fields["identification_time_end"] = normalize_chinese_datetime(
            fields.get("identification_time_end", ""))

        if not fields.get("identification_date"):
            date_val = extract_date_from_datetime(fields["identification_time_start"])
            if date_val:
                fields["identification_date"] = date_val

        # case_date 规范化
        case_date_raw = fields.get("case_date", "")
        if case_date_raw:
            cd_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", case_date_raw)
            if cd_match:
                y, m, d = cd_match.groups()
                date_str = f"{y}年{int(m)}月{int(d)}日"
                if "凌晨" in case_date_raw:
                    date_str = date_str + "凌晨" + case_date_raw.split("凌晨")[-1].strip()
                fields["case_date"] = date_str

        # 指认地点默认案发地点
        if not fields.get("identification_place"):
            case_loc = fields.get("case_location", "")
            if case_loc:
                fields["identification_place"] = case_loc

        identifier = fields.get("identifier_name", "")
        target_obj = fields.get("identification_target", "")
        viol = fields.get("violation_type", "")
        case_loc = fields.get("case_location", "")

        if identifier and target_obj and not fields.get("identification_purpose"):
            fields["identification_purpose"] = f"让{identifier}指认{target_obj}，锁定案件证据"

        if not fields.get("case_description"):
            if identifier and case_loc and viol:
                fields["case_description"] = f"伙同他人在{case_loc}{viol}了相关财物"

        if not fields.get("identification_confirmation"):
            if identifier and target_obj and viol:
                fields["identification_confirmation"] = f"该{target_obj}就是其{viol}的现场"

        return fields

    # ── 辨认笔录 ──────────────────────────────────────────

    def _process_lineup_record(
        self, fields: dict[str, Any], input_text: str = "",
    ) -> dict[str, Any]:
        fields["identification_time_start"] = normalize_chinese_datetime(
            fields.get("identification_time_start", ""))
        fields["identification_time_end"] = normalize_chinese_datetime(
            fields.get("identification_time_end", ""))

        # 辨认地点默认值
        if not fields.get("identification_place"):
            station = fields.get("police_station", "")
            if station:
                fields["identification_place"] = f"{station}询问室"

        # case_date 规范化
        case_date_raw = fields.get("case_date", "")
        if case_date_raw:
            cd_match = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", case_date_raw)
            if cd_match:
                y, m, d = cd_match.groups()
                date_str = f"{y}年{int(m)}月{int(d)}日"
                if "凌晨" in case_date_raw:
                    date_str = date_str + "凌晨" + case_date_raw.split("凌晨")[-1].strip()
                fields["case_date"] = date_str

        identifier = fields.get("identifier_name", "")
        case_date = fields.get("case_date", "")
        case_loc = fields.get("case_location", "")
        viol = fields.get("violation_type", "")

        if not fields.get("identification_purpose"):
            if identifier and case_date and case_loc and viol:
                fields["identification_purpose"] = (
                    f"让辨认人辨别确认照片中是否有在{case_date}在{case_loc}{viol}的相关人员。"
                )

        if not fields.get("identification_operation"):
            if identifier:
                fields["identification_operation"] = (
                    f"辨认人{identifier}将所有照片认真仔细的审视了一遍，然后指出来："
                )

        if not fields.get("identification_conclusion"):
            fields["identification_conclusion"] = "至此，辨认结束。"

        if not fields.get("identification_confirmation"):
            if identifier:
                fields["identification_confirmation"] = f"以上笔录，{identifier}看过。"

        return fields

    # ── 现场勘查笔录 ──────────────────────────────────────

    def _process_crime_scene_record(
        self, fields: dict[str, Any], input_text: str = "",
    ) -> dict[str, Any]:
        fields["crime_scene_time_start"] = normalize_chinese_datetime(
            fields.get("crime_scene_time_start", ""))
        fields["crime_scene_time_end"] = normalize_chinese_datetime(
            fields.get("crime_scene_time_end", ""))
        return fields

    # ── 行政处罚告知笔录 ──────────────────────────────────

    def _process_penalty_notification(
        self, fields: dict[str, Any], input_text: str = "",
    ) -> dict[str, Any]:
        fields["notification_time"] = normalize_chinese_datetime(
            fields.get("notification_time", ""))

        if not fields.get("legal_representative"):
            fields["legal_representative"] = ""
        if not fields.get("evidence_list"):
            fields["evidence_list"] = "检查笔录、违法行为人的陈述和申辩，其他"
        if not fields.get("notified_person_statement"):
            fields["notified_person_statement"] = "我不提出陈述和申辩。"

        pp = fields.get("proposed_penalty", "")
        if pp.endswith("的处罚"):
            fields["proposed_penalty"] = pp[:-3]

        if not fields.get("penalty_basis"):
            search_text = " ".join(
                fields.get(k, "") for k in ["case_description", "violation_type"]
                if fields.get(k, "")
            )
            if search_text:
                law_result = self._fallback_law_search(search_text)
                if law_result:
                    fields["penalty_basis"] = f"《{law_result[0]}》第{law_result[1]}条"

        return fields

    # ── 私有辅助方法 ──────────────────────────────────────

    @staticmethod
    def _find_date_in_text(text: str) -> str:
        """从文本中提取第一个日期。"""
        patterns = [
            r"(\d{4})年(\d{1,2})月(\d{1,2})日",
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",
        ]
        for pat in patterns:
            m = re.search(pat, str(text))
            if m:
                y, mo, d = m.groups()
                return f"{y}年{int(mo)}月{int(d)}日"
        return ""

    @staticmethod
    def _derive_gov_org(
        county_match: re.Match | None,
        gov_match: re.Match | None,
        dept: str,
        suffix: str,
    ) -> str:
        """从办案单位名称派生政府机关/法院名称。"""
        if county_match:
            return f"{county_match.group(1)}{suffix}"
        elif gov_match:
            return f"{gov_match.group(1)}市{suffix}"
        elif dept:
            fallback = re.match(r"(.+?[市县区])", dept)
            return f"{fallback.group(1)}{suffix}" if fallback else f"XX{suffix}"
        return f"XX{suffix}"

    # 程序性条款关键词 —— 这些条款不应作为处罚依据
    _PROCEDURAL_KEYWORDS = {
        "传唤", "询问查证", "八小时", "二十四小时", "传唤时间",
        "受案回执", "受理", "检查", "勘验", "辨认", "辨认笔录",
        "搜查", "搜查证", "搜查笔录", "扣押", "查封", "讯问",
        "立案", "审查", "检查笔录", "现场勘查", "见证人",
    }

    def _fallback_law_search(self, search_text: str) -> tuple[str, str, str] | None:
        """从中文字段文本中匹配最相关法条。返回 (法条名, 条款号, 处罚幅度) 或 None。

        优先匹配有 penalty_range 的实体罚则，过滤程序性条款。
        """
        if not self._law_retriever or not search_text.strip():
            return None
        scored = []
        for law in self._law_retriever._laws:
            score = 0.0
            keywords = law.get("keywords", [])
            # 排除纯程序性条款（无处罚幅度且关键词全是程序性的）
            has_penalty = bool(law.get("penalty_range", ""))
            is_procedural = all(
                kw in self._PROCEDURAL_KEYWORDS for kw in keywords
            ) if keywords else False
            if is_procedural and not has_penalty:
                continue
            # 关键词匹配
            for kw in keywords:
                if kw in search_text:
                    score += 1.0
            # 法条名在文本中出现
            if law.get("law_name", "") in search_text:
                score += 3.0
            # 有处罚幅度的实体条款加权
            if has_penalty:
                score += 2.0
            # doc_type/案由直接匹配关键词加权
            article = str(law.get("article_number", ""))
            if f"第{article}条" in search_text:
                score += 5.0
            if score > 0:
                scored.append((score, law))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored:
            top = scored[0][1]
            return (
                top.get("law_name", ""),
                top.get("article_number", ""),
                top.get("penalty_range", ""),
            )
        return None
