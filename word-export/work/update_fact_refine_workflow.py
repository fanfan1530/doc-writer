import json
import re
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


HELPER_CODE = r'''

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
    if text in ('无', '不明', '未知', '行政案件', '治安案件', '行政处罚决定书'):
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
'''


def update_code(code: str) -> str:
    code = code.replace("line = line.strip('：:;；，,。 ')", "line = line.strip()")
    code = re.sub(
        r"\n\ndef _normalize_violation\(value\).*?\n\ndef main\(",
        lambda _match: HELPER_CODE + "\n\ndef main(",
        code,
        flags=re.S,
    )
    if "def _normalize_violation" not in code:
        code = code.replace("\n\ndef main(", HELPER_CODE + "\n\ndef main(", 1)
    code = code.replace(
        """            if not case_nature:
                case_nature = extract.get('case_nature', '') or ''
            laws = extract.get('suggested_laws', []) or []""",
        """            if not case_nature:
                case_nature = extract.get('case_nature', '') or ''
            if not case_nature and isinstance(elements, dict):
                case_nature = elements.get('violation_type', '') or ''
            laws = extract.get('suggested_laws', []) or []""",
    )
    code = code.replace(
        """    polish_clean = _clean_content(polish_text)
    case_text_clean = _clean_content(case_text)
    fact_text = polish_clean or elements.get('illegal_fact') or case_text_clean""",
        """    polish_clean = _clean_content(polish_text)
    case_text_clean = _clean_content(case_text)
    violation_name = _normalize_violation(elements.get('violation_type') or case_nature)
    fact_source = polish_clean or elements.get('illegal_fact') or case_text_clean
    fact_text = _ensure_violation_sentence(fact_source, violation_name)
    if violation_name:
        case_nature = violation_name
        elements['violation_type'] = violation_name""",
    )
    return code


graph = json.loads(psql(f"SELECT graph::text FROM workflows WHERE app_id='{APP_ID}' AND version='draft';"))

classify = find_node(graph, "llm-classify")
classify["data"]["prompt_template"][0]["text"] = """你是一名公安法制民警。根据以下讯问/询问笔录内容，判断应该生成哪种法律文书和具体案由。

判断规则：
1. 如果是讯问/询问违法行为人、被侵害人、证人，且需要处罚决定 → 行政处罚决定书
2. 如果是现场勘验检查记录 → 现场勘查笔录
3. 如果是组织辨认过程记录 → 辨认笔录
4. 如果是搜查过程记录 → 搜查笔录
5. 如果是对人/场所/物品的检查记录 → 检查笔录
6. 如果是处罚前告知过程记录 → 行政处罚告知笔录
7. 如果是调解纠纷记录 → 调解协议书
8. 如果是扣押物品记录 → 扣押决定书
9. 如果是犯罪现场指认记录 → 指认笔录
10. 如果是案件侦办总结 → 结案报告

案件性质必须输出具体涉嫌违法行为/罪名名称，例如：扰乱公共场所秩序、盗窃、殴打他人、寻衅滋事、赌博、吸毒。不要输出“行政案件”“治安案件”这类泛称。

直接输出JSON，不要任何思考过程：
{"doc_type": "文书名称", "case_nature": "具体涉嫌违法行为或罪名"}"""

extract = find_node(graph, "llm-extract")
extract["data"]["prompt_template"][0]["text"] = """你是专业法律文书录入员。从以下讯问/询问笔录中提取关键信息，直接输出JSON。

规则：
1. 只提取笔录中实际出现的内容，缺项填null
2. 时间统一为：YYYY年MM月DD日HH时格式
3. violation_type必须填写具体涉嫌违法行为/罪名名称，例如扰乱公共场所秩序、盗窃、殴打他人
4. illegal_fact只写处罚书事实段需要的事实：时间、地点、人员、起因、核心行为、后果/影响；不要堆砌调查过程、到案过程、扣押过程和证据清单
5. illegal_fact控制在150到450字，末尾写明“其行为涉嫌/构成××违法行为”
6. suggested_laws按案件性质推荐法律条文，如盗窃案推荐《治安管理处罚法》第四十九条
7. 直接输出JSON，不要思考过程"""
extract["data"]["prompt_template"][1]["text"] = """已识别文书类型和案由：{{#llm-classify.text#}}

笔录内容：
{{#context#}}

请提取并直接输出JSON（不要思考过程）：
{"elements": {"police_station":"办案单位", "party_name":"当事人姓名", "party_gender":"性别", "party_age":"年龄", "party_id_number":"身份证号", "party_address":"住址", "case_date":"案发时间", "case_location":"案发地点", "violation_type":"具体涉嫌违法行为或罪名", "illegal_fact":"精简事实段", "evidence_list":"证据", "party_statement":"当事人陈述", "officer_name":"办案人员", "amount_involved":"涉案金额", "items_involved":"涉案物品", "work_unit":"工作单位", "criminal_record":"前科"}, "suggested_laws": ["法律条文"]}"""

polish = find_node(graph, "llm-polish")
polish["data"]["prompt_template"][0]["text"] = """将笔录中的案件事实润色为行政处罚决定书中的事实段。

输出要求：
1. 只输出一段事实，不分条，不写标题，不写证据清单
2. 精简但事实清楚，控制在150到450字
3. 必须写清：违法行为人、时间、地点、起因、核心行为、造成的影响/后果
4. 删除与事实无关的过程性内容，例如到案、传唤、接受调查、手机扣押、审批等
5. 不照搬笔录流水账，不展开所有参与人细节，只保留认定违法事实必要内容
6. 末尾必须写明具体涉嫌违法行为/罪名，例如“其行为涉嫌扰乱公共场所秩序违法行为。”；行政处罚案件优先写“违法行为”，不要误写成刑事罪名
7. 保留笔录中明确的时间、地点、人名、身份证号、金额、物品等关键信息

只输出润色后的事实段落，不要思考过程。"""
polish["data"]["prompt_template"][1]["text"] = """已识别案由：
{{#llm-classify.text#}}

已提取要素：
{{#llm-extract.text#}}

原始笔录：
{{#context#}}

请生成行政处罚决定书事实段："""

fill = find_node(graph, "code-fill")
fill["data"]["code"] = update_code(fill["data"]["code"])

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
print(psql(sql))
