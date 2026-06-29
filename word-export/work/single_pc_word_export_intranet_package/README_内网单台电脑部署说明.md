# 警务文书 Dify 工作流：内网单台电脑导出服务版

这个版本用于你的实际限制场景：

- 内网 Dify 是统一部署的。
- 你只能通过网页导入和使用 Dify。
- 不能在 Dify 服务器部署服务。
- 但可以找一台普通内网 Windows 电脑长期运行 Word 导出服务。

这台电脑可以不是 Dify 服务器，只要 Dify 服务器和使用者浏览器都能访问它。

## 包内文件

- `dify_workflow_内网单机导出服务版.yml`
  - 导入内网 Dify 的工作流 DSL。
  - 已按你提供的内网样例调整为 `version: 0.3.1`。
  - LLM 供应商格式使用 `langgenius/openai_api_compatible/openai_api_compatible`。
- `word_export_service.py`
  - Word 导出服务。
- `templates/`
  - 所有标准 Word 模板。
- `start_word_export_windows.bat`
  - Windows 启动脚本。
- `show_my_ip_windows.bat`
  - 查看本机内网 IP。
- `check_service_windows.bat`
  - 检查服务是否启动。
- `open_firewall_8123_admin.bat`
  - 放行 Windows 防火墙 8123 端口，可能需要管理员权限。

## 一、选择一台内网电脑

这台电脑要满足：

1. 能长期开机。
2. IP 尽量固定。
3. Dify 服务器能访问它的 `8123` 端口。
4. 使用 Dify 的人的浏览器也能访问它的 `8123` 端口。

例如这台电脑 IP 是：

```text
192.168.1.50
```

那么：

- Dify 工作流调用地址是：

```text
http://192.168.1.50:8123/api/export-word
```

- 用户下载 Word 地址是：

```text
http://192.168.1.50:8123/downloads/xxx.docx
```

## 二、安装 Python

在这台内网电脑安装 Python 3.10 或更高版本。

安装时必须勾选：

```text
Add Python to PATH
```

安装完成后打开命令行，检查：

```bat
python --version
```

或：

```bat
py -3 --version
```

## 三、查看本机 IP

双击：

```text
show_my_ip_windows.bat
```

记录和 Dify 同网段的 IPv4 地址。

## 四、启动 Word 导出服务

假设本机 IP 是 `192.168.1.50`，在当前目录命令行执行：

```bat
set WORD_EXPORT_PUBLIC_BASE_URL=http://192.168.1.50:8123
start_word_export_windows.bat
```

注意：

- 启动窗口不要关闭。
- 关闭窗口后，Dify 不能导出 Word。
- 生成文件会保存到 `outputs/word_exports/`。

## 五、放行防火墙

如果其他电脑访问不了：

```text
http://192.168.1.50:8123/health
```

右键运行：

```text
open_firewall_8123_admin.bat
```

选择“以管理员身份运行”。

## 六、检查服务

在服务电脑本机打开浏览器访问：

```text
http://127.0.0.1:8123/health
```

正常返回：

```json
{"status":"ok"}
```

在其他内网电脑浏览器访问：

```text
http://192.168.1.50:8123/health
```

也应该返回：

```json
{"status":"ok"}
```

## 七、修改 Dify DSL 里的 IP

导入 Dify 前，打开：

```text
dify_workflow_内网单机导出服务版.yml
```

搜索：

```text
http://内网电脑IP:8123/api/export-word
```

替换为真实 IP，例如：

```text
http://192.168.1.50:8123/api/export-word
```

然后保存。

## 八、导入内网 Dify

在 Dify 网页导入：

```text
dify_workflow_内网单机导出服务版.yml
```

导入后检查：

- 开始节点里有文书类型：
  - 行政处罚决定书
  - 检查笔录
  - 辨认笔录
  - 入所表
  - 前科证明
- `Word Export` 代码节点里的 `EXPORT_API` 已经是你的内网电脑 IP。

## 九、测试

上传一个 `.docx` 笔录，选择一种文书类型运行。

如果输出类似：

```text
[下载Word文档](http://192.168.1.50:8123/downloads/xxx.docx)
```

点击能下载，说明成功。

## 常见问题

### 1. Dify 输出 Word export failed

检查：

- 服务电脑是否开机。
- `start_word_export_windows.bat` 窗口是否还在运行。
- Dify DSL 里的 IP 是否写错。
- Dify 服务器是否能访问 `http://服务电脑IP:8123/health`。

### 2. 用户点击链接打不开

检查：

- `WORD_EXPORT_PUBLIC_BASE_URL` 是否设置成了真实内网 IP。
- Windows 防火墙是否放行 8123。
- 用户电脑是否能访问 `http://服务电脑IP:8123/health`。

### 3. 电脑 IP 变了

需要重新：

1. 用新 IP 启动服务。
2. 修改 Dify 工作流 `EXPORT_API`。
3. 重新发布工作流。

