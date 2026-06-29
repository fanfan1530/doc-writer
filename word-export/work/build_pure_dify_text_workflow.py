from pathlib import Path

import yaml


src = Path("/tmp/police_service_workflow_intranet_031.yml")
out = Path("/tmp/police_workflow_pure_dify_text_only.yml")
data = yaml.safe_load(src.read_text(encoding="utf-8-sig"))

app = data["app"]
app["name"] = "警务文书智能生成（纯Dify文本版）"
app["description"] = "只使用Dify内置节点：上传Word笔录，选择文书类型，输出可复制的公安法律文书正文"

workflow = data["workflow"]
graph = workflow["graph"]

graph["nodes"] = [node for node in graph["nodes"] if node.get("id") != "export-word"]
graph["edges"] = [
    edge
    for edge in graph["edges"]
    if edge.get("source") != "export-word"
    and edge.get("target") != "export-word"
    and edge.get("id") not in {"code-export-word", "export-word-end"}
]

if not any(edge.get("id") == "code-fill-end" for edge in graph["edges"]):
    graph["edges"].append(
        {
            "data": {
                "isInIteration": False,
                "isInLoop": False,
                "sourceType": "code",
                "targetType": "end",
            },
            "id": "code-fill-end",
            "source": "code-fill",
            "sourceHandle": "source",
            "target": "end-node",
            "targetHandle": "target",
            "type": "custom",
            "zIndex": 0,
        }
    )

for node in graph["nodes"]:
    if node.get("id") == "start-node":
        node["data"]["title"] = "选择文书并上传笔录"
        node["data"]["desc"] = "纯Dify文本版：上传Word笔录后生成可复制的文书正文，不调用外部导出服务"
        node["data"]["variables"] = [
            var
            for var in node["data"].get("variables", [])
            if var.get("variable") not in {"photo_upload_choice", "check_photo_1", "check_photo_2"}
        ]
        for var in node["data"]["variables"]:
            if var.get("variable") == "document_type":
                var["hint"] = "选择本次要生成的文书正文；纯Dify版不生成docx文件"
            if var.get("variable") == "transcript":
                var["label"] = "笔录文件（.docx）"
                var["allowed_file_extensions"] = [".docx"]
                var["hint"] = "请上传 .docx 文件"

for node in graph["nodes"]:
    if node.get("id") == "end-node":
        node["data"]["title"] = "输出文书正文"
        node["data"]["outputs"] = [
            {
                "value_selector": ["code-fill", "content"],
                "value_type": "string",
                "variable": "document",
            }
        ]
        node["height"] = 90

