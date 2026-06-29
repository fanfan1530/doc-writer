# 纯 Dify 文本版说明

文件：

```text
police_workflow_pure_dify_text_only.yml
```

用途：

- 只使用 Dify 内置节点。
- 不调用外部 Word 导出服务。
- 不调用 Docker。
- 不调用 Word 插件工具。
- 上传 `.docx` 笔录后，输出可复制的文书正文。

支持文书类型：

- 行政处罚决定书
- 检查笔录
- 辨认笔录
- 入所表
- 前科证明

重要限制：

- 不能生成 `.docx` 下载文件。
- 不能生成入所材料六份 Word 的 zip。
- 不能严格保留原 Word 模板版式。
- 检查笔录照片只能在正文中保留说明，不能生成照片页。

适用场景：

- 内网只能导入 Dify DSL。
- 不能部署后台服务。
- 不能使用 Docker。
- 不能使用外部工具节点。

导入方式：

1. 打开内网 Dify。
2. 选择导入 DSL。
3. 上传 `police_workflow_pure_dify_text_only.yml`。
4. 上传 Word 笔录，选择文书类型运行。
5. 复制输出正文到 Word 使用。

