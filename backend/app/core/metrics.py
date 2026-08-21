"""Custom Prometheus metrics for ComicStudio.

Auto-collected by prometheus-fastapi-instrumentator:
- http_requests_total{method, path, status}
- http_request_duration_seconds_bucket
- http_request_duration_seconds_sum / count

Custom metrics defined here:
- engine_concurrent_requests
- credits_consumed_total
- result_cache_hits_total / misses_total (Task 9)
- websocket_connections_active (Task 10)
- provider_circuit_state (Task 13)
"""
from prometheus_client import Counter, Gauge, Histogram, Info

# Engine metrics
engine_concurrent_requests = Gauge(
    "engine_concurrent_requests",
    "Active concurrent requests per engine type",
    ["engine_type"],
)

engine_requests_total = Counter(
    "engine_requests_total",
    "Total engine requests",
    ["engine_type", "result"],  # result: success | failure | timeout
)

# Business metrics
credits_consumed_total = Counter(
    "credits_consumed_total",
    "Total credits consumed",
    ["operation"],  # text2img, tts, chat, video_compose, character_generate
)

credits_refunded_total = Counter(
    "credits_refunded_total",
    "Total credits refunded (failures)",
    ["operation"],
)

# Cache metrics (populated by Task 9)
result_cache_hits_total = Counter(
    "result_cache_hits_total",
    "Result cache hits",
    ["engine_type"],
)

result_cache_misses_total = Counter(
    "result_cache_misses_total",
    "Result cache misses",
    ["engine_type"],
)

# WebSocket metrics (populated by Task 10)
websocket_connections_active = Gauge(
    "websocket_connections_active",
    "Active WebSocket connections",
)

websocket_messages_sent_total = Counter(
    "websocket_messages_sent_total",
    "WebSocket messages sent",
    ["type"],  # progress | completed | error | ping
)

# Provider failover metrics (populated by Task 13)
provider_circuit_state = Gauge(
    "provider_circuit_state",
    "Provider circuit breaker state (0=closed, 1=half_open, 2=open)",
    ["provider"],
)

provider_calls_total = Counter(
    "provider_calls_total",
    "Total provider calls",
    ["provider", "result"],  # result: success | failure | fallback
)

# Celery worker metrics (Phase 8 P4: K8s HPA worker by queue depth)
celery_queue_length = Gauge(
    "celery_queue_length",
    "Number of tasks waiting in Celery queue",
    ["queue"],
)

celery_active_workers = Gauge(
    "celery_active_workers",
    "Number of active Celery workers",
)

# Phase 8 P6: LLM token 使用指标（用于成本监控与配额告警）
llm_tokens_consumed_total = Counter(
    "llm_tokens_consumed_total",
    "Total LLM tokens consumed",
    ["provider", "token_type"],  # token_type: prompt | completion | total
)

llm_request_duration_seconds = Histogram(
    "llm_request_duration_seconds",
    "LLM request duration in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0),
)

# Phase 8 P6: 存储后端指标（用于 OSS 上传失败监控）
storage_operations_total = Counter(
    "storage_operations_total",
    "Storage backend operations",
    ["backend", "operation", "result"],  # backend: local | oss; operation: save | get | delete; result: success | failure
)

# App info
app_info = Info(
    "comicstudio",
    "Application info",
)
app_info.info({"version": "0.1.0", "env": "production"})
