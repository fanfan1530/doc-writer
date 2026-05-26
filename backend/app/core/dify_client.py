"""Dify Workflow API 客户端 —— 通过 Dify 工作流替代直连 LLM API。"""

from __future__ import annotations

import json
import logging

import httpx

from app.core.llm_client import _make_http_client

logger = logging.getLogger(__name__)


class DifyClient:
    """Dify Workflow API 客户端，提供与 LLMClient 相同的 chat() 接口。"""

    def __init__(
        self,
        base_url: str = "",
        api_key: str = "",
        timeout: float = 90,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http_client = _make_http_client(timeout)
        self._workflow_endpoint = f"{self._base_url}/workflows/run"

    async def chat(
        self,
        *,
        model: str = "",
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: float = 90,
    ) -> str:
        """调用 Dify 工作流，返回响应文本。

        Dify 工作流期望的 inputs:
          - prompt: 完整的用户提示词
          - system_prompt: 系统指令（可选）
          - temperature: 温度参数（可选）
          - max_tokens: 最大 token 数（可选）
        """
        system_prompt = ""
        user_parts: list[str] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                user_parts.append(msg.get("content", ""))

        prompt = "\n\n".join(user_parts)

        body = {
            "inputs": {
                "prompt": prompt,
                "system_prompt": system_prompt,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            "response_mode": "blocking",
            "user": "doc-writer",
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        response = await self._http_client.post(
            self._workflow_endpoint,
            json=body,
            headers=headers,
            timeout=httpx.Timeout(timeout, connect=15.0),
        )

        if response.status_code != 200:
            detail = response.text[:300]
            logger.error("Dify 工作流调用失败 HTTP %d: %s", response.status_code, detail)
            raise RuntimeError(f"Dify 工作流调用失败 (HTTP {response.status_code}): {detail}")

        data = response.json()
        workflow_data = data.get("data", {})
        status = workflow_data.get("status", "")

        if status == "failed":
            error_msg = workflow_data.get("error", "未知错误")
            logger.error("Dify 工作流执行失败: %s", error_msg)
            raise RuntimeError(f"Dify 工作流执行失败: {error_msg}")

        outputs = workflow_data.get("outputs", {})
        text = outputs.get("text", "")
        if not text and outputs:
            text = json.dumps(outputs, ensure_ascii=False)
        return text

    async def close(self) -> None:
        await self._http_client.aclose()
