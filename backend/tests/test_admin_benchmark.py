"""Tests for Task 15: POST /admin/benchmark endpoint (P2)."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def _reset_dm_singleton():
    """重置 DeviceManager 单例"""
    from app.core.device_manager import DeviceManager
    inst = DeviceManager._instance
    DeviceManager._instance = None
    yield
    DeviceManager._instance = inst


def test_post_benchmark_returns_result(_reset_dm_singleton):
    """POST /admin/benchmark 返回基准测试结果"""
    from app.api.admin import router, get_current_admin
    from app.core.device_manager import DeviceManager

    # mock DeviceManager 单例
    fake_dm = MagicMock()
    fake_dm.benchmark = AsyncMock(return_value={
        "device": {
            "vendor": "nvidia",
            "device_name": "NVIDIA RTX 3060",
            "vram_gb": 12.0,
        },
        "metrics": [
            {"name": "llm_tokens_per_sec", "value": 35.5, "unit": "tok/s"},
            {"name": "image_seconds", "value": 8.2, "unit": "s"},
            {"name": "vram_peak_gb", "value": 9.1, "unit": "GB"},
        ],
        "timestamp": "2026-07-20T12:00:00Z",
    })
    DeviceManager._instance = fake_dm

    # mock admin 鉴权（使用 FastAPI dependency_overrides，因 Depends 在路由定义时已绑定原函数对象）
    fake_admin = MagicMock()
    fake_admin.id = 1
    fake_admin.role = "admin"

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_admin] = lambda: fake_admin
    client = TestClient(app)

    resp = client.post("/admin/benchmark")

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert "data" in body
    data = body["data"]
    assert "device" in data
    assert "metrics" in data
    assert len(data["metrics"]) == 3


def test_post_benchmark_force_parameter(_reset_dm_singleton):
    """POST /admin/benchmark?force=true 强制重新运行基准测试"""
    from app.api.admin import router, get_current_admin
    from app.core.device_manager import DeviceManager

    fake_dm = MagicMock()
    fake_dm.benchmark = AsyncMock(return_value={
        "device": {"vendor": "amd", "device_name": "AMD RX 7900 XTX", "vram_gb": 24.0},
        "metrics": [],
        "timestamp": "2026-07-20T12:00:00Z",
    })
    DeviceManager._instance = fake_dm

    fake_admin = MagicMock(id=1, role="admin")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_admin] = lambda: fake_admin
    client = TestClient(app)

    resp = client.post("/admin/benchmark?force=true")

    assert resp.status_code == 200
    # 验证 benchmark 被调用且 force=True
    fake_dm.benchmark.assert_awaited_once()
    args, kwargs = fake_dm.benchmark.call_args
    assert kwargs.get("force") is True or (args and args[0] is True)


def test_post_benchmark_admin_required():
    """POST /admin/benchmark 需要 admin 鉴权"""
    from app.api.admin import router, get_current_admin
    from app.core.device_manager import DeviceManager
    from fastapi import HTTPException

    # 不设置 DeviceManager 单例
    DeviceManager._instance = None

    # mock 鉴权失败：抛 401
    def _raise_401():
        raise HTTPException(status_code=401, detail="Not authenticated")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_admin] = _raise_401
    client = TestClient(app)

    resp = client.post("/admin/benchmark")

    assert resp.status_code == 401


def test_post_benchmark_returns_500_on_failure(_reset_dm_singleton):
    """POST /admin/benchmark 当基准测试失败时返回 500"""
    from app.api.admin import router, get_current_admin
    from app.core.device_manager import DeviceManager

    fake_dm = MagicMock()
    fake_dm.benchmark = AsyncMock(side_effect=RuntimeError("torch not installed"))
    DeviceManager._instance = fake_dm

    fake_admin = MagicMock(id=1, role="admin")

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_admin] = lambda: fake_admin
    client = TestClient(app)

    resp = client.post("/admin/benchmark")

    assert resp.status_code == 500
