"""从本地文档库查找原始 .doc 文件，按模板名称匹配。"""

import os
import re
from pathlib import Path

# 原始文档路径（与 template_seeder 保持一致）
DOC_COLLECTION = (
    r"C:\Users\Lenovo\Desktop"
    r"\2024 GA刑事和行政法律文书电子word版-20241108(1)"
    r"\2024 GA刑事和行政法律文书电子word版-20241108"
)

CRIMINAL_DIR = os.path.join(DOC_COLLECTION, "公安刑事法律文书式样(2022)")
ADMIN_DIR = os.path.join(DOC_COLLECTION, "2024版公安行政法律文书式样word版本-法度笔录-241108")


# 2024版行政文件名 → doc_type 的映射
# 多个 doc_type 可能指向同一文件（复合式样）
ADMIN_FILE_MAP: dict[str, str] = {
    "1-行政案件立案登记表、接受证据清单（式样一）.doc": "行政立案登记表",
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


def find_original_doc(doc_type: str, category: str = "行政") -> str | None:
    """根据模板 doc_type 和 category 查找原始 .doc 文件路径。"""

    if category == "刑事":
        return _find_criminal_doc(doc_type)

    # 行政: 遍历 ADMIN_FILE_MAP
    for fname, mapped_type in ADMIN_FILE_MAP.items():
        if mapped_type == doc_type:
            path = os.path.join(ADMIN_DIR, fname)
            if os.path.isfile(path):
                return path

    # 回退: 直接用 doc_type 模糊匹配
    if os.path.isdir(ADMIN_DIR):
        for fname in sorted(os.listdir(ADMIN_DIR)):
            if not fname.endswith('.doc'):
                continue
            # 去掉编号前缀和扩展名
            name_no_ext = Path(fname).stem
            name_clean = re.sub(r'^\d+[-—.]?\s*', '', name_no_ext)
            if doc_type in name_clean or name_clean in doc_type:
                return os.path.join(ADMIN_DIR, fname)

    return None


# 刑事单独文件映射 (部分刑事模板有独立的 .doc 文件)
CRIMINAL_FILE_MAP: dict[str, str] = {
    "变更羁押期限通知书": "变更羁押期限通知书.doc",
    "换押证": "换押证.doc",
    "提讯提解证": "提讯提解证.doc",
}


def _find_criminal_doc(doc_type: str) -> str | None:
    """刑事模板: 优先查找独立 .doc，不存在则返回 None（不退回到合集文档）。"""
    # 独立文件
    fname = CRIMINAL_FILE_MAP.get(doc_type)
    if fname:
        path = os.path.join(CRIMINAL_DIR, fname)
        if os.path.isfile(path):
            return path

    # 其余 93 个刑事模板都在合集文档中，暂不直接返回合集（太大）
    # 回退时由 API 层生成 .docx
    return None
