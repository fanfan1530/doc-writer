from pathlib import Path

import yaml


src = Path("/tmp/police_workflow_inner_direct_word.yml")
out = Path("/tmp/police_workflow_inner_direct_word_encoding_fix.yml")
data = yaml.safe_load(src.read_text(encoding="utf-8-sig"))

data["app"]["name"] = "警务文书智能生成（Word插件防乱码版）"
data["app"]["description"] = "上传Word笔录，一键生成公安法律文书；通过LLM整理为Markdown后交给Dify文档插件转Word，减少中文乱码"

graph = data["workflow"]["graph"]
nodes = graph["nodes"]
edges = graph["edges"]

if not any(node.get("id") == "llm-markdown" for node in nodes):
    polish_node = next(node for node in nodes if node.get("id") == "llm-polish")
    model = polish_node["data"]["model"]
    nodes.append(
        {
            "data": {
                "context": {"enabled": False, "variable_selector": []},
                "memory": {"role_prefix": {"assistant": "", "user": ""}, "window": {"enabled": False}},
                "model": model,
                "prompt_template": [
                    {
                        "id": "md-system",
                        "role": "system",
                        "text": (
                            "你是中文Word文档排版助手。请把输入的公安法律文书正文整理成标准Markdown，"
                            "用于Dify的Markdown转DOCX工具生成Word。\n\n"
                            "要求：\n"
                            "1. 必须保留原文中文，不得输出乱码、拼音、Unicode转义（例如\\u4e2d）或HTML实体。\n"
                            "2. 不要使用代码块，不要包裹```。\n"
                            "3. 第一行使用一级标题，标题为文书类型。\n"
                            "4. 正文按自然段输出，保留签名栏、日期、落款。\n"
                            "5. 不要添加操作说明、下载说明、生成过程。"
                        ),
                    },
                    {
                        "id": "md-user",
                        "role": "user",
                        "text": (
                            "文书类型：{{#code-fill.doc_type#}}\n\n"
                            "文书正文：\n{{#code-fill.content#}}\n\n"
                            "请直接输出可转Word的Markdown正文："
                        ),
                    },
                ],
                "selected": False,
                "title": "转Word前Markdown整理",
                "type": "llm",
                "vision": {"enabled": False},
            },
            "height": 87,
            "id": "llm-markdown",
            "position": {"x": 1288, "y": 260},
            "positionAbsolute": {"x": 1288, "y": 260},
            "selected": False,
            "sourcePosition": "right",
            "targetPosition": "left",
            "type": "custom",
            "width": 242,
        }
    )

# Replace direct code-fill -> converter edge with code-fill -> llm-markdown -> converter.
edges[:] = [
    edge
    for edge in edges
    if edge.get("id") not in {"code-fill-docx-converter", "llm-markdown-docx-converter", "code-fill-llm-markdown"}
]
edges.append(
    {
        "data": {"isInIteration": False, "isInLoop": False, "sourceType": "code", "targetType": "llm"},
        "id": "code-fill-llm-markdown",
        "source": "code-fill",
        "sourceHandle": "source",
        "target": "llm-markdown",
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
    }
)
edges.append(
    {
        "data": {"isInIteration": False, "isInLoop": False, "sourceType": "llm", "targetType": "tool"},
        "id": "llm-markdown-docx-converter",
        "source": "llm-markdown",
        "sourceHandle": "source",
        "target": "docx-converter",
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
    }
)

for node in nodes:
    if node.get("id") == "docx-converter":
        node["data"]["tool_parameters"]["markdown_content"] = {
            "type": "mixed",
            "value": "{{#llm-markdown.text#}}",
        }
        node["data"]["tool_parameters"]["title"] = {
            "type": "mixed",
            "value": "{{#code-fill.doc_type#}}",
        }
        node["position"] = {"x": 1590, "y": 260}
        node["positionAbsolute"] = {"x": 1590, "y": 260}
    if node.get("id") == "end-node":
        node["position"] = {"x": 1892, "y": 260}
        node["positionAbsolute"] = {"x": 1892, "y": 260}

out.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
print(out)
