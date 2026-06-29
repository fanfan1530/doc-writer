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
from urllib.parse import unquote, urlparse
from xml.etree import ElementTree as ET


PORT = int(os.environ.get("WORD_EXPORT_PORT", "8123"))
PUBLIC_BASE_URL = os.environ.get("WORD_EXPORT_PUBLIC_BASE_URL", f"http://localhost:{PORT}")
OUTPUT_DIR = Path(os.environ.get("WORD_EXPORT_OUTPUT_DIR", "outputs/word_exports")).resolve()
TEMPLATE_PATH = Path(os.environ.get("WORD_EXPORT_TEMPLATE", "work/reference_layout.docx")).resolve()

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


def build_docx(content: str) -> bytes:
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

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filename = _safe_filename(payload.get("filename"))
        file_path = OUTPUT_DIR / filename
        if file_path.exists():
            filename = _safe_filename(f"{file_path.stem}-{uuid.uuid4().hex[:8]}.docx")
            file_path = OUTPUT_DIR / filename

        file_path.write_bytes(build_docx(content))
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
