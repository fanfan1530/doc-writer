from __future__ import annotations

import copy
import html
import io
import json
import os
import re
import time
import uuid
import zipfile
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as url_request
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET


PORT = int(os.environ.get("WORD_EXPORT_PORT", "8123"))
PUBLIC_BASE_URL = os.environ.get("WORD_EXPORT_PUBLIC_BASE_URL", f"http://localhost:{PORT}")
DIFY_FILE_BASE_URL = os.environ.get("DIFY_FILE_BASE_URL", "http://docker-nginx-1")
DIFY_DB_HOST = os.environ.get("DIFY_DB_HOST", "docker-db_postgres-1")
DIFY_DB_PORT = int(os.environ.get("DIFY_DB_PORT", "5432"))
DIFY_DB_NAME = os.environ.get("DIFY_DB_NAME", "dify")
DIFY_DB_USER = os.environ.get("DIFY_DB_USER", "postgres")
DIFY_DB_PASSWORD = os.environ.get("DIFY_DB_PASSWORD") or os.environ.get("POSTGRES_PASSWORD") or "difyai123456"
OUTPUT_DIR = Path(os.environ.get("WORD_EXPORT_OUTPUT_DIR", "outputs/word_exports")).resolve()
TEMPLATE_PATH = Path(os.environ.get("WORD_EXPORT_TEMPLATE", "work/reference_layout.docx")).resolve()
CHECK_TEMPLATE_PATH = Path(os.environ.get("WORD_EXPORT_CHECK_TEMPLATE", "work/check_record_template.docx")).resolve()
IDENTIFICATION_TEMPLATE_PATH = Path(
    os.environ.get("WORD_EXPORT_IDENTIFICATION_TEMPLATE", "work/identification_record_template.docx")
).resolve()
CRIMINAL_RECORD_TEMPLATE_PATH = Path(
    os.environ.get("WORD_EXPORT_CRIMINAL_RECORD_TEMPLATE", "work/criminal_record_template.docx")
).resolve()
SEARCH_RECORD_TEMPLATE_PATH = Path(
    os.environ.get("WORD_EXPORT_SEARCH_RECORD_TEMPLATE", "work/search_record_template.docx")
).resolve()
ENTRY_MATERIALS_TEMPLATE_DIR = Path(
    os.environ.get("WORD_EXPORT_ENTRY_MATERIALS_TEMPLATE_DIR", "work/entry_materials_docx_templates")
).resolve()

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W = f"{{{W_NS}}}"
R = f"{{{R_NS}}}"
A = f"{{{A_NS}}}"
XML = f"{{{XML_NS}}}"

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
ET.register_namespace("a", A_NS)
ET.register_namespace("xml", XML_NS)

SLOT_ORDER = [
    "agency",
    "title",
    "doc_number",
    "party",
    "fact",
    "evidence",
    "penalty",
    "execution",
    "overdue",
    "copies",
    "appeal",
    "appendix",
    "stamp_agency",
    "stamp_date",
    "delivery",
    "sign",
    "sign_date",
    "receiver",
    "receiver_unit",
    "receiver_date",
    "case_number",
    "person_number",
]


DEFAULT_SLOT_VALUES = {
    "agency": "藤县公安局",
    "title": "行政处罚决定书",
    "doc_number": "",
    "party": "违法行为人，居民身份证号码，出生，籍贯：，户籍：，现住：，工作单位：，违法犯罪经历：。",
    "fact": "",
    "evidence": "上述事实有以下证据证实：",
    "penalty": "根据相关法律规定，现决定依法作出相应行政处罚。",
    "execution": "执行方式和期限：",
    "overdue": "逾期不交纳罚款的，每日按罚款数额的百分之三加处罚款，罚款的数额不超过罚款本数。",
    "copies": "一式四份，被处罚人和执行单位各一份，被侵害人一份，一份附卷。登陆www.gazxfz.gov.cn查询该行政处罚公开和网上申请行政复议。",
    "appeal": "如不服本决定，可以在收到本决定书之日起六十日内向藤县人民政府申请行政复议或者在六个月内依法向藤县人民法院提起行政诉讼。",
    "appendix": "附：  清单共  份",
    "stamp_agency": "藤县公安局",
    "stamp_date": time.strftime("%Y-%m-%d"),
    "delivery": "行政处罚决定书已向我宣告并送达。",
    "sign": "被处罚人:                        被侵害人：",
    "sign_date": "年    月    日                  年    月    日",
    "receiver": "接收人员：",
    "receiver_unit": "接收单位（印）",
    "receiver_date": "年    月    日",
    "case_number": "案件编号：",
    "person_number": "人员编号：",
}


CHECK_DEFAULT_SLOT_VALUES = {
    "agency": "藤 县 公 安 局",
    "title": "检 查 笔 录",
    "time": "时间：",
    "place": "地点 ： ",
    "inspector_1": "检查人姓名和工作单位：",
    "inspector_2": "",
    "object": "检查或者辨认对象：",
    "party_heading": "当事人/辨认人基本情况（姓名、性别、身份证件种类及号码）",
    "party_basic": "",
    "witness": "见证人基本情况 （姓名、性别、身份证件种类及号码）",
    "reason": "事由和目的：",
    "process": "过程和结果：",
    "checker_sign": "检查人：                                  年   月   日 ",
    "recorder_sign": "记录人：                                  年   月   日 ",
    "party_sign": "当事人：                                  年　 月　 日  ",
    "witness_sign": "见证人：                                  年   月   日   ",
    "photo_title": "身体检查照片",
    "footer_unit": "                    办案单位：",
    "footer_officers": "办案人员：",
    "footer_date": "                    时    间：",
}

IDENTIFICATION_DEFAULT_SLOT_VALUES = {
    "title": " 辨 认 笔 录",
    "time": "时间：",
    "place": "地点：",
    "officers": "办案人员姓名、单位：",
    "identifier": "辨认人姓名：  地址：",
    "witness": "见证人姓名、单位：     住址：",
    "object": "辨认对象：",
    "purpose": "辨认目的：",
    "process_heading": "辨认过程及结果：",
    "process": "",
    "review": "辨认人将所有照片认真仔细的审视了一遍，然后指出来：",
    "result_1": "",
    "result_2": "",
    "result_3": "",
    "result_4": "",
    "result_5": "",
    "end": "至此，辨认结束。",
    "sign_officers": "办案人员：　　　\u3000        \u3000    记录人：　　　　",
    "sign_people": "见证人：                      辨认人：　　　　           ",
}

CRIMINAL_RECORD_DEFAULT_SLOT_VALUES = {
    "title": "前科证明",
    "party": "梁炎洪，性别：男 ，出生日期：2010年10月26日，                  身份证件种类及号码：居民身份证450422201010261752，户籍住址：广西藤县埌南镇莫埌村凤凰组42号。",
    "query_result": "经我所民警在全国违法犯罪人员信息资源库、全国在逃人员信息库、全国吸毒人员信息库、广西警务信息综合应用平台和我所档案室查找档案，在本证明出具之日前，未发现梁炎洪在本辖区居住期间有违法犯罪记录。",
    "statement": "特此证明。",
    "agency": "广西藤县公安局埌南派出所",
    "issue_date": time.strftime("%Y年%m月%d日"),
}

