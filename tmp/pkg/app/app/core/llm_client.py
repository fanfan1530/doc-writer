"""统一 LLM 客户端 —— 封装 OpenAI 兼容 API 和 Anthropic Messages API。"""

from __future__ import annotations

import logging

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _make_http_client(timeout: float) -> httpx.AsyncClient:
    """创建不依赖系统代理的 httpx 客户端，避免企业代理干扰内网 API 直连。"""
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=15.0),
        trust_env=False,  # 忽略 HTTP_PROXY / HTTPS_PROXY 环境变量
    )


class LLMClient:
    """协议无关的 LLM 客户端，根据 api_type 选择合适的 SDK。"""

    def __init__(
        self,
        api_type: str = "openai",
        base_url: str = "",
        api_key: str = "",
        timeout: float = 90,
    ) -> None:
        self._api_type = api_type
        http_client = _make_http_client(timeout)

        if api_type == "anthropic":
            from anthropic import AsyncAnthropic

            self._anthropic = AsyncAnthropic(
                base_url=base_url,
                api_key=api_key or "sk-local",
                timeout=timeout,
                http_client=http_client,
            )
            self._openai = None
        else:
            self._openai = AsyncOpenAI(
                base_url=base_url,
                api_key=api_key or "sk-local",
                timeout=timeout,
                http_client=http_client,
            )
            self._anthropic = None

    async def chat(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: float = 90,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
    ) -> str | dict:
        """发送聊天请求，返回模型响应文本或工具调用 dict。"""
        if self._api_type == "anthropic":
            return await self._chat_anthropic(
                model=model, messages=messages, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout, tools=tools,
            )
        return await self._chat_openai(
            model=model, messages=messages, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout, tools=tools, tool_choice=tool_choice,
        )

    async def _chat_openai(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        timeout: float,
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
    ) -> str | dict:
        kwargs: dict = dict(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens, timeout=timeout,
        )
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = tool_choice

        response = await self._openai.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        if msg.tool_calls:
            return {
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in msg.tool_calls
                ],
                "content": msg.content,
            }
        return msg.content or ""

    async def chat_stream(
        self,
        *,
        model: str,
        messages: list[dict],
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout: float = 90,
        tools: list[dict] | None = None,
    ):
        """流式聊天，yield 每个 chunk 文本 或 tool_call delta。

        当 tools 不为空时，yield 格式为:
          {"type": "chunk", "text": "..."}   — 文本片段
          {"type": "tool_call", "id": "...", "name": "...", "arguments": "..."}  — 工具调用增量
          {"type": "done"}  — 流结束

        当 tools 为空时，直接 yield 字符串（向后兼容）。
        """
        if self._api_type == "anthropic":
            async for chunk in self._chat_anthropic_stream(
                model=model, messages=messages, temperature=temperature,
                max_tokens=max_tokens, timeout=timeout,
            ):
                yield chunk
            return

        kwargs: dict = dict(
            model=model, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
            timeout=timeout, stream=True, stream_options={"include_usage": True},
        )
        if tools:
            kwargs["tools"] = [{"type": "function", "function": t} for t in tools]
            kwargs["tool_choice"] = "auto"

        response = await self._openai.chat.completions.create(**kwargs)

        if not tools:
            async for chunk in response:
                choice = chunk.choices[0] if chunk.choices else None
                if choice and choice.delta and choice.delta.content:
                    yield choice.delta.content
            return

        # 带工具的流式：解析 tool_call delta
        tool_calls_acc: dict[int, dict] = {}  # index -> {id, name, arguments}
        async for chunk in response:
            choice = chunk.choices[0] if chunk.choices else None
            if not choice:
                continue
            delta = choice.delta
            if delta and delta.content:
                yield {"type": "chunk", "text": delta.content}
            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": tc.id or "", "name": "", "arguments": ""}
                    acc = tool_calls_acc[idx]
                    if tc.id:
                        acc["id"] = tc.id
                    if tc.function and tc.function.name:
                        acc["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        acc["arguments"] += tc.function.arguments
                        yield {
                            "type": "tool_call",
                            "id": acc["id"],
                            "name": acc["name"],
                            "arguments": acc["arguments"],
                        }
        yield {"type": "done"}

    async def _chat_anthropic_stream(
        self, model: str, messages: list[dict],
        temperature: float, max_tokens: int, timeout: float,
    ):
        system_prompt = ""
        user_msgs: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            else:
                user_msgs.append({"role": msg["role"], "content": msg["content"]})

        safe_temp = temperature if temperature > 0 else 0.01
        async with self._anthropic.messages.stream(
            model=model, max_tokens=max_tokens,
            system=system_prompt if system_prompt else None,
            temperature=safe_temp, messages=user_msgs, timeout=timeout,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def _chat_anthropic(
        self,
        model: str,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        timeout: float,
        tools: list[dict] | None = None,
    ) -> str | dict:
        system_prompt = ""
        user_messages: list[dict] = []
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
            elif msg.get("role") == "tool":
                user_messages.append({"role": "user", "content": f"[工具结果] {msg.get('content', '')}"})
            elif msg.get("content") is not None:
                user_messages.append({"role": msg["role"], "content": msg["content"]})

        if user_messages and user_messages[0].get("role") != "user":
            filtered = []
            for m in user_messages:
                if not filtered and m["role"] != "user":
                    continue
                filtered.append(m)
            user_messages = filtered
        if not user_messages:
            user_messages = [{"role": "user", "content": "Hi"}]

        safe_temp = temperature if temperature > 0 else 0.01
        kwargs: dict = dict(
            model=model, max_tokens=max_tokens,
            system=system_prompt if system_prompt else None,
            temperature=safe_temp, messages=user_messages, timeout=timeout,
        )
        if tools:
            kwargs["tools"] = tools

        response = await self._anthropic.messages.create(**kwargs)
        # Check for tool use
        for block in response.content:
            if hasattr(block, "type") and block.type == "tool_use":
                return {
                    "tool_calls": [],
                    "content": response.content[0].text if hasattr(response.content[0], "text") else "",
                }
        parts = []
        for block in response.content:
            if hasattr(block, "text"):
                parts.append(block.text)
        return "".join(parts) or ""
