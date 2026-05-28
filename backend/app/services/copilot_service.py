"""AI Copilot 服务 —— 工具调用编排 + SSE 流式响应。"""

from __future__ import annotations
import asyncio
import json
import logging
import time
from typing import Any, AsyncGenerator

from app.core.tools import TOOL_DEFINITIONS, ToolExecutor
from app.core.llm_client import LLMClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_DETAILED = """你是一名资深公安法制审核专家，服务于一线民警的日常警务工作，精通刑法、治安管理处罚法、刑事诉讼法、公安机关办理案件程序规定等法律法规。

## 可用工具
1. search_laws —— 检索法律条文（刑法、治安管理处罚法等），返回具体法条全文
2. search_procedures —— 检索办案程序规定（办案期限、审批流程、证据规则等）
3. generate_document —— 根据案情自动生成公安法律文书（笔录、处罚决定书等）
4. polish_document —— 根据指令修改/润色指定的文书内容
5. check_deadlines —— 检查案件的法定办案期限是否超期
6. analyze_case_nature —— 分析案件属于行政违法、刑事犯罪还是民事纠纷
7. evidence_checklist —— 根据案件类型推荐证据收集清单和取证要点
8. penalty_reference —— 查询特定违法行为的处罚种类、幅度和裁量标准

## 工作原则（必须严格遵守）
- **强制工具使用**：凡是涉及法律条文、办案程序、处罚标准、案件定性、证据指引的问题，必须调用对应工具获取权威信息后再回答，禁止仅凭训练数据直接作答
- **法条引用**：引用法律条文时必须标注法律名称全称、条款编号和具体内容，不得编造或模糊引用
- **回答结构**：先给出结论要点，再展开法律依据和分析，最后给出实务建议
- **专业性**：使用规范的公安法律术语，保持严谨、准确、简洁的文风
- **诚实边界**：对于超出知识范围或工具无法解决的问题，明确告知并建议咨询法制部门
- **文书处理**：生成或修改文书后，完整输出文书全文，不要省略任何部分
- **上下文利用**：如果当前对话关联了文书全文（doc_context），修改文书时必须使用 polish_document 工具"""

SYSTEM_PROMPT_CONCISE = """你是一名随叫随到的公安法制助手，服务于正在一线办案的民警，精通刑法、治安管理处罚法、刑事诉讼法等法律法规。办案时间宝贵，你必须用最短的篇幅给出最直接的答案。

## 可用工具
1. search_laws —— 检索法律条文
2. search_procedures —— 检索办案程序规定
3. generate_document —— 根据案情自动生成文书
4. polish_document —— 修改/润色文书内容
5. check_deadlines —— 检查法定办案期限
6. analyze_case_nature —— 分析案件性质
7. evidence_checklist —— 推荐证据收集清单
8. penalty_reference —— 查询处罚种类和幅度

## 工作原则（必须严格遵守）
- **强制工具使用**：涉及法律条文、程序、处罚、定性、证据的问题，必须调用工具获取权威信息后再回答
- **极简回答**：直接给出结论和关键依据，不展开长篇分析，不主动提供无关的延伸建议
- **结合案情**：优先针对当前案件/文书的具体情况作答，不做泛泛的法律科普
- **法条用法**：只引用与本案直接相关的条款原文，无需逐条全文罗列
- **格式**：优先使用要点列表（bullet points），而非段落叙述。每条不超过两行
- **文书处理**：生成或修改文书后完整输出全文，不得省略"""


