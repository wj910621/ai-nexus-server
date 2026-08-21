"""Tests for Task 15: ModelManager."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from app.engines.model_manager import ModelManager, ModelInfo, ModelState


def test_model_info_defaults_to_not_downloaded():
    """ModelInfo starts in NOT_DOWNLOADED state."""
    info = ModelInfo(name="sdxl-base", type="image", size_mb=6500)
    assert info.state == ModelState.NOT_DOWNLOADED


@pytest.mark.asyncio
async def test_download_model_creates_local_dir(tmp_path):
    """download() creates the local model directory."""
    mgr = ModelManager(model_dir=str(tmp_path))
    with patch("app.engines.model_manager.snapshot_download", new=MagicMock()) as mock_dl:
        # Make snapshot_download return a path string (its real return type)
        mock_dl.return_value = str(tmp_path / "test-model")
        info = await mgr.download("test-model", repo_id="test/repo")
    assert info.state == ModelState.READY
    assert info.local_path.startswith(str(tmp_path))


@pytest.mark.asyncio
async def test_list_models_returns_registry():
    """list_models() returns all registered models (defaults + custom)."""
    mgr = ModelManager(model_dir="/tmp/models-test-list")
    mgr._registry["m1"] = ModelInfo(name="m1", type="image", size_mb=1000)
    mgr._registry["m2"] = ModelInfo(name="m2", type="llm", size_mb=4000)
    models = mgr.list_models()
    names = {m.name for m in models}
    # Both custom models must be present
    assert "m1" in names
    assert "m2" in names
    # Plus the 3 default models registered on init
    assert "sdxl-base" in names
    assert "qwen2.5-7b" in names
    assert "piper-en-lessac" in names
    assert len(models) == 5


@pytest.mark.asyncio
async def test_delete_model_removes_from_registry(tmp_path):
    """delete() removes model files and registry entry."""
    mgr = ModelManager(model_dir=str(tmp_path))
    # Create a fake model dir
    model_dir = tmp_path / "test-model"
    model_dir.mkdir()
    (model_dir / "weights.bin").write_bytes(b"fake")
    mgr._registry["test-model"] = ModelInfo(
        name="test-model", type="image", size_mb=1,
        state=ModelState.READY, local_path=str(model_dir),
    )
    await mgr.delete("test-model")
    assert "test-model" not in mgr._registry
    assert not model_dir.exists()


@pytest.mark.asyncio
async def test_get_model_path_returns_path_when_ready(tmp_path):
    """get_model_path() returns path when model is READY."""
    mgr = ModelManager(model_dir=str(tmp_path))
    mgr._registry["m1"] = ModelInfo(
        name="m1", type="image", size_mb=1000,
        state=ModelState.READY, local_path=str(tmp_path / "m1"),
    )
    path = mgr.get_model_path("m1")
    assert path == str(tmp_path / "m1")


def test_get_model_path_returns_none_when_not_ready():
    """get_model_path() returns None when model is not READY."""
    mgr = ModelManager(model_dir="/tmp/models-test-not-ready")
    mgr._registry["m1"] = ModelInfo(
        name="m1", type="image", size_mb=1000,
        state=ModelState.NOT_DOWNLOADED,
    )
    assert mgr.get_model_path("m1") is None


@pytest.mark.asyncio
async def test_load_lora_attaches_to_model(tmp_path):
    """load_lora() attaches LoRA weights to an existing model."""
    mgr = ModelManager(model_dir=str(tmp_path))
    mgr._registry["base"] = ModelInfo(
        name="base", type="image", size_mb=1000,
        state=ModelState.READY, local_path=str(tmp_path / "base"),
    )
    # Mock the pipeline loader
    fake_pipeline = MagicMock()
    fake_pipeline.load_lora_weights = MagicMock()
    with patch.object(mgr, "_load_pipeline", new=AsyncMock(return_value=fake_pipeline)):
        lora_path = await mgr.load_lora("base", "/path/to/lora.safetensors", weight=0.8)
    assert lora_path == "/path/to/lora.safetensors"
    fake_pipeline.load_lora_weights.assert_called_once_with(
        "/path/to/lora.safetensors", weight=0.8
    )
