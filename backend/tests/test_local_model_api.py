"""Tests for LocalModel API + 表扩展."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.local_model import LocalModel


def test_local_model_has_user_id_field():
    """LocalModel 表应有 user_id 字段"""
    assert hasattr(LocalModel, "user_id")
    col = LocalModel.user_id
    assert col.nullable is False


def test_local_model_has_hardware_profile_field():
    """LocalModel 表应有 hardware_profile 字段"""
    assert hasattr(LocalModel, "hardware_profile")


def test_local_model_has_md5_field():
    """LocalModel 表应有 md5 字段（用于校验下载完整性）"""
    assert hasattr(LocalModel, "md5")


def test_local_model_has_download_url_field():
    """LocalModel 表应有 download_url 字段"""
    assert hasattr(LocalModel, "download_url")


def test_local_model_has_original_size_mb_field():
    """LocalModel 表应有 original_size_mb 字段"""
    assert hasattr(LocalModel, "original_size_mb")


@pytest.mark.asyncio
async def test_get_models_by_hardware_profile():
    """GET /models/local/{hardware_profile} 返回推荐模型"""
    from app.api.models import router
    from fastapi.testclient import TestClient
    from fastapi import FastAPI

    # mock model_manager.list_models
    fake_models = [
        MagicMock(to_dict=MagicMock(return_value={
            "name": "FLUX.1-dev",
            "model_type": "image",
            "hardware_profile": "high",
            "size_mb": 23800,
        })),
        MagicMock(to_dict=MagicMock(return_value={
            "name": "Qwen2.5-7B",
            "model_type": "llm",
            "hardware_profile": "mid",
            "size_mb": 4500,
        })),
    ]

    with patch("app.api.models.model_manager") as mock_mm:
        mock_mm.list_models = MagicMock(return_value=fake_models)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # mock auth
        with patch("app.core.deps.get_current_user", new=AsyncMock(return_value=MagicMock(id=1))):
            resp = client.get("/models/local/high")

    assert resp.status_code == 200
    data = resp.json()
    assert "data" in data
    assert len(data["data"]) >= 1
