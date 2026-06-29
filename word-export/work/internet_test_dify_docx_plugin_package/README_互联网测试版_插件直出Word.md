# 互联网测试版：Dify 插件直出 Word

文件：

```text
police_workflow_inner_direct_word.yml
```

这个版本参考你给的 `第二题.yml`，使用同一个 Dify 插件：

```text
stvlynn/doc:0.0.1
```

工具：

```text
markdown_to_docx_converter
```

## 功能

- 上传 Word 笔录
- 选择文书类型
- 生成文书正文
- 通过 Dify 插件直接转成 Word 文件
- 结束节点输出 `files: array[file]`

## 支持文书类型

- 行政处罚决定书
- 检查笔录
- 辨认笔录
- 入所表
- 前科证明

## 限制

这个版本是“先看效果”的测试版：

- 可以直接在 Dify 输出 Word 文件
- 不调用外部 `8123` 服务
- 不需要 Docker
- 不需要单台电脑后台服务
- 但不能严格套用原始 `.docx` 模板版式
- 不能生成入所材料 6 份原模板 zip
- 检查照片页不能按之前模板严格排版

## 导入要求

Dify 环境需要已经安装：

```text
stvlynn/doc:0.0.1
```

如果导入后提示依赖缺失，需要先在插件市场安装这个插件，或者让管理员安装。

