"""Tests for TrainingEngineProvider (P3 Task 8)."""
import pytest
from unittest.mock import patch, MagicMock


def test_provider_select_local():
    """select('local') 返回 LocalTrainingEngine"""
    from app.engines.training import TrainingEngineProvider
    from app.engines.training.local import LocalTrainingEngine

    eng = TrainingEngineProvider.select("local")
    assert isinstance(eng, LocalTrainingEngine)


def test_provider_select_replicate():
    """select('replicate') 返回 ReplicateTrainingEngine"""
    from app.engines.training import TrainingEngineProvider
    from app.engines.training.replicate import ReplicateTrainingEngine

    eng = TrainingEngineProvider.select("replicate")
    assert isinstance(eng, ReplicateTrainingEngine)


def test_provider_select_invalid():
    """select 无效 location 抛 ValueError"""
    from app.engines.training import TrainingEngineProvider

    with pytest.raises(ValueError, match="Unknown training location"):
        TrainingEngineProvider.select("aws")


def test_provider_auto_select_local_available():
    """本地可用时 auto_select 返回 local"""
    from app.engines.training import TrainingEngineProvider
    from app.engines.training.local import LocalTrainingEngine

    fake_local = MagicMock()
    fake_local.check_available.return_value = (True, "ok")

    with patch(
        "app.engines.training.LocalTrainingEngine",
        return_value=fake_local,
    ):
        location, eng = TrainingEngineProvider.auto_select()
    assert location == "local"
    assert eng is fake_local


def test_provider_auto_select_fallback_to_replicate():
    """本地不可用时 auto_select 回退到 replicate"""
    from app.engines.training import TrainingEngineProvider
    from app.engines.training.replicate import ReplicateTrainingEngine

    fake_local = MagicMock()
    fake_local.check_available.return_value = (False, "VRAM 不足")
    fake_replicate = MagicMock()

    with patch(
        "app.engines.training.LocalTrainingEngine",
        return_value=fake_local,
    ), patch(
        "app.engines.training.ReplicateTrainingEngine",
        return_value=fake_replicate,
    ):
        location, eng = TrainingEngineProvider.auto_select()
    assert location == "replicate"
    assert eng is fake_replicate