class CopilotService:
    """警务 AI 副驾驶服务。"""

    def __init__(
        self,
        model_manager: "ModelManager | None" = None,
        rag_retriever: "RAGRetriever | None" = None,
        doc_service: "DocumentService | None" = None,
    ):
        self._model_manager = model_manager
        self._tools = ToolExecutor(rag_retriever=rag_retriever, doc_service=doc_service)
        self._doc = doc_service

    # ── 客户端/模型参数 ───────────────────────────────────

    def _get_client(self) -> LLMClient:
        if self._model_manager:
            return self._model_manager.get_client()
        from app.config import get_settings
        settings = get_settings()
        return LLMClient(
            api_type="openai",
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key.get_secret_value() or "sk-local",
        )

    def _get_model_name(self) -> str:
        if self._model_manager:
            return self._model_manager.get_active_config().get("model_name", "")
        from app.config import get_settings
        return get_settings().llm_model_small

    # ── 核心流式对话 ──────────────────────────────────────

    async def stream_chat(
        self,
        user_message: str,
        history: list[dict] | None = None,
        doc_context: str = "",
        mode: str = "concise",
    ) -> AsyncGenerator[str, None]:
        """SSE 流式对话生成器。mode: 'concise' | 'detailed'"""
        t0 = time.time()
        is_concise = mode == "concise"

        # 构建消息
        system_prompt = SYSTEM_PROMPT_CONCISE if is_concise else SYSTEM_PROMPT_DETAILED
        messages = [{"role": "system", "content": system_prompt}]

        if doc_context:
            messages.append({
                "role": "system",
                "content": f"当前文书全文（用户可能会要求修改此文书）：\n---\n{doc_context}\n---",
            })

        if history:
            messages.extend(history)

        messages.append({"role": "user", "content": user_message})

        model = self._get_model_name()
        client = self._get_client()

        # 第一轮：让 LLM 决定是否调用工具
        yield self._sse("thinking", {"message": "正在分析您的问题..."})

        try:
            # 先用非流式调用检查是否需要工具
            tool_response = await client.chat(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=512,
                tools=TOOL_DEFINITIONS,
                tool_choice="auto",
                timeout=60,
            )
        except Exception as e:
            logger.warning("LLM 工具选择失败: %s", str(e)[:100])
            yield self._sse("error", {"message": "AI 服务暂时不可用，请稍后重试"})
            yield self._sse("done", {"elapsed_ms": int((time.time() - t0) * 1000)})
            return

        # 多轮工具调用循环（最多 3 轮，让 LLM 可以基于工具结果继续调用其他工具）
        MAX_TOOL_ROUNDS = 3
        all_tool_calls: list[dict] = []

        for round_num in range(MAX_TOOL_ROUNDS):
            tool_calls = self._parse_tool_calls(tool_response)

            if not tool_calls:
                break

            all_tool_calls.extend(tool_calls)
            tool_names = [tc["name"] for tc in tool_calls]
            yield self._sse("thinking", {
                "message": f"正在{'并行' if len(tool_calls) > 1 else ''}调用: {', '.join(tool_names)}..."
                + (f" (第{round_num + 1}轮)" if round_num > 0 else ""),
            })

            # 通知前端所有工具调用
            for tc in tool_calls:
                yield self._sse("tool_call", {"tool": tc["name"], "args": tc.get("arguments", {})})

            # 并行执行
            async def _exec_one(tc: dict) -> tuple:
                return tc["name"], await self._tools.execute(tc["name"], tc.get("arguments", {}))

            results = await asyncio.gather(
                *[_exec_one(tc) for tc in tool_calls], return_exceptions=True,
            )

            # 按序 yield 结果并构建 tool role messages
            tool_msgs: list[dict] = []
            for tc, res in zip(tool_calls, results):
                tool_name = tc["name"]
                if isinstance(res, Exception):
                    err_msg = f"{tool_name} 执行失败: {str(res)}"
                    logger.warning("工具执行异常: %s", err_msg[:100])
                    yield self._sse("tool_result", {"tool": tool_name, "result": err_msg[:500]})
                    tool_msgs.append({"role": "tool", "tool_call_id": tc.get("id", tool_name),
                                      "content": err_msg})
                    continue

                tool_name, tool_result = res
                display_result = tool_result if tool_name == "polish_document" else tool_result[:500]
                yield self._sse("tool_result", {"tool": tool_name, "result": display_result})

                if tool_name == "polish_document":
                    yield self._sse("doc_modified", {"content": tool_result})

                tool_msgs.append({"role": "tool", "tool_call_id": tc.get("id", tool_name),
                                  "content": tool_result})

            # 将工具调用和结果以 assistent+tool 角色对追加到消息历史
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {"id": tc.get("id", f"call_{i}"), "type": "function",
                     "function": {"name": tc["name"], "arguments": json.dumps(tc.get("arguments", {}), ensure_ascii=False)}}
                    for i, tc in enumerate(tool_calls)
                ],
            })
            messages.extend(tool_msgs)

            # 如果不是最后一轮，让 LLM 决定是否需要继续调用工具
            if round_num < MAX_TOOL_ROUNDS - 1:
                yield self._sse("thinking", {"message": "正在评估是否需要继续调用工具..."})
                try:
                    tool_response = await client.chat(
                        model=model, messages=messages,
                        temperature=0.1, max_tokens=512,
                        tools=TOOL_DEFINITIONS, tool_choice="auto", timeout=60,
                    )
                    # 检查是否还有工具调用，否则退出循环
                    next_tool_calls = self._parse_tool_calls(tool_response)
                    if not next_tool_calls:
                        break
                    tool_calls = next_tool_calls  # 继续循环
                except Exception as e:
                    logger.warning("多轮工具检查失败: %s", str(e)[:100])
                    break

        # 工具执行完毕后，生成最终回复
        yield self._sse("thinking", {"message": "正在整理回复..."})

        # 流式生成最终回复 (简洁模式限 1024 tokens，详细模式 4096)
        try:
            async for chunk in client.chat_stream(
                model=model,
                messages=messages,
                temperature=0.2 if is_concise else 0.5,
                max_tokens=1024 if is_concise else 4096,
                timeout=90,
            ):
                text = self._extract_chunk_text(chunk)
                if text:
                    yield self._sse("chunk", {"text": text})
        except Exception as e:
            logger.warning("LLM 流式调用失败, 回退到非流式: %s", str(e)[:100])
            # 回退到非流式
            try:
                fallback = await client.chat(
                    model=model,
                    messages=messages,
                    temperature=0.2 if is_concise else 0.5,
                    max_tokens=1024 if is_concise else 4096,
                    timeout=90,
                )
                yield self._sse("chunk", {"text": fallback})
            except Exception:
                yield self._sse("error", {"message": "回复生成失败，请重试"})

        yield self._sse("done", {"elapsed_ms": int((time.time() - t0) * 1000)})

    # ── 辅助方法 ──────────────────────────────────────────

    def _parse_tool_calls(self, response: Any) -> list[dict]:
        """从 LLM 响应中解析工具调用。"""
        if isinstance(response, dict):
            tcs = response.get("tool_calls", [])
            if tcs:
                return [
                    {
                        "name": tc.get("function", {}).get("name", ""),
                        "arguments": json.loads(tc.get("function", {}).get("arguments", "{}")),
                    }
                    for tc in tcs
                ]
        return []

    def _extract_chunk_text(self, chunk: Any) -> str:
        """从流式 chunk 中提取文本。"""
        if isinstance(chunk, str):
            return chunk
        if isinstance(chunk, dict):
            choices = chunk.get("choices", [])
            if choices:
                delta = choices[0].get("delta", {})
                return delta.get("content", "") or ""
        return ""

    @staticmethod
    def _sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
