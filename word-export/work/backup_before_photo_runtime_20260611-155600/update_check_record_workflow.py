import json
import subprocess


APP_ID = "d531fa3c-7ad9-44ae-8c50-d6e58a69dd18"


def psql(sql: str) -> str:
    proc = subprocess.run(
        [
            "docker",
            "exec",
            "-i",
            "docker-db_postgres-1",
            "psql",
            "-U",
            "postgres",
            "-d",
            "dify",
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
        ],
        input=sql.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if proc.returncode:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="replace"))
    return proc.stdout.decode("utf-8", errors="replace")


def find_node(graph: dict, node_id: str) -> dict:
    for node in graph["nodes"]:
        if node.get("id") == node_id:
            return node
    raise KeyError(node_id)


CODE_FILL = r'''
import json
import re
from datetime import date, datetime


def _strip_noise(text: str) -> str:
    text = text or ''
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    text = re.sub(r'```\w*\n?', '', text)
    return text.strip()


def _extract_json_block(text: str):
    text = _strip_noise(text)
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        text = text[start:end + 1]
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)
    return json.loads(text)


def _clean_content(text: str) -> str:
    text = _strip_noise(text).replace('\r\n', '\n').replace('\r', '\n')
    cleaned = []
    for line in text.split('\n'):
        line = re.sub(r'[ \t]+', ' ', line).strip()
        if not line:
            continue
        if cleaned and cleaned[-1] == line:
            continue
        cleaned.append(line)
    return '\n\n'.join(cleaned).strip()


def _trim_final_punct(value) -> str:
    text = str(value or '').strip()
    text = re.sub(r'[\s\u3002\uff1b;\uff0c,\u3001]+$', '', text)
    return text


def _first(*values) -> str:
    for value in values:
        if isinstance(value, (list, tuple)):
            value = '、'.join(str(item) for item in value if item)
        text = str(value or '').strip()
        if text and text.lower() not in ('null', 'none'):
            return text
    return ''


def _normalize_datetime(value) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    text = text.replace('：', ':')
    match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日\s*(\d{1,2})\s*时\s*(\d{1,2})?\s*分?', text)
    if match:
        year, month, day, hour, minute = match.groups()
        minute = minute or '00'
        return f'{int(year):04d}年{int(month):02d}月{int(day):02d}日{int(hour):02d}时{int(minute):02d}分'
    match = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})日?\s*(\d{1,2})?[:时]?(\d{1,2})?', text)
    if match:
        year, month, day, hour, minute = match.groups()
        if hour:
            minute = minute or '00'
            return f'{int(year):04d}年{int(month):02d}月{int(day):02d}日{int(hour):02d}时{int(minute):02d}分'
        return f'{int(year):04d}年{int(month):02d}月{int(day):02d}日'
    return text


def _footer_date(value) -> str:
    text = _normalize_datetime(value)
    match = re.search(r'(\d{4})年0?(\d{1,2})月0?(\d{1,2})日', text)
    if match:
        year, month, day = match.groups()
        return f'{int(year):04d}  年 {int(month)} 月{int(day)}日'
    return text


def _normalize_doc_type(selected: str, classified: str) -> str:
    text = str(selected or '').strip() or str(classified or '').strip()
    if '检查' in text:
        return '检查笔录'
    if '处罚' in text:
        return '行政处罚决定书'
    return '行政处罚决定书'


def _space_agency(value: str) -> str:
    text = re.sub(r'\s+', '', str(value or '').strip())
    if not text:
        text = '藤县公安局'
    if len(text) <= 12:
        return ' '.join(text)
    return text


def _default_doc_number(police_station: str) -> str:
    from time import time
    prefix = (police_station or 'XX').replace('公安局', '').replace('分局', '')[:6]
    return f'{prefix}公行罚决字[{date.today().year}]' + str(int(time() * 1000))[-6:] + '号'


def _normalize_violation(value) -> str:
    if isinstance(value, (list, tuple)):
        value = '、'.join(str(item) for item in value if item)
    text = str(value or '').strip()
    if not text:
        return ''
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            text = data.get('case_nature') or data.get('violation_type') or ''
    except Exception:
        pass
    text = _strip_noise(str(text))
    text = re.sub(r"[\s\"“”'\[\]{}]+", '', text)
    text = re.sub(r'^(案件性质|案由|涉嫌|构成|违法行为名称|罪名)[:：]?', '', text)
    for suffix in ('违法行为', '行政违法行为', '行政违法', '行为'):
        if text.endswith(suffix) and len(text) > len(suffix):
            text = text[:-len(suffix)]
    text = text.strip('：:;；，,。 ')
    if text in ('无', '不明', '未知', '行政案件', '治安案件', '行政处罚决定书', '检查笔录'):
        return ''
    return text[:40]


def _compact_fact(text: str, max_len: int = 450) -> str:
    text = _strip_noise(text).replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n+', '。', text)
    text = re.sub(r'。+', '。', text).strip(' 。')
    if not text:
        return ''

    for marker in (
        '上述事实有以下证据证实', '上述事实有', '根据《', '根据相关法律',
        '执行方式和期限', '逾期', '一式', '如不服', '附：', '行政处罚决定书已向我宣告'
    ):
        pos = text.find(marker)
        if pos > 0:
            text = text[:pos].strip(' 。')

    raw_sentences = re.findall(r'.+?[。！？!?]|.+$', text)
    sentences = []
    drop_keywords = (
        '接受调查', '依法扣押', '已被扣押', '被传唤', '口头传唤',
        '到案后', '到公安机关', '到派出所', '审批'
    )
    for sentence in raw_sentences:
        sentence = sentence.strip(' 。；;')
        if not sentence:
            continue
        if sentence.startswith(('证据', '上述事实', '根据', '执行方式', '逾期', '一式', '如不服')):
            continue
        if any(keyword in sentence for keyword in drop_keywords):
            continue
        sentences.append(sentence + '。')

    if not sentences:
        sentences = [text.rstrip('。') + '。']

    compact = ''
    for sentence in sentences:
        if len(compact) + len(sentence) > max_len and compact:
            break
        compact += sentence
    if not compact:
        compact = sentences[0][:max_len].rstrip('，；、。') + '。'
    if len(compact) > max_len:
        compact = compact[:max_len].rstrip('，；、。') + '。'
    return compact.strip()


def _ensure_violation_sentence(fact: str, violation: str) -> str:
    fact = _compact_fact(fact)
    violation = _normalize_violation(violation)
    if not fact:
        return ''
    if not violation:
        return fact
    if re.search(r'(涉嫌|构成).{0,40}(违法行为|犯罪|罪)', fact):
        return fact
    if violation.endswith('罪'):
        sentence = f'其行为涉嫌{violation}。'
    else:
        sentence = f'其行为涉嫌{violation}违法行为。'
    return fact.rstrip('。；;') + '。' + sentence


def _party_basic(elements: dict) -> str:
    name = _first(elements.get('party_name'), elements.get('person_name'), elements.get('checked_person_name'))
    gender = _first(elements.get('party_gender'), elements.get('person_gender'))
    id_number = _first(elements.get('party_id_number'), elements.get('id_number'), elements.get('person_id_number'))
    parts = []
    if name:
        parts.append(name)
    if gender:
        parts.append(gender)
    if id_number:
        parts.append(f'身份证号码：{id_number}')
    return '，'.join(parts)


def _witness_basic(elements: dict) -> str:
    name = _first(elements.get('witness_name'))
    gender = _first(elements.get('witness_gender'))
    id_number = _first(elements.get('witness_id_number'), elements.get('witness_id'))
    parts = []
    if name:
        parts.append(name)
    if gender:
        parts.append(gender)
    if id_number:
        parts.append(f'身份证号码：{id_number}')
    return '，'.join(parts)


def _compact_check_process(text: str, party_name: str, violation: str) -> str:
    text = _strip_noise(text).replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.S)
    text = re.sub(r'过程和结果[:：]?', '', text).strip()
    text = re.sub(r'其行为涉嫌.*?(违法行为|犯罪|罪)。?', '', text)
    text = re.sub(r'\s+', '', text)
    if not text:
        reason = f'其涉嫌{violation}违法行为' if violation else '案件调查需要'
        subject = party_name or '被检查人'
        return f'为收集相关证据材料、认定违法事实，民警经出示人民警察证，对{subject}的身体进行了检查，经检查，{subject}身体无异常，检查过程依法进行，被检查人配合检查工作。'
    if len(text) > 520:
        text = text[:520].rstrip('，；、。') + '。'
    if not text.endswith('。'):
        text += '。'
    return text


def _build_check_record(elements: dict, case_text: str, polish_text: str, violation: str) -> str:
    party_name = _first(elements.get('party_name'), elements.get('person_name'), elements.get('checked_person_name'))
    agency = _first(elements.get('police_station'), elements.get('agency'), '藤县公安局')
    handling_unit = _first(elements.get('handling_unit'), elements.get('police_station'), '藤县公安局')
    start_time = _normalize_datetime(_first(elements.get('inspection_time_start'), elements.get('check_time_start'), elements.get('case_date')))
    end_time = _normalize_datetime(_first(elements.get('inspection_time_end'), elements.get('check_time_end'), start_time))
    location = _first(elements.get('inspection_location'), elements.get('check_location'), elements.get('case_location'), f'{handling_unit}办案区检查室')
    inspector_unit_1 = _first(elements.get('inspector_unit_1'), elements.get('inspector_unit'), agency)
    inspector_unit_2 = _first(elements.get('inspector_unit_2'), inspector_unit_1)
    inspection_object = _first(elements.get('inspection_object'), elements.get('check_object'), f'{party_name}的身体' if party_name else '被检查人的身体')
    party_basic = _party_basic(elements)
    witness_basic = _witness_basic(elements)
    witness_name = _first(elements.get('witness_name'))
    inspector_names = _first(elements.get('inspector_names'), elements.get('officer_name'), elements.get('officer_names'))
    recorder_name = _first(elements.get('recorder_name'))
    reason = _first(elements.get('reason_purpose'), elements.get('inspection_reason'), elements.get('purpose'))
    if not reason:
        subject = party_name or '被检查人'
        if violation:
            reason = f'调查{subject}是否有涉嫌{violation}的行为，收集相关的证据。'
        else:
            reason = f'调查{subject}相关情况，收集相关的证据。'
    process = _compact_check_process(_first(elements.get('process_result'), polish_text, elements.get('illegal_fact'), case_text), party_name, violation)
    footer_date = _footer_date(_first(elements.get('footer_date'), start_time, date.today().strftime('%Y年%m月%d日')))

    lines = [
        _space_agency(agency),
        '检 查 笔 录',
        f'时间：{start_time}至{end_time}' if start_time and end_time else f'时间：{start_time or end_time}',
        f'地点 ： {location}',
        f'检查人姓名和工作单位：                     {inspector_unit_1}',
        f'                                           {inspector_unit_2}',
        f'检查或者辨认对象：{inspection_object}',
        '当事人/辨认人基本情况（姓名、性别、身份证件种类及号码）',
        party_basic,
        f'见证人基本情况 （姓名、性别、身份证件种类及号码）           {witness_basic}',
        f'事由和目的：{reason}',
        f'过程和结果：{process}',
        f'检查人：{inspector_names}                              年   月   日',
        f'记录人：{recorder_name}                              年   月   日',
        f'当事人：{party_name}                              年　 月　 日',
        f'见证人：{witness_name}                                  年   月   日',
        '身体检查照片',
        f'办案单位：{handling_unit}',
        f'办案人员：{inspector_names}',
        f'时    间： {footer_date}',
    ]
    return '\n\n'.join(lines)


def _build_penalty_decision(elements: dict, fact_text: str) -> str:
    elements['police_station'] = elements.get('police_station') or '藤县公安局'
    elements['doc_number'] = elements.get('doc_number') or _default_doc_number(elements['police_station'])
    elements['work_unit'] = elements.get('work_unit') or '无'
    elements['criminal_record'] = elements.get('criminal_record') or '无'
    elements['illegal_fact'] = fact_text
    elements['evidence_list'] = elements.get('evidence_list') or '检查笔录、违法行为人的陈述和申辩、其他证据'
    elements['penalty_basis'] = elements.get('penalty_basis') or '《中华人民共和国治安管理处罚法》相关规定'
    elements['penalty_content'] = elements.get('penalty_content') or '依法作出相应行政处罚'
    elements['execution_detail'] = elements.get('execution_detail') or '收到决定书之日起15日内按照本决定执行。'
    elements['reconsideration_org'] = elements.get('reconsideration_org') or '藤县人民政府'
    elements['lawsuit_court'] = elements.get('lawsuit_court') or '藤县人民法院'
    elements['stamp_date'] = elements.get('stamp_date') or date.today().strftime('%Y-%m-%d')

    evidence_text = _trim_final_punct(elements.get('evidence_list', ''))
    penalty_basis_text = _trim_final_punct(elements.get('penalty_basis', ''))
    basis_suffix = '' if penalty_basis_text.endswith('规定') else '之规定'
    return '\n\n'.join([
        elements['police_station'],
        '行政处罚决定书',
        elements['doc_number'],
        f"违法行为人{elements.get('party_name', '')}，{elements.get('party_gender', '')}，{elements.get('party_age', '')}岁，居民身份证号码{elements.get('party_id_number', '')}，{elements.get('birth_date', '')}出生，籍贯：{elements.get('native_place', '')}，户籍：{elements.get('household_register', '')}，现住：{elements.get('party_address', '')}，工作单位：{elements.get('work_unit', '')}，违法犯罪经历：{elements.get('criminal_record', '')}。",
        elements['illegal_fact'],
        f"上述事实有以下证据证实：{evidence_text}。",
        f"根据{penalty_basis_text}{basis_suffix}，现决定对违法行为人{elements.get('party_name', '')}处以{elements.get('penalty_content', '')}。",
        f"执行方式和期限：{elements.get('execution_detail', '')}",
        '逾期不履行的，依法承担相应法律后果。',
        '一式四份，被处罚人和执行单位各一份，一份附卷。',
        f"如不服本决定，可以在收到本决定书之日起六十日内向{elements.get('reconsideration_org', '')}申请行政复议或者在六个月内向{elements.get('lawsuit_court', '')}提起行政诉讼。",
        '附：清单共  份',
        elements['police_station'],
        elements['stamp_date'],
        '行政处罚决定书已向我宣告并送达。',
        '被处罚人:                        被侵害人：',
        '年    月    日                  年    月    日',
        '接收人员：',
        '接收单位（印）',
        '年    月    日',
        '案件编号：',
        '人员编号：',
    ])


def main(
    case_text: str = '',
    classify_text: str = '',
    extract_text: str = '',
    polish_text: str = '',
    selected_doc_type: str = ''
) -> dict:
    classified_doc_type = ''
    case_nature = ''
    try:
        classify = _extract_json_block(classify_text)
        classified_doc_type = classify.get('doc_type', '') or ''
        case_nature = classify.get('case_nature', '') or ''
    except Exception:
        pass

    elements = {}
    laws = []
    try:
        extract = _extract_json_block(extract_text)
        if isinstance(extract, dict):
            elements = extract.get('elements', {}) or {}
            if not case_nature:
                case_nature = extract.get('case_nature', '') or ''
            if not case_nature and isinstance(elements, dict):
                case_nature = elements.get('violation_type', '') or ''
            laws = extract.get('suggested_laws', []) or []
    except Exception:
        pass

    for key, value in list(elements.items()):
        if value is None:
            elements[key] = ''
        elif isinstance(value, str) and value.strip().lower() in ('null', 'none'):
            elements[key] = ''

    doc_type = _normalize_doc_type(selected_doc_type, classified_doc_type)
    polish_clean = _clean_content(polish_text)
    case_text_clean = _clean_content(case_text)
    violation_name = _normalize_violation(elements.get('violation_type') or case_nature)
    if violation_name:
        case_nature = violation_name
        elements['violation_type'] = violation_name

    if doc_type == '检查笔录':
        content = _build_check_record(elements, case_text_clean, polish_clean, violation_name)
    else:
        fact_source = polish_clean or elements.get('illegal_fact') or case_text_clean
        fact_text = _ensure_violation_sentence(fact_source, violation_name)
        content = _build_penalty_decision(elements, fact_text)

    output_content = content.strip() if doc_type == '检查笔录' else _clean_content(content)
    return {
        'content': output_content,
        'doc_type': doc_type,
        'case_nature': case_nature,
        'elements': json.dumps(elements, ensure_ascii=False, indent=2),
        'suggested_laws': '\n'.join(str(item) for item in laws if item),
    }
'''