entry_func = r'''

def _build_entry_materials_text(elements: dict, violation: str) -> str:
    name = _first(elements.get('party_name'), elements.get('person_name'), elements.get('checked_person_name'))
    gender = _first(elements.get('party_gender'), elements.get('person_gender'), elements.get('gender'))
    id_number = _first(elements.get('party_id_number'), elements.get('id_number'), elements.get('person_id_number'))
    birth = _format_chinese_date(elements.get('birth_date'))
    if not birth and id_number:
        parsed_birth = _birth_from_id(id_number)
        if parsed_birth:
            birth = f'{parsed_birth.year:04d}年{parsed_birth.month:02d}月{parsed_birth.day:02d}日'
    entry_date = _format_chinese_date(_first(elements.get('entry_date'), elements.get('detention_date'), elements.get('case_date')), default_today=True)
    address = _first(elements.get('party_address'), elements.get('residence_address'), elements.get('household_register_detail'), elements.get('household_register'))
    native_place = _first(elements.get('native_place'), elements.get('household_register'))
    ethnicity = _first(elements.get('ethnicity'), elements.get('nation'), elements.get('nationality'))
    education = _first(elements.get('education'), elements.get('education_level'))
    marital = _first(elements.get('marital_status'), elements.get('marriage'))
    political = _first(elements.get('political_status')) or '群众'
    occupation = _first(elements.get('occupation'), elements.get('job')) or '无'
    work_unit = _first(elements.get('work_unit'), elements.get('workplace')) or '无'
    sending_unit = _first(elements.get('sending_unit'), elements.get('handling_unit'), elements.get('police_station'))
    escort_officers = _first(elements.get('escort_officers'), elements.get('handling_officers'), elements.get('officer_name'))
    escort_phone = _first(elements.get('escort_phone'), elements.get('contact_phone'), elements.get('phone'))
    case_name = _first(elements.get('case_name'), elements.get('case_title'), violation + '案' if violation else '')
    fact = _first(elements.get('entry_fact'), elements.get('illegal_fact'), elements.get('case_fact'))
    decision_agency = _first(elements.get('decision_agency'), elements.get('police_station'), sending_unit)
    detention_type = _first(elements.get('detention_type')) or '行政拘留'
    detention_period = _first(elements.get('detention_period'), elements.get('detention_days'))

    sections = [
        '入所材料',
        '',
        '一、被拘留人员信息卡、入所登记表',
        f'姓名：{name}',
        f'性别：{gender}',
        f'出生日期：{birth}',
        f'身份证件种类及号码：居民身份证{id_number}',
        f'民族：{ethnicity}',
        f'政治面貌：{political}',
        f'婚姻状况：{marital}',
        f'文化程度：{education}',
        f'籍贯：{native_place}',
        f'户籍/现住址：{address}',
        f'职业：{occupation}',
        f'服务场所/工作单位：{work_unit}',
        f'违法事实：{fact}',
        f'收拘类型：{detention_type}',
        f'入所时间：{entry_date}',
        f'送拘单位名称：{sending_unit}',
        f'送拘执行人员姓名：{escort_officers}',
        f'送拘执行人员联系电话：{escort_phone}',
        f'送拘凭证类别：{detention_type}',
        f'案别：{case_name}',
        f'拘留期限：{detention_period}天',
        f'决定拘留机关名称：{decision_agency}',
        '',
        '二、入所健康检查表',
        f'检查日期：{entry_date}',
        f'姓名：{name}',
        f'性别：{gender}',
        f'出生日期：{birth}',
        f'文化程度：{education}',
        f'民族：{ethnicity}',
        f'婚姻状况：{marital}',
        f'身份证件种类和号码：{id_number}',
        f'送拘单位：{sending_unit}',
        '体表特殊标记：',
        '既往病史：',
        '吸毒史：',
        '有无传染病：',
        '自述症状：',
        '检查状况：',
        '医生意见：',
        '',
        '三、梧州市拘留所在押人员病历档案首页',
        f'姓名：{name}',
        f'性别：{gender}',
        f'入所时间：{entry_date}',
        '入所体检情况：',
        '既往史：',
        '吸毒史：',
        '药物过敏史：',
        '现病史：',
        '治疗情况：',
        '备注：',
        '',
        '四、梧州市拘留所矛盾化解纠纷排查表',
        f'姓名：{name}',
        f'性别：{gender}',
        f'案由：{case_name}',
        f'入所时间：{entry_date}',
        f'拘留期限：{detention_period}天',
        '是否需要拘留所组织调解：否',
        '',
        '五、梧州市拘留所被拘留人权利义务告知书',
        '为规范拘留所的执法管理，保障被拘留人的合法权利，维护拘留所监管秩序和安全，拘留所已向被拘留人告知其在拘留期间依法享有的权利和应当履行的义务。以上告知内容本人已阅知。',
        '',
        '六、防治艾滋病基本知识',
        '民警已向本人宣传防治艾滋病基本知识，包括艾滋病传播途径、预防措施、检测治疗和个人防护等内容。本人已知悉上述宣传告知内容。',
    ]
    return '\n'.join(sections).strip()
'''

for node in graph["nodes"]:
    if node.get("id") == "code-fill":
        node["data"]["title"] = "文书正文生成"
        code = node["data"].get("code", "")
        if "_build_entry_materials_text" not in code:
            code = code.replace("\ndef main(\n", entry_func + "\ndef main(\n")
        old = """if doc_type == '入所表':\n        if polish_clean and not elements.get('entry_fact'):\n            elements['entry_fact'] = polish_clean\n        content = '入所材料'"""
        new = """if doc_type == '入所表':\n        if polish_clean and not elements.get('entry_fact'):\n            elements['entry_fact'] = polish_clean\n        content = _build_entry_materials_text(elements, violation_name)"""
        if old in code:
            code = code.replace(old, new)
        node["data"]["code"] = code

for node in graph["nodes"]:
    if node.get("id") == "llm-polish":
        for item in node["data"].get("prompt_template", []):
            if item.get("role") == "system" and "纯Dify文本版" not in item.get("text", ""):
                item["text"] = item["text"] + "\n\n当前工作流为纯Dify文本版，只输出文书正文，不输出操作过程，不生成Word下载链接。"
    if node.get("id") == "llm-extract":
        for item in node["data"].get("prompt_template", []):
            if item.get("role") == "system" and "纯Dify文本版" not in item.get("text", ""):
                item["text"] = item["text"] + "\n\n当前工作流为纯Dify文本版，请只抽取生成正文需要的要素，不要输出下载、导出、工具调用相关内容。"

out.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(out)
