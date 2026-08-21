"""Tests for training-related Pydantic schemas (P3 Task 2)."""
import pytest
from datetime import datetime, UTC


def test_dataset_create_schema():
    """DatasetCreate schema 验证"""
    from app.schemas.training_dataset import DatasetCreate

    ds = DatasetCreate(
        character_id="ch_001",
        name="测试数据集",
        caption_mode="auto",
        trigger_word="zkq_char",
    )
    assert ds.character_id == "ch_001"
    assert ds.name == "测试数据集"
    assert ds.caption_mode == "auto"
    assert ds.trigger_word == "zkq_char"


def test_dataset_create_defaults():
    """DatasetCreate 默认值"""
    from app.schemas.training_dataset import DatasetCreate

    ds = DatasetCreate(character_id="ch_001", name="test")
    assert ds.caption_mode == "auto"
    assert ds.trigger_word == ""


def test_dataset_item_response_schema():
    """DatasetItemResponse schema"""
    from app.schemas.training_dataset import DatasetItemResponse

    item = DatasetItemResponse(
        id="di_001",
        dataset_id="ds_001",
        image_path="/uploads/datasets/ds_001/img.png",
        caption="a cat",
        caption_source="auto",
        width=512,
        height=512,
        created_at=datetime.now(UTC),
    )
    assert item.id == "di_001"
    assert item.caption_source == "auto"


def test_dataset_response_schema():
    """DatasetResponse schema 含 items"""
    from app.schemas.training_dataset import DatasetResponse, DatasetItemResponse

    ds = DatasetResponse(
        id="ds_001",
        character_id="ch_001",
        user_id="u_001",
        name="test",
        status="drafting",
        image_count=2,
        caption_mode="auto",
        trigger_word="zkq",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        items=[
            DatasetItemResponse(
                id="di_1",
                dataset_id="ds_001",
                image_path="/uploads/x.png",
                caption="cap1",
                caption_source="auto",
                width=512,
                height=512,
                created_at=datetime.now(UTC),
            ),
        ],
    )
    assert ds.status == "drafting"
    assert len(ds.items) == 1
    assert ds.items[0].id == "di_1"


def test_caption_update_schema():
    """CaptionUpdate schema"""
    from app.schemas.training_dataset import CaptionUpdate

    cu = CaptionUpdate(caption="new caption text")
    assert cu.caption == "new caption text"


def test_train_request_schema():
    """TrainRequest schema 验证"""
    from app.schemas.training import TrainRequest

    req = TrainRequest(
        dataset_id="ds_001",
        location="local",
        trigger_word="zkq_char",
        preset="standard",
    )
    assert req.dataset_id == "ds_001"
    assert req.location == "local"
    assert req.preset == "standard"
    assert req.advanced is None


def test_train_request_validation():
    """TrainRequest location 必须是 local/replicate"""
    from app.schemas.training import TrainRequest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TrainRequest(
            dataset_id="ds_001",
            location="invalid",
            trigger_word="zkq",
            preset="standard",
        )

    with pytest.raises(ValidationError):
        TrainRequest(
            dataset_id="ds_001",
            location="local",
            trigger_word="zkq",
            preset="invalid_preset",
        )


def test_train_status_response_schema():
    """TrainStatusResponse schema"""
    from app.schemas.training import TrainStatusResponse

    resp = TrainStatusResponse(
        status="training",
        progress=45,
        message="训练中 450/1000",
        task_id="task_xxx",
    )
    assert resp.status == "training"
    assert resp.progress == 45


def test_train_params_advanced_schema():
    """TrainParamsAdvanced schema"""
    from app.schemas.training import TrainParamsAdvanced

    adv = TrainParamsAdvanced(
        rank=64,
        learning_rate=0.0002,
        max_train_steps=2000,
    )
    assert adv.rank == 64
    assert adv.max_train_steps == 2000

    # 默认值
    adv2 = TrainParamsAdvanced()
    assert adv2.rank == 32
    assert adv2.learning_rate == 0.0001