EXPORT_CODE = r'''
import json
import urllib.request


EXPORT_API = 'http://host.docker.internal:8123/api/export-word'


def _file_payload(value):
    if not value:
        return None
    if isinstance(value, dict):
        return value
    return {'value': str(value)}


def main(input_text: str, doc_type: str = '', photo_1=None, photo_2=None) -> dict:
    content = str(input_text or '').strip()
    doc_type = str(doc_type or '').strip()
    if not content:
        return {'word_download_link': ''}

    filename = 'generated-check-record.docx' if '检查' in doc_type else 'generated-document.docx'
    photos = [item for item in (_file_payload(photo_1), _file_payload(photo_2)) if item]
    payload = json.dumps({
        'content': content,
        'doc_type': doc_type,
        'filename': filename,
        'photos': photos,
    }, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        EXPORT_API,
        data=payload,
        headers={'Content-Type': 'application/json; charset=utf-8'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode('utf-8'))
        url = data.get('url') or ''
        if not url:
            return {'word_download_link': 'Word export failed: empty download url'}
        label = chr(19979) + chr(36733) + 'Word' + chr(25991) + chr(26723)
        return {'word_download_link': '[' + label + '](' + url + ')'}
    except Exception as exc:
        return {'word_download_link': 'Word export failed: ' + str(exc)}
'''


