"""模型管理器 —— 统一管理多厂商 LLM 模型配置和客户端创建。

支持运行时切换模型、配置 API Key，所有核心模块通过本管理器获取 LLM 客户端。
配置保存在 models.json，服务重启后保留。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI


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
        self._client: AsyncOpenAI | None = None
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
        if not self._active_model_id and self._providers:
            self._active_model_id = self._providers[0]["id"]

    def _save(self) -> None:
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "active_model_id": self._active_model_id,
                    "providers": self._providers,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

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

    def get_client(self) -> "AsyncOpenAI":
        """获取当前激活模型的 AsyncOpenAI 客户端。

        客户端会缓存，仅当模型配置发生变化时才重建。
        """
        config = self.get_active_config()
        config_hash = f"{config.get('base_url', '')}|{config.get('api_key', '')}"

        if self._client is None or self._client_config_hash != config_hash:
            base_url = config.get("base_url", "")
            api_key = config.get("api_key", "")
            if not base_url:
                raise ValueError(f"模型 '{config.get('name', '')}' 未配置 base_url")
            self._client = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key or "sk-local",
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
        """测试模型连通性。"""
        base_url = config.get("base_url", "")
        api_key = config.get("api_key", "")
        model_name = config.get("model_name", "")

        if not base_url:
            return {"success": False, "message": "未配置 Base URL"}
        if not model_name:
            return {"success": False, "message": "未配置模型名称"}

        try:
            client = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key or "sk-local",
                timeout=15,
            )
            response = await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=5,
                temperature=0,
            )
            return {
                "success": True,
                "message": f"连接成功 (模型: {response.model})",
            }
        except Exception as e:
            return {"success": False, "message": f"连接失败: {str(e)[:200]}"}
