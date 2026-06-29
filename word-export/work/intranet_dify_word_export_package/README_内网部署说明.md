# Dify 警务文书工作流内网部署包

这个包用于把当前工作流迁移到内网 Dify。

## 重要说明

纯 Dify DSL 不能可靠完成 Word 文件生成和下载托管。这个包采用稳定方案：

- `dify_workflow_import.yml`：导入 Dify 的工作流 DSL。
- `word-export`：本地 Word 导出服务，负责按模板生成 `.docx` / `.zip` 并提供下载链接。
- `templates/`：所有 Word 标准模板。

导入 DSL 后，必须启动 `word-export` 服务，否则工作流只能生成文本，不能生成可下载 Word。

## 文件清单

- `dify_workflow_import.yml`
- `docker-compose.word-export.yml`
- `word_export_service.py`
- `templates/reference_layout.docx`
- `templates/check_record_template.docx`
- `templates/identification_record_template.docx`
- `templates/criminal_record_template.docx`
- `templates/entry_materials_docx_templates/*.docx`

## 第一步：确认 Dify 沙箱网络名

在内网 Dify 服务器执行：

```bash
docker network ls
```

一般 Dify Docker 部署会有类似：

```text
docker_ssrf_proxy_network
```

如果网络名不是这个，后面启动时设置 `DIFY_SANDBOX_NETWORK`。

## 第二步：启动 Word 导出服务

进入本目录，执行：

```bash
docker compose -f docker-compose.word-export.yml up -d
```

如果 Dify 沙箱网络名不同，例如叫 `dify_ssrf_proxy_network`：

```bash
DIFY_SANDBOX_NETWORK=dify_ssrf_proxy_network docker compose -f docker-compose.word-export.yml up -d
```

如果内网用户需要通过服务器 IP 下载文件，建议这样启动：

```bash
WORD_EXPORT_PUBLIC_BASE_URL=http://内网服务器IP:8123 docker compose -f docker-compose.word-export.yml up -d
```

也可以同时设置：

```bash
DIFY_SANDBOX_NETWORK=dify_ssrf_proxy_network WORD_EXPORT_PUBLIC_BASE_URL=http://内网服务器IP:8123 docker compose -f docker-compose.word-export.yml up -d
```

## 第三步：检查导出服务

在服务器执行：

```bash
curl http://127.0.0.1:8123/health
```

正常返回：

```json
{"status":"ok"}
```

在 Dify 沙箱网络里检查服务名是否可访问：

```bash
docker run --rm --network ${DIFY_SANDBOX_NETWORK:-docker_ssrf_proxy_network} curlimages/curl:8.7.1 http://word-export:8123/health
```

正常返回：

```json
{"status":"ok"}
```

## 第四步：导入 Dify DSL

在内网 Dify 页面：

1. 进入工作室。
2. 选择导入 DSL。
3. 上传 `dify_workflow_import.yml`。
4. 导入后检查开始节点的文书类型，应包含：
   - 行政处罚决定书
   - 检查笔录
   - 辨认笔录
   - 入所表
   - 前科证明

## 第五步：测试

上传一个 `.docx` 笔录文件，选择任意文书类型运行。

如果输出链接类似下面这样，说明正常：

```text
http://内网服务器IP:8123/downloads/xxx.docx
```

如果输出 `Word export failed`，优先检查：

1. `word-export` 容器是否启动。
2. Dify 沙箱网络名是否设置正确。
3. `dify_workflow_import.yml` 里的 `EXPORT_API` 是否是 `http://word-export:8123/api/export-word`。
4. `WORD_EXPORT_PUBLIC_BASE_URL` 是否是用户浏览器能访问的内网地址。

## 不使用 Docker 的备选方式

如果内网服务器不能拉取 `python:3.12-slim` 镜像，也可以在服务器安装 Python 3.10+ 后执行：

```bash
python word_export_service.py
```

但这种方式下，Dify 工作流里的 `EXPORT_API` 需要改成：

```python
EXPORT_API = 'http://内网服务器IP:8123/api/export-word'
```

