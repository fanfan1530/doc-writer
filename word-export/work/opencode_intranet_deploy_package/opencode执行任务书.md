# OpenCode 执行任务书

你正在配置一套 Dify 警务文书工作流的内网单机部署环境。

## 目标

把当前 zip 解压后的内容配置成：

1. 一台内网 Windows 电脑上能启动 Word 导出服务。
2. 这台电脑的 IP 能写入 Dify DSL。
3. 内网 Dify 网页导入 DSL 后，能直接使用 Word 导出功能。

## 约束

- 不依赖公网。
- 不依赖 Docker。
- 不手工安装第三方 Python 包。
- 只能使用 zip 里的文件。
- 如需修改 DSL，只改导出地址占位符。

## 执行顺序

### 第一步：检查包内容

确认以下文件存在：

- `dify_workflow_内网单机导出服务版.yml`
- `service\word_export_service.py`
- `service\templates\`
- `01_prepare_runtime_windows.bat`
- `02_show_ip_windows.bat`
- `03_configure_dify_dsl_ip_windows.bat`
- `04_start_word_export_windows.bat`
- `05_check_service_windows.bat`
- `06_open_firewall_8123_admin.bat`
- `07_install_startup_task_admin.bat`

### 第二步：准备运行时

双击或执行：

```bat
01_prepare_runtime_windows.bat
```

这个脚本会解压包内 Python 运行时。

### 第三步：获取服务电脑 IP

双击或执行：

```bat
02_show_ip_windows.bat
```

选择一个固定内网 IPv4 地址。

### 第四步：配置 DSL

执行：

```bat
03_configure_dify_dsl_ip_windows.bat
```

输入这台 Word 导出服务电脑的内网 IP。

生成文件：

```text
dify_workflow_内网单机导出服务版_已配置IP.yml
```

### 第五步：启动 Word 导出服务

先确保服务电脑 IP 已写入 `service_ip.txt`，然后执行：

```bat
04_start_word_export_windows.bat
```

要求：

- 保持窗口打开。
- 如果启动失败，检查 `runtime\python-3.12.10-embed-amd64\python.exe` 是否存在。

### 第六步：放行防火墙

如果其他内网机器访问不了 `8123` 端口，执行：

```bat
06_open_firewall_8123_admin.bat
```

### 第七步：检查健康状态

执行：

```bat
05_check_service_windows.bat
```

确认返回：

```json
{"status":"ok"}
```

### 第八步：导入 Dify

把这个文件导入内网 Dify：

```text
dify_workflow_内网单机导出服务版_已配置IP.yml
```

导入后检查：

- 文书类型包含：
  - 行政处罚决定书
  - 检查笔录
  - 辨认笔录
  - 入所表
  - 前科证明
- `Word Export` 节点里的 `EXPORT_API` 已替换为服务电脑 IP。

### 第九步：必要时设置开机自启

如果需要开机自动启动，执行：

```bat
07_install_startup_task_admin.bat
```

该脚本会创建登录自启任务 `DifyWordExport`。

## 验收标准

1. 打开 `http://服务电脑IP:8123/health` 返回 `{"status":"ok"}`。
2. Dify 导入 DSL 成功。
3. 在 Dify 中运行工作流后能生成 Word 下载链接。
4. 点击下载链接能下载 Word 文件。

