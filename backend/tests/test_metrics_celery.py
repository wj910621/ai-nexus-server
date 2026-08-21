"""Phase 8 P4 - Celery 队列指标测试。"""
import pytest
from prometheus_client import REGISTRY


def test_celery_queue_length_gauge_exists():
    """celery_queue_length Gauge 已注册。"""
    from app.core.metrics import celery_queue_length
    assert celery_queue_length is not None


def test_celery_queue_length_can_set_value():
    """可以设置 celery_queue_length 值。"""
    from app.core.metrics import celery_queue_length
    celery_queue_length.labels(queue="default").set(5)
    # 验证值已设置（通过 prometheus_client REGISTRY）
    from prometheus_client import generate_latest
    output = generate_latest().decode("utf-8")
    assert "celery_queue_length" in output
    assert "queue=\"default\"" in output


def test_celery_active_workers_gauge_exists():
    """celery_active_workers Gauge 已注册。"""
    from app.core.metrics import celery_active_workers
    assert celery_active_workers is not None
    celery_active_workers.set(3)
    from prometheus_client import generate_latest
    output = generate_latest().decode("utf-8")
    assert "celery_active_workers" in output


def test_celery_queue_length_supports_multiple_queues():
    """celery_queue_length 支持多队列标签。"""
    from app.core.metrics import celery_queue_length
    celery_queue_length.labels(queue="default").set(10)
    celery_queue_length.labels(queue="gpu").set(2)
    celery_queue_length.labels(queue="background").set(0)
    from prometheus_client import generate_latest
    output = generate_latest().decode("utf-8")
    assert output.count("celery_queue_length") >= 3