SEARCH_RECORD_DEFAULT_SLOT_VALUES = {
    "title": "搜 查 笔 录",
    "time": "时间：______年__月__日__时__分至______年__月__日__时__分",
    "location": "搜查地点：",
    "officers": "搜查人员姓名、单位:                、               公安局",
    "party": "当事人姓名：",
    "object": "被搜查对象：",
    "basis": "根据______年__月__日______签发的___搜查字[____]_____号搜查证，在见证人________的见证下，对本案嫌疑人________的________进行搜查。",
    "process_1": "过程和结果：",
    "process_2": "在搜查过程中没有损坏任何物品，侦查人员对以上搜出的涉案物品依法进行清点、扣押，清点数量、扣押物品详见《扣押清单》。",
    "process_3": "搜查过程进行拍照，至此搜查结束。",
    "sign_officers": "侦查人员：                       记录人：",
    "sign_party": "当事人：                         见证人：",
    "photo_title": "搜 查 照 片（一）",
    "photo_caption": "",
    "footer": "办案单位：          办案人员：          时间：",
}

ENTRY_MATERIALS_FILENAMES = [
    "被拘留人员信息卡、入所登记表（202501版）.docx",
    "入所健康检查表.docx",
    "梧州市拘留所在押人员病历档案首页.docx",
    "梧州市拘留所矛盾化解纠纷排查表.docx",
    "梧州市拘留所被拘留人权利义务告知书.docx",
    "防治艾滋病基本知识.docx",
]

ENTRY_MATERIALS_DIRECT_COPY = ("防治艾滋病基本知识", "权利义务告知书")


def _escape(value: object) -> str:
    return html.escape(str(value or ""), quote=False)


def _paragraph(text: str, title: bool = False) -> str:
    escaped = _escape(text)
    if title:
        ppr = '<w:pPr><w:jc w:val="center"/><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
        rpr = (
            '<w:rPr><w:rFonts w:ascii="SimHei" w:eastAsia="SimHei" w:hAnsi="SimHei"/>'
            '<w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>'
        )
    else:
        ppr = '<w:pPr><w:ind w:firstLine="480"/><w:spacing w:line="360" w:lineRule="auto"/></w:pPr>'
        rpr = (
            '<w:rPr><w:rFonts w:ascii="FangSong" w:eastAsia="FangSong" w:hAnsi="FangSong"/>'
            '<w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>'
        )
    return f'<w:p>{ppr}<w:r>{rpr}<w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>'


def build_simple_docx(content: str) -> bytes:
    lines = str(content or "").strip().splitlines()
    body: list[str] = []
    first_text = True
    for line in lines:
        stripped = line.strip()
        if not stripped:
            body.append("<w:p/>")
            continue
        body.append(_paragraph(stripped, title=first_text))
        first_text = False

    document_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {chr(10).join(body)}
    <w:sectPr><w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr>
  </w:body>