compile(CODE_FILL, "<code-fill>", "exec")
compile(EXPORT_CODE, "<export-word>", "exec")

graph = json.loads(psql(f"SELECT graph::text FROM workflows WHERE app_id='{APP_ID}' AND version='draft';"))

start = find_node(graph, "start-node")
variables = start["data"].setdefault("variables", [])
variables = [
    var for var in variables
    if var.get("variable") not in {"document_type", "photo_upload_choice", "check_photo_1", "check_photo_2"}
]
variables.insert(0, {
    "type": "select",
    "label": "文书类型",
    "required": True,
    "variable": "document_type",
    "options": ["行政处罚决定书", "检查笔录"],
    "max_length": 48,
    "placeholder": "请选择文书类型",
    "hint": "选择本次要生成的公安法律文书",
})
variables.insert(1, {
    "type": "select",
    "label": "身体检查照片",
    "required": False,
    "variable": "photo_upload_choice",
    "options": ["不上传检查照片", "上传两张检查照片"],
    "max_length": 48,
    "placeholder": "检查笔录可选",
    "hint": "生成检查笔录时可不上传照片；上传时请提供两张",
})
variables.append({
    "type": "file",
    "label": "检查照片1（可选）",
    "required": False,
    "variable": "check_photo_1",
    "allowed_file_types": ["image"],
    "allowed_file_extensions": [".jpg", ".jpeg", ".png", ".bmp", ".webp"],
    "allowed_file_upload_methods": ["local_file"],
    "hint": "生成检查笔录时使用，留空则照片页为空白",
})
variables.append({
    "type": "file",
    "label": "检查照片2（可选）",
    "required": False,
    "variable": "check_photo_2",
    "allowed_file_types": ["image"],
    "allowed_file_extensions": [".jpg", ".jpeg", ".png", ".bmp", ".webp"],
    "allowed_file_upload_methods": ["local_file"],
    "hint": "生成检查笔录时使用，留空则照片页为空白",
})
start["data"]["variables"] = variables
start["data"]["title"] = "选择文书并上传笔录"
start["data"]["desc"] = "选择要生成的文书类型，上传笔录Word文档，AI自动解析并按模板导出Word"
for var in start["data"]["variables"]:
    if var.get("variable") == "transcript":
        var["label"] = "笔录文件（.docx）"
        var["hint"] = "请上传 .docx 文件；旧版 .doc 需先用 Word 另存为 .docx"
        var["allowed_file_extensions"] = [".docx"]

