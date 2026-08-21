"""Tests for ReplicateTrainingEngine (P3 Task 7)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_replicate_engine_check_available_ok():
    """有 API token → 可用"""
    from app.engines.training.replicate import ReplicateTrainingEngine
    from app.core.config import settings

    with patch.object(settings, "replicate_api_token", "r8_xxx"):
        eng = ReplicateTrainingEngine()
        ok, reason = eng.check_available()
    assert ok is True
    assert reason == "ok"


def test_replicate_engine_check_available_no_token():
    """无 API token → 不可用"""
    from app.engines.training.replicate import ReplicateTrainingEngine
    from app.core.config import settings

    with patch.object(settings, "replicate_api_token", ""):
        eng = ReplicateTrainingEngine()
        ok, reason = eng.check_available()
    assert ok is False
    assert "token" in reason.lower()


@pytest.mark.asyncio
async def test_replicate_engine_train_success(tmp_path):
    """train 成功提交 prediction 并下载产物"""
    from app.engines.training.replicate import ReplicateTrainingEngine
    from app.engines.training.base import TrainingParams

    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (tmp_path / "dataset").mkdir()

    eng = ReplicateTrainingEngine()
    params = TrainingParams.from_preset("quick", trigger_word="zkq")

    # mock _submit_prediction + _poll_until_complete + _download_adapter
    async def fake_submit(images, params):
        return "pred_abc123"

    async def fake_poll(pred_id, progress_callback):
        await progress_callback(50, "云端训练中 50%")
        return {"status": "succeeded", "output_url": "https://replicate.com/x.safetensors"}

    async def fake_download(url, dest):
        (output_dir / "adapter.safetensors").write_bytes(b"fake cloud weights")
        return str(output_dir / "adapter.safetensors")

    with patch.object(eng, "_submit_prediction", side_effect=fake_submit), \
         patch.object(eng, "_poll_until_complete", side_effect=fake_poll), \
         patch.object(eng, "_download_adapter", side_effect=fake_download):
        progress_calls = []
        async def cb(p, m):
            progress_calls.append((p, m))

        result = await eng.train(
            dataset_path=str(tmp_path / "dataset"),
            output_dir=str(output_dir),
            params=params,
            progress_callback=cb,
        )

    assert result.adapter_path.endswith("adapter.safetensors")
    assert result.metrics.get("prediction_id") == "pred_abc123"
    assert len(progress_calls) >= 1


@pytest.mark.asyncio
async def test_replicate_engine_train_timeout(tmp_path):
    """prediction 超时应抛出 RuntimeError"""
    from app.engines.training.replicate import ReplicateTrainingEngine
    from app.engines.training.base import TrainingParams

    eng = ReplicateTrainingEngine()
    params = TrainingParams.from_preset("quick", trigger_word="zkq")

    async def fake_submit(images, params):
        return "pred_timeout"

    async def fake_poll(pred_id, progress_callback):
        raise RuntimeError("Replicate prediction timed out after 1800s")

    with patch.object(eng, "_submit_prediction", side_effect=fake_submit), \
         patch.object(eng, "_poll_until_complete", side_effect=fake_poll):
        with pytest.raises(RuntimeError, match="timed out"):
            await eng.train(
                dataset_path=str(tmp_path),
                output_dir=str(tmp_path / "out"),
                params=params,
                progress_callback=AsyncMock(),
            )


@pytest.mark.asyncio
async def test_replicate_engine_train_upload_phase(tmp_path):
    """train 应有上传阶段进度"""
    from app.engines.training.replicate import ReplicateTrainingEngine
    from app.engines.training.base import TrainingParams

    eng = ReplicateTrainingEngine()
    params = TrainingParams.from_preset("standard", trigger_word="zkq")

    async def fake_submit(images, params):
        return "pred_x"

    async def fake_poll(pred_id, progress_callback):
        await progress_callback(80, "训练中")
        return {"status": "succeeded", "output_url": "http://x.com/a.safetensors"}

    async def fake_download(url, dest):
        (tmp_path / "adapter.safetensors").write_bytes(b"x")
        return str(tmp_path / "adapter.safetensors")

    with patch.object(eng, "_submit_prediction", side_effect=fake_submit), \
         patch.object(eng, "_poll_until_complete", side_effect=fake_poll), \
         patch.object(eng, "_download_adapter", side_effect=fake_download):
        messages = []
        async def cb(p, m):
            messages.append(m)

        await eng.train(
            dataset_path=str(tmp_path),
            output_dir=str(tmp_path),
            params=params,
            progress_callback=cb,
        )

    assert any("上传" in m for m in messages)
    assert any("下载" in m for m in messages)
