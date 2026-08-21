"""Phase 8 P6 - 监控指标测试（LLM token + storage operations）。"""
import pytest
from prometheus_client import generate_latest


def test_llm_tokens_consumed_total_counter_exists():
    """llm_tokens_consumed_total Counter 已注册。"""
    from app.core.metrics import llm_tokens_consumed_total
    assert llm_tokens_consumed_total is not None


def test_llm_tokens_can_be_counted_by_provider():
    """可以按 provider 和 token_type 统计 token 用量。"""
    from app.core.metrics import llm_tokens_consumed_total
    llm_tokens_consumed_total.labels(provider="deepseek", token_type="prompt").inc(100)
    llm_tokens_consumed_total.labels(provider="deepseek", token_type="completion").inc(50)
    llm_tokens_consumed_total.labels(provider="glm", token_type="prompt").inc(80)

    output = generate_latest().decode("utf-8")
    assert "llm_tokens_consumed_total" in output
    assert 'provider="deepseek"' in output
    assert 'token_type="prompt"' in output
    assert 'token_type="completion"' in output
    assert 'provider="glm"' in output


def test_llm_request_duration_histogram_exists():
    """llm_request_duration_seconds Histogram 已注册。"""
    from app.core.metrics import llm_request_duration_seconds
    assert llm_request_duration_seconds is not None


def test_llm_request_duration_can_observe():
    """可以观察 LLM 请求时长。"""
    from app.core.metrics import llm_request_duration_seconds
    llm_request_duration_seconds.labels(provider="deepseek", model="deepseek-chat").observe(1.5)
    llm_request_duration_seconds.labels(provider="deepseek", model="deepseek-chat").observe(0.8)

    output = generate_latest().decode("utf-8")
    assert "llm_request_duration_seconds" in output
    assert 'provider="deepseek"' in output
    assert 'model="deepseek-chat"' in output


def test_storage_operations_total_counter_exists():
    """storage_operations_total Counter 已注册。"""
    from app.core.metrics import storage_operations_total
    assert storage_operations_total is not None


def test_storage_operations_can_track_success_and_failure():
    """可以按 backend/operation/result 跟踪存储操作。"""
    from app.core.metrics import storage_operations_total
    storage_operations_total.labels(backend="local", operation="save", result="success").inc()
    storage_operations_total.labels(backend="local", operation="save", result="success").inc()
    storage_operations_total.labels(backend="local", operation="save", result="failure").inc()
    storage_operations_total.labels(backend="oss", operation="save", result="success").inc()

    output = generate_latest().decode("utf-8")
    assert "storage_operations_total" in output
    assert 'backend="local"' in output
    assert 'backend="oss"' in output
    assert 'operation="save"' in output
    assert 'result="success"' in output
    assert 'result="failure"' in output


def test_llm_request_duration_has_reasonable_buckets():
    """LLM 请求时长直方图有合理的 bucket。"""
    from app.core.metrics import llm_request_duration_seconds
    # 通过 observe 后检查 generate_latest 输出是否包含 bucket
    llm_request_duration_seconds.labels(provider="test", model="m").observe(0.5)
    output = generate_latest().decode("utf-8")
    # 应该有 bucket 边界（_bucket 后缀）
    assert "llm_request_duration_seconds_bucket" in output
    # 关键 bucket 边界
    assert 'le="0.1"' in output
    assert 'le="1.0"' in output
    assert 'le="60.0"' in output
    assert 'le="+Inf"' in output