classify = find_node(graph, "llm-classify")
classify["data"]["prompt_template"][0]["text"] = """你是一名公安法制民警。用户选择的目标文书类型是：{{#start-node.document_type#}}。

要求：
1. 如果用户选择了“行政处罚决定书”或“检查笔录”，doc_type必须以用户选择为准。
2. 同时根据笔录内容识别具体涉嫌违法行为/罪名名称，例如：扰乱公共场所秩序、盗窃、殴打他人、寻衅滋事、赌博、吸毒、帮助信息网络犯罪活动。
3. 不要输出“行政案件”“治安案件”这类泛称。

直接输出JSON，不要任何思考过程：
{"doc_type": "文书名称", "case_nature": "具体涉嫌违法行为或罪名"}"""

extract = find_node(graph, "llm-extract")
extract["data"]["prompt_template"][0]["text"] = """你是专业公安法律文书录入员。用户选择的目标文书类型是：{{#start-node.document_type#}}。从笔录中提取生成目标文书需要的字段，直接输出JSON。

通用规则：
1. 只提取笔录中实际出现的内容，缺项填null，不要编造姓名、身份证号、地点。
2. 时间尽量输出到分钟，格式如：2026年05月29日11时15分。
3. violation_type填写具体涉嫌违法行为/罪名名称。

如果目标文书是行政处罚决定书：
- illegal_fact只写处罚书事实段需要的事实：时间、地点、人员、起因、核心行为、后果/影响；不要堆砌调查过程、到案过程、扣押过程和证据清单。
- illegal_fact控制在150到450字，末尾写明“其行为涉嫌/构成××违法行为”。

如果目标文书是检查笔录：
- 必须提取检查笔录字段：检查开始时间、结束时间、地点、检查人单位、检查/辨认对象、当事人基本情况、见证人基本情况、事由和目的、过程和结果、办案单位、办案人员。
- process_result只写“过程和结果”段，保留出示人民警察证、检查对象、检查结果、配合情况等内容，不要写处罚决定书事实段。

直接输出JSON，不要思考过程。"""
extract["data"]["prompt_template"][1]["text"] = """用户选择文书类型：{{#start-node.document_type#}}
已识别文书类型和案由：{{#llm-classify.text#}}

笔录内容：
{{#context#}}

请提取并直接输出JSON（不要思考过程）：
{"elements": {
  "police_station":"公安机关/办案单位",
  "party_name":"当事人姓名",
  "party_gender":"性别",
  "party_age":"年龄",
  "party_id_number":"身份证号",
  "party_address":"住址",
  "case_date":"案发或检查时间",
  "case_location":"案发或检查地点",
  "violation_type":"具体涉嫌违法行为或罪名",
  "illegal_fact":"行政处罚决定书精简事实段",
  "evidence_list":"证据",
  "party_statement":"当事人陈述",
  "officer_name":"办案人员",
  "amount_involved":"涉案金额",
  "items_involved":"涉案物品",
  "work_unit":"工作单位",
  "criminal_record":"前科",
  "inspection_time_start":"检查开始时间",
  "inspection_time_end":"检查结束时间",
  "inspection_location":"检查地点",
  "inspector_names":"检查人姓名",
  "inspector_unit_1":"检查人工作单位第一行",
  "inspector_unit_2":"检查人工作单位第二行",
  "inspection_object":"检查或者辨认对象",
  "witness_name":"见证人姓名",
  "witness_gender":"见证人性别",
  "witness_id_number":"见证人身份证号",
  "reason_purpose":"检查事由和目的",
  "process_result":"检查过程和结果",
  "recorder_name":"记录人",
  "handling_unit":"办案单位",
  "footer_date":"页脚时间"
}, "suggested_laws": ["法律条文"]}"""

