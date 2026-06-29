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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib import request as url_request
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET


PORT = int(os.environ.get("WORD_EXPORT_PORT", "8123"))
PUBLIC_BASE_URL = os.environ.get("WORD_EXPORT_PUBLIC_BASE_URL", f"http://localhost:{PORT}")
DIFY_FILE_BASE_URL = os.environ.get("DIFY_FILE_BASE_URL", "http://host.docker.internal")
OUTPUT_DIR = Path(os.environ.get("WORD_EXPORT_OUTPUT_DIR", "outputs/word_exports")).resolve()
TEMPLATE_PATH = Path(os.environ.get("WORD_EXPORT_TEMPLATE", "work/reference_layout.docx")).resolve()
CHECK_TEMPLATE_PATH = Path(os.environ.get("WORD_EXPORT_CHECK_TEMPLATE", "work/check_record_template.docx")).resolve()

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
XML_NS = "http://www.w3.org/XML/1998/namespace"
W = f"{{{W_NS}}}"
R = f"{{{R_NS}}}"
XML = f"{{{XML_NS}}}"

ET.register_namespace("w", W_NS)
ET.register_namespace("r", R_NS)
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


def _remove_inline_images(node: ET.Element) -> None:
    image_tags = {f"{W}pict", f"{W}drawing", f"{W}object"}
    for child in list(node):
        if child.tag in image_tags:
            node.remove(child)
        else:
            _remove_inline_images(child)


def _trim_inline_images(node: ET.Element, keep_count: int, state: dict[str, int] | None = None) -> None:
    if state is None:
        state = {"seen": 0}
    image_tags = {f"{W}pict", f"{W}drawing", f"{W}object"}
    for child in list(node):
        if child.tag in image_tags:
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


def _photo_url(source: object) -> str:
    if not source:
        return ""
    if isinstance(source, dict):
        url = str(source.get("url") or source.get("remote_url") or source.get("source_url") or "").strip()
    else:
        url = str(source).strip()
    if not url:
        return ""
    if url.startswith("/"):
        return DIFY_FILE_BASE_URL.rstrip("/") + url
    return url


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
        url = _photo_url(source)
        if not url:
            continue
        try:
            local_path = Path(url)
            if not url.startswith(("http://", "https://")) and local_path.exists():
                data = local_path.read_bytes()
            else:
                with url_request.urlopen(url, timeout=20) as resp:
                    data = resp.read()
            if data:
                loaded.append(_jpeg_bytes(data))
        except Exception as exc:
            print(f"photo fetch failed: {exc}")
    return loaded


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


def build_docx(content: str, doc_type: str = "", photos: object = None) -> bytes:
    if "检查笔录" in str(doc_type or "") and CHECK_TEMPLATE_PATH.exists():
        try:
            return build_check_record_docx(content, photos)
        except Exception as exc:
            print(f"check record template export failed: {exc}")

    if TEMPLATE_PATH.exists():
        try:
            return build_template_docx(content)
        except Exception as exc:
            print(f"template export failed: {exc}")
    return build_simple_docx(content)


def _safe_filename(value: str | None) -> str:
    base = re.sub(r"[^A-Za-z0-9_.-]+", "-", value or "").strip(".-")
    if not base:
        base = f"document-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    if not base.lower().endswith(".docx"):
        base += ".docx"
    return base[:120]


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
        if "/" in name or "\\" in name or not name.lower().endswith(".docx"):
            self._send_error(400, "invalid filename")
            return

        file_path = (OUTPUT_DIR / name).resolve()
        if OUTPUT_DIR not in file_path.parents or not file_path.exists():
            self._send_error(404, "file not found")
            return

        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
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

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = _safe_filename(payload.get("filename"))
        file_path = OUTPUT_DIR / filename
        if file_path.exists():
            filename = _safe_filename(f"{file_path.stem}-{uuid.uuid4().hex[:8]}.docx")
            file_path = OUTPUT_DIR / filename

        file_path.write_bytes(build_docx(content, doc_type, photos))
        url = f"{PUBLIC_BASE_URL.rstrip('/')}/downloads/{filename}"
        self._send_json(200, {"url": url, "markdown": f"[下载Word文档]({url})"})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Word export service listening on http://localhost:{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()
