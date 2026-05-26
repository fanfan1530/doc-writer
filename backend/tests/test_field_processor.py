"""FieldProcessor 单元测试 —— 验证所有文书类型的字段后处理逻辑。"""

import pytest
from app.services.field_processor import FieldProcessor


@pytest.fixture
def processor():
    return FieldProcessor(law_retriever=None)


class TestInspectionRecord:
    def test_time_normalization(self, processor):
        fields = {
            "inspection_time_start": "2026-05-22 11:20",
            "inspection_time_end": "2026-05-22 11:50",
        }
        result = processor.process("检查笔录", fields)
        assert result["inspection_time_start"] == "2026年5月22日11时20分"
        assert result["inspection_time_end"] == "2026年5月22日11时50分"

    def test_date_extraction_from_time(self, processor):
        fields = {"inspection_time_start": "2026年5月22日11时20分"}
        result = processor.process("检查笔录", fields)
        assert result["inspection_date"] == "2026年5月22日"

    def test_place_default_from_station(self, processor):
        fields = {"police_station": "藤县公安局埌南派出所"}
        result = processor.process("检查笔录", fields)
        assert result["inspection_place"] == "藤县公安局埌南派出所检查室"

    def test_target_display(self, processor):
        fields = {"inspection_target": "张三"}
        result = processor.process("检查笔录", fields)
        assert result["inspection_target_display"] == "张三的身体"

    def test_violation_prefix_stripped(self, processor):
        fields = {"violation_type": "涉嫌盗窃"}
        result = processor.process("检查笔录", fields)
        assert result["violation_type"] == "盗窃"

    def test_reason_auto_generation(self, processor):
        fields = {"inspection_target": "张三", "violation_type": "盗窃"}
        result = processor.process("检查笔录", fields)
        assert result["inspection_reason"] == "收集张三是否有盗窃的证据"

    def test_items_found_default(self, processor):
        fields = {}
        result = processor.process("检查笔录", fields)
        assert result["items_found"] == "没有发现任何涉案物品"

    def test_items_found_preserved(self, processor):
        fields = {"items_found": "发现一把刀具"}
        result = processor.process("检查笔录", fields)
        assert result["items_found"] == "发现一把刀具"

    def test_injury_found_default(self, processor):
        fields = {}
        result = processor.process("检查笔录", fields)
        assert result["injury_found"] == "无任何损伤"


class TestPenaltyDecision:
    def test_time_normalization(self, processor):
        fields = {
            "penalty_decision_date": "2026-05-15",
            "case_occurrence_date": "2026-05-10",
            "birth_date": "1990-01-15",
        }
        result = processor.process("行政处罚决定书", fields)
        assert result["penalty_decision_date"] == "2026年5月15日"
        assert result["case_occurrence_date"] == "2026年5月10日"
        assert result["birth_date"] == "1990年1月15日"

    def test_stamp_date_generation(self, processor):
        fields = {"penalty_decision_date": "2026-05-15"}
        result = processor.process("行政处罚决定书", fields)
        assert result["stamp_date"] == "二○二六年五月十五日"

    def test_default_work_unit(self, processor):
        fields = {}
        result = processor.process("行政处罚决定书", fields)
        assert result["work_unit"] == "无"
        assert result["criminal_record"] == "无"

    def test_criminal_record_period_removed(self, processor):
        fields = {"criminal_record": "曾因盗窃被处罚。"}
        result = processor.process("行政处罚决定书", fields)
        assert result["criminal_record"] == "曾因盗窃被处罚"

    def test_native_place_fallback(self, processor):
        fields = {"household_register": "广西藤县XX镇XX村XX号"}
        result = processor.process("行政处罚决定书", fields)
        assert result["native_place"] == "广西藤县XX镇XX村XX号"

    def test_reconsideration_org_derived(self, processor):
        fields = {"department": "藤县公安局埌南派出所"}
        result = processor.process("行政处罚决定书", fields)
        assert result["reconsideration_org"] == "藤县人民政府"
        assert result["lawsuit_court"] == "藤县人民法院"

    def test_illegal_fact_evidence_removed(self, processor):
        fields = {"illegal_fact": "张三盗窃了财物。以上事实有检查笔录、证人证言等证据证实。"}
        result = processor.process("行政处罚决定书", fields)
        assert "以上事实有" not in result["illegal_fact"]

    def test_execution_detail_default(self, processor):
        fields = {}
        result = processor.process("行政处罚决定书", fields)
        assert "15日" in result["execution_detail"]

    def test_doc_number_generation(self, processor):
        fields = {
            "department": "藤县公安局",
            "penalty_decision_date": "2026年5月15日",
        }
        result = processor.process("行政处罚决定书", fields)
        assert "藤县" in result["doc_number"]
        assert "2026" in result["doc_number"]
        assert "罚决字" in result["doc_number"]

    def test_doc_number_from_case_number(self, processor):
        fields = {"case_number": "藤公(刑)行罚决字[2026]001号"}
        result = processor.process("行政处罚决定书", fields)
        assert result["doc_number"] == "藤公(刑)行罚决字[2026]001号"


