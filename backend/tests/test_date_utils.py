"""Date utils 单元测试。"""

import pytest
from datetime import datetime, date
from app.utils.date_utils import (
    normalize_chinese_datetime,
    extract_date_from_datetime,
    to_chinese_num,
    to_stamp_date,
    parse_datetime,
    parse_date,
    safe_str,
)


class TestNormalizeChineseDatetime:
    def test_already_chinese_returns_unchanged(self):
        assert normalize_chinese_datetime("2026年5月22日11时20分") == "2026年5月22日11时20分"

    def test_iso_datetime_with_space(self):
        result = normalize_chinese_datetime("2026-05-22 11:20")
        assert result == "2026年5月22日11时20分"

    def test_iso_datetime_with_T(self):
        result = normalize_chinese_datetime("2026-05-22T14:30")
        assert result == "2026年5月22日14时30分"

    def test_iso_date_only(self):
        result = normalize_chinese_datetime("2026-05-22")
        assert result == "2026年5月22日"

    def test_date_with_slashes(self):
        result = normalize_chinese_datetime("2026/05/22")
        assert result == "2026年5月22日"

    def test_single_digit_month_day(self):
        result = normalize_chinese_datetime("2026-1-3 9:05")
        assert result == "2026年1月3日9时5分"

    def test_empty_string(self):
        assert normalize_chinese_datetime("") == ""

    def test_none_value(self):
        assert normalize_chinese_datetime(None) is None  # type: ignore[arg-type]


class TestExtractDateFromDatetime:
    def test_from_chinese_datetime(self):
        assert extract_date_from_datetime("2026年5月22日11时20分") == "2026年5月22日"

    def test_from_iso(self):
        assert extract_date_from_datetime("2026-05-22") == "2026年5月22日"

    def test_empty(self):
        assert extract_date_from_datetime("") == ""


class TestToChineseNum:
    def test_single_digit(self):
        assert to_chinese_num(1) == "一"
        assert to_chinese_num(5) == "五"
        assert to_chinese_num(9) == "九"

    def test_ten(self):
        assert to_chinese_num(10) == "十"

    def test_teens(self):
        assert to_chinese_num(11) == "十一"
        assert to_chinese_num(15) == "十五"
        assert to_chinese_num(19) == "十九"

    def test_tens(self):
        assert to_chinese_num(20) == "二十"
        assert to_chinese_num(30) == "三十"

    def test_compound(self):
        assert to_chinese_num(25) == "二十五"
        assert to_chinese_num(31) == "三十一"
        assert to_chinese_num(99) == "九十九"


class TestToStampDate:
    def test_full_conversion(self):
        result = to_stamp_date("2026年5月15日")
        assert result == "二○二六年五月十五日"

    def test_single_digit_month_day(self):
        result = to_stamp_date("2026年1月3日")
        assert result == "二○二六年一月三日"

    def test_december(self):
        result = to_stamp_date("2024年12月31日")
        assert result == "二○二四年十二月三十一日"

    def test_empty(self):
        assert to_stamp_date("") == ""

    def test_non_matching_returns_original(self):
        assert to_stamp_date("not a date") == "not a date"


class TestParseDatetime:
    def test_full_datetime(self):
        result = parse_datetime("2026-05-22 11:20:00")
        assert result == datetime(2026, 5, 22, 11, 20, 0)

    def test_iso_with_T(self):
        result = parse_datetime("2026-05-22T14:30:00")
        assert result == datetime(2026, 5, 22, 14, 30, 0)

    def test_date_only(self):
        result = parse_datetime("2026-05-22")
        assert result == datetime(2026, 5, 22)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_datetime("not a date")


class TestParseDate:
    def test_from_datetime_string(self):
        result = parse_date("2026-05-22")
        assert result == date(2026, 5, 22)


class TestSafeStr:
    def test_none_returns_empty(self):
        assert safe_str(None) == ""

    def test_string_none_returns_empty(self):
        assert safe_str("None") == ""

    def test_string_null_returns_empty(self):
        assert safe_str("null") == ""

    def test_normal_string(self):
        assert safe_str("hello") == "hello"

    def test_number(self):
        assert safe_str(123) == "123"
