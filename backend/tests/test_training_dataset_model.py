"""Tests for TrainingDataset + DatasetItem models (P3 Task 1)."""
import pytest
from datetime import datetime


@pytest.mark.asyncio
async def test_create_training_dataset(db_session):
    """创建 TrainingDataset 记录"""
    from app.models.training_dataset import TrainingDataset

    ds = TrainingDataset(
        id="ds_test001",
        character_id="ch_001",
        user_id="u_001",
        name="角色A数据集",
        status="drafting",
        image_count=0,
        caption_mode="auto",
        trigger_word="zkq_char",
    )
    db_session.add(ds)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(TrainingDataset).where(TrainingDataset.id == "ds_test001")
    )
    fetched = result.scalar_one()
    assert fetched.name == "角色A数据集"
    assert fetched.status == "drafting"
    assert fetched.caption_mode == "auto"
    assert fetched.trigger_word == "zkq_char"
    assert fetched.image_count == 0


@pytest.mark.asyncio
async def test_create_dataset_item(db_session):
    """创建 DatasetItem 记录并关联数据集"""
    from app.models.training_dataset import TrainingDataset, DatasetItem

    ds = TrainingDataset(
        id="ds_test002",
        character_id="ch_002",
        user_id="u_001",
        name="测试数据集",
    )
    db_session.add(ds)
    await db_session.flush()

    item = DatasetItem(
        id="di_001",
        dataset_id="ds_test002",
        image_path="/uploads/datasets/ds_test002/img_001.png",
        caption="a woman with red hair",
        caption_source="manual",
        width=1024,
        height=1024,
    )
    db_session.add(item)
    await db_session.commit()

    from sqlalchemy import select
    result = await db_session.execute(
        select(DatasetItem).where(DatasetItem.id == "di_001")
    )
    fetched = result.scalar_one()
    assert fetched.dataset_id == "ds_test002"
    assert fetched.caption == "a woman with red hair"
    assert fetched.caption_source == "manual"
    assert fetched.width == 1024


@pytest.mark.asyncio
async def test_dataset_item_relationship(db_session):
    """数据集与条目的关系（cascade delete）"""
    from app.models.training_dataset import TrainingDataset, DatasetItem

    ds = TrainingDataset(
        id="ds_test003",
        character_id="ch_003",
        user_id="u_001",
        name="关系测试",
    )
    db_session.add(ds)
    await db_session.flush()

    for i in range(3):
        db_session.add(DatasetItem(
            id=f"di_rel_{i}",
            dataset_id="ds_test003",
            image_path=f"/uploads/datasets/ds_test003/img_{i}.png",
            caption=f"caption {i}",
            caption_source="auto",
        ))
    await db_session.commit()

    from sqlalchemy import select
    # 验证关系
    result = await db_session.execute(
        select(DatasetItem).where(DatasetItem.dataset_id == "ds_test003")
    )
    items = result.scalars().all()
    assert len(items) == 3

    # 删除数据集应级联删除条目（通过 ORM cascade="all, delete-orphan"）
    # 注：bulk delete() 不会触发 ORM 级联，需使用 session.delete()
    await db_session.delete(ds)
    await db_session.commit()

    result = await db_session.execute(
        select(DatasetItem).where(DatasetItem.dataset_id == "ds_test003")
    )
    remaining = result.scalars().all()
    assert len(remaining) == 0


def test_dataset_status_values():
    """status 字段应接受所有合法值"""
    from app.models.training_dataset import TrainingDataset

    legal = ["drafting", "captioning", "ready", "training", "used"]
    for s in legal:
        ds = TrainingDataset(
            id=f"ds_{s}",
            character_id="ch_x",
            user_id="u_x",
            name="test",
            status=s,
        )
        assert ds.status == s


def test_dataset_caption_mode_values():
    """caption_mode 字段应接受 auto/manual"""
    from app.models.training_dataset import TrainingDataset

    for mode in ["auto", "manual"]:
        ds = TrainingDataset(
            id=f"ds_{mode}",
            character_id="ch_x",
            user_id="u_x",
            name="test",
            caption_mode=mode,
        )
        assert ds.caption_mode == mode
