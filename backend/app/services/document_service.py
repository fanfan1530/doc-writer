"""文档生成服务 —— 编排 LLM 调用、字段处理、模板填充、法条检索。

替代原先的 DocumentGenerator God Class（937行），将不同职责委托给子模块：
- FieldProcessor: 字段后处理
- LLM prompts: 集中在 core/llm/prompts.py
- docx_exporter: 集中在 core/export/docx_exporter.py
"""

from __future__ import annotations
import asyncio
import json
import logging
import re
import time
from typing import Any

from app.core.llm_client import LLMClient
from app.core.llm.prompts import EXTRACTION_PROMPT, POLISH_PROMPT, CASE_SUMMARY_PROMPT
from app.services.field_processor import FieldProcessor

logger = logging.getLogger(__name__)


class DocumentService:
    """文书生成服务（编排层）。"""

    def __init__(
        self,
        model_manager: "ModelManager | None" = None,
        rag_retriever: "RAGRetriever | None" = None,
    ):
        self._model_manager = model_manager
        self._rag = rag_retriever
        self._field_processor = FieldProcessor(law_retriever=rag_retriever)

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

    def _get_temperature(self) -> float:
        if self._model_manager:
            return self._model_manager.get_temperature()
        return 0.1

    def _get_max_tokens(self) -> int:
        if self._model_manager:
            return self._model_manager.get_max_tokens()
        return 4096

    def _get_system_prompt(self) -> str:
        if self._model_manager:
            return self._model_manager.get_system_prompt()
        return ""

    # ── LLM 调用（带重试） ────────────────────────────────

    async def _call_llm(
        self, user_prompt: str, max_tokens: int | None = None,
    ) -> str:
        """统一 LLM 调用：自动注入 system_prompt，内置缓存 + 3 次重试 + 指数退避。"""
        sys_prompt = self._get_system_prompt()
        messages = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages.append({"role": "user", "content": user_prompt})

        model = self._get_model_name()
        temperature = self._get_temperature()

        # 检查缓存
        full_prompt = f"{sys_prompt}\n{user_prompt}" if sys_prompt else user_prompt
        cached = await __import__("app.core.llm_cache", fromlist=["get_cached"]).get_cached(
            full_prompt, model, temperature,
        )
        if cached:
            return cached

        last_error = ""
        for attempt in range(3):
            try:
                result = await self._get_client().chat(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens or self._get_max_tokens(),
                    timeout=90,
                )
                # 写入缓存
                import asyncio
                asyncio.ensure_future(
                    __import__("app.core.llm_cache", fromlist=["set_cached"]).set_cached(
                        full_prompt, model, temperature, result,
                    )
                )
                return result
            except Exception as e:
                last_error = str(e)[:200]
                logger.warning("LLM 调用失败 (第%d次): %s", attempt + 1, last_error)
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)

        logger.error("LLM 调用最终失败: %s", last_error)
        raise RuntimeError(f"LLM 调用失败（重试3次后仍无法连接）: {last_error}")

    # ── 要素抽取 ──────────────────────────────────────────

    async def extract_elements(
        self, input_text: str, doc_type: str,
    ) -> dict[str, Any]:
        """调用 LLM 从案情描述中抽取关键要素。"""
        template = self._rag.retrieve_template(doc_type) if self._rag else None
        element_schema = json.dumps(
            template.get("schema_fields", []) if template else [],
            ensure_ascii=False,
        )
        prompt = EXTRACTION_PROMPT.format(
            input_text=input_text, doc_type=doc_type, element_schema=element_schema,
        )
        try:
            text = await self._call_llm(prompt)
            return self._parse_json(text)
        except RuntimeError:
            return {"elements": {}, "suggested_laws": [], "case_nature": ""}

    # ── 事实润色 ──────────────────────────────────────────

    async def polish_fact(self, raw_fact: str, doc_type: str = "") -> str:
        if not raw_fact.strip():
            return raw_fact
        prompt = POLISH_PROMPT.format(
            raw_fact=raw_fact, doc_type=doc_type or "公安法律文书",
        )
        try:
            result = await self._call_llm(prompt, max_tokens=2048)
            return result or raw_fact
        except RuntimeError:
            return raw_fact

    # ── 法条推荐 ──────────────────────────────────────────

    async def suggest_laws(self, fact: str, doc_type: str) -> list[dict]:
        if not self._rag:
            return []
        law_text = self._rag.retrieve_laws(fact, doc_type)
        if not law_text or law_text == "未找到相关法条。":
            return []
        results: list[dict] = []
        for block in law_text.split("\n\n"):
            if "】" in block and "条:" in block:
                results.append({"content": block.strip()})
        return results

    # ── 完整文档生成 ──────────────────────────────────────

    async def generate_document(
        self, doc_type: str, input_text: str, template: dict | None = None,
    ) -> dict[str, Any]:
        """完整文书生成流程：要素抽取 → 润色 → 字段处理 → 模板填充。"""
        t0 = time.time()
        # 1. 要素抽取
        extracted = await self.extract_elements(input_text, doc_type)
        elements = extracted.get("elements", {})

        # 2. 润色事实描述段落
        fact_keywords = [
            "illegal_fact", "case_brief", "case_fact", "fact_description",
            "dispute_fact", "inspection_process", "inspection_findings",
            "search_process", "investigation_summary", "case_summary",
            "scene_description", "identification_process",
            "case_background", "identification_results",
        ]
        for kw in fact_keywords:
            if kw in elements and elements[kw]:
                polished = await self.polish_fact(str(elements[kw]), doc_type)
                elements[kw] = polished
                break

        # 3. 字段后处理
        elements = self._field_processor.process(doc_type, elements, input_text)

        # 4. 辨认笔录特殊处理：未提取 results 时从文本抽取
        if doc_type == "辨认笔录" and not elements.get("identification_results"):
            identifier_name = str(elements.get("identifier_name", ""))
            names = self._extract_suspect_names(input_text, identifier_name)
            if names:
                lines = [f"辨认照片一组中（X）号照片的人就是{n}" for n in names]
                lines.append("该组照片中的其他人员均不是本案涉案人员")
                elements["identification_results"] = "\n".join(lines)

        # 5. 法条推荐
        laws = await self.suggest_laws(input_text, doc_type)

        # 6. 模板填充
        template_text = ""
        if template:
            template_text = template.get("template_text", "")
        elif self._rag:
            t = self._rag.retrieve_template(doc_type)
            if t:
                template_text = t.get("template_text", "")

        content = self._fill_template(template_text, elements)

        result = {
            "elements": elements,
            "suggested_laws": (
                [l["content"] for l in laws] or extracted.get("suggested_laws", [])
            ),
            "case_nature": extracted.get("case_nature", ""),
            "content": content or input_text,
            "template_used": template is not None,
        }
        elapsed_ms = int((time.time() - t0) * 1000)
        self._schedule_history_record(
            doc_type=doc_type, input_text=input_text, result=result,
            model_name=self._get_model_name(), elapsed_ms=elapsed_ms,
        )
        return result

    # ── 手动模板填充 ──────────────────────────────────────

    async def fill_template(
        self, doc_type: str, fields: dict[str, Any],
    ) -> dict[str, Any]:
        """手动模式：用户填写字段 → 字段处理 → 模板填充 + 法条推荐 + 期限检查。"""
        t0 = time.time()
        if self._rag:
            template = self._rag.retrieve_template(doc_type)
            if not template:
                raise ValueError(f"未找到类型为 {doc_type} 的文书模板")
        else:
            raise ValueError("知识库未初始化")

        # 字段后处理
        fields = self._field_processor.process(doc_type, fields)

        # 模板填充
        template_text = template.get("template_text", "")
        content = self._fill_template(template_text, fields)

        # 法条推荐
        fact_text = " ".join(str(v) for v in fields.values() if v)
        laws = await self.suggest_laws(fact_text, doc_type)

        # 期限检查
        deadlines = self.check_legal_deadlines(fields, doc_type)

        result = {
            "doc_type": doc_type,
            "elements": fields,
            "suggested_laws": [l["content"] for l in laws] if laws else [],
            "case_nature": fields.get("case_nature", ""),
            "content": content,
            "deadline_warnings": deadlines,
        }
        elapsed_ms = int((time.time() - t0) * 1000)
        # 手动模式需要构造 input_text 用于历史记录
        manual_input = " ".join(str(v) for v in fields.values() if v)[:500]
        self._schedule_history_record(
            doc_type=doc_type, input_text=manual_input, result=result,
            model_name=self._get_model_name(), elapsed_ms=elapsed_ms,
        )
        return result

    # ── 文件摘要 ──────────────────────────────────────────

    async def summarize_case_file_text(
        self, raw_text: str, doc_type_hint: str = "",
    ) -> dict[str, str]:
        """从文书文件中提取的原始文本整理为结构化案件摘要。"""
        if not raw_text.strip():
            return {"summary": "", "warning": "提取的文本为空"}

        prompt = CASE_SUMMARY_PROMPT.format(raw_text=raw_text)
        try:
            content = (await self._call_llm(prompt)).strip()
            if not content:
                return {"summary": "", "warning": "AI 模型未能提取有效案情信息"}
            return {"summary": content, "warning": ""}
        except RuntimeError as e:
            return {"summary": "", "warning": f"AI 模型调用失败: {str(e)[:200]}"}

    # ── 批量文书链 ────────────────────────────────────────

    async def generate_document_chain(
        self, input_text: str, doc_types: list[str],
    ) -> list[dict[str, Any]]:
        results = []
        for doc_type in doc_types:
            result = await self.generate_document(doc_type, input_text)
            results.append(result)
        return results

    # ── 法定期限检查 ──────────────────────────────────────

    def check_legal_deadlines(
        self, fields: dict[str, Any], doc_type: str,
    ) -> list[dict]:
        """检查法律期限合规性。"""
        warnings: list[dict] = []
        from datetime import datetime, timedelta

        try:
            if doc_type == "行政处罚告知笔录":
                notif_time = fields.get("notification_time", "")
                if notif_time:
                    t1 = self._parse_datetime(str(notif_time))
                    deadline = t1 + timedelta(days=3)
                    warnings.append({
                        "level": "info",
                        "message": f"告知后应在 {deadline.strftime('%Y-%m-%d')} 前作出处罚决定。",
                        "law_ref": "《行政处罚法》第62条",
                    })

            elif doc_type == "行政处罚决定书":
                filing = fields.get("filing_date") or fields.get("report_time")
                decision = fields.get("penalty_decision_date") or fields.get("notification_date")
                if filing and decision:
                    d1 = self._parse_date(str(filing))
                    d2 = self._parse_date(str(decision))
                    delta = (d2 - d1).days
                    if delta > 30:
                        warnings.append({
                            "level": "critical",
                            "message": f"办案期限 {delta} 日，超过30日法定上限。",
                            "law_ref": "《公安机关办理行政案件程序规定》第165条",
                        })

            elif doc_type == "扣押决定书":
                seizure = fields.get("seizure_date", "")
                if seizure:
                    d1 = self._parse_date(str(seizure))
                    deadline = d1 + timedelta(days=30)
                    warnings.append({
                        "level": "info",
                        "message": f"扣押期限至 {deadline.strftime('%Y-%m-%d')}（30日）。",
                        "law_ref": "《治安管理处罚法》第89条",
                    })
        except (ValueError, TypeError):
            pass
        return warnings

    # ── 辅助方法 ──────────────────────────────────────────

    def _fill_template(self, template_text: str, elements: dict[str, Any]) -> str:
        if not template_text:
            return ""
        result = template_text
        for key, value in elements.items():
            placeholder = "{{" + key + "}}"
            if value is None or str(value) in ("None", "null", ""):
                result = result.replace(placeholder, "")
            else:
                result = result.replace(placeholder, str(value))
        return result

    @staticmethod
    def _extract_suspect_names(input_text: str, identifier_name: str) -> list[str]:
        """从案情描述中抽取除辨认人外的其他涉案人员姓名。"""
        names: list[str] = []
        pattern = r'(?:伙同|与|及|和|包括)\s*([一-龥]{2,3}(?:[、，][一-龥]{2,3})*)'
        for m in re.finditer(pattern, input_text):
            for part in re.split(r'[、，]', m.group(1)):
                part = re.sub(r'等.*$', '', part.strip())
                exclude = ('等人', '本案', '在场', '参与', '涉案', '其他',
                          '一起', '共同', '多名', '若干', '其中', '上述')
                if (re.match(r'^[一-龥]{2,3}$', part)
                        and part not in exclude
                        and part != identifier_name
                        and part not in names):
                    names.append(part)
        return names

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        # 移除推理模型思考标签
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE).strip()
        # 提取代码块
        for marker in ("```json", "```"):
            if marker in text:
                parts = text.split(marker)
                if len(parts) >= 2:
                    inner = parts[1].split("```")
                    if inner:
                        text = inner[0].strip()
                        break
        # 提取 JSON 对象
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                fixed = re.sub(r",\s*}", "}", text)
                fixed = re.sub(r",\s*]", "]", fixed)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass
        return {"elements": {}, "suggested_laws": [], "case_nature": ""}

    @staticmethod
    def _parse_datetime(val: str) -> "datetime":
        from datetime import datetime
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(val, fmt)
            except ValueError:
                continue
        raise ValueError(f"Cannot parse datetime: {val}")

    @staticmethod
    def _parse_date(val: str) -> "date":
        return DocumentService._parse_datetime(val).date()

    # ── 历史记录 ────────────────────────────────────────────

    def _schedule_history_record(
        self, doc_type: str, input_text: str, result: dict[str, Any],
        model_name: str, elapsed_ms: int,
    ) -> None:
        """异步写入生成历史到数据库（fire-and-forget）。"""
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(
                self._record_history(doc_type, input_text, result, model_name, elapsed_ms)
            )
        except RuntimeError:
            pass

    async def _record_history(
        self, doc_type: str, input_text: str, result: dict[str, Any],
        model_name: str, elapsed_ms: int,
    ) -> None:
        try:
            from app.infrastructure.database import AsyncSessionLocal
            from app.infrastructure.models import GenerationHistory
            async with AsyncSessionLocal() as db:
                db.add(GenerationHistory(
                    doc_type=doc_type,
                    input_text=input_text[:2000],
                    output_content=str(result.get("content", ""))[:5000],
                    model_used=model_name,
                    latency_ms=elapsed_ms,
                    elements=result.get("elements", {}),
                    suggested_laws=result.get("suggested_laws", []),
                ))
                await db.commit()
        except Exception:
            logger.warning("历史记录写入失败", exc_info=True)
