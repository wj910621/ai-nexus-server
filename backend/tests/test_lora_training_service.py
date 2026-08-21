"""Tests for LoraTrainingService (P3 Task 10)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_lora_training_service_registers_handler():
    """LoraTrainingService 初始化时注册 lora_train handler"""
    from app.services.lora_training_service import LoraTrainingService

    with patch("app.services.lora_training_service.task_service") as fake_ts:
        svc = LoraTrainingService()
        fake_ts.register_handler.assert_called_once_with(
            "lora_train", svc._handle_train_task,
        )


@pytest.mark.asyncio
async def test_build_params_from_payload_preset():
    """_build_params 从 preset 构建参数"""
    from app.services.lora_training_service import LoraTrainingService
    from app.engines.training.base import TrainingParams

    svc = LoraTrainingService.__new__(LoraTrainingService)

    payload = {
        "preset": "quick",
        "trigger_word": "zkq",
        "advanced": None,
    }
    params = svc._build_params(payload)
    assert params.preset == "quick"
    assert params.max_train_steps == 500
    assert params.trigger_word == "zkq"


@pytest.mark.asyncio
async def test_build_params_with_advanced():
    """_build_params 高级参数覆盖 preset"""
    from app.services.lora_training_service import LoraTrainingService

    svc = LoraTrainingService.__new__(LoraTrainingService)

    payload = {
        "preset": "standard",
        "trigger_word": "zkq",
        "advanced": {
            "rank": 64,
            "learning_rate": 0.0002,
            "max_train_steps": 2000,
        },
    }
    params = svc._build_params(payload)
    assert params.rank == 64
    assert params.learning_rate == 0.0002
    assert params.max_train_steps == 2000
    assert params.preset == "standard"


@pytest.mark.asyncio
async def test_handle_train_task_success(db_session):
    """_handle_train_task 成功完成训练"""
    from app.services.lora_training_service import LoraTrainingService
    from app.engines.training.base import TrainingResult

    svc = LoraTrainingService.__new__(LoraTrainingService)

    # mock task
    task = MagicMock()
    task.id = "task_test01"
    task.payload = {
        "dataset_id": "ds_001",
        "character_id": "ch_001",
        "location": "local",
        "trigger_word": "zkq",
        "preset": "quick",
        "advanced": None,
    }

    # mock engine
    fake_engine = MagicMock()
    fake_engine.train = AsyncMock(return_value=TrainingResult(
        adapter_path="/uploads/lora_adapters/ch_001/20260721/adapter.safetensors",
        metrics={"final_loss": 0.1, "steps": 500},
    ))

    fake_character = MagicMock()
    fake_character.lora_training_status = "none"

    with patch(
        "app.services.lora_training_service.TrainingEngineProvider.select",
        return_value=fake_engine,
    ), patch(
        "app.services.lora_training_service.task_service.update_progress",
        new=AsyncMock(),
    ), patch(
        "app.services.lora_training_service.storage",
    ), patch(
        "app.services.lora_training_service.CharacterService",
    ) as FakeCharSvc:
        char_svc_instance = MagicMock()
        char_svc_instance.get_by_id = AsyncMock(return_value=fake_character)
        char_svc_instance.update = AsyncMock()
        FakeCharSvc.return_value = char_svc_instance

        result = await svc._handle_train_task(task, db_session)

    assert result["adapter_path"].endswith("adapter.safetensors")
    assert result["metrics"]["steps"] == 500
    # Character 应被更新为 ready
    char_svc_instance.update.assert_called()


@pytest.mark.asyncio
async def test_handle_train_task_failure(db_session):
    """_handle_train_task 训练失败时更新 Character 为 failed"""
    from app.services.lora_training_service import LoraTrainingService

    svc = LoraTrainingService.__new__(LoraTrainingService)

    task = MagicMock()
    task.id = "task_test02"
    task.payload = {
        "dataset_id": "ds_002",
        "character_id": "ch_002",
        "location": "local",
        "trigger_word": "zkq",
        "preset": "quick",
        "advanced": None,
    }

    fake_engine = MagicMock()
    fake_engine.train = AsyncMock(side_effect=RuntimeError("OOM"))

    fake_character = MagicMock()

    with patch(
        "app.services.lora_training_service.TrainingEngineProvider.select",
        return_value=fake_engine,
    ), patch(
        "app.services.lora_training_service.task_service.update_progress",
        new=AsyncMock(),
    ), patch(
        "app.services.lora_training_service.CharacterService",
    ) as FakeCharSvc:
        char_svc_instance = MagicMock()
        char_svc_instance.get_by_id = AsyncMock(return_value=fake_character)
        char_svc_instance.update = AsyncMock()
        FakeCharSvc.return_value = char_svc_instance

        with pytest.raises(RuntimeError, match="OOM"):
            await svc._handle_train_task(task, db_session)

    # Character 应被更新为 failed
    char_svc_instance.update.assert_called()
    update_args = char_svc_instance.update.call_args
    # 第二位置参数是 dict
    update_dict = update_arg = update_args[0][1] if len(update_args[0]) > 1 else update_args[1]
    assert update_dict.get("lora_training_status") == "failed"


def test_get_dataset_image_dir():
    """_get_dataset_image_dir 返回数据集图片目录"""
    from app.services.lora_training_service import LoraTrainingService

    svc = LoraTrainingService.__new__(LoraTrainingService)
    with patch("app.services.lora_training_service.storage") as fake_storage:
        fake_storage.get_full_path.return_value = MagicMock()
        fake_storage.get_full_path.return_value.__truediv__ = lambda self, x: f"uploads/datasets/ds_001/{x}"
        # 此测试验证方法存在且返回路径
        result = svc._get_dataset_image_dir("ds_001")
    assert "ds_001" in str(result)