</w:document>'''
    content_types = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''
    rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''
    doc_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>'''
    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>'''

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", document_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)
        zf.writestr("word/styles.xml", styles)
    return buffer.getvalue()


def _text_of_paragraph(paragraph: ET.Element) -> str:
    return "".join(node.text or "" for node in paragraph.findall(f".//{W}t"))


def _clear_text_nodes(paragraph: ET.Element) -> None:
    for node in list(paragraph):
        if node.tag != f"{W}pPr":
            paragraph.remove(node)


def _set_paragraph_text(paragraph: ET.Element, text: str) -> None:
    text = str(text or "")
    if not text:
        _clear_text_nodes(paragraph)
        return

    first_run = paragraph.find(f"{W}r")
    run_props = None
    if first_run is not None:
        run_props = first_run.find(f"{W}rPr")

    _clear_text_nodes(paragraph)

    run = ET.SubElement(paragraph, f"{W}r")
    if run_props is not None:
        run.append(copy.deepcopy(run_props))
    text_node = ET.SubElement(run, f"{W}t")
    text_node.set(f"{XML}space", "preserve")
    text_node.text = text


def _content_lines(content: str) -> list[str]:
    lines = []
    for line in str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        clean = re.sub(r"[ \t]+", " ", line).strip()
        if clean:
            lines.append(clean)
    return lines


def _find_index(lines: list[str], predicate, start: int = 0) -> int:
    for index in range(max(start, 0), len(lines)):
        if predicate(lines[index]):
            return index
    return -1


def _join_paragraph(lines: list[str]) -> str:
    return "".join(line.strip() for line in lines if line.strip())


def _canonical_static(value: str, slot: str) -> str:
    value = str(value or "").strip()
    if slot == "appendix" and value.startswith("附"):
        return DEFAULT_SLOT_VALUES["appendix"]
    if slot == "delivery" and value.startswith("行政处罚决定书已向我宣告"):
        return DEFAULT_SLOT_VALUES["delivery"]
    if slot == "sign" and value.startswith("被处罚人"):
        return DEFAULT_SLOT_VALUES["sign"]
    if slot in {"sign_date", "receiver_date"} and "年" in value and "月" in value and "日" in value:
        return DEFAULT_SLOT_VALUES[slot]
    if slot == "receiver" and value.startswith("接收人员"):
        return DEFAULT_SLOT_VALUES["receiver"]
    if slot == "receiver_unit" and value.startswith("接收单位"):
        return DEFAULT_SLOT_VALUES["receiver_unit"]
    if slot == "case_number" and value.startswith("案件编号"):
        return DEFAULT_SLOT_VALUES["case_number"]
    if slot == "person_number" and value.startswith("人员编号"):
        return DEFAULT_SLOT_VALUES["person_number"]
    return value


def _extract_slots(content: str) -> dict[str, str]:
    lines = _content_lines(content)
    slots = dict(DEFAULT_SLOT_VALUES)
    if not lines:
        return slots

    agency_idx = _find_index(lines, lambda text: "公安局" in text and len(text) <= 30)
    title_idx = _find_index(lines, lambda text: text == "行政处罚决定书" or text.endswith("处罚决定书"))
    doc_idx = _find_index(lines, lambda text: "罚决字" in text or text.endswith("号"), start=0)
    party_idx = _find_index(lines, lambda text: text.startswith("违法行为人"))
    evidence_idx = _find_index(lines, lambda text: text.startswith("上述事实"))
    penalty_idx = _find_index(lines, lambda text: text.startswith("根据"))
    execution_idx = _find_index(lines, lambda text: text.startswith("执行方式"))
    overdue_idx = _find_index(lines, lambda text: text.startswith("逾期"))
    copies_idx = _find_index(lines, lambda text: text.startswith("一式"))
    appeal_idx = _find_index(lines, lambda text: text.startswith("如不服"))
    appendix_idx = _find_index(lines, lambda text: text.startswith("附"))
    delivery_idx = _find_index(lines, lambda text: text.startswith("行政处罚决定书已向我宣告"))
    sign_idx = _find_index(lines, lambda text: text.startswith("被处罚人"))
    receiver_idx = _find_index(lines, lambda text: text.startswith("接收人员"))
    unit_idx = _find_index(lines, lambda text: text.startswith("接收单位"))
    case_idx = _find_index(lines, lambda text: text.startswith("案件编号"))
    person_idx = _find_index(lines, lambda text: text.startswith("人员编号"))

    for key, index in {
        "agency": agency_idx,
        "title": title_idx,
        "doc_number": doc_idx,
        "party": party_idx,
        "evidence": evidence_idx,
        "penalty": penalty_idx,
        "execution": execution_idx,
        "overdue": overdue_idx,
        "copies": copies_idx,
        "appeal": appeal_idx,
        "appendix": appendix_idx,
        "delivery": delivery_idx,
        "sign": sign_idx,
        "receiver": receiver_idx,
        "receiver_unit": unit_idx,
        "case_number": case_idx,
        "person_number": person_idx,
    }.items():
        if index >= 0:
            slots[key] = _canonical_static(lines[index], key)

    date_idx = _find_index(lines, lambda text: bool(re.fullmatch(r"\d{4}[-年]\d{1,2}[-月]\d{1,2}日?", text)))
    if date_idx >= 0:
        slots["stamp_date"] = lines[date_idx]

    if appendix_idx >= 0:
        stamp_agency_idx = _find_index(lines, lambda text: "公安局" in text and len(text) <= 30, start=appendix_idx + 1)
        if stamp_agency_idx >= 0:
            slots["stamp_agency"] = lines[stamp_agency_idx]
        stamp_date_idx = _find_index(
            lines,
            lambda text: bool(re.fullmatch(r"\d{4}[-年]\d{1,2}[-月]\d{1,2}日?", text)),
            start=appendix_idx + 1,
        )
        if stamp_date_idx >= 0:
            slots["stamp_date"] = lines[stamp_date_idx]

    if sign_idx >= 0:
        sign_date_idx = _find_index(lines, lambda text: "年" in text and "月" in text and "日" in text, start=sign_idx + 1)
        if sign_date_idx >= 0:
            slots["sign_date"] = DEFAULT_SLOT_VALUES["sign_date"]
    if unit_idx >= 0:
        unit_date_idx = _find_index(lines, lambda text: "年" in text and "月" in text and "日" in text, start=unit_idx + 1)
        if unit_date_idx >= 0:
            slots["receiver_date"] = DEFAULT_SLOT_VALUES["receiver_date"]

    fact_start = max(agency_idx, title_idx, doc_idx, party_idx) + 1
    if fact_start <= 0:
        fact_start = 0
    fact_end_candidates = [idx for idx in [evidence_idx, penalty_idx, execution_idx, overdue_idx] if idx >= fact_start]
    fact_end = min(fact_end_candidates) if fact_end_candidates else len(lines)
    fact_lines = lines[fact_start:fact_end]
    if fact_lines:
        slots["fact"] = _join_paragraph(fact_lines)
    elif not any(index >= 0 for index in [title_idx, doc_idx, party_idx, evidence_idx, penalty_idx]):
        slots["fact"] = _join_paragraph(lines)

    if slots["stamp_agency"] == DEFAULT_SLOT_VALUES["stamp_agency"] and slots["agency"]:
        slots["stamp_agency"] = slots["agency"]
    return slots


def _check_content_lines(content: str) -> list[str]:
    lines = []
    for line in str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line.strip():
            lines.append(line.rstrip())
    return lines


def _compact_for_match(text: str) -> str:
    return re.sub(r"[\s　：:]+", "", str(text or ""))


def _space_agency(value: str) -> str:
    text = re.sub(r"\s+", "", str(value or "").strip())
    if not text:
        return CHECK_DEFAULT_SLOT_VALUES["agency"]
    if len(text) <= 12 and " " not in value:
        return " ".join(text)
    return str(value).strip()


def _line_starts(line: str, prefix: str) -> bool:
    return _compact_for_match(line).startswith(_compact_for_match(prefix))


def _line_after_label(line: str, label: str) -> str:
    compact_label = _compact_for_match(label)
    raw = str(line or "").strip()
    if _compact_for_match(raw).startswith(compact_label):
        for marker in ("：", ":"):
            pos = raw.find(marker)
            if pos >= 0:
                return raw[pos + 1 :].strip()
    return ""


def _first_line(lines: list[str], *prefixes: str) -> str:
    for line in lines:
        if any(_line_starts(line, prefix) for prefix in prefixes):
            return line.strip()
    return ""


def _strip_image_relationships(data: bytes) -> bytes:
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    try:
        root = ET.fromstring(data)
    except Exception:
        return data
    for rel in list(root):
        if str(rel.get("Type") or "").endswith("/image"):
            root.remove(rel)
    ET.register_namespace("", rel_ns)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _filter_image_relationships(data: bytes, keep_ids: set[str]) -> bytes:
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    try:
        root = ET.fromstring(data)
    except Exception:
        return data
    for rel in list(root):
        if str(rel.get("Type") or "").endswith("/image") and rel.get("Id") not in keep_ids:
            root.remove(rel)
    ET.register_namespace("", rel_ns)
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _has_image_embed(element: ET.Element) -> bool:
    """True if the element is a drawing/pict that references an image via r:embed."""
    for blip in element.iter(f"{A}blip"):
        if blip.get(f"{R}embed"):
            return True
    return False


def _remove_inline_images(node: ET.Element) -> None:
    image_tags = {f"{W}pict", f"{W}drawing", f"{W}object"}
    for child in list(node):
        if child.tag in image_tags and _has_image_embed(child):
            node.remove(child)
        else:
            _remove_inline_images(child)


def _trim_inline_images(node: ET.Element, keep_count: int, state: dict[str, int] | None = None) -> None:
    if state is None:
        state = {"seen": 0}
    image_tags = {f"{W}pict", f"{W}drawing", f"{W}object"}
    for child in list(node):
        if child.tag in image_tags and _has_image_embed(child):
            if state["seen"] >= keep_count:
                node.remove(child)
            state["seen"] += 1
        else:
            _trim_inline_images(child, keep_count, state)


def _collect_image_relationship_ids(root: ET.Element) -> set[str]:
    ids = set()
    for node in root.iter():
        rel_id = node.attrib.get(f"{R}id")
        if rel_id:
            ids.add(rel_id)
    return ids


def _ensure_page_break_before(paragraph: ET.Element) -> None:
    ppr = paragraph.find(f"{W}pPr")
    if ppr is None:
        ppr = ET.Element(f"{W}pPr")
        paragraph.insert(0, ppr)
    if ppr.find(f"{W}pageBreakBefore") is None:
        ET.SubElement(ppr, f"{W}pageBreakBefore")


def _photo_urls(source: object) -> list[str]:
    if not source:
        return []
    if isinstance(source, dict):
        url = str(source.get("url") or source.get("remote_url") or source.get("source_url") or "").strip()
    else:
        url = str(source).strip()
    if not url:
        return []
    if url.startswith("/"):
        bases = [
            DIFY_FILE_BASE_URL,
            "http://docker-nginx-1",
            "http://docker-api-1:5001",
            "http://host.docker.internal",
        ]
        candidates: list[str] = []
        seen: set[str] = set()
        for base in bases:
            normalized = base.rstrip("/")
            if normalized and normalized not in seen:
                seen.add(normalized)
                candidates.append(normalized + url)
        return candidates
    return [url]


def _photo_url(source: object) -> str:
    urls = _photo_urls(source)
    return urls[0] if urls else ""


def _jpeg_bytes(data: bytes) -> bytes:
    try:
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="JPEG", quality=92, optimize=True)
            return output.getvalue()
    except Exception:
        return data


def _load_photo_bytes(photos: object) -> list[bytes]:
    if not photos:
        return []
    if isinstance(photos, dict):
        sources = [photos]
    elif isinstance(photos, (list, tuple)):
        sources = list(photos)
    else:
        sources = [photos]

    loaded: list[bytes] = []
    for source in sources[:2]:
        urls = _photo_urls(source)
        if not urls:
            continue
        last_error = None
        for url in urls:
            try:
                local_path = Path(url)
                if not url.startswith(("http://", "https://")) and local_path.exists():
                    data = local_path.read_bytes()
                else:
                    with url_request.urlopen(url, timeout=12) as resp:
                        data = resp.read()
                if data:
                    loaded.append(_jpeg_bytes(data))
                    last_error = None
                    break
            except Exception as exc:
                last_error = exc
        if last_error is not None:
            print(f"photo fetch failed: {last_error}")
    return loaded


def _json_object(value: object) -> dict:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        data = json.loads(str(value))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _connect_dify_db():
    import psycopg2

    kwargs = {
        "host": DIFY_DB_HOST,
        "port": DIFY_DB_PORT,
        "dbname": DIFY_DB_NAME,
        "user": DIFY_DB_USER,
        "connect_timeout": 3,
    }
    if DIFY_DB_PASSWORD:
        kwargs["password"] = DIFY_DB_PASSWORD
    return psycopg2.connect(**kwargs)


def _photo_payloads_from_inputs(inputs: dict) -> list[dict]:
    choice = str(inputs.get("photo_upload_choice") or "").strip()
    if "不上传" in choice:
        return []

    photos: list[dict] = []
    for key in ("check_photo_1", "check_photo_2"):
        value = inputs.get(key)
        if not isinstance(value, dict):
            continue
        if value.get("type") == "image" or value.get("url") or value.get("remote_url"):
            photos.append(value)
    return photos[:2]


def _photos_from_workflow_run(workflow_run_id: object) -> list[dict]:
    run_id = str(workflow_run_id or "").strip()
    if not run_id:
        return []

    conn = None
    try:
        conn = _connect_dify_db()
        with conn.cursor() as cur:
            cur.execute("SELECT inputs FROM workflow_runs WHERE id = %s", (run_id,))
            row = cur.fetchone()
            if row:
                photos = _photo_payloads_from_inputs(_json_object(row[0]))
                if photos:
                    return photos

            cur.execute(
                """
                SELECT inputs
                FROM workflow_node_executions
                WHERE workflow_run_id = %s AND node_type = 'start'
                ORDER BY index ASC, created_at ASC
                LIMIT 1
                """,
                (run_id,),
            )
            row = cur.fetchone()
            if row:
                return _photo_payloads_from_inputs(_json_object(row[0]))
    except Exception as exc:
        print(f"workflow photo lookup failed: {exc}")
    finally:
        if conn is not None:
            conn.close()
    return []


def _extract_check_slots(content: str) -> dict[str, str]:
    lines = _check_content_lines(content)
    slots = dict(CHECK_DEFAULT_SLOT_VALUES)
    if not lines:
        return slots

    agency = lines[0].strip() if lines else ""
    if "公安" in agency and not _line_starts(agency, "时间"):
        slots["agency"] = _space_agency(agency)

    for key, prefixes in {
        "time": ("时间",),
        "place": ("地点",),
        "inspector_1": ("检查人姓名和工作单位",),
        "object": ("检查或者辨认对象",),
        "witness": ("见证人基本情况",),
        "reason": ("事由和目的",),
        "process": ("过程和结果",),
        "footer_unit": ("办案单位",),
        "footer_officers": ("办案人员",),
    }.items():
        line = _first_line(lines, *prefixes)
        if line:
            slots[key] = line

    for key, prefix, exclusions in (
        ("checker_sign", "检查人", ("检查人姓名和工作单位",)),
        ("recorder_sign", "记录人", ()),
        ("party_sign", "当事人", ("当事人/辨认人基本情况",)),
        ("witness_sign", "见证人", ("见证人基本情况",)),
    ):
        for line in lines:
            if _line_starts(line, prefix) and not any(_line_starts(line, item) for item in exclusions):
                slots[key] = line.strip()
                break

    time_footer = ""
    for line in lines:
        if _compact_for_match(line).startswith("时间") and line != slots.get("time"):
            time_footer = line.strip()
    if time_footer:
        slots["footer_date"] = time_footer

    heading_idx = -1
    for index, line in enumerate(lines):
        if _line_starts(line, "当事人/辨认人基本情况"):
            heading_idx = index
            slots["party_heading"] = line.strip()
            break
    if heading_idx >= 0 and heading_idx + 1 < len(lines):
        next_line = lines[heading_idx + 1].strip()
        if not any(_line_starts(next_line, prefix) for prefix in ("见证人基本情况", "事由和目的", "过程和结果")):
            slots["party_basic"] = next_line

    inspector_idx = -1
    for index, line in enumerate(lines):
        if _line_starts(line, "检查人姓名和工作单位"):
            inspector_idx = index
            break
    if inspector_idx >= 0 and inspector_idx + 1 < len(lines):
        next_line = lines[inspector_idx + 1]
        if not any(_line_starts(next_line, prefix) for prefix in ("检查或者辨认对象", "当事人", "见证人")):
            slots["inspector_2"] = next_line

    return slots


def build_check_record_docx(content: str, photos: object = None) -> bytes:
    photo_bytes = _load_photo_bytes(photos)
    with zipfile.ZipFile(CHECK_TEMPLATE_PATH, "r") as template:
        root = ET.fromstring(template.read("word/document.xml"))
        body = root.find(f"{W}body")
        if body is None:
            return build_simple_docx(content)

        paragraphs = [node for node in list(body) if node.tag == f"{W}p"]
        if len(paragraphs) > 16:
            _ensure_page_break_before(paragraphs[16])
        if photo_bytes:
            _trim_inline_images(root, len(photo_bytes))
        else:
            _remove_inline_images(root)

        slots = _extract_check_slots(content)
        mapping = {
            0: "agency",
            1: "title",
            2: "time",
            3: "place",
            4: "inspector_1",
            5: "inspector_2",
            6: "object",
            7: "party_heading",
            8: "party_basic",
            9: "witness",
            10: "reason",
            11: "process",
            12: "checker_sign",
            13: "recorder_sign",
            14: "party_sign",
            15: "witness_sign",
            16: "photo_title",
            31: "footer_unit",
            32: "footer_officers",
            33: "footer_date",
        }
        for index, slot in mapping.items():
            if index < len(paragraphs):
                _set_paragraph_text(paragraphs[index], slots.get(slot, ""))

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        keep_image_ids = _collect_image_relationship_ids(root)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
            for item in template.infolist():
                if item.filename == "word/document.xml":
                    output.writestr(item, document_xml)
                elif item.filename == "word/_rels/document.xml.rels":
                    if photo_bytes:
                        output.writestr(item, _filter_image_relationships(template.read(item.filename), keep_image_ids))
                    else:
                        output.writestr(item, _strip_image_relationships(template.read(item.filename)))
                elif item.filename.startswith("word/media/"):
                    if item.filename.endswith("image1.jpeg") and len(photo_bytes) >= 1:
                        output.writestr(item, photo_bytes[0])
                    elif item.filename.endswith("image2.jpeg") and len(photo_bytes) >= 2:
                        output.writestr(item, photo_bytes[1])
                    elif photo_bytes:
                        continue
                    else:
                        continue
                else:
                    output.writestr(item, template.read(item.filename))
        return buffer.getvalue()


def _extract_identification_slots(content: str) -> dict[str, str]:
    lines = _check_content_lines(content)
    slots = dict(IDENTIFICATION_DEFAULT_SLOT_VALUES)
    if not lines:
        return slots

    for key, prefixes in {
        "time": ("时间",),
        "place": ("地点",),
        "officers": ("办案人员姓名、单位",),
        "identifier": ("辨认人姓名",),
        "witness": ("见证人姓名、单位",),
        "object": ("辨认对象",),
        "purpose": ("辨认目的",),
        "process_heading": ("辨认过程及结果",),
    }.items():
        line = _first_line(lines, *prefixes)
        if line:
            slots[key] = line

    process_idx = -1
    for index, line in enumerate(lines):
        if _line_starts(line, "辨认过程及结果"):
            process_idx = index
            break
    if process_idx >= 0:
        process_parts: list[str] = []
        for line in lines[process_idx + 1 :]:
            if _line_starts(line, "辨认人") and "指出" in line:
                break
            if _line_starts(line, "辨认照片") or _line_starts(line, "至此") or _line_starts(line, "办案人员"):
                break
            process_parts.append(line.strip())
        if process_parts:
            slots["process"] = "    " + "".join(process_parts).strip()

    review = ""
    for line in lines:
        if _line_starts(line, "辨认人") and "指出" in line:
            review = line.strip()
            break
    if review:
        slots["review"] = review

    result_lines = [
        line.strip()
        for line in lines
        if _line_starts(line, "辨认照片") or re.search(r"照片.*[（(]\d+[）)].*就是", line)
    ]
    for index, line in enumerate(result_lines[:5], start=1):
        slots[f"result_{index}"] = line

    line = _first_line(lines, "至此")
    if line:
        slots["end"] = line
    for line in lines:
        if _line_starts(line, "办案人员") and not _line_starts(line, "办案人员姓名"):
            slots["sign_officers"] = line
            break
    for line in lines:
        if _line_starts(line, "见证人") and not _line_starts(line, "见证人姓名"):
            slots["sign_people"] = line
            break
    return slots


def build_identification_record_docx(content: str) -> bytes:
    with zipfile.ZipFile(IDENTIFICATION_TEMPLATE_PATH, "r") as template:
        root = ET.fromstring(template.read("word/document.xml"))
        body = root.find(f"{W}body")
        if body is None:
            return build_simple_docx(content)

        paragraphs = [node for node in list(body) if node.tag == f"{W}p"]
        slots = _extract_identification_slots(content)
        mapping = {
            0: "title",
            1: "time",
            2: "place",
            3: "officers",
            4: "identifier",
            5: "witness",
            6: "object",
            7: "purpose",
            8: "process_heading",
            9: "process",
            10: "review",
            11: "result_1",
            12: "result_2",
            13: "result_3",
            14: "result_4",
            15: "result_5",
            18: "end",
            19: "sign_officers",
            20: "sign_people",
        }
        for index, slot in mapping.items():
            if index < len(paragraphs):
                _set_paragraph_text(paragraphs[index], slots.get(slot, ""))

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
            for item in template.infolist():
                if item.filename == "word/document.xml":
                    output.writestr(item, document_xml)
                else:
                    output.writestr(item, template.read(item.filename))
        return buffer.getvalue()


def build_template_docx(content: str) -> bytes:
    with zipfile.ZipFile(TEMPLATE_PATH, "r") as template:
        root = ET.fromstring(template.read("word/document.xml"))
        body = root.find(f"{W}body")
        if body is None:
            return build_simple_docx(content)

        paragraphs = [node for node in list(body) if node.tag == f"{W}p"]
        non_empty_indexes = [
            index for index, paragraph in enumerate(paragraphs) if _text_of_paragraph(paragraph).strip()
        ]
        slots = _extract_slots(content)
        values = [slots.get(slot, "") for slot in SLOT_ORDER]

        for index, value in zip(non_empty_indexes, values):
            _set_paragraph_text(paragraphs[index], value)
        for index in non_empty_indexes[len(values):]:
            _set_paragraph_text(paragraphs[index], "")

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
            for item in template.infolist():
                if item.filename == "word/document.xml":
                    output.writestr(item, document_xml)
                else:
                    output.writestr(item, template.read(item.filename))
        return buffer.getvalue()


def _extract_criminal_record_slots(content: str) -> dict[str, str]:
    lines = [
        line.strip()
        for line in str(content or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if line.strip()
    ]
    slots = dict(CRIMINAL_RECORD_DEFAULT_SLOT_VALUES)
    if not lines:
        return slots

    if len(lines) >= 1 and "前科证明" in lines[0]:
        slots["title"] = lines[0]

    for line in lines:
        if "身份证件种类及号码" in line or ("性别" in line and "出生日期" in line):
            slots["party"] = line
            continue
        if "未发现" in line and "违法犯罪记录" in line:
            slots["query_result"] = line
            continue
        if line.startswith("特此证明"):
            slots["statement"] = line
            continue
        if "公安" in line and ("派出所" in line or "公安局" in line):
            slots["agency"] = line
            continue
        if re.fullmatch(r"\d{4}年\d{1,2}月\d{1,2}日", line):
            match = re.fullmatch(r"(\d{4})年(\d{1,2})月(\d{1,2})日", line)
            if match:
                year, month, day = match.groups()
                slots["issue_date"] = f"{int(year):04d}年{int(month):02d}月{int(day):02d}日"
            else:
                slots["issue_date"] = line
    return slots


def build_criminal_record_docx(content: str) -> bytes:
    with zipfile.ZipFile(CRIMINAL_RECORD_TEMPLATE_PATH, "r") as template:
        root = ET.fromstring(template.read("word/document.xml"))
        body = root.find(f"{W}body")
        if body is None:
            return build_simple_docx(content)

        paragraphs = [node for node in list(body) if node.tag == f"{W}p"]
        non_empty_indexes = [
            index for index, paragraph in enumerate(paragraphs) if _text_of_paragraph(paragraph).strip()
        ]
        slots = _extract_criminal_record_slots(content)
        values = [
            slots["title"],
            slots["party"],
            slots["query_result"],
            slots["statement"],
            slots["agency"],
            slots["issue_date"],
        ]

        for index, value in zip(non_empty_indexes, values):
            _set_paragraph_text(paragraphs[index], value)

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
            for item in template.infolist():
                if item.filename == "word/document.xml":
                    output.writestr(item, document_xml)
                else:
                    output.writestr(item, template.read(item.filename))
        return buffer.getvalue()


def _parse_elements_payload(value: object) -> dict:
    if isinstance(value, dict):
        data = value
    else:
        text = str(value or "").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
        except Exception:
            return {}
    if isinstance(data, dict) and isinstance(data.get("elements"), dict):
        return data.get("elements") or {}
    return data if isinstance(data, dict) else {}


def _entry_first(elements: dict, *keys: str, default: str = "") -> str:
    for key in keys:
        value = elements.get(key)
        if isinstance(value, (list, tuple)):
            value = "、".join(str(item).strip() for item in value if str(item).strip())
        text = str(value or "").strip()
        if text and text.lower() not in {"null", "none"}:
            return text
    return default


def _entry_parse_date(value: object) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("：", ":")
    patterns = (
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        r"(\d{4})[./-](\d{1,2})[./-](\d{1,2})",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year, month, day = (int(part) for part in match.groups())
            try:
                return date(year, month, day)
            except ValueError:
                return None
    return None


def _entry_birth_from_id(id_number: str) -> date | None:
    id_number = re.sub(r"\s+", "", str(id_number or ""))
    match = re.match(r"^\d{6}(\d{4})(\d{2})(\d{2})", id_number)
    if match:
        year, month, day = (int(part) for part in match.groups())
        try:
            return date(year, month, day)
        except ValueError:
            return None
    match = re.match(r"^\d{6}(\d{2})(\d{2})(\d{2})", id_number)
    if match:
        year, month, day = (int(part) for part in match.groups())
        year += 1900 if year >= 30 else 2000
        try:
            return date(year, month, day)
        except ValueError:
            return None
    return None


def _entry_clean_age(value: str) -> str:
    match = re.search(r"\d{1,3}", str(value or ""))
    return match.group(0) if match else ""


def _entry_age(birth: date | None, at_date: date | None) -> str:
    if not birth:
        return ""
    at_date = at_date or date.today()
    age = at_date.year - birth.year - ((at_date.month, at_date.day) < (birth.month, birth.day))
    return str(max(age, 0))


def _entry_strip_violation(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\s\"“”'\[\]{}]+", "", text)
    text = re.sub(r"^(涉嫌|构成|违法行为名称|罪名|案由)[:：]?", "", text)
    for suffix in ("违法行为", "行政违法行为", "行政违法", "行为"):
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[: -len(suffix)]
    return text.strip("：:;；，,。 ")


def _entry_chinese_date(value: date | None) -> str:
    if not value:
        return ""
    return f"{value.year}年{value.month:02d}月{value.day:02d}日"


def _entry_spaced_date(value: date | None, double_space: bool = False) -> str:
    if not value:
        return ""
    if double_space:
        return f"{value.year}年  {value.month}月  {value.day} 日"
    return f"{value.year}年 {value.month} 月 {value.day} 日"


def _entry_iso_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def _entry_dot_date(value: date | None) -> str:
    return f"{value.year:04d}.{value.month:02d}.{value.day:02d}" if value else ""


def _entry_decision_agency(elements: dict, sending_unit: str) -> str:
    agency = _entry_first(elements, "decision_agency", "detention_decision_agency", "police_station", "agency")
    if agency:
        return agency
    match = re.search(r"(.+?公安局)", sending_unit or "")
    return match.group(1) if match else sending_unit


def _entry_case_name(elements: dict, case_date: date | None, violation: str) -> str:
    case_name = _entry_first(elements, "case_name", "case_title")
    if case_name:
        return case_name
    if case_date and violation:
        return f"{_entry_dot_date(case_date)}{violation}案"
    return violation + "案" if violation else ""


def _entry_fact(elements: dict, entry_date: date | None, case_date: date | None, violation: str) -> str:
    fact = _entry_first(elements, "entry_fact", "illegal_fact", "case_fact", "fact")
    if fact:
        return fact
    location = _entry_first(elements, "case_location", "incident_location", "inspection_location")
    event_date = case_date or entry_date
    when = _entry_chinese_date(event_date) if event_date else ""
    if when or location or violation:
        return f"我所民警在工作中发现：{when}00时00分左右，在{location}，有人涉嫌{violation}。"
    return ""


def _entry_text_chunks(text: str, widths: list[int]) -> list[str]:
    text = str(text or "").strip()
    chunks: list[str] = []
    cursor = 0
    for width in widths:
        if cursor >= len(text):
            chunks.append("")
            continue
        chunks.append(text[cursor : cursor + width])
        cursor += width
    if cursor < len(text):
        if chunks:
            chunks[-1] += text[cursor:]
        else:
            chunks.append(text[cursor:])
    return chunks


def _entry_replacement_data(elements: dict) -> dict[str, str]:
    id_number = _entry_first(elements, "party_id_number", "id_number", "person_id_number")
    entry_date = _entry_parse_date(_entry_first(
        elements,
        "entry_date",
        "detention_date",
        "custody_date",
        "case_date",
        "inspection_time_start",
    ))
    case_date = _entry_parse_date(_entry_first(elements, "case_date", "incident_date", "illegal_time", "entry_date"))
    birth = _entry_parse_date(_entry_first(elements, "birth_date", "birthday")) or _entry_birth_from_id(id_number)
    age = _entry_clean_age(_entry_first(elements, "party_age", "age")) or _entry_age(birth, entry_date)
    violation = _entry_strip_violation(_entry_first(elements, "violation_type", "case_nature", "suspected_charge"))
    sending_unit = _entry_first(
        elements,
        "sending_unit",
        "escort_unit",
        "detention_unit",
        "handling_unit",
        "police_station",
    )
    education = _entry_first(elements, "education", "education_level")
    education_culture = education if not education or education.endswith("文化") else education + "文化"
    address = _entry_first(elements, "party_address", "residence_address", "current_address", "address")
    household_detail = _entry_first(elements, "household_register_detail", "household_register", "registered_address", default=address)
    district = _entry_first(elements, "residence_district", "district", "native_place")
    native_place = _entry_first(elements, "native_place", "birth_place", "household_register")
    if not district and address:
        district = re.sub(r"([县区市]).*$", r"\1", address)
    if not native_place:
        native_place = district
    case_name = _entry_case_name(elements, case_date or entry_date, violation)
    fact = _entry_fact(elements, entry_date, case_date, violation)
    fact_lines = _entry_text_chunks(fact, [24, 18, 28])
    case_lines = _entry_text_chunks(case_name, [13, 28])
    return {
        "name": _entry_first(elements, "party_name", "person_name", "checked_person_name", "identifier_name"),
        "id_number": id_number,
        "gender": _entry_first(elements, "party_gender", "person_gender", "gender"),
        "age": age,
        "age_with_suffix": age + "岁" if age else "",
        "birth_iso": _entry_iso_date(birth),
        "birth_dot": _entry_dot_date(birth),
        "education": education,
        "education_culture": education_culture,
        "ethnicity": _entry_first(elements, "ethnicity", "nation", "nationality"),
        "marital_status": _entry_first(elements, "marital_status", "marriage"),
        "political_status": _entry_first(elements, "political_status", default="群众"),
        "religion": _entry_first(elements, "religion", default="无"),
        "alias": _entry_first(elements, "alias", "nickname", default="无"),
        "former_name": _entry_first(elements, "former_name", default="无"),
        "accent": _entry_first(elements, "accent", default="外地"),
        "country": _entry_first(elements, "country", "nationality_region", default="中华人民共和国"),
        "native_place": native_place,
        "household_register": _entry_first(elements, "household_register", "registered_area", default=native_place),
        "household_detail": household_detail,
        "residence_district": district,
        "address": address,
        "occupation": _entry_first(elements, "occupation", "job", default="无"),
        "work_unit": _entry_first(elements, "work_unit", "workplace", default="无"),
        "criminal_record": _entry_first(elements, "criminal_record", "previous_record", default="无"),
        "entry_iso": _entry_iso_date(entry_date),
        "entry_health_date": f"{entry_date.year}年 {entry_date.month:02d}月{entry_date.day:02d}日" if entry_date else "",
        "entry_spaced": _entry_spaced_date(entry_date, double_space=True),
        "start_spaced": _entry_spaced_date(entry_date),
        "sending_unit": sending_unit,
        "escort_officers": _entry_first(elements, "escort_officers", "escort_persons", "officer_name", "handling_officers"),
        "escort_phone": _entry_first(elements, "escort_phone", "contact_phone", "phone"),
        "detention_type": _entry_first(elements, "detention_type", "custody_type", default="行政拘留"),
        "detention_period": _entry_first(elements, "detention_period", "detention_days"),
        "decision_agency": _entry_decision_agency(elements, sending_unit),
        "case_name": case_name,
        "case_line_1": case_lines[0] if case_lines else "",
        "case_line_2": case_lines[1] if len(case_lines) > 1 else "",
        "fact_line_1": fact_lines[0] if fact_lines else "",
        "fact_line_2": fact_lines[1] if len(fact_lines) > 1 else "",
        "fact_line_3": fact_lines[2] if len(fact_lines) > 2 else "",
    }


def _entry_replace_exact(paragraphs: list[ET.Element], replacements: dict[str, str]) -> None:
    for paragraph in paragraphs:
        text = _text_of_paragraph(paragraph)
        if text in replacements:
            _set_paragraph_text(paragraph, replacements[text])


def _entry_replace_sequence(paragraphs: list[ET.Element], old_lines: list[str], new_lines: list[str]) -> None:
    if not old_lines:
        return
    texts = [_text_of_paragraph(paragraph) for paragraph in paragraphs]
    for index in range(0, len(texts) - len(old_lines) + 1):
        if texts[index : index + len(old_lines)] == old_lines:
            for offset, line in enumerate(new_lines[: len(old_lines)]):
                _set_paragraph_text(paragraphs[index + offset], line)
            for offset in range(len(new_lines), len(old_lines)):
                _set_paragraph_text(paragraphs[index + offset], "")
            return


def _entry_replace_prefix(paragraphs: list[ET.Element], prefix: str, value: str) -> None:
    for paragraph in paragraphs:
        text = _text_of_paragraph(paragraph)
        if text.startswith(prefix):
            _set_paragraph_text(paragraph, value)
            return


def _build_entry_materials_docx(template_path: Path, data: dict[str, str]) -> bytes:
    filename = template_path.name
    with zipfile.ZipFile(template_path, "r") as template:
        root = ET.fromstring(template.read("word/document.xml"))
        paragraphs = root.findall(f".//{W}p")

        common = {
            "罗上倍": data["name"],
            "45262920010424151X": data["id_number"],
            "男": data["gender"],
            "    男": "    " + data["gender"] if data["gender"] else "",
            "壮": data["ethnicity"],
            "未婚": data["marital_status"],
            "      未婚": "      " + data["marital_status"] if data["marital_status"] else "",
            "大专": data["education"],
            "大专文化": data["education_culture"],
            "24": data["age"],
            "24岁": data["age_with_suffix"],
            "2001-04-24": data["birth_iso"],
            "1973.10.24": data["birth_dot"],
            "藤县公安局埌南派出所": data["sending_unit"],
            "何飞运、罗积鑫": data["escort_officers"],
            "0774-7185136": data["escort_phone"],
            "行政拘留": data["detention_type"],
            "2026.05.21扰乱公共场所秩序案": data["case_name"],
            "藤县公安局": data["decision_agency"],
            "广西乐业县": data["native_place"],
            "广西乐业县雅长乡新场村岜岩屯二组140号": data["address"],
            "群众": data["political_status"],
            "外地": data["accent"],
            "中华人民共和国": data["country"],
        }

        if "入所健康检查表" in filename:
            _entry_replace_prefix(
                paragraphs,
                "                检查日期",
                "                检查日期  " + data["entry_health_date"],
            )
        elif "病历档案首页" in filename:
            common["2026-05-22"] = data["entry_iso"]
        elif "矛盾化解纠纷排查表" in filename:
            _entry_replace_prefix(paragraphs, "入所时间:", "入所时间:" + data["entry_iso"])
            _entry_replace_sequence(
                paragraphs,
                ["2026.05.21扰乱", "公共场所秩序案"],
                [data["case_line_1"], data["case_line_2"]],
            )
        elif "信息卡" in filename or "入所登记表" in filename:
            common.update({
                "无": "无",
                "2026年  5月  22 日": data["entry_spaced"],
                "2026年 5 月 22 日": data["start_spaced"],
            })
            _entry_replace_sequence(
                paragraphs,
                [
                    "我所民警在工作中发现：2026年05月22日",
                    "00时00分左右，在广西藤县藤州镇东山路",
                    "维也纳酒店，有人涉嫌扰乱公共场所秩序。",
                ],
                [data["fact_line_1"], data["fact_line_2"], data["fact_line_3"]],
            )

        _entry_replace_exact(paragraphs, common)

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
            for item in template.infolist():
                if item.filename == "word/document.xml":
                    output.writestr(item, document_xml)
                else:
                    output.writestr(item, template.read(item.filename))
        return buffer.getvalue()


def _extract_search_record_slots(content: str) -> dict[str, str]:
    lines = _check_content_lines(content)
    slots = dict(SEARCH_RECORD_DEFAULT_SLOT_VALUES)
    if not lines:
        return slots

    for key, prefixes in {
        "time": ("时间",),
        "location": ("搜查地点",),
        "officers": ("搜查人员姓名、单位",),
        "party": ("当事人姓名",),
        "object": ("被搜查对象",),
        "basis": ("根据",),
        "process_1": ("过程和结果",),
        "photo_caption": ("照片说明", "经搜查发现"),
        "footer": ("办案单位",),
    }.items():
        line = _first_line(lines, *prefixes)
        if line:
            slots[key] = line

    for key, prefix, exclusions in (
        ("sign_officers", "侦查人员", ()),
        ("sign_party", "当事人", ("当事人姓名",)),
    ):
        for line in lines:
            if _line_starts(line, prefix) and not any(_line_starts(line, item) for item in exclusions):
                slots[key] = line.strip()
                break

    return slots


def build_search_record_docx(content: str, photos: object = None) -> bytes:
    photo_bytes = _load_photo_bytes(photos)
    with zipfile.ZipFile(SEARCH_RECORD_TEMPLATE_PATH, "r") as template:
        root = ET.fromstring(template.read("word/document.xml"))
        body = root.find(f"{W}body")
        if body is None:
            return build_simple_docx(content)

        paragraphs = [node for node in list(body) if node.tag == f"{W}p"]
        if photo_bytes:
            _trim_inline_images(root, len(photo_bytes))
        else:
            _remove_inline_images(root)

        slots = _extract_search_record_slots(content)
        mapping = {
            0: "title",
            1: "time",
            2: "location",
            3: "officers",
            4: "party",
            5: "object",
            6: "basis",
            7: "process_1",
            8: "process_2",
            9: "process_3",
            10: "sign_officers",
            11: "sign_party",
            13: "photo_title",
            16: "photo_caption",
            25: "footer",
        }
        for index, slot in mapping.items():
            if index < len(paragraphs):
                _set_paragraph_text(paragraphs[index], slots.get(slot, ""))

        document_xml = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        keep_image_ids = _collect_image_relationship_ids(root)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
            for item in template.infolist():
                if item.filename == "word/document.xml":
                    output.writestr(item, document_xml)
                elif item.filename == "word/_rels/document.xml.rels":
                    if photo_bytes:
                        output.writestr(item, _filter_image_relationships(template.read(item.filename), keep_image_ids))
                    else:
                        output.writestr(item, _strip_image_relationships(template.read(item.filename)))
                elif item.filename.startswith("word/media/"):
                    if item.filename.endswith("image1.jpeg") and len(photo_bytes) >= 1:
                        output.writestr(item, photo_bytes[0])
                    elif item.filename.endswith("image2.jpeg") and len(photo_bytes) >= 2:
                        output.writestr(item, photo_bytes[1])
                    elif photo_bytes:
                        continue
                    else:
                        continue
                else:
                    output.writestr(item, template.read(item.filename))
        return buffer.getvalue()


def build_entry_materials_zip(elements: object) -> bytes:
    data = _entry_replacement_data(_parse_elements_payload(elements))
    missing = [name for name in ENTRY_MATERIALS_FILENAMES if not (ENTRY_MATERIALS_TEMPLATE_DIR / name).exists()]
    if missing:
        raise FileNotFoundError("missing entry materials templates: " + ", ".join(missing))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as output:
        for filename in ENTRY_MATERIALS_FILENAMES:
            path = ENTRY_MATERIALS_TEMPLATE_DIR / filename
            if any(marker in filename for marker in ENTRY_MATERIALS_DIRECT_COPY):
                data_bytes = path.read_bytes()
            else:
                data_bytes = _build_entry_materials_docx(path, data)
            output.writestr(filename, data_bytes)
    return buffer.getvalue()


def build_docx(content: str, doc_type: str = "", photos: object = None) -> bytes:
    if "检查笔录" in str(doc_type or "") and CHECK_TEMPLATE_PATH.exists():
        try:
            return build_check_record_docx(content, photos)
        except Exception as exc:
            print(f"check record template export failed: {exc}")

    if "辨认笔录" in str(doc_type or "") and IDENTIFICATION_TEMPLATE_PATH.exists():
        try:
            return build_identification_record_docx(content)
        except Exception as exc:
            print(f"identification record template export failed: {exc}")

    if "前科" in str(doc_type or "") and CRIMINAL_RECORD_TEMPLATE_PATH.exists():
        try:
            return build_criminal_record_docx(content)
        except Exception as exc:
            print(f"criminal record template export failed: {exc}")

    if "搜查" in str(doc_type or "") and SEARCH_RECORD_TEMPLATE_PATH.exists():
        try:
            return build_search_record_docx(content, photos)
        except Exception as exc:
            print(f"search record template export failed: {exc}")

    if TEMPLATE_PATH.exists():
        try:
            return build_template_docx(content)
        except Exception as exc:
            print(f"template export failed: {exc}")
    return build_simple_docx(content)


def _safe_filename(value: str | None, extension: str = ".docx") -> str:
    extension = extension if extension.startswith(".") else "." + extension
    base = re.sub(r"[^A-Za-z0-9_.-]+", "-", value or "").strip(".-")
    if not base:
        base = f"document-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    if not base.lower().endswith(extension.lower()):
        base = re.sub(r"\.(docx|zip)$", "", base, flags=re.IGNORECASE)
        base += extension
    if len(base) > 120:
        base = base[: 120 - len(extension)].rstrip(".-") + extension
    return base


class Handler(BaseHTTPRequestHandler):
    server_version = "WordExport/1.0"

    def _send_json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, status: int, message: str) -> None:
        self._send_json(status, {"error": message})

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        if not parsed.path.startswith("/downloads/"):
            self._send_error(404, "not found")
            return

        name = unquote(parsed.path.removeprefix("/downloads/"))
        lower_name = name.lower()
        if "/" in name or "\\" in name or not lower_name.endswith((".docx", ".zip")):
            self._send_error(400, "invalid filename")
            return

        file_path = (OUTPUT_DIR / name).resolve()
        if OUTPUT_DIR not in file_path.parents or not file_path.exists():
            self._send_error(404, "file not found")
            return

        data = file_path.read_bytes()
        self.send_response(200)
        if lower_name.endswith(".zip"):
            content_type = "application/zip"
        else:
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/export-word":
            self._send_error(404, "not found")
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except Exception:
            self._send_error(400, "invalid json")
            return

        content = str(payload.get("content") or payload.get("input_text") or "").strip()
        if not content:
            self._send_error(400, "content is required")
            return
        doc_type = str(payload.get("doc_type") or payload.get("document_type") or "").strip()
        photos = payload.get("photos") or payload.get("images") or []
        workflow_run_id = payload.get("workflow_run_id") or payload.get("run_id") or ""
        if not photos and ("检查" in doc_type or "搜查" in doc_type) and workflow_run_id:
            photos = _photos_from_workflow_run(workflow_run_id)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        is_entry_materials = "入所" in doc_type
        extension = ".zip" if is_entry_materials else ".docx"
        filename = _safe_filename(payload.get("filename"), extension=extension)
        file_path = OUTPUT_DIR / filename
        if file_path.exists():
            filename = _safe_filename(f"{file_path.stem}-{uuid.uuid4().hex[:8]}{extension}", extension=extension)
            file_path = OUTPUT_DIR / filename

        if is_entry_materials:
            file_path.write_bytes(build_entry_materials_zip(payload.get("elements") or payload.get("data") or content))
            label = "下载入所材料"
        else:
            file_path.write_bytes(build_docx(content, doc_type, photos))
            label = "下载Word文档"
        url = f"{PUBLIC_BASE_URL.rstrip('/')}/downloads/{filename}"
        self._send_json(200, {"url": url, "markdown": f"[{label}]({url})"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Word export service listening on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