class TestIdentificationRecord:
    def test_time_normalization(self, processor):
        fields = {
            "identification_time_start": "2026-05-22 09:00",
            "identification_time_end": "2026-05-22 09:30",
        }
        result = processor.process("指认笔录", fields)
        assert result["identification_time_start"] == "2026年5月22日9时0分"
        assert result["identification_time_end"] == "2026年5月22日9时30分"

    def test_date_extraction(self, processor):
        fields = {"identification_time_start": "2026年5月22日9时0分"}
        result = processor.process("指认笔录", fields)
        assert result["identification_date"] == "2026年5月22日"

    def test_place_default_from_case_location(self, processor):
        fields = {"case_location": "广西藤县埌南镇界垌村工地"}
        result = processor.process("指认笔录", fields)
        assert result["identification_place"] == "广西藤县埌南镇界垌村工地"

    def test_purpose_auto_generation(self, processor):
        fields = {
            "identifier_name": "张三",
            "identification_target": "案发现场",
            "violation_type": "盗窃",
        }
        result = processor.process("指认笔录", fields)
        assert "让张三指认案发现场" in result["identification_purpose"]


class TestLineupRecord:
    def test_time_normalization(self, processor):
        fields = {
            "identification_time_start": "2026-05-22 14:00",
            "identification_time_end": "2026-05-22 14:30",
        }
        result = processor.process("辨认笔录", fields)
        assert result["identification_time_start"] == "2026年5月22日14时0分"

    def test_place_default(self, processor):
        fields = {"police_station": "藤县公安局"}
        result = processor.process("辨认笔录", fields)
        assert result["identification_place"] == "藤县公安局询问室"

    def test_purpose_auto_generation(self, processor):
        fields = {
            "identifier_name": "张三",
            "case_date": "2026年5月20日",
            "case_location": "藤县埌南镇",
            "violation_type": "盗窃",
        }
        result = processor.process("辨认笔录", fields)
        assert "2026年5月20日" in result["identification_purpose"]
        assert "藤县埌南镇" in result["identification_purpose"]

    def test_operation_conclusion_auto(self, processor):
        fields = {"identifier_name": "张三"}
        result = processor.process("辨认笔录", fields)
        assert result["identification_operation"] == "辨认人张三将所有照片认真仔细的审视了一遍，然后指出来："
        assert result["identification_conclusion"] == "至此，辨认结束。"
        assert result["identification_confirmation"] == "以上笔录，张三看过。"


class TestPenaltyNotification:
    def test_default_evidence_list(self, processor):
        fields = {}
        result = processor.process("行政处罚告知笔录", fields)
        assert "检查笔录" in result["evidence_list"]

    def test_default_statement(self, processor):
        fields = {}
        result = processor.process("行政处罚告知笔录", fields)
        assert result["notified_person_statement"] == "我不提出陈述和申辩。"

    def test_penalty_suffix_stripped(self, processor):
        fields = {"proposed_penalty": "罚款500元的处罚"}
        result = processor.process("行政处罚告知笔录", fields)
        assert result["proposed_penalty"] == "罚款500元"


class TestCrimeSceneRecord:
    def test_time_normalization(self, processor):
        fields = {
            "crime_scene_time_start": "2026-05-22 08:00",
            "crime_scene_time_end": "2026-05-22 12:00",
        }
        result = processor.process("现场勘查笔录", fields)
        assert result["crime_scene_time_start"] == "2026年5月22日8时0分"


class TestUnknownDocType:
    def test_passthrough(self, processor):
        fields = {"some_field": "some_value"}
        result = processor.process("结案报告", fields)
        assert result["some_field"] == "some_value"
