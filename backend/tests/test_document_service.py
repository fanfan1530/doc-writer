"""DocumentService 单元测试 —— 验证核心辅助方法（不依赖 LLM 调用）。"""

import pytest
from app.services.document_service import DocumentService


@pytest.fixture
def svc():
    return DocumentService()


class TestFillTemplate:
    def test_basic_substitution(self, svc):
        template = "当事人：{{name}}，性别{{gender}}"
        elements = {"name": "张三", "gender": "男"}
        result = svc._fill_template(template, elements)
        assert result == "当事人：张三，性别男"

    def test_none_value_removed(self, svc):
        template = "住址：{{address}}。"
        elements = {"address": None}
        result = svc._fill_template(template, elements)
        assert result == "住址：。"

    def test_null_string_removed(self, svc):
        template = "职业：{{occupation}}。"
        elements = {"occupation": "null"}
        result = svc._fill_template(template, elements)
        assert result == "职业：。"

    def test_none_string_removed(self, svc):
        template = "单位：{{work_unit}}。"
        elements = {"work_unit": "None"}
        result = svc._fill_template(template, elements)
        assert result == "单位：。"

    def test_multiple_placeholders(self, svc):
        template = "{{a}} {{b}} {{c}}"
        elements = {"a": "一", "b": "二", "c": "三"}
        result = svc._fill_template(template, elements)
        assert result == "一 二 三"

    def test_empty_template(self, svc):
        assert svc._fill_template("", {"a": "1"}) == ""

    def test_missing_key_left_unchanged(self, svc):
        template = "{{name}} {{missing}}"
        elements = {"name": "张三"}
        result = svc._fill_template(template, elements)
        assert result == "张三 {{missing}}"


class TestParseJson:
    def test_valid_json(self, svc):
        result = svc._parse_json('{"elements": {"name": "张三"}, "suggested_laws": [], "case_nature": "盗窃"}')
        assert result["elements"]["name"] == "张三"
        assert result["case_nature"] == "盗窃"

    def test_json_in_code_block(self, svc):
        text = '''```json
{"elements": {"name": "张三"}, "suggested_laws": [], "case_nature": ""}
```'''
        result = svc._parse_json(text)
        assert result["elements"]["name"] == "张三"

    def test_json_with_prefix_text(self, svc):
        text = '好的，以下是抽取结果：\n{"elements": {"name": "张三"}, "suggested_laws": [], "case_nature": ""}'
        result = svc._parse_json(text)
        assert result["elements"]["name"] == "张三"

    def test_json_with_suffix_text(self, svc):
        text = '{"elements": {"name": "张三"}, "suggested_laws": [], "case_nature": ""}\n以上是抽取结果。'
        result = svc._parse_json(text)
        assert result["elements"]["name"] == "张三"

    def test_trailing_comma_fixed(self, svc):
        text = '{"elements": {"name": "张三",}, "suggested_laws": [], "case_nature": "",}'
        result = svc._parse_json(text)
        assert result["elements"]["name"] == "张三"

    def test_think_tags_removed(self, svc):
        text = '<think>推理过程...</think>\n{"elements": {"name": "李四"}, "suggested_laws": [], "case_nature": ""}'
        result = svc._parse_json(text)
        assert result["elements"]["name"] == "李四"

    def test_invalid_json_returns_empty(self, svc):
        result = svc._parse_json("这不是 JSON")
        assert result == {"elements": {}, "suggested_laws": [], "case_nature": ""}

    def test_unclosed_code_block_handled(self, svc):
        text = '```json\n{"elements": {"name": "test"}, "suggested_laws": [], "case_nature": ""}'
        result = svc._parse_json(text)
        assert result["elements"]["name"] == "test"


class TestExtractSuspectNames:
    def test_basic_extraction(self, svc):
        text = "张三伙同李四、王五等人在藤县盗窃了电缆"
        names = svc._extract_suspect_names(text, "张三")
        assert "李四" in names
        assert "王五" in names
        assert "张三" not in names  # identifier excluded

    def test_multiple_patterns(self, svc):
        text = "赵六与孙七、周八共同实施了盗窃"
        names = svc._extract_suspect_names(text, "")
        assert len(names) >= 2

    def test_excluded_words_removed(self, svc):
        text = "伙同等人"
        names = svc._extract_suspect_names(text, "")
        assert "等人" not in names

    def test_no_match_returns_empty(self, svc):
        names = svc._extract_suspect_names("单纯的案情描述", "")
        assert names == []


class TestCheckLegalDeadlines:
    def test_penalty_notification(self, svc):
        warnings = svc.check_legal_deadlines(
            {"notification_time": "2026-05-20 10:00:00"},
            "行政处罚告知笔录",
        )
        assert len(warnings) == 1
        assert warnings[0]["level"] == "info"

    def test_penalty_decision_overdue(self, svc):
        warnings = svc.check_legal_deadlines(
            {"filing_date": "2026-01-01", "penalty_decision_date": "2026-05-01"},
            "行政处罚决定书",
        )
        assert len(warnings) == 1
        assert warnings[0]["level"] == "critical"

    def test_seizure_deadline(self, svc):
        warnings = svc.check_legal_deadlines(
            {"seizure_date": "2026-05-20"},
            "扣押决定书",
        )
        assert len(warnings) == 1

    def test_unknown_doc_type_no_warnings(self, svc):
        warnings = svc.check_legal_deadlines({}, "检查笔录")
        assert warnings == []