polish = find_node(graph, "llm-polish")
polish["data"]["prompt_template"][0]["text"] = """根据用户选择的文书类型润色对应段落。用户选择的目标文书类型是：{{#start-node.document_type#}}。

如果目标文书是行政处罚决定书：
1. 只输出一段事实，不分条，不写标题，不写证据清单。
2. 精简但事实清楚，控制在150到450字。
3. 写清违法行为人、时间、地点、起因、核心行为、造成的影响/后果。
4. 删除到案、传唤、接受调查、手机扣押、审批等过程性内容。
5. 末尾写明具体涉嫌违法行为/罪名，例如“其行为涉嫌扰乱公共场所秩序违法行为。”

如果目标文书是检查笔录：
1. 只输出“过程和结果”段正文，不写“过程和结果：”标题。
2. 写清检查时间背景、检查原因、出示人民警察证、检查对象、检查结果、检查过程是否合法、被检查人是否配合。
3. 不要写处罚决定书事实认定，不要写“其行为涉嫌××违法行为”结尾。
4. 控制在80到300字。

只输出润色后的段落，不要思考过程。"""
polish["data"]["prompt_template"][1]["text"] = """用户选择文书类型：{{#start-node.document_type#}}

已识别案由：
{{#llm-classify.text#}}

已提取要素：
{{#llm-extract.text#}}

原始笔录：
{{#context#}}

请按用户选择的文书类型生成对应段落："""

