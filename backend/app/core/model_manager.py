"""模型管理器 —— 统一管理多厂商 LLM 模型配置和客户端创建。

支持运行时切换模型、配置 API Key，所有核心模块通过本管理器获取 LLM 客户端。
配置保存在 models.json，服务重启后保留。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.core.crypto import decrypt_api_key, encrypt_api_key
from app.core.dify_client import DifyClient
from app.core.llm_client import LLMClient


class ModelManager:
    """多厂商模型管理器（单例）。"""

    _instance: ModelManager | None = None

    def __new__(cls) -> ModelManager:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        self._config_path = (
            Path(__file__).resolve().parent.parent / "knowledge" / "models.json"
        )
        self._providers: list[dict[str, Any]] = []
        self._active_model_id: str = ""
        self._client: LLMClient | None = None
        self._client_config_hash: str = ""
        self._load()

    # ── 加载 / 保存 ──────────────────────────────────────

    def _load(self) -> None:
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}

        self._providers = data.get("providers", [])
        self._active_model_id = data.get("active_model_id", "")

        # 如果 JSON 无数据，尝试从数据库加载
        if not self._providers:
            self._try_load_from_db()

        # 向后兼容：旧配置无 api_type 则默认 openai
        for p in self._providers:
            p.setdefault("api_type", "openai")
        if not self._active_model_id and self._providers:
            self._active_model_id = self._providers[0]["id"]

        # 解密已存储的 API Key
        self._decrypt_keys()

    def _try_load_from_db(self) -> None:
        """JSON 为空时尝试从数据库恢复配置。"""
        try:
            import asyncio
            from app.infrastructure.database import AsyncSessionLocal
            from app.infrastructure.models import ModelConfig
            from sqlalchemy import select

            async def _load():
                async with AsyncSessionLocal() as db:
                    result = await db.execute(select(ModelConfig))
                    rows = result.scalars().all()
                    if rows:
                        self._providers = [
                            {
                                "id": r.id,
                                "name": r.name,
                                "provider": r.provider,
                                "base_url": r.base_url,
                                "model_name": r.model_name,
                                "model_name_large": r.model_name_large,
                                "api_key": r.api_key,
                                "api_type": r.api_type,
                                "requires_key": r.requires_key,
                                "temperature": r.temperature,
                                "max_tokens": r.max_tokens,
                                "system_prompt": r.system_prompt,
                            }
                            for r in rows
                        ]
                        active = [r for r in rows if r.is_active]
                        self._active_model_id = active[0].id if active else (
                            self._providers[0]["id"] if self._providers else ""
                        )
                        self._decrypt_keys()

            try:
                loop = asyncio.get_running_loop()
                # 在运行中的事件循环中，用 create_task
                import concurrent.futures
                future = asyncio.run_coroutine_threadsafe(_load(), loop)
                future.result(timeout=5)
            except RuntimeError:
                asyncio.run(_load())
        except Exception:
            pass

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "active_model_id": self._active_model_id,
                    "providers": self._encrypted_providers(),
                },
                f,
                ensure_ascii=False,
                indent=2,
            )
        # 异步同步到数据库（不阻塞主流程）
        self._schedule_db_sync()

    def _schedule_db_sync(self) -> None:
        """尝试将当前配置同步到数据库（仅在事件循环运行时）。"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._sync_to_db())
        except RuntimeError:
            pass  # 无事件循环运行，跳过 DB 同步

    async def _sync_to_db(self) -> None:
        """将内存中的 providers 同步到数据库（API Key 加密存储）。"""
        try:
            from app.infrastructure.database import AsyncSessionLocal
            from app.infrastructure.models import ModelConfig

            async with AsyncSessionLocal() as db:
                from sqlalchemy import select
                result = await db.execute(select(ModelConfig.id))
                existing_ids = set(result.scalars().all())

                for p in self._providers:
                    pid = p["id"]
                    encrypted_key = encrypt_api_key(p.get("api_key", ""))
                    if pid in existing_ids:
                        stmt = select(ModelConfig).where(ModelConfig.id == pid)
                        r = await db.execute(stmt)
                        m = r.scalar_one_or_none()
                        if m:
                            m.name = p.get("name", "")
                            m.provider = p.get("provider", "自定义")
                            m.base_url = p.get("base_url", "")
                            m.model_name = p.get("model_name", "")
                            m.model_name_large = p.get("model_name_large", "")
                            m.api_key = encrypted_key
                            m.api_type = p.get("api_type", "openai")
                            m.is_active = p["id"] == self._active_model_id
                    else:
                        db.add(ModelConfig(
                            id=pid,
                            name=p.get("name", ""),
                            provider=p.get("provider", "自定义"),
                            base_url=p.get("base_url", ""),
                            model_name=p.get("model_name", ""),
                            model_name_large=p.get("model_name_large", ""),
                            api_key=encrypted_key,
                            api_type=p.get("api_type", "openai"),
                            is_active=p["id"] == self._active_model_id,
                        ))
                await db.commit()
        except Exception:
            pass  # DB 同步失败不影响主流程

    # ── 加解密辅助 ────────────────────────────────────────

    def _decrypt_keys(self) -> None:
        """解密内存中所有 provider 的 API Key。"""
        for p in self._providers:
            key = p.get("api_key", "")
            if key:
                p["api_key"] = decrypt_api_key(key)

    def _encrypted_providers(self) -> list[dict[str, Any]]:
        """返回 API Key 已加密的 providers 列表（用于持久化）。"""
        result: list[dict[str, Any]] = []
        for p in self._providers:
            item = dict(p)
            key = item.get("api_key", "")
            if key:
                item["api_key"] = encrypt_api_key(key)
            result.append(item)
        return result

    # ── 查询方法 ─────────────────────────────────────────

    def list_models(self) -> list[dict[str, Any]]:
        """返回所有可用模型列表（API Key 脱敏）。"""
        result: list[dict[str, Any]] = []
        for p in self._providers:
            item = dict(p)
            api_key = item.get("api_key", "")
            item["has_api_key"] = bool(api_key)
            # 脱敏：仅显示 key 的前4位和后4位
            if api_key and len(api_key) > 8:
                item["api_key"] = api_key[:4] + "****" + api_key[-4:]
            elif api_key:
                item["api_key"] = "****"
            item["is_active"] = item["id"] == self._active_model_id
            result.append(item)
        return result

    def get_active_config(self) -> dict[str, Any]:
        """返回当前激活的模型配置（不含脱敏）。"""
        for p in self._providers:
            if p["id"] == self._active_model_id:
                return dict(p)
        if self._providers:
            return dict(self._providers[0])
        return {}

    def get_temperature(self) -> float:
        """获取当前模型的推荐 temperature。"""
        return self.get_active_config().get("temperature", 0.1)

    def get_max_tokens(self) -> int:
        """获取当前模型的推荐 max_tokens。"""
        return self.get_active_config().get("max_tokens", 4096)

    def get_system_prompt(self) -> str:
        """获取当前模型的系统提示词。"""
        return self.get_active_config().get("system_prompt", "")

    # ── 客户端获取 ───────────────────────────────────────

    def get_client(self) -> "LLMClient | DifyClient":
        """获取当前激活模型的客户端。

        客户端会缓存，仅当模型配置发生变化时才重建。
        """
        config = self.get_active_config()
        config_hash = f"{config.get('api_type', 'openai')}|{config.get('base_url', '')}|{config.get('api_key', '')}"

        if self._client is None or self._client_config_hash != config_hash:
            base_url = config.get("base_url", "")
            api_key = config.get("api_key", "")
            api_type = config.get("api_type", "openai")
            if not base_url:
                raise ValueError(f"模型 '{config.get('name', '')}' 未配置 base_url")
            if api_type == "dify":
                self._client = DifyClient(
                    base_url=base_url,
                    api_key=api_key or "sk-local",
                    timeout=90,
                )
            else:
                self._client = LLMClient(
                    api_type=api_type,
                    base_url=base_url,
                    api_key=api_key or "sk-local",
                    timeout=90,
                )
            self._client_config_hash = config_hash

        return self._client

    # ── 切换模型 ─────────────────────────────────────────

    def switch_model(self, model_id: str) -> dict[str, Any]:
        """切换到指定模型。"""
        found = False
        for p in self._providers:
            if p["id"] == model_id:
                found = True
                break
        if not found:
            raise ValueError(f"模型 '{model_id}' 不存在")

        self._active_model_id = model_id
        self._client = None  # 清除客户端缓存，下次获取时重建
        self._client_config_hash = ""
        self._save()
        return self.get_active_config()

    # ── 配置模型 ─────────────────────────────────────────

    def save_model_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """保存或更新模型配置（含 API Key）。"""
        model_id = config.get("id", "")

        if model_id:
            # 更新已有模型
            for i, p in enumerate(self._providers):
                if p["id"] == model_id:
                    # 如果用户未填写 API Key，保留已有 Key
                    merged = {**config}
                    if not merged.get("api_key") and p.get("api_key"):
                        merged["api_key"] = p["api_key"]
                    self._providers[i] = {**p, **merged}
                    self._save()
                    # 如果更新的是当前激活模型，清除客户端缓存
                    if model_id == self._active_model_id:
                        self._client = None
                        self._client_config_hash = ""
                    return dict(self._providers[i])
            raise ValueError(f"模型 '{model_id}' 不存在")
        else:
            # 新增自定义模型
            custom_nums = []
            for p in self._providers:
                if p['id'].startswith('custom-'):
                    try:
                        custom_nums.append(int(p['id'].split('-')[1]))
                    except ValueError:
                        pass
            next_num = max(custom_nums, default=0) + 1
            new_id = f"custom-{next_num}"
            new_config = {
                "id": new_id,
                "name": config.get("name", "自定义模型"),
                "provider": config.get("provider", "自定义"),
                "base_url": config.get("base_url", ""),
                "model_name": config.get("model_name", ""),
                "model_name_large": config.get("model_name_large", ""),
                "api_key": config.get("api_key", ""),
                "api_type": config.get("api_type", "openai"),
                "requires_key": config.get("requires_key", True),
                "temperature": config.get("temperature", 0.1),
                "max_tokens": config.get("max_tokens", 4096),
                "system_prompt": config.get("system_prompt", ""),
            }
            self._providers.append(new_config)
            self._save()
            return new_config

    # ── 测试连接 ─────────────────────────────────────────

    async def test_connection(self, config: dict[str, Any]) -> dict[str, Any]:
        """测试模型连通性（用标准库 urllib，不依赖 SDK/httpx，绕过代理）。"""
        import json
        import ssl
        import urllib.request
        import urllib.error

        base_url = config.get("base_url", "").rstrip("/")
        api_key = config.get("api_key", "")
        model_name = config.get("model_name", "")
        api_type = config.get("api_type", "openai")

        if not base_url:
            return {"success": False, "message": "未配置 Base URL"}

        # Dify 工作流模式
        if api_type == "dify":
            url = base_url + "/workflows/run"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key or 'sk-local'}",
            }
            body = json.dumps({
                "inputs": {"prompt": "Hi", "system_prompt": ""},
                "response_mode": "blocking",
                "user": "doc-writer",
            }).encode("utf-8")

            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE

            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            try:
                resp = urllib.request.urlopen(req, timeout=15, context=ssl_ctx)
                data = json.loads(resp.read().decode("utf-8"))
                wf_data = data.get("data", {})
                if wf_data.get("status") == "succeeded":
                    return {"success": True, "message": "Dify 工作流连接成功"}
                elif wf_data.get("status") == "failed":
                    err = wf_data.get("error", "工作流执行失败")
                    return {"success": True, "message": f"Dify 连接成功（工作流提示: {err[:100]}）"}
                return {"success": True, "message": "Dify 连接成功"}
            except urllib.error.HTTPError as e:
                if e.code == 401:
                    return {"success": False, "message": "Dify API Key 无效"}
                if e.code == 400 or e.code == 422:
                    detail = e.read().decode("utf-8", errors="replace")[:200]
                    return {"success": True, "message": f"Dify 连接成功（请检查工作流配置: {detail}）"}
                detail = e.read().decode("utf-8", errors="replace")[:300]
                return {"success": False, "message": f"HTTP {e.code}: {detail}"}
            except urllib.error.URLError as e:
                return {"success": False, "message": f"网络不通: {e.reason}"}
            except Exception as e:
                return {"success": False, "message": f"连接失败: {str(e)[:200]}"}

        if not model_name:
            return {"success": False, "message": "未配置模型名称"}

        # 构建请求
        if api_type == "anthropic":
            url = base_url + "/messages"
            headers = {
                "Content-Type": "application/json",
                "x-api-key": api_key or "sk-local",
                "anthropic-version": "2023-06-01",
            }
            body = json.dumps({
                "model": model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }).encode("utf-8")
        else:
            url = base_url + "/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key or 'sk-local'}",
            }
            body = json.dumps({
                "model": model_name,
                "messages": [{"role": "user", "content": "Hi"}],
                "max_tokens": 5,
            }).encode("utf-8")

        # SSL: 允许内网自签证书
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, data=body, headers=headers, method="POST")

        try:
            resp = urllib.request.urlopen(
                req, timeout=15, context=ssl_ctx,
            )
            data = json.loads(resp.read().decode("utf-8"))
            if api_type == "anthropic":
                model_used = data.get("model", "unknown")
            else:
                model_used = data.get("model", "unknown")
            return {"success": True, "message": f"连接成功 (模型: {model_used})"}
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")[:300]
            return {"success": False, "message": f"HTTP {e.code}: {detail}"}
        except urllib.error.URLError as e:
            return {"success": False, "message": f"网络不通: {e.reason}"}
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)[:200]}"}
