"""Tests for TrainingEngine abstract base + dataclasses (P3 Task 5)."""
import pytest
from dataclasses import dataclass, asdict


def test_training_params_defaults():
    """TrainingParams 默认值"""
    from app.engines.training.base import TrainingParams

    p = TrainingParams()
    assert p.base_model == "stabilityai/sdxl-base-1.0"
    assert p.resolution == 1024
    assert p.rank == 32
    assert p.learning_rate == 1e-4
    assert p.batch_size == 1
    assert p.max_train_steps == 1000
    assert p.gradient_accumulation == 4
    assert p.lr_scheduler == "cosine"
    assert p.seed == 42
    assert p.trigger_word == ""
    assert p.preset == "standard"


def test_training_params_preset_override():
    """preset 快速/标准/高质量 改变 max_train_steps"""
    from app.engines.training.base import TrainingParams, PRESET_STEPS

    assert PRESET_STEPS == {"quick": 500, "standard": 1000, "high_quality": 2000}

    p_quick = TrainingParams.from_preset("quick", trigger_word="zkq")
    assert p_quick.max_train_steps == 500
    assert p_quick.preset == "quick"
    assert p_quick.trigger_word == "zkq"

    p_hq = TrainingParams.from_preset("high_quality", trigger_word="zkq")
    assert p_hq.max_train_steps == 2000


def test_training_result_dataclass():
    """TrainingResult dataclass"""
    from app.engines.training.base import TrainingResult

    r = TrainingResult(
        adapter_path="/uploads/lora_adapters/ch_001/20260721/adapter.safetensors",
        metrics={"final_loss": 0.12, "steps": 1000, "train_time_sec": 1800},
    )
    assert r.adapter_path.endswith("adapter.safetensors")
    assert r.metrics["final_loss"] == 0.12
    assert r.metrics["steps"] == 1000


def test_training_engine_is_abstract():
    """TrainingEngine 不能直接实例化"""
    from app.engines.training.base import TrainingEngine

    with pytest.raises(TypeError):
        TrainingEngine()


def test_training_engine_subclass_must_implement():
    """子类必须实现 train 和 check_available"""

    from app.engines.training.base import TrainingEngine

    class IncompleteEngine(TrainingEngine):
        pass

    with pytest.raises(TypeError):
        IncompleteEngine()

    class CompleteEngine(TrainingEngine):
        async def train(self, dataset_path, output_dir, params, progress_callback):
            from app.engines.training.base import TrainingResult
            return TrainingResult(adapter_path="x", metrics={})

        def check_available(self):
            return True, "ok"

    eng = CompleteEngine()
    assert eng.check_available() == (True, "ok")
