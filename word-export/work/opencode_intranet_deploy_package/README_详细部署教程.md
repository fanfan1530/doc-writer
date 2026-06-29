# Dify 警务文书工作流内网部署教程

## 一、这个包解决什么问题

这个包用于在一台普通内网 Windows 电脑上运行 Word 导出服务，然后让统一部署的内网 Dify 调用它。

优点：

- 不需要改 Dify 服务器。
- 不需要在 Dify 服务器装 Docker。
- Dify 网页导入 DSL 后即可使用。
- 保留严格 Word 模板能力。

## 二、工作原理

```text
Dify 工作流
  -> 调用 http://服务电脑IP:8123/api/export-word
  -> Word 导出服务按模板生成 docx/zip
  -> 返回 http://服务电脑IP:8123/downloads/xxx.docx
  -> 用户浏览器点击下载
```

所以必须保证两件事：

1. Dify 服务器能访问 `http://服务电脑IP:8123/api/export-word`
2. 用户电脑能访问 `http://服务电脑IP:8123/downloads/...`

## 三、部署步骤

### 1. 解压 zip

把整个 zip 解压到一台内网 Windows 电脑，例如：

```text
D:\dify-word-export
```

### 2. 准备 Python 运行时

双击：

```text
01_prepare_runtime_windows.bat
```

该脚本会解压包内 Python 运行时，不需要联网安装 Python。

### 3. 查看本机 IP

双击：

```text
02_show_ip_windows.bat
```

记下内网 IP，例如：

```text
192.168.1.50
```

### 4. 生成已配置 IP 的 Dify DSL

双击：

```text
03_configure_dify_dsl_ip_windows.bat
```

输入：

```text
192.168.1.50
```

会生成：

```text
dify_workflow_内网单机导出服务版_已配置IP.yml
```

### 5. 启动 Word 导出服务

双击：

```text
04_start_word_export_windows.bat
```

看到类似内容：

```text
Word export service listening on http://localhost:8123
```

保持窗口打开。

### 6. 放行防火墙

如果其他电脑访问不了：

```text
http://192.168.1.50:8123/health
```

右键管理员运行：

```text
06_open_firewall_8123_admin.bat
```

### 7. 检查服务

双击：

```text
05_check_service_windows.bat
```

正常输出：

```json
{"status":"ok"}
```

也可以在其他内网电脑浏览器打开：

```text
http://192.168.1.50:8123/health
```

### 8. 导入 Dify

在内网 Dify 网页导入：

```text
dify_workflow_内网单机导出服务版_已配置IP.yml
```

导入后确认：

- 开始节点文书类型包含：
  - 行政处罚决定书
  - 检查笔录
  - 辨认笔录
  - 入所表
  - 前科证明
- `Word Export` 节点代码中：

```python
EXPORT_API = 'http://192.168.1.50:8123/api/export-word'
```

### 9. 测试

上传一个 `.docx` 笔录文件，选择文书类型运行。

如果看到：

```text
[下载Word文档](http://192.168.1.50:8123/downloads/xxx.docx)
```

点击能下载，就部署成功。

## 四、开机自动启动

如果需要每次登录 Windows 后自动启动，右键管理员运行：

```text
07_install_startup_task_admin.bat
```

任务名称：

```text
DifyWordExport
```

## 五、常见问题

### Dify 显示 Word export failed

检查：

- `04_start_word_export_windows.bat` 是否还在运行。
- Dify DSL 里的 IP 是否正确。
- Dify 服务器能否访问 `http://服务电脑IP:8123/health`。
- 服务电脑防火墙是否放行 8123。

### 本机能访问，其他电脑不能访问

通常是防火墙问题。运行：

```text
06_open_firewall_8123_admin.bat
```

### 点击下载链接打不开

检查启动服务时使用的 IP 是否正确。

如果 `WORD_EXPORT_PUBLIC_BASE_URL` 是 `127.0.0.1`，其他电脑一定打不开。应改成：

```text
http://服务电脑IP:8123
```

### 电脑 IP 变化

重新运行：

```text
03_configure_dify_dsl_ip_windows.bat
```

再把新生成的 DSL 导入或覆盖到 Dify。

