智慧警务智能工作台 v2.0 — 离线部署包
========================================

系统概述
--------
基于 AI 大语言模型的公安文书智能编写系统，支持：
  - 文书生成：行政处罚决定书、勘验/检查笔录等
  - AI 助手：法律咨询、案由定性
  - 类案检索：语义搜索相似案例
  - 案件分析：要素提取 + 时间线可视化
  - 知识库：法律法规浏览检索

技术栈
--------
  后端: FastAPI + SQLAlchemy + ChromaDB + JWT
  前端: React 18 + TypeScript + Ant Design 5
  协议: OpenAI 兼容（支持 DeepSeek / 通义千问 / 自定义）

文件清单
--------
  app-source.tar.gz         后端源码 + 知识库数据
  frontend-dist.tar.gz      前端生产构建（静态文件）
  wheels.tar.gz.part-00~09  Python 依赖离线包（共10个分卷）
  deploy.bat                Windows 部署脚本
  deploy.sh                 Linux/Mac 部署脚本
  README.txt                本说明文件

部署要求
--------
  - Python 3.10+
  - 4GB+ 可用磁盘空间
  - （可选）Nginx 作为前端 Web 服务器
  - （可选）Redis（任务队列，不装则用内存队列）

Windows 部署
--------
  1. 确保已安装 Python 3.10+ 并添加到 PATH
  2. 双击运行 deploy.bat
  3. 等待自动完成
  4. 启动后端:
       cd app
       ..\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8091
  5. 前端静态文件在 frontend-dist/，用 Nginx 或直接开发服务器托管

Linux 部署
--------
  1. chmod +x deploy.sh && ./deploy.sh
  2. 启动: cd app && source ../venv/bin/activate && uvicorn app.main:app --host 0.0.0.0 --port 8091

首次配置
--------
  1. 浏览器访问 http://服务器IP:8091
  2. 默认账号: admin / admin123
  3. 进入「系统设置」→ 配置 LLM 模型 API 地址和 Key
  4. 切换到内网可用的模型后即可正常使用

注意事项
--------
  - 首次启动会自动构建 ChromaDB 向量索引（约30秒）
  - .env 文件中的 SECRET_KEY 部署后请修改为随机字符串
  - models.json 中已预配示例模型，部署后按需修改
  - SQLite 数据库位于 app/knowledge/data.db，定期备份

联系与反馈
--------
  版本: v2.0
  日期: 2026-05-27