fill = find_node(graph, "code-fill")
fill["data"]["code"] = CODE_FILL
fill["data"]["variables"] = [
    {"variable": "case_text", "value_selector": ["flatten-text", "flat_text"]},
    {"variable": "classify_text", "value_selector": ["llm-classify", "text"]},
    {"variable": "extract_text", "value_selector": ["llm-extract", "text"]},
    {"variable": "polish_text", "value_selector": ["llm-polish", "text"]},
    {"variable": "selected_doc_type", "value_selector": ["start-node", "document_type"]},
]

export = find_node(graph, "export-word")
export["data"]["code"] = EXPORT_CODE
export["data"]["variables"] = [
    {"variable": "input_text", "value_selector": ["code-fill", "content"]},
    {"variable": "doc_type", "value_selector": ["code-fill", "doc_type"]},
    {"variable": "photo_1", "value_selector": ["start-node", "check_photo_1"]},
    {"variable": "photo_2", "value_selector": ["start-node", "check_photo_2"]},
]

graph_json = json.dumps(graph, ensure_ascii=False)
sql = f"""
BEGIN;
UPDATE workflows
SET graph = $codex_graph${graph_json}$codex_graph$::jsonb,
    updated_at = now()
WHERE app_id = '{APP_ID}' AND version = 'draft';
WITH draft AS (
    SELECT * FROM workflows WHERE app_id = '{APP_ID}' AND version = 'draft' LIMIT 1
), inserted AS (
    INSERT INTO workflows (
        id, tenant_id, app_id, type, version, graph, features, created_by, created_at,
        updated_by, updated_at, environment_variables, conversation_variables,
        marked_name, marked_comment, rag_pipeline_variables
    )
    SELECT
        gen_random_uuid(), tenant_id, app_id, type,
        to_char(now() at time zone 'UTC', 'YYYY-MM-DD HH24:MI:SS.US'),
        graph, features, created_by, now(), updated_by, now(), environment_variables,
        conversation_variables, marked_name, marked_comment, rag_pipeline_variables
    FROM draft
    RETURNING id
)
UPDATE apps
SET workflow_id = inserted.id,
    updated_at = now()
FROM inserted
WHERE apps.id = '{APP_ID}';
COMMIT;
SELECT workflow_id FROM apps WHERE id = '{APP_ID}';
"""
print(psql(sql).strip())
