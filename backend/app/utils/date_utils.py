"""日期格式化工具 — 全项目统一的日期/时间处理函数。

消除原先在 generation.py 和 document_generator.py 中重复定义的
_normalize_chinese_datetime 等函数。
"""

import re
from datetime import datetime, date

# 中文数字映射
_CHINESE_DIGITS = {"0": "○", "1": "一", "2": "二", "3": "三", "4": "四",
                   "5": "五", "6": "六", "7": "七", "8": "八", "9": "九"}


def normalize_chinese_datetime(value: str) -> str:
    """ISO 时间 → 中文格式：2026-05-22 11:20 → 2026年5月22日11时20分
    也处理仅有日期的格式：2026-05-22 → 2026年5月22日
    已为中文格式的原样返回。
    """
    if not value:
        return value
    if "年" in value and "月" in value:
        return value

    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})[\sT](\d{1,2}):(\d{2})", value)
    if m:
        y, mo, d, h, mi = m.groups()
        return f"{y}年{int(mo)}月{int(d)}日{int(h)}时{int(mi)}分"

    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})$", value)
    if m:
        y, mo, d = m.groups()
        return f"{y}年{int(mo)}月{int(d)}日"
    return value


def extract_date_from_datetime(time_str: str) -> str:
    """从中文或ISO时间字符串中提取日期部分。
    2026年5月22日11时20分 → 2026年5月22日
    """
    if not time_str:
        return ""
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", time_str)
    if m:
        y, mo, d = m.groups()
        return f"{y}年{int(mo)}月{int(d)}日"
    m = re.match(r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})", time_str)
    if m:
        y, mo, d = m.groups()
        return f"{y}年{int(mo)}月{int(d)}日"
    return time_str


def to_chinese_num(n: int) -> str:
    """数字转中文大写：1→一, 10→十, 15→十五, 31→三十一"""
    if n <= 9:
        return _CHINESE_DIGITS[str(n)]
    elif n == 10:
        return "十"
    elif n < 20:
        return "十" + _CHINESE_DIGITS[str(n % 10)]
    elif n % 10 == 0:
        return _CHINESE_DIGITS[str(n // 10)] + "十"
    else:
        return _CHINESE_DIGITS[str(n // 10)] + "十" + _CHINESE_DIGITS[str(n % 10)]


def to_stamp_date(raw_date: str) -> str:
    """将中文日期转为公文落款格式：2026年5月15日 → 二○二六年五月十五日"""
    if not raw_date:
        return raw_date
    m = re.match(r"(\d{4})年(\d{1,2})月(\d{1,2})日", raw_date)
    if not m:
        return raw_date
    y, mo, d = m.groups()
    cy = "".join(_CHINESE_DIGITS.get(c, c) for c in y)
    cm = to_chinese_num(int(mo))
    cd = to_chinese_num(int(d))
    return f"{cy}年{cm}月{cd}日"


def parse_datetime(val: str) -> datetime:
    """尽力解析日期时间字符串。"""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse datetime: {val}")


def parse_date(val: str) -> date:
    """尽力解析日期字符串。"""
    return parse_datetime(val).date()


def safe_str(val: object) -> str:
    """将值转为字符串，处理 None/null。"""
    if val is None:
        return ""
    s = str(val)
    return "" if s.lower() in ("none", "null") else s
