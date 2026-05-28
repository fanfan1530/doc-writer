"""Prometheus 监控指标导出。"""

from prometheus_fastapi_instrumentator import Instrumentator, metrics
from prometheus_client import Counter, Histogram, Gauge, Info

# 自定义指标
llm_call_counter = Counter(
    "llm_calls_total", "LLM 调用总次数", ["model", "doc_type"],
)
llm_call_latency = Histogram(
    "llm_call_latency_seconds", "LLM 调用延迟", ["model"],
    buckets=[0.5, 1, 2, 5, 10, 20, 30, 60, 90],
)
llm_call_errors = Counter(
    "llm_call_errors_total", "LLM 调用失败次数", ["model", "error_type"],
)
doc_generation_counter = Counter(
    "doc_generations_total", "文书生成总次数", ["doc_type"],
)
active_requests = Gauge(
    "active_requests", "当前活跃请求数",
)

# 应用信息（静态标签指标，仅在 /metrics 端点展示）
app_info = Info("doc_writer_info", "Application info")


def setup_monitoring(app):
    """配置 FastAPI 应用的 Prometheus 监控。"""
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_instrument_requests_inprogress=True,
    )
    instrumentator.add(metrics.latency())
    instrumentator.add(metrics.requests())
    instrumentator.instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    return instrumentator
