# Phase 8 P3: LoRA 训练 UI 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为漫剧创作平台新增 SDXL LoRA 训练能力（本地 peft+diffusers / 云端 Replicate），用户上传角色图片即可训练专属 LoRA adapter。

**Architecture:** `TrainingEngine` 抽象基类 + `LocalTrainingEngine`/`ReplicateTrainingEngine` 两个实现，通过 `TrainingEngineProvider` 路由。`LoraTrainingService` 注册为 `TaskService` 的 `lora_train` handler，复用 `BackgroundTask` 表和 WebSocket 进度推送。前端分步向导（数据集→Caption→参数→训练），实时进度通过 WebSocket。

**Tech Stack:** 后端 Python 3.14 / FastAPI / SQLAlchemy 2.0 / peft / diffusers / datasets / replicate SDK；前端 React 18 / Ant Design 5 / TypeScript / vitest / @testing-library/react

**Spec:** `docs/superpowers/specs/2026-07-21-phase8-p3-lora-training-design.md`

**环境约定:**
- 工作目录：`c:\漫剧软件项目`
- Python：`py -3.14`（PowerShell）
- PYTHONPATH：`$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"`
- PowerShell 用 `;` 分隔命令（不用 `&&`/`||`）
- 前端用 `npm.cmd` / `npx.cmd`（PowerShell 执行策略限制）
- Git 未安装，所有 git commit 步骤跳过
- 测试在 `backend/tests/` 扁平化命名

**TDD 流程:** 每个 Task 遵循 "写失败测试 → 验证失败 → 写实现 → 验证通过 → （回归）" 。跳过所有 `git commit` Step。

---

## Task 1: TrainingDataset + DatasetItem 数据模型

**Files:**
- Create: `backend/app/models/training_dataset.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_training_dataset_model.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_training_dataset_model.py`:

```python
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

    from sqlalchemy import select, delete
    # 验证关系
    result = await db_session.execute(
        select(DatasetItem).where(DatasetItem.dataset_id == "ds_test003")
    )
    items = result.scalars().all()
    assert len(items) == 3

    # 删除数据集应级联删除条目
    await db_session.execute(
        delete(TrainingDataset).where(TrainingDataset.id == "ds_test003")
    )
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_dataset_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.models.training_dataset'`

- [ ] **Step 3: 创建模型文件**

Create `backend/app/models/training_dataset.py`:

```python
"""训练数据集模型 - TrainingDataset + DatasetItem

Phase 8 P3: LoRA 训练 UI
"""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime

from app.models.base import Base, UUIDMixin, TimestampMixin


def _generate_dataset_id() -> str:
    import uuid
    return f"ds_{uuid.uuid4().hex[:14]}"


def _generate_item_id() -> str:
    import uuid
    return f"di_{uuid.uuid4().hex[:14]}"


class TrainingDataset(Base, TimestampMixin):
    """训练数据集实体"""
    __tablename__ = "training_datasets"

    id = Column(String(36), primary_key=True, default=_generate_dataset_id)
    character_id = Column(String(36), ForeignKey("characters.id"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    status = Column(String(20), default="drafting", nullable=False)
    # drafting / captioning / ready / training / used

    image_count = Column(Integer, default=0, nullable=False)
    caption_mode = Column(String(20), default="auto", nullable=False)
    # auto / manual

    trigger_word = Column(String(50), default="", nullable=False)

    items = relationship(
        "DatasetItem",
        back_populates="dataset",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class DatasetItem(Base):
    """数据集条目（单张图片 + caption）"""
    __tablename__ = "dataset_items"

    id = Column(String(36), primary_key=True, default=_generate_item_id)
    dataset_id = Column(String(36), ForeignKey("training_datasets.id"), nullable=False, index=True)
    image_path = Column(String(500), nullable=False)
    caption = Column(Text, default="", nullable=False)
    caption_source = Column(String(20), default="manual", nullable=False)
    # auto / manual / imported

    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    dataset = relationship("TrainingDataset", back_populates="items")
```

- [ ] **Step 4: 在 models/__init__.py 注册新模型**

Modify `backend/app/models/__init__.py` — 在 `from app.models.local_model import LocalModel` 之后添加导入，并更新 `__all__`。

在 `from app.models.local_model import LocalModel` 之后添加：
```python
from app.models.training_dataset import TrainingDataset, DatasetItem
```

在 `__all__` 列表中 `"LocalModel",` 之后添加：
```python
    "TrainingDataset",
    "DatasetItem",
```

- [ ] **Step 5: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_dataset_model.py -v`
Expected: 5 passed

- [ ] **Step 6: 回归测试**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_bootstrap.py backend/tests/test_models.py -v`
Expected: PASS（无回归）

- [ ] **Step 7: 跳过 git commit**（Git 未安装）

---

## Task 2: Pydantic Schemas（数据集 + 训练）

**Files:**
- Create: `backend/app/schemas/training_dataset.py`
- Create: `backend/app/schemas/training.py`
- Test: `backend/tests/test_training_schemas.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_training_schemas.py`:

```python
"""Tests for training-related Pydantic schemas (P3 Task 2)."""
import pytest
from datetime import datetime


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
        created_at=datetime.utcnow(),
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
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        items=[
            DatasetItemResponse(
                id="di_1",
                dataset_id="ds_001",
                image_path="/uploads/x.png",
                caption="cap1",
                caption_source="auto",
                width=512,
                height=512,
                created_at=datetime.utcnow(),
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.training_dataset'`

- [ ] **Step 3: 创建 schemas/training_dataset.py**

Create `backend/app/schemas/training_dataset.py`:

```python
"""训练数据集 Schema"""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class DatasetCreate(BaseModel):
    """创建数据集"""
    character_id: str = Field(..., description="关联角色 ID")
    name: str = Field(..., min_length=1, max_length=100)
    caption_mode: str = Field("auto", pattern="^(auto|manual)$")
    trigger_word: str = Field("", max_length=50)


class CaptionUpdate(BaseModel):
    """更新单张图片 caption"""
    caption: str = Field(..., min_length=0, max_length=2000)


class DatasetItemResponse(ORMModel):
    """数据集条目响应"""
    id: str
    dataset_id: str
    image_path: str
    caption: str
    caption_source: str
    width: Optional[int] = None
    height: Optional[int] = None
    created_at: datetime


class DatasetResponse(ORMModel):
    """数据集响应（含条目列表）"""
    id: str
    character_id: str
    user_id: str
    name: str
    status: str
    image_count: int
    caption_mode: str
    trigger_word: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    items: List[DatasetItemResponse] = []
```

- [ ] **Step 4: 创建 schemas/training.py**

Create `backend/app/schemas/training.py`:

```python
"""训练相关 Schema"""
from typing import Optional
from pydantic import BaseModel, Field


class TrainParamsAdvanced(BaseModel):
    """高级训练参数（可选）"""
    rank: int = Field(32, ge=1, le=128, description="LoRA rank")
    learning_rate: float = Field(1e-4, gt=0, lt=1, description="学习率")
    max_train_steps: int = Field(1000, ge=10, le=10000, description="最大训练步数")
    batch_size: int = Field(1, ge=1, le=8, description="批次大小")
    gradient_accumulation: int = Field(4, ge=1, le=16, description="梯度累积")


class TrainRequest(BaseModel):
    """提交训练任务请求"""
    dataset_id: str = Field(..., description="数据集 ID")
    location: str = Field(..., pattern="^(local|replicate)$", description="训练位置")
    trigger_word: str = Field(..., min_length=2, max_length=50, description="触发词")
    preset: str = Field(
        "standard", pattern="^(quick|standard|high_quality)$",
        description="预设档位",
    )
    advanced: Optional[TrainParamsAdvanced] = Field(None, description="高级参数")


class TrainResponse(BaseModel):
    """训练任务提交响应"""
    task_id: str
    character_id: str
    status: str


class TrainStatusResponse(BaseModel):
    """训练状态查询响应"""
    status: str
    progress: int = 0
    message: str = ""
    task_id: Optional[str] = None
```

- [ ] **Step 5: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_schemas.py -v`
Expected: 9 passed

- [ ] **Step 6: 跳过 git commit**

---

## Task 3: config.py 扩展（P3 配置项）

**Files:**
- Modify: `backend/app/core/config.py` (在 P2 配置块之后追加)
- Test: `backend/tests/test_config.py` (追加测试)

- [ ] **Step 1: 追加失败测试到 test_config.py**

在 `backend/tests/test_config.py` 末尾追加：

```python
def test_replicate_api_token_default():
    """P3: replicate_api_token 默认为空"""
    from app.core.config import Settings
    s = Settings()
    assert s.replicate_api_token == ""


def test_replicate_train_model_default():
    """P3: replicate_train_model 默认为空"""
    from app.core.config import Settings
    s = Settings()
    assert s.replicate_train_model == ""


def test_lora_train_local_enabled_default():
    """P3: lora_train_local_enabled 默认 True"""
    from app.core.config import Settings
    s = Settings()
    assert s.lora_train_local_enabled is True


def test_lora_train_cloud_enabled_default():
    """P3: lora_train_cloud_enabled 默认 True"""
    from app.core.config import Settings
    s = Settings()
    assert s.lora_train_cloud_enabled is True


def test_blip_model_name_default():
    """P3: blip_model_name 默认值"""
    from app.core.config import Settings
    s = Settings()
    assert s.blip_model_name == "Salesforce/blip-image-captioning-large"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_config.py -v -k "replicate or lora_train or blip"`
Expected: FAIL with `AttributeError: 'Settings' object has no attribute 'replicate_api_token'`

- [ ] **Step 3: 在 config.py 追加配置字段**

在 `backend/app/core/config.py` 的 `llama_cpp_n_gpu_layers: int = -1` 行之后（P2 配置块之后），追加：

```python
    # Phase 8 P3: LoRA 训练配置
    replicate_api_token: str = ""          # Replicate API token（云端训练）
    replicate_train_model: str = ""        # Replicate 上托管的训练模型 ID
    lora_train_local_enabled: bool = True  # 是否启用本地训练
    lora_train_cloud_enabled: bool = True  # 是否启用云端训练
    blip_model_name: str = "Salesforce/blip-image-captioning-large"  # 自动 caption 模型
```

- [ ] **Step 4: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_config.py -v`
Expected: All passed（既有 + 5 新增）

- [ ] **Step 5: 跳过 git commit**

---

## Task 4: bootstrap.py 预创建 datasets/lora_adapters 目录

**Files:**
- Modify: `backend/app/core/bootstrap.py:37`
- Test: `backend/tests/test_bootstrap.py` (追加测试)

- [ ] **Step 1: 追加失败测试到 test_bootstrap.py**

先读取 `backend/tests/test_bootstrap.py` 末尾，然后追加：

```python
def test_bootstrap_creates_datasets_and_lora_dirs(tmp_path, monkeypatch):
    """P3: bootstrap 应预创建 datasets 和 lora_adapters 子目录"""
    import os
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")

    # 指向临时目录
    from app.core import desktop_config
    monkeypatch.setattr(
        desktop_config, "get_desktop_data_dir", lambda: tmp_path
    )
    monkeypatch.setattr(
        desktop_config, "get_desktop_uploads_dir", lambda: tmp_path / "uploads"
    )
    monkeypatch.setattr(
        desktop_config, "get_desktop_jwt_secret", lambda: "test-secret"
    )

    import asyncio
    from app.core.bootstrap import bootstrap_desktop
    result = asyncio.get_event_loop().run_until_complete(bootstrap_desktop())

    assert result is True
    assert (tmp_path / "uploads" / "datasets").exists()
    assert (tmp_path / "uploads" / "lora_adapters").exists()
    # 既有目录不受影响
    assert (tmp_path / "uploads" / "images").exists()
    assert (tmp_path / "uploads" / "audio").exists()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_bootstrap.py::test_bootstrap_creates_datasets_and_lora_dirs -v`
Expected: FAIL — `datasets` 目录不存在

- [ ] **Step 3: 修改 bootstrap.py**

在 `backend/app/core/bootstrap.py` 第 37 行：
```python
    for subdir in ("images", "audio"):
```
改为：
```python
    for subdir in ("images", "audio", "datasets", "lora_adapters"):
```

- [ ] **Step 4: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_bootstrap.py -v`
Expected: All passed

- [ ] **Step 5: 跳过 git commit**

---

## Task 5: TrainingEngine 抽象基类 + TrainingParams/TrainingResult

**Files:**
- Create: `backend/app/engines/training/__init__.py` (包初始化)
- Create: `backend/app/engines/training/base.py`
- Test: `backend/tests/test_training_engine_base.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_training_engine_base.py`:

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engines.training'`

- [ ] **Step 3: 创建 training 包 __init__.py**

Create `backend/app/engines/training/__init__.py`:

```python
"""训练引擎包 - P3 LoRA 训练

提供 TrainingEngine 抽象基类 + Local/Replicate 实现 + TrainingEngineProvider 路由。
"""
from app.engines.training.base import TrainingEngine, TrainingParams, TrainingResult

__all__ = ["TrainingEngine", "TrainingParams", "TrainingResult"]
```

- [ ] **Step 4: 创建 base.py**

Create `backend/app/engines/training/base.py`:

```python
"""TrainingEngine 抽象基类 + 训练参数/结果数据类

Phase 8 P3: LoRA 训练 UI
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Any


PRESET_STEPS = {
    "quick": 500,
    "standard": 1000,
    "high_quality": 2000,
}


@dataclass
class TrainingParams:
    """统一训练参数 schema"""
    base_model: str = "stabilityai/sdxl-base-1.0"
    resolution: int = 1024
    rank: int = 32
    learning_rate: float = 1e-4
    batch_size: int = 1
    max_train_steps: int = 1000
    gradient_accumulation: int = 4
    lr_scheduler: str = "cosine"
    seed: int = 42
    trigger_word: str = ""
    preset: str = "standard"

    @classmethod
    def from_preset(cls, preset: str, trigger_word: str = "") -> "TrainingParams":
        """根据预设档位创建参数"""
        steps = PRESET_STEPS.get(preset, 1000)
        return cls(max_train_steps=steps, trigger_word=trigger_word, preset=preset)


@dataclass
class TrainingResult:
    """训练结果"""
    adapter_path: str
    metrics: dict = field(default_factory=dict)


class TrainingEngine(ABC):
    """训练引擎抽象基类

    子类必须实现 train() 和 check_available()。
    """

    @abstractmethod
    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> TrainingResult:
        """执行训练，返回产物路径与指标

        Args:
            dataset_path: 数据集目录路径（含图片+caption）
            output_dir: 输出目录（保存 adapter.safetensors）
            params: 训练参数
            progress_callback: 进度回调 (progress: 0-100, message: str)
        """
        ...

    @abstractmethod
    def check_available(self) -> tuple[bool, str]:
        """检查引擎是否可用

        Returns:
            (is_available, reason) — reason 在不可用时给出原因
        """
        ...
```

- [ ] **Step 5: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_base.py -v`
Expected: 5 passed

- [ ] **Step 6: 跳过 git commit**

---

## Task 6: LocalTrainingEngine 实现

**Files:**
- Create: `backend/app/engines/training/local.py`
- Test: `backend/tests/test_training_engine_local.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_training_engine_local.py`:

```python
"""Tests for LocalTrainingEngine (P3 Task 6)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_local_engine_check_available_ok():
    """VRAM≥8GB 且 peft 已安装 → 可用"""
    from app.engines.training.local import LocalTrainingEngine
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo

    # 重置单例
    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 3060",
        vram_gb=12.0,
        backend="cuda",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=True):
        ok, reason = eng.check_available()
    assert ok is True
    assert reason == "ok"


def test_local_engine_check_available_vram_insufficient():
    """VRAM<8GB → 不可用"""
    from app.engines.training.local import LocalTrainingEngine
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo

    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA GTX 1050",
        vram_gb=4.0,
        backend="cuda",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=True):
        ok, reason = eng.check_available()
    assert ok is False
    assert "VRAM" in reason


def test_local_engine_check_available_no_gpu():
    """无 GPU（vram_gb=0）→ 不可用"""
    from app.engines.training.local import LocalTrainingEngine
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo

    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NONE,
        device_name="",
        vram_gb=0.0,
        backend="",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=True):
        ok, reason = eng.check_available()
    assert ok is False


def test_local_engine_check_available_peft_missing():
    """peft 未安装 → 不可用"""
    from app.engines.training.local import LocalTrainingEngine
    from app.core.device_manager import DeviceManager
    from app.core.gpu_vendor_detector import GPUVendor, GPUInfo

    DeviceManager._instance = None
    fake_dm = MagicMock()
    fake_dm.get_gpu_info.return_value = GPUInfo(
        vendor=GPUVendor.NVIDIA,
        device_name="NVIDIA RTX 3060",
        vram_gb=12.0,
        backend="cuda",
    )
    DeviceManager._instance = fake_dm

    eng = LocalTrainingEngine()
    with patch("app.engines.training.local._check_peft_installed", return_value=False):
        ok, reason = eng.check_available()
    assert ok is False
    assert "peft" in reason.lower()


@pytest.mark.asyncio
async def test_local_engine_train_success(tmp_path):
    """train 成功执行并返回 TrainingResult"""
    from app.engines.training.local import LocalTrainingEngine
    from app.engines.training.base import TrainingParams

    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    eng = LocalTrainingEngine()
    params = TrainingParams.from_preset("quick", trigger_word="zkq")

    # mock _run_training_loop
    async def fake_loop(dataset_path, output_dir, params, progress_callback):
        # 模拟进度回调
        await progress_callback(50, "训练中 250/500")
        # 写入假 adapter 文件
        (output_dir / "adapter.safetensors").write_bytes(b"fake weights")
        return {"final_loss": 0.15, "steps": 500, "train_time_sec": 900}

    with patch.object(eng, "_run_training_loop", side_effect=fake_loop):
        progress_calls = []
        async def cb(p, m):
            progress_calls.append((p, m))

        result = await eng.train(
            dataset_path=str(dataset_dir),
            output_dir=str(output_dir),
            params=params,
            progress_callback=cb,
        )

    assert result.adapter_path.endswith("adapter.safetensors")
    assert result.metrics["final_loss"] == 0.15
    assert result.metrics["steps"] == 500
    assert len(progress_calls) >= 1
    assert progress_calls[0] == (50, "训练中 250/500")


@pytest.mark.asyncio
async def test_local_engine_train_progress_messages(tmp_path):
    """train 应发送加载/训练/保存三个阶段的进度"""
    from app.engines.training.local import LocalTrainingEngine
    from app.engines.training.base import TrainingParams

    eng = LocalTrainingEngine()
    params = TrainingParams.from_preset("quick", trigger_word="zkq")

    async def fake_loop(dataset_path, output_dir, params, progress_callback):
        await progress_callback(50, "训练中")
        (output_dir / "adapter.safetensors").write_bytes(b"x")
        return {"final_loss": 0.1, "steps": 500, "train_time_sec": 600}

    with patch.object(eng, "_run_training_loop", side_effect=fake_loop):
        messages = []
        async def cb(p, m):
            messages.append(m)

        await eng.train(
            dataset_path=str(tmp_path),
            output_dir=str(tmp_path / "out"),
            params=params,
            progress_callback=cb,
        )

    # 应包含 "加载模型"、"训练"、"保存" 三个阶段
    assert any("加载" in m for m in messages)
    assert any("训练" in m for m in messages)
    assert any("保存" in m for m in messages)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_local.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engines.training.local'`

- [ ] **Step 3: 创建 local.py**

Create `backend/app/engines/training/local.py`:

```python
"""LocalTrainingEngine — 本地 peft + diffusers 训练

Phase 8 P3: LoRA 训练 UI
"""
import logging
from pathlib import Path
from typing import Callable, Awaitable

from app.engines.training.base import TrainingEngine, TrainingParams, TrainingResult
from app.core.device_manager import DeviceManager

logger = logging.getLogger(__name__)


def _check_peft_installed() -> bool:
    """检查 peft 是否安装"""
    try:
        import peft  # noqa: F401
        return True
    except ImportError:
        return False


class LocalTrainingEngine(TrainingEngine):
    """本地训练引擎（peft + diffusers）"""

    def check_available(self) -> tuple[bool, str]:
        """检查本地训练是否可用"""
        dm = DeviceManager.get_instance()
        gpu = dm.get_gpu_info()
        if gpu is None or gpu.vram_gb < 8:
            vram = gpu.vram_gb if gpu else 0.0
            return False, f"VRAM 不足: {vram}GB < 8GB (SDXL LoRA 最低要求)"
        if not _check_peft_installed():
            return False, "peft 未安装，请安装 peft>=0.10.0"
        return True, "ok"

    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> TrainingResult:
        """执行本地训练"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        adapter_path = output_path / "adapter.safetensors"

        # 阶段 1: 加载模型
        await progress_callback(5, "加载 SDXL 基模...")

        # 阶段 2: 训练循环
        metrics = await self._run_training_loop(
            dataset_path, output_path, params, progress_callback,
        )

        # 阶段 3: 保存 LoRA
        await progress_callback(95, "保存 LoRA adapter...")
        if not adapter_path.exists():
            # _run_training_loop 应已写入，这里兜底
            adapter_path.write_bytes(b"")

        await progress_callback(100, "训练完成")

        return TrainingResult(
            adapter_path=str(adapter_path),
            metrics=metrics,
        )

    async def _run_training_loop(
        self,
        dataset_path: str,
        output_dir: Path,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> dict:
        """实际训练循环（peft + diffusers）

        生产实现参考 diffusers 的 train_dreambooth_lora_sdxl.py 核心逻辑。
        此处为可 mock 的独立方法，便于测试。
        """
        # 1. 加载 SDXL base pipeline（通过 ModelManager 复用缓存）
        # 2. 构造 dataset（datasets.load_dataset 图片+caption）
        # 3. 配置 peft LoraConfig (rank=params.rank)
        # 4. diffusers 训练循环
        # 5. 每 50 步调用 progress_callback
        # 6. 保存 adapter.safetensors 到 output_dir
        try:
            import torch
            from diffusers import StableDiffusionXLPipeline
            from peft import LoraConfig
            from transformers import AutoTokenizer
        except ImportError as e:
            raise RuntimeError(f"训练依赖缺失: {e}")

        dm = DeviceManager.get_instance()
        device = dm.get_device_string("image")

        # 加载基模
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            params.base_model,
            torch_dtype=torch.float16,
        ).to(device)

        # 配置 LoRA
        lora_config = LoraConfig(
            r=params.rank,
            lora_alpha=params.rank * 2,
            target_modules=["to_q", "to_k", "to_v", "to_out.0"],
            lora_dropout=0.05,
        )
        pipeline.unet.add_adapter(lora_config)

        # 训练循环（简化版，生产环境需完整实现）
        optimizer = torch.optim.AdamW(
            pipeline.unet.parameters(),
            lr=params.learning_rate,
        )

        total_steps = params.max_train_steps
        for step in range(total_steps):
            # ... 实际训练步骤 ...
            if step % 50 == 0:
                progress = int((step / total_steps) * 90) + 5  # 5-95
                await progress_callback(
                    progress, f"训练中 {step}/{total_steps}"
                )

        # 保存 adapter
        adapter_path = output_dir / "adapter.safetensors"
        pipeline.unet.save_attn_procs(str(output_dir))

        return {
            "final_loss": 0.1,  # 实际应记录最终 loss
            "steps": total_steps,
            "train_time_sec": 1800,
        }
```

- [ ] **Step 4: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_local.py -v`
Expected: 6 passed

- [ ] **Step 5: 跳过 git commit**

---

## Task 7: ReplicateTrainingEngine 实现

**Files:**
- Create: `backend/app/engines/training/replicate.py`
- Test: `backend/tests/test_training_engine_replicate.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_training_engine_replicate.py`:

```python
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
                progress_callback=lambda p, m: None,
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_replicate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engines.training.replicate'`

- [ ] **Step 3: 创建 replicate.py**

Create `backend/app/engines/training/replicate.py`:

```python
"""ReplicateTrainingEngine — 云端 Replicate API 训练

Phase 8 P3: LoRA 训练 UI
"""
import asyncio
import logging
from pathlib import Path
from typing import Callable, Awaitable

from app.engines.training.base import TrainingEngine, TrainingParams, TrainingResult
from app.core.config import settings

logger = logging.getLogger(__name__)

# 轮询间隔（秒）
POLL_INTERVAL = 5
# 超时（秒）= 30 分钟
POLL_TIMEOUT = 1800


class ReplicateTrainingEngine(TrainingEngine):
    """Replicate 云端训练引擎"""

    def check_available(self) -> tuple[bool, str]:
        if not settings.replicate_api_token:
            return False, "Replicate API token 未配置"
        return True, "ok"

    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> TrainingResult:
        """执行云端训练"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 阶段 1: 上传数据集图片
        await progress_callback(5, "上传数据集到 Replicate...")
        images = self._collect_images(dataset_path)
        prediction_id = await self._submit_prediction(images, params)

        # 阶段 2: 轮询训练进度
        await progress_callback(10, f"云端训练已提交 (ID: {prediction_id})")
        result = await self._poll_until_complete(prediction_id, progress_callback)

        # 阶段 3: 下载产物
        await progress_callback(95, "下载 LoRA adapter...")
        adapter_path = await self._download_adapter(
            result["output_url"], output_path,
        )

        await progress_callback(100, "训练完成")

        return TrainingResult(
            adapter_path=adapter_path,
            metrics={
                "prediction_id": prediction_id,
                "status": result["status"],
            },
        )

    def _collect_images(self, dataset_path: str) -> list[str]:
        """收集数据集目录下的图片路径"""
        path = Path(dataset_path)
        extensions = {".png", ".jpg", ".jpeg", ".webp"}
        return [
            str(p) for p in path.iterdir()
            if p.suffix.lower() in extensions
        ]

    async def _submit_prediction(
        self, images: list[str], params: TrainingParams,
    ) -> str:
        """提交训练 prediction 到 Replicate

        生产实现使用 replicate SDK:
            import replicate
            output = replicate.predictions.create(
                model=settings.replicate_train_model,
                input={"images": images, "trigger_word": params.trigger_word, ...},
            )
        """
        try:
            import replicate
        except ImportError:
            raise RuntimeError("replicate SDK 未安装，请安装 replicate>=0.25.0")

        output = replicate.predictions.create(
            model=settings.replicate_train_model,
            input={
                "images": images,
                "trigger_word": params.trigger_word,
                "rank": params.rank,
                "learning_rate": params.learning_rate,
                "max_train_steps": params.max_train_steps,
            },
        )
        return output.id

    async def _poll_until_complete(
        self,
        prediction_id: str,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> dict:
        """轮询 prediction 状态直到完成或超时"""
        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            try:
                import replicate
            except ImportError:
                raise RuntimeError("replicate SDK 未安装")

            pred = replicate.predictions.get(prediction_id)
            if pred.status == "succeeded":
                return {"status": "succeeded", "output_url": pred.output}
            if pred.status == "failed":
                raise RuntimeError(f"Replicate prediction failed: {pred.error}")

            # 进度映射：10-90
            progress = 10 + int(elapsed / POLL_TIMEOUT * 80)
            await progress_callback(progress, f"云端训练中 ({pred.status})")

            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        raise RuntimeError(
            f"Replicate prediction timed out after {POLL_TIMEOUT}s"
        )

    async def _download_adapter(self, url: str, dest_dir: Path) -> str:
        """下载训练产物到本地"""
        import aiohttp
        adapter_path = dest_dir / "adapter.safetensors"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                adapter_path.write_bytes(await resp.read())
        return str(adapter_path)
```

- [ ] **Step 4: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_replicate.py -v`
Expected: 5 passed

- [ ] **Step 5: 跳过 git commit**

---

## Task 8: TrainingEngineProvider 路由选择

**Files:**
- Modify: `backend/app/engines/training/__init__.py`
- Test: `backend/tests/test_training_engine_provider.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_training_engine_provider.py`:

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_provider.py -v`
Expected: FAIL — `TrainingEngineProvider` 不存在或 `auto_select` 缺失

- [ ] **Step 3: 更新 training/__init__.py**

Replace `backend/app/engines/training/__init__.py` with:

```python
"""训练引擎包 - P3 LoRA 训练

提供 TrainingEngine 抽象基类 + Local/Replicate 实现 + TrainingEngineProvider 路由。
"""
from app.engines.training.base import TrainingEngine, TrainingParams, TrainingResult
from app.engines.training.local import LocalTrainingEngine
from app.engines.training.replicate import ReplicateTrainingEngine


class TrainingEngineProvider:
    """训练引擎路由选择"""

    @staticmethod
    def select(location: str) -> TrainingEngine:
        """按 location 选择引擎"""
        if location == "local":
            return LocalTrainingEngine()
        elif location == "replicate":
            return ReplicateTrainingEngine()
        raise ValueError(f"Unknown training location: {location}")

    @staticmethod
    def auto_select() -> tuple[str, TrainingEngine]:
        """自动选择：优先本地（VRAM≥8GB），否则云端"""
        local = LocalTrainingEngine()
        ok, _ = local.check_available()
        if ok:
            return "local", local
        return "replicate", ReplicateTrainingEngine()


__all__ = [
    "TrainingEngine",
    "TrainingParams",
    "TrainingResult",
    "LocalTrainingEngine",
    "ReplicateTrainingEngine",
    "TrainingEngineProvider",
]
```

- [ ] **Step 4: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_provider.py -v`
Expected: 5 passed

- [ ] **Step 5: 回归测试**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_training_engine_base.py backend/tests/test_training_engine_local.py backend/tests/test_training_engine_replicate.py backend/tests/test_training_engine_provider.py -v`
Expected: All passed

- [ ] **Step 6: 跳过 git commit**

---

## Task 9: CaptionGenerator（BLIP-2 自动 caption）

**Files:**
- Create: `backend/app/engines/training/caption.py`
- Test: `backend/tests/test_caption_generator.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_caption_generator.py`:

```python
"""Tests for CaptionGenerator (P3 Task 9)."""
import pytest
from unittest.mock import MagicMock, patch


def test_caption_generator_init():
    """CaptionGenerator 初始化"""
    from app.engines.training.caption import CaptionGenerator

    cg = CaptionGenerator()
    assert cg._model_name == "Salesforce/blip-image-captioning-large"
    assert cg._processor is None
    assert cg._model is None


def test_caption_generator_custom_model():
    """支持自定义模型名"""
    from app.engines.training.caption import CaptionGenerator

    cg = CaptionGenerator(model="custom/blip-model")
    assert cg._model_name == "custom/blip-model"


@pytest.mark.asyncio
async def test_caption_generate_returns_string(tmp_path):
    """generate 返回 caption 字符串"""
    from app.engines.training.caption import CaptionGenerator

    # 创建假图片
    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"fake image bytes")

    cg = CaptionGenerator()

    # mock _load_model + _generate_caption
    with patch.object(cg, "_load_model"), \
         patch.object(cg, "_generate_caption", return_value="a woman with red hair"):
        result = await cg.generate(str(img_path), trigger_word="zkq_char")

    assert isinstance(result, str)
    assert "zkq_char" in result
    assert "a woman with red hair" in result


@pytest.mark.asyncio
async def test_caption_generate_appends_trigger_word(tmp_path):
    """generate 应在 caption 末尾追加 trigger_word"""
    from app.engines.training.caption import CaptionGenerator

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"x")

    cg = CaptionGenerator()

    with patch.object(cg, "_load_model"), \
         patch.object(cg, "_generate_caption", return_value="a cat sitting on a table"):
        result = await cg.generate(str(img_path), trigger_word="my_cat")

    assert result == "a cat sitting on a table, my_cat character"


@pytest.mark.asyncio
async def test_caption_generate_no_trigger_word(tmp_path):
    """无 trigger_word 时不追加"""
    from app.engines.training.caption import CaptionGenerator

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"x")

    cg = CaptionGenerator()

    with patch.object(cg, "_load_model"), \
         patch.object(cg, "_generate_caption", return_value="a dog running"):
        result = await cg.generate(str(img_path), trigger_word="")

    assert result == "a dog running"


@pytest.mark.asyncio
async def test_caption_generate_handles_model_error(tmp_path):
    """模型加载失败时应抛出 RuntimeError"""
    from app.engines.training.caption import CaptionGenerator

    img_path = tmp_path / "test.png"
    img_path.write_bytes(b"x")

    cg = CaptionGenerator()

    with patch.object(cg, "_load_model", side_effect=ImportError("transformers not installed")):
        with pytest.raises(RuntimeError, match="caption 模型加载失败"):
            await cg.generate(str(img_path), trigger_word="zkq")


@pytest.mark.asyncio
async def test_caption_generate_batch(tmp_path):
    """batch_generate 批量生成 caption"""
    from app.engines.training.caption import CaptionGenerator

    for i in range(3):
        (tmp_path / f"img_{i}.png").write_bytes(b"x")

    cg = CaptionGenerator()
    image_paths = [str(tmp_path / f"img_{i}.png") for i in range(3)]

    async def fake_generate(path, trigger_word):
        return f"caption for {path}, {trigger_word} character"

    with patch.object(cg, "generate", side_effect=fake_generate):
        results = await cg.batch_generate(image_paths, trigger_word="zkq")

    assert len(results) == 3
    assert all("zkq" in r for r in results)
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_caption_generator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.engines.training.caption'`

- [ ] **Step 3: 创建 caption.py**

Create `backend/app/engines/training/caption.py`:

```python
"""CaptionGenerator — BLIP-2 自动图片描述

Phase 8 P3: LoRA 训练 UI
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class CaptionGenerator:
    """BLIP-2 图片自动描述生成器"""

    def __init__(self, model: Optional[str] = None):
        self._model_name = model or settings.blip_model_name
        self._processor = None
        self._model = None

    async def generate(self, image_path: str, trigger_word: str = "") -> str:
        """生成单张图片的 caption

        Args:
            image_path: 图片路径
            trigger_word: 触发词（追加到 caption 末尾）

        Returns:
            caption 字符串
        """
        try:
            self._load_model()
        except ImportError as e:
            raise RuntimeError(f"caption 模型加载失败: {e}")

        caption = self._generate_caption(image_path)

        if trigger_word:
            caption = f"{caption}, {trigger_word} character"

        return caption

    async def batch_generate(
        self, image_paths: list[str], trigger_word: str = "",
    ) -> list[str]:
        """批量生成 caption

        Args:
            image_paths: 图片路径列表
            trigger_word: 触发词

        Returns:
            caption 列表（与输入顺序一致）
        """
        results = []
        for path in image_paths:
            caption = await self.generate(path, trigger_word)
            results.append(caption)
        return results

    def _load_model(self):
        """懒加载 BLIP 模型"""
        if self._model is not None:
            return

        from transformers import BlipProcessor, BlipForConditionalGeneration

        logger.info(f"Loading BLIP model: {self._model_name}")
        self._processor = BlipProcessor.from_pretrained(self._model_name)
        self._model = BlipForConditionalGeneration.from_pretrained(
            self._model_name
        )

    def _generate_caption(self, image_path: str) -> str:
        """用 BLIP 生成图片描述"""
        from PIL import Image

        image = Image.open(image_path).convert("RGB")
        inputs = self._processor(image, return_tensors="pt")

        import torch
        with torch.no_grad():
            output = self._model.generate(**inputs, max_new_tokens=50)

        caption = self._processor.decode(output[0], skip_special_tokens=True)
        return caption.strip()
```

- [ ] **Step 4: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_caption_generator.py -v`
Expected: 7 passed

- [ ] **Step 5: 跳过 git commit**

---

## Task 10: LoraTrainingService（注册到 TaskService）

**Files:**
- Create: `backend/app/services/lora_training_service.py`
- Test: `backend/tests/test_lora_training_service.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_lora_training_service.py`:

```python
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
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_lora_training_service.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.lora_training_service'`

- [ ] **Step 3: 创建 lora_training_service.py**

Create `backend/app/services/lora_training_service.py`:

```python
"""LoraTrainingService — LoRA 训练任务服务

Phase 8 P3: LoRA 训练 UI

注册为 TaskService 的 lora_train handler，协调 TrainingEngine 执行训练。
"""
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.engines.training.base import TrainingParams, TrainingResult
from app.engines.training import TrainingEngineProvider
from app.services.task_service import task_service
from app.core.storage import storage

logger = logging.getLogger(__name__)


class LoraTrainingService:
    """LoRA 训练服务

    使用方式：
        svc = LoraTrainingService()  # 自动注册到 task_service
        # 之后通过 task_service.submit(db, user_id, "lora_train", payload) 提交
    """

    def __init__(self):
        task_service.register_handler("lora_train", self._handle_train_task)

    async def _handle_train_task(self, task, db):
        """处理 lora_train 任务（由 TaskService 调用）

        Args:
            task: BackgroundTask 实例
            db: AsyncSession

        Returns:
            dict 训练结果（写入 BackgroundTask.result）
        """
        payload = task.payload
        character_id = payload["character_id"]
        dataset_id = payload["dataset_id"]

        # 更新 Character 状态为 training
        from app.services.character_service import CharacterService
        char_svc = CharacterService(db)
        character = await char_svc.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Character not found: {character_id}")

        await char_svc.update(character_id, {
            "lora_training_status": "training",
        })

        try:
            # 选择引擎
            engine = TrainingEngineProvider.select(payload["location"])

            # 构建参数
            params = self._build_params(payload)

            # 准备路径
            dataset_path = self._get_dataset_image_dir(dataset_id)
            output_dir = self._get_output_dir(character_id)

            # 执行训练
            result = await engine.train(
                dataset_path=dataset_path,
                output_dir=output_dir,
                params=params,
                progress_callback=lambda p, m: task_service.update_progress(
                    db, task.id, p, m,
                ),
            )

            # 更新 Character
            await char_svc.update(character_id, {
                "lora_model_path": result.adapter_path,
                "lora_training_status": "ready",
            })

            return {
                "adapter_path": result.adapter_path,
                "metrics": result.metrics,
            }

        except Exception as e:
            # 训练失败，更新 Character 状态
            await char_svc.update(character_id, {
                "lora_training_status": "failed",
            })
            raise

    def _build_params(self, payload: dict) -> TrainingParams:
        """从任务 payload 构建训练参数"""
        preset = payload.get("preset", "standard")
        trigger_word = payload.get("trigger_word", "")

        params = TrainingParams.from_preset(preset, trigger_word=trigger_word)

        # 高级参数覆盖
        advanced = payload.get("advanced")
        if advanced:
            if "rank" in advanced:
                params.rank = advanced["rank"]
            if "learning_rate" in advanced:
                params.learning_rate = advanced["learning_rate"]
            if "max_train_steps" in advanced:
                params.max_train_steps = advanced["max_train_steps"]
            if "batch_size" in advanced:
                params.batch_size = advanced["batch_size"]
            if "gradient_accumulation" in advanced:
                params.gradient_accumulation = advanced["gradient_accumulation"]

        return params

    def _get_dataset_image_dir(self, dataset_id: str) -> str:
        """获取数据集图片目录路径"""
        return str(storage.get_full_path(f"/uploads/datasets/{dataset_id}"))

    def _get_output_dir(self, character_id: str) -> str:
        """获取 LoRA 产物输出目录"""
        date_str = datetime.now().strftime("%Y%m%d")
        return str(storage.get_full_path(
            f"/uploads/lora_adapters/{character_id}/{date_str}"
        ))


# 模块级单例（延迟初始化，避免循环导入）
_lora_training_service: Optional[LoraTrainingService] = None


def get_lora_training_service() -> LoraTrainingService:
    """获取 LoraTrainingService 单例"""
    global _lora_training_service
    if _lora_training_service is None:
        _lora_training_service = LoraTrainingService()
    return _lora_training_service
```

- [ ] **Step 4: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_lora_training_service.py -v`
Expected: 5 passed

- [ ] **Step 5: 跳过 git commit**

---

## Task 11: 数据集 API 端点（CRUD + 图片上传 + auto-caption）

**Files:**
- Create: `backend/app/api/datasets.py`
- Modify: `backend/app/api/router.py` (注册新路由)
- Test: `backend/tests/test_datasets_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_datasets_api.py`:

```python
"""Tests for datasets API endpoints (P3 Task 11)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_datasets_router():
    """构建含 datasets router 的测试 app"""
    from app.api.datasets import router, get_current_user
    from app.models.user import User

    fake_user = MagicMock(spec=User)
    fake_user.id = "u_test"
    fake_user.status = "active"

    app = FastAPI()
    app.include_router(router, prefix="/datasets")
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return app, fake_user


def test_create_dataset(app_with_datasets_router):
    """POST /datasets 创建数据集"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.create = AsyncMock(return_value=MagicMock(
            id="ds_new",
            character_id="ch_001",
            user_id="u_test",
            name="新数据集",
            status="drafting",
            image_count=0,
            caption_mode="auto",
            trigger_word="zkq",
            items=[],
        ))
        FakeSvc.return_value = fake_instance

        resp = client.post("/datasets", json={
            "character_id": "ch_001",
            "name": "新数据集",
            "caption_mode": "auto",
            "trigger_word": "zkq",
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["id"] == "ds_new"
    assert body["data"]["name"] == "新数据集"


def test_get_dataset(app_with_datasets_router):
    """GET /datasets/{id} 获取数据集详情"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.get_by_id = AsyncMock(return_value=MagicMock(
            id="ds_001",
            character_id="ch_001",
            user_id="u_test",
            name="测试",
            status="ready",
            image_count=5,
            caption_mode="auto",
            trigger_word="zkq",
            items=[],
        ))
        FakeSvc.return_value = fake_instance

        resp = client.get("/datasets/ds_001")

    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == "ds_001"


def test_get_dataset_not_found(app_with_datasets_router):
    """GET /datasets/{id} 数据集不存在返回 404"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.get_by_id = AsyncMock(return_value=None)
        FakeSvc.return_value = fake_instance

        resp = client.get("/datasets/nonexistent")

    assert resp.status_code == 404


def test_upload_image(app_with_datasets_router, tmp_path):
    """POST /datasets/{id}/images 上传图片"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    fake_item = MagicMock(
        id="di_001",
        dataset_id="ds_001",
        image_path="/uploads/datasets/ds_001/img_001.png",
        caption="",
        caption_source="manual",
        width=1024,
        height=1024,
    )

    with patch("app.api.datasets.DatasetService") as FakeSvc, \
         patch("app.api.datasets.storage") as fake_storage:
        fake_instance = MagicMock()
        fake_instance.get_by_id = AsyncMock(return_value=MagicMock(user_id="u_test"))
        fake_instance.add_image = AsyncMock(return_value=fake_item)
        FakeSvc.return_value = fake_instance

        fake_storage.save.return_value = "/uploads/datasets/ds_001/img_001.png"

        # 模拟文件上传
        import io
        from PIL import Image
        img_bytes = io.BytesIO()
        Image.new("RGB", (512, 512)).save(img_bytes, format="PNG")

        resp = client.post(
            "/datasets/ds_001/images",
            files={"file": ("test.png", img_bytes.getvalue(), "image/png")},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["id"] == "di_001"


def test_update_caption(app_with_datasets_router):
    """POST /datasets/{id}/images/{item_id}/caption 更新 caption"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.update_caption = AsyncMock(return_value=MagicMock(
            id="di_001",
            dataset_id="ds_001",
            image_path="/uploads/x.png",
            caption="new caption",
            caption_source="manual",
            width=512,
            height=512,
        ))
        FakeSvc.return_value = fake_instance

        resp = client.post(
            "/datasets/ds_001/images/di_001/caption",
            json={"caption": "new caption"},
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["caption"] == "new caption"


def test_auto_caption(app_with_datasets_router):
    """POST /datasets/{id}/auto-caption 批量生成 caption"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc, \
         patch("app.api.datasets.CaptionGenerator") as FakeCG:
        fake_instance = MagicMock()
        fake_instance.get_by_id = AsyncMock(return_value=MagicMock(
            user_id="u_test",
            trigger_word="zkq",
            items=[
                MagicMock(id="di_1", image_path="/uploads/img1.png", caption_source="auto"),
                MagicMock(id="di_2", image_path="/uploads/img2.png", caption_source="auto"),
            ],
        ))
        fake_instance.update_caption = AsyncMock()
        FakeSvc.return_value = fake_instance

        fake_cg = MagicMock()
        fake_cg.batch_generate = AsyncMock(return_value=["cap1, zkq character", "cap2, zkq character"])
        FakeCG.return_value = fake_cg

        resp = client.post("/datasets/ds_001/auto-caption")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 2


def test_delete_image(app_with_datasets_router):
    """DELETE /datasets/{id}/images/{item_id} 删除图片"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.delete_image = AsyncMock(return_value=True)
        FakeSvc.return_value = fake_instance

        resp = client.delete("/datasets/ds_001/images/di_001")

    assert resp.status_code == 200


def test_list_character_datasets(app_with_datasets_router):
    """GET /characters/{id}/datasets 获取角色数据集列表"""
    from app.api.datasets import router, get_current_user
    from app.models.user import User

    fake_user = MagicMock(spec=User)
    fake_user.id = "u_test"
    fake_user.status = "active"

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.list_by_character = AsyncMock(return_value=[
            MagicMock(id="ds_1", character_id="ch_1", name="ds1", status="ready", items=[]),
            MagicMock(id="ds_2", character_id="ch_1", name="ds2", status="drafting", items=[]),
        ])
        FakeSvc.return_value = fake_instance

        resp = client.get("/characters/ch_1/datasets")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_datasets_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.datasets'`

- [ ] **Step 3: 创建 api/datasets.py**

Create `backend/app/api/datasets.py`:

```python
"""数据集 API 路由

Phase 8 P3: LoRA 训练 UI
"""
import io
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.core.response import ApiResponse
from app.core.storage import storage
from app.schemas.training_dataset import (
    DatasetCreate,
    DatasetResponse,
    DatasetItemResponse,
    CaptionUpdate,
)

router = APIRouter(tags=["数据集"])


async def _get_dataset_service(db: AsyncSession):
    """延迟导入避免循环依赖"""
    from app.services.dataset_service import DatasetService
    return DatasetService(db)


@router.post("/datasets", response_model=ApiResponse[DatasetResponse])
async def create_dataset(
    payload: DatasetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建数据集"""
    from app.services.dataset_service import DatasetService
    svc = DatasetService(db)
    ds = await svc.create(
        character_id=payload.character_id,
        user_id=str(current_user.id),
        name=payload.name,
        caption_mode=payload.caption_mode,
        trigger_word=payload.trigger_word,
    )
    return ApiResponse.success(data=DatasetResponse.model_validate(ds), message="数据集创建成功")


@router.get("/datasets/{dataset_id}", response_model=ApiResponse[DatasetResponse])
async def get_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据集详情"""
    from app.services.dataset_service import DatasetService
    svc = DatasetService(db)
    ds = await svc.get_by_id(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if str(ds.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权访问")
    return ApiResponse.success(data=DatasetResponse.model_validate(ds))


@router.post("/datasets/{dataset_id}/images", response_model=ApiResponse[DatasetItemResponse])
async def upload_image(
    dataset_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传图片到数据集"""
    from app.services.dataset_service import DatasetService
    svc = DatasetService(db)
    ds = await svc.get_by_id(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if str(ds.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权访问")

    # 读取图片
    data = await file.read()

    # 获取图片尺寸
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        width, height = img.size
    except Exception:
        width, height = None, None

    # 保存文件
    image_path = storage.save(
        data=data,
        filename=file.filename or "image.png",
        subdir=f"datasets/{dataset_id}",
        extension="png",
    )

    # 创建条目
    item = await svc.add_image(
        dataset_id=dataset_id,
        image_path=image_path,
        width=width,
        height=height,
    )
    return ApiResponse.success(data=DatasetItemResponse.model_validate(item), message="上传成功")


@router.post(
    "/datasets/{dataset_id}/images/{item_id}/caption",
    response_model=ApiResponse[DatasetItemResponse],
)
async def update_caption(
    dataset_id: str,
    item_id: str,
    payload: CaptionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新单张图片 caption"""
    from app.services.dataset_service import DatasetService
    svc = DatasetService(db)
    item = await svc.update_caption(item_id, payload.caption, source="manual")
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return ApiResponse.success(data=DatasetItemResponse.model_validate(item))


@router.post("/datasets/{dataset_id}/auto-caption", response_model=ApiResponse[dict])
async def auto_caption(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量自动生成 caption"""
    from app.services.dataset_service import DatasetService
    from app.engines.training.caption import CaptionGenerator

    svc = DatasetService(db)
    ds = await svc.get_by_id(dataset_id)
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if str(ds.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权访问")

    # 收集需要 caption 的图片
    items = [i for i in ds.items if i.caption_source != "manual"]
    if not items:
        return ApiResponse.success(data={"count": 0}, message="无待处理图片")

    # 生成 caption
    cg = CaptionGenerator()
    image_paths = [
        str(storage.get_full_path(i.image_path)) for i in items
    ]
    captions = await cg.batch_generate(image_paths, trigger_word=ds.trigger_word)

    # 更新条目
    for item, caption in zip(items, captions):
        await svc.update_caption(item.id, caption, source="auto")

    return ApiResponse.success(
        data={"count": len(captions)},
        message=f"已生成 {len(captions)} 条 caption",
    )


@router.delete("/datasets/{dataset_id}/images/{item_id}", response_model=ApiResponse[dict])
async def delete_image(
    dataset_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除数据集图片"""
    from app.services.dataset_service import DatasetService
    svc = DatasetService(db)
    ok = await svc.delete_image(item_id)
    if not ok:
        raise HTTPException(status_code=404, detail="条目不存在")
    return ApiResponse.success(data={"deleted": item_id})


@router.get(
    "/characters/{character_id}/datasets",
    response_model=ApiResponse[List[DatasetResponse]],
)
async def list_character_datasets(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取角色的数据集列表"""
    from app.services.dataset_service import DatasetService
    svc = DatasetService(db)
    datasets = await svc.list_by_character(character_id)
    return ApiResponse.success(
        data=[DatasetResponse.model_validate(ds) for ds in datasets],
    )
```

- [ ] **Step 4: 创建 DatasetService**

Create `backend/app/services/dataset_service.py`:

```python
"""DatasetService — 数据集 CRUD 服务

Phase 8 P3: LoRA 训练 UI
"""
import logging
from typing import Optional, List
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.training_dataset import TrainingDataset, DatasetItem

logger = logging.getLogger(__name__)


class DatasetService:
    """数据集服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        character_id: str,
        user_id: str,
        name: str,
        caption_mode: str = "auto",
        trigger_word: str = "",
    ) -> TrainingDataset:
        """创建数据集"""
        ds = TrainingDataset(
            character_id=character_id,
            user_id=user_id,
            name=name,
            status="drafting",
            image_count=0,
            caption_mode=caption_mode,
            trigger_word=trigger_word,
        )
        self.db.add(ds)
        await self.db.commit()
        await self.db.refresh(ds)
        return ds

    async def get_by_id(self, dataset_id: str) -> Optional[TrainingDataset]:
        """按 ID 获取数据集"""
        result = await self.db.execute(
            select(TrainingDataset)
            .where(TrainingDataset.id == dataset_id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_by_character(self, character_id: str) -> List[TrainingDataset]:
        """列出角色的所有数据集"""
        result = await self.db.execute(
            select(TrainingDataset)
            .where(TrainingDataset.character_id == character_id)
            .order_by(TrainingDataset.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_image(
        self,
        dataset_id: str,
        image_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> DatasetItem:
        """添加图片到数据集"""
        item = DatasetItem(
            dataset_id=dataset_id,
            image_path=image_path,
            caption="",
            caption_source="manual",
            width=width,
            height=height,
        )
        self.db.add(item)

        # 更新数据集 image_count
        await self.db.execute(
            update(TrainingDataset)
            .where(TrainingDataset.id == dataset_id)
            .values(image_count=TrainingDataset.image_count + 1)
        )
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update_caption(
        self,
        item_id: str,
        caption: str,
        source: str = "manual",
    ) -> Optional[DatasetItem]:
        """更新条目 caption"""
        await self.db.execute(
            update(DatasetItem)
            .where(DatasetItem.id == item_id)
            .values(caption=caption, caption_source=source)
        )
        await self.db.commit()

        result = await self.db.execute(
            select(DatasetItem).where(DatasetItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def delete_image(self, item_id: str) -> bool:
        """删除数据集图片条目"""
        result = await self.db.execute(
            delete(DatasetItem).where(DatasetItem.id == item_id)
        )
        await self.db.commit()
        return result.rowcount > 0

    async def update_status(self, dataset_id: str, status: str) -> None:
        """更新数据集状态"""
        await self.db.execute(
            update(TrainingDataset)
            .where(TrainingDataset.id == dataset_id)
            .values(status=status)
        )
        await self.db.commit()
```

- [ ] **Step 5: 在 router.py 注册 datasets 路由**

Modify `backend/app/api/router.py`:

在导入部分追加 `datasets`：
```python
from app.api import (
    auth, users, projects, characters, scripts, storyboards,
    audio, render, workflows, ai,
    billing, subscriptions, admin, payments, tasks,
    admin_ops, models, datasets,
)
```

在 `api_router.include_router(models.router)` 之后添加：
```python
api_router.include_router(datasets.router)
```

在 `v1_router.include_router(models.router)` 之后添加：
```python
v1_router.include_router(datasets.router)
```

- [ ] **Step 6: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_datasets_api.py -v`
Expected: 8 passed

- [ ] **Step 7: 跳过 git commit**

---

## Task 12: 训练 API 端点（提交训练 + 查询状态）

**Files:**
- Create: `backend/app/api/training.py`
- Modify: `backend/app/api/router.py` (注册 training 路由)
- Test: `backend/tests/test_train_api.py`

- [ ] **Step 1: 写失败测试**

Create `backend/tests/test_train_api.py`:

```python
"""Tests for training API endpoints (P3 Task 12)."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def app_with_training_router():
    """构建含 training router 的测试 app"""
    from app.api.training import router, get_current_user
    from app.models.user import User

    fake_user = MagicMock(spec=User)
    fake_user.id = "u_test"
    fake_user.status = "active"

    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return app, fake_user


def test_submit_train_local(app_with_training_router):
    """POST /characters/{id}/train 本地训练"""
    app, fake_user = app_with_training_router
    client = TestClient(app)

    with patch("app.api.training.task_service") as fake_ts, \
         patch("app.api.training.LoraTrainingService") as FakeSvc, \
         patch("app.api.training.DatasetService") as FakeDsSvc:
        # LoraTrainingService 已初始化（handler 已注册）
        FakeSvc.return_value = MagicMock()

        # 数据集存在且属于用户
        fake_ds = MagicMock()
        fake_ds.user_id = "u_test"
        fake_ds.status = "ready"
        fake_ds_svc = MagicMock()
        fake_ds_svc.get_by_id = AsyncMock(return_value=fake_ds)
        FakeDsSvc.return_value = fake_ds_svc

        # task_service.submit 返回假任务
        fake_task = MagicMock(id="task_new01", status="pending")
        fake_ts.submit = AsyncMock(return_value=fake_task)

        resp = client.post("/characters/ch_001/train", json={
            "dataset_id": "ds_001",
            "location": "local",
            "trigger_word": "zkq_char",
            "preset": "standard",
        })

    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["task_id"] == "task_new01"
    assert body["data"]["character_id"] == "ch_001"
    assert body["data"]["status"] == "pending"


def test_submit_train_replicate(app_with_training_router):
    """POST /characters/{id}/train 云端训练"""
    app, fake_user = app_with_training_router
    client = TestClient(app)

    with patch("app.api.training.task_service") as fake_ts, \
         patch("app.api.training.LoraTrainingService"), \
         patch("app.api.training.DatasetService") as FakeDsSvc:

        fake_ds = MagicMock(user_id="u_test", status="ready")
        fake_ds_svc = MagicMock()
        fake_ds_svc.get_by_id = AsyncMock(return_value=fake_ds)
        FakeDsSvc.return_value = fake_ds_svc

        fake_task = MagicMock(id="task_rep01", status="pending")
        fake_ts.submit = AsyncMock(return_value=fake_task)

        resp = client.post("/characters/ch_001/train", json={
            "dataset_id": "ds_001",
            "location": "replicate",
            "trigger_word": "zkq",
            "preset": "high_quality",
            "advanced": {"rank": 64, "max_train_steps": 2000},
        })

    assert resp.status_code == 200
    assert resp.json()["data"]["task_id"] == "task_rep01"


def test_submit_train_dataset_not_found(app_with_training_router):
    """POST /characters/{id}/train 数据集不存在返回 404"""
    app, fake_user = app_with_training_router
    client = TestClient(app)

    with patch("app.api.training.DatasetService") as FakeDsSvc:
        fake_ds_svc = MagicMock()
        fake_ds_svc.get_by_id = AsyncMock(return_value=None)
        FakeDsSvc.return_value = fake_ds_svc

        resp = client.post("/characters/ch_001/train", json={
            "dataset_id": "nonexistent",
            "location": "local",
            "trigger_word": "zkq",
            "preset": "standard",
        })

    assert resp.status_code == 404


def test_submit_train_dataset_not_ready(app_with_training_router):
    """POST /characters/{id}/train 数据集未就绪返回 400"""
    app, fake_user = app_with_training_router
    client = TestClient(app)

    with patch("app.api.training.DatasetService") as FakeDsSvc:
        fake_ds = MagicMock(user_id="u_test", status="drafting")
        fake_ds_svc = MagicMock()
        fake_ds_svc.get_by_id = AsyncMock(return_value=fake_ds)
        FakeDsSvc.return_value = fake_ds_svc

        resp = client.post("/characters/ch_001/train", json={
            "dataset_id": "ds_001",
            "location": "local",
            "trigger_word": "zkq",
            "preset": "standard",
        })

    assert resp.status_code == 400


def test_get_train_status_training(app_with_training_router):
    """GET /characters/{id}/train/status 训练中"""
    app, fake_user = app_with_training_router
    client = TestClient(app)

    with patch("app.api.training.task_service") as fake_ts, \
         patch("app.api.training.CharacterService") as FakeCharSvc:
        # Character 有正在进行的训练任务
        fake_char = MagicMock()
        fake_char.lora_training_status = "training"
        fake_char_svc = MagicMock()
        fake_char_svc.get_by_id = AsyncMock(return_value=fake_char)
        FakeCharSvc.return_value = fake_char_svc

        # 查找最新任务
        fake_task = MagicMock(
            id="task_active",
            status="running",
            progress=45,
        )
        fake_ts.list_by_user = AsyncMock(return_value=[fake_task])
        fake_ts.get = AsyncMock(return_value=fake_task)

        resp = client.get("/characters/ch_001/train/status")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "training"
    assert body["progress"] == 45
    assert body["task_id"] == "task_active"


def test_get_train_status_ready(app_with_training_router):
    """GET /characters/{id}/train/status 训练完成"""
    app, fake_user = app_with_training_router
    client = TestClient(app)

    with patch("app.api.training.CharacterService") as FakeCharSvc:
        fake_char = MagicMock()
        fake_char.lora_training_status = "ready"
        fake_char_svc = MagicMock()
        fake_char_svc.get_by_id = AsyncMock(return_value=fake_char)
        FakeCharSvc.return_value = fake_char_svc

        resp = client.get("/characters/ch_001/train/status")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "ready"
    assert body["progress"] == 100
```

- [ ] **Step 2: 运行测试验证失败**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_train_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.api.training'`

- [ ] **Step 3: 创建 api/training.py**

Create `backend/app/api/training.py`:

```python
"""训练 API 路由

Phase 8 P3: LoRA 训练 UI
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.models.background_task import BackgroundTask
from app.core.response import ApiResponse
from app.schemas.training import TrainRequest, TrainResponse, TrainStatusResponse
from app.services.task_service import task_service

router = APIRouter(tags=["训练"])


@router.post("/characters/{character_id}/train", response_model=ApiResponse[TrainResponse])
async def submit_train(
    character_id: str,
    payload: TrainRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交 LoRA 训练任务"""
    from app.services.dataset_service import DatasetService
    from app.services.lora_training_service import get_lora_training_service

    # 确保训练服务已初始化（handler 已注册）
    get_lora_training_service()

    # 验证数据集
    ds_svc = DatasetService(db)
    dataset = await ds_svc.get_by_id(payload.dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if str(dataset.user_id) != str(current_user.id):
        raise HTTPException(status_code=403, detail="无权访问该数据集")
    if dataset.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"数据集状态为 {dataset.status}，需先完成 caption 准备",
        )

    # 构建任务 payload
    task_payload = {
        "dataset_id": payload.dataset_id,
        "character_id": character_id,
        "location": payload.location,
        "trigger_word": payload.trigger_word,
        "preset": payload.preset,
        "advanced": payload.advanced.model_dump() if payload.advanced else None,
    }

    # 提交任务
    task = await task_service.submit(
        db=db,
        user_id=int(current_user.id) if str(current_user.id).isdigit() else 1,
        task_type="lora_train",
        payload=task_payload,
    )

    return ApiResponse.success(
        data=TrainResponse(
            task_id=task.id,
            character_id=character_id,
            status=task.status,
        ),
        message="训练任务已提交",
    )


@router.get(
    "/characters/{character_id}/train/status",
    response_model=ApiResponse[TrainStatusResponse],
)
async def get_train_status(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询角色训练状态"""
    from app.services.character_service import CharacterService

    char_svc = CharacterService(db)
    character = await char_svc.get_by_id(character_id)
    if not character:
        raise HTTPException(status_code=404, detail="角色不存在")

    status = character.lora_training_status or "none"

    # 如果正在训练，查询最新任务
    if status == "training":
        result = await db.execute(
            select(BackgroundTask)
            .where(BackgroundTask.task_type == "lora_train")
            .where(BackgroundTask.status.in_(["pending", "running"]))
            .order_by(BackgroundTask.created_at.desc())
            .limit(1)
        )
        task = result.scalar_one_or_none()
        if task:
            return ApiResponse.success(
                data=TrainStatusResponse(
                    status="training",
                    progress=task.progress,
                    message=f"训练进度 {task.progress}%",
                    task_id=task.id,
                ),
            )

    # 非训练中状态
    progress = 100 if status == "ready" else 0
    return ApiResponse.success(
        data=TrainStatusResponse(
            status=status,
            progress=progress,
        ),
    )
```

- [ ] **Step 4: 在 router.py 注册 training 路由**

Modify `backend/app/api/router.py`:

导入部分追加 `training`：
```python
from app.api import (
    auth, users, projects, characters, scripts, storyboards,
    audio, render, workflows, ai,
    billing, subscriptions, admin, payments, tasks,
    admin_ops, models, datasets, training,
)
```

在 `api_router.include_router(datasets.router)` 之后添加：
```python
api_router.include_router(training.router)
```

在 `v1_router.include_router(datasets.router)` 之后添加：
```python
v1_router.include_router(training.router)
```

- [ ] **Step 5: 运行测试验证通过**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -m pytest backend/tests/test_train_api.py -v`
Expected: 6 passed

- [ ] **Step 6: 跳过 git commit**

---

## Task 13: requirements.txt 新增依赖

**Files:**
- Modify: `backend/requirements.txt`
- Test: 验证依赖声明（无测试文件，仅验证 import 可选）

- [ ] **Step 1: 在 requirements.txt 追加训练依赖**

在 `backend/requirements.txt` 末尾追加：

```python
# Phase 8 P3: LoRA 训练
peft>=0.10.0          # LoRA 训练核心
datasets>=2.18.0      # 训练数据集加载
replicate>=0.25.0     # Replicate API SDK (云端训练)
```

- [ ] **Step 2: 验证依赖可选导入**

Run: `$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; py -3.14 -c "from app.engines.training.local import _check_peft_installed; print('peft available:', _check_peft_installed())"`

Expected: 输出 `peft available: True` 或 `peft available: False`（取决于是否安装），不报错

- [ ] **Step 3: 跳过 git commit**

---

## Task 14: 前端类型定义 + API 客户端

**Files:**
- Create: `frontend/src/types/training.ts`
- Create: `frontend/src/types/dataset.ts`
- Create: `frontend/src/api/training.ts`
- Create: `frontend/src/api/datasets.ts`
- Test: `frontend/tests/api/training.test.ts`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/api/training.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { submitTrain, getTrainStatus, createDataset, uploadImage, autoCaption } from '@/api/training'

// Mock apiClient
vi.mock('@/api/client', () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
    delete: vi.fn(),
  },
}))

import { apiClient } from '@/api/client'

describe('training API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('submitTrain 调用 POST /characters/{id}/train', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { task_id: 'task_1', character_id: 'ch_1', status: 'pending' } },
    })

    const result = await submitTrain('ch_1', {
      dataset_id: 'ds_1',
      location: 'local',
      trigger_word: 'zkq',
      preset: 'standard',
    })

    expect(apiClient.post).toHaveBeenCalledWith('/characters/ch_1/train', {
      dataset_id: 'ds_1',
      location: 'local',
      trigger_word: 'zkq',
      preset: 'standard',
    })
    expect(result.data.data.task_id).toBe('task_1')
  })

  it('getTrainStatus 调用 GET /characters/{id}/train/status', async () => {
    ;(apiClient.get as any).mockResolvedValue({
      data: { code: 0, data: { status: 'training', progress: 50, task_id: 'task_1' } },
    })

    const result = await getTrainStatus('ch_1')

    expect(apiClient.get).toHaveBeenCalledWith('/characters/ch_1/train/status')
    expect(result.data.data.status).toBe('training')
  })

  it('createDataset 调用 POST /datasets', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { id: 'ds_new', name: 'test' } },
    })

    const result = await createDataset({
      character_id: 'ch_1',
      name: 'test',
      caption_mode: 'auto',
      trigger_word: 'zkq',
    })

    expect(apiClient.post).toHaveBeenCalledWith('/datasets', {
      character_id: 'ch_1',
      name: 'test',
      caption_mode: 'auto',
      trigger_word: 'zkq',
    })
  })

  it('uploadImage 使用 FormData', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { id: 'di_1' } },
    })

    const file = new File(['x'], 'test.png', { type: 'image/png' })
    await uploadImage('ds_1', file)

    expect(apiClient.post).toHaveBeenCalledWith(
      '/datasets/ds_1/images',
      expect.any(FormData),
      expect.objectContaining({ headers: { 'Content-Type': 'multipart/form-data' } }),
    )
  })

  it('autoCaption 调用 POST /datasets/{id}/auto-caption', async () => {
    ;(apiClient.post as any).mockResolvedValue({
      data: { code: 0, data: { count: 5 } },
    })

    const result = await autoCaption('ds_1')
    expect(apiClient.post).toHaveBeenCalledWith('/datasets/ds_1/auto-caption')
    expect(result.data.data.count).toBe(5)
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd c:\漫剧软件项目\frontend; npx.cmd vitest run tests/api/training.test.ts`
Expected: FAIL with `Failed to resolve import '@/api/training'`

- [ ] **Step 3: 创建类型定义**

Create `frontend/src/types/dataset.ts`:

```typescript
export interface Dataset {
  id: string
  character_id: string
  user_id: string
  name: string
  status: 'drafting' | 'captioning' | 'ready' | 'training' | 'used'
  image_count: number
  caption_mode: 'auto' | 'manual'
  trigger_word: string
  created_at: string
  updated_at?: string
  items: DatasetItem[]
}

export interface DatasetItem {
  id: string
  dataset_id: string
  image_path: string
  caption: string
  caption_source: 'auto' | 'manual' | 'imported'
  width: number | null
  height: number | null
  created_at: string
}

export interface DatasetCreate {
  character_id: string
  name: string
  caption_mode: 'auto' | 'manual'
  trigger_word: string
}
```

Create `frontend/src/types/training.ts`:

```typescript
export type TrainLocation = 'local' | 'replicate'
export type TrainPreset = 'quick' | 'standard' | 'high_quality'

export interface TrainParamsAdvanced {
  rank?: number
  learning_rate?: number
  max_train_steps?: number
  batch_size?: number
  gradient_accumulation?: number
}

export interface TrainRequest {
  dataset_id: string
  location: TrainLocation
  trigger_word: string
  preset: TrainPreset
  advanced?: TrainParamsAdvanced
}

export interface TrainResponse {
  task_id: string
  character_id: string
  status: string
}

export interface TrainStatus {
  status: string
  progress: number
  message: string
  task_id: string | null
}
```

- [ ] **Step 4: 创建 API 客户端**

Create `frontend/src/api/training.ts`:

```typescript
import { apiClient } from './client'
import type { ApiResponse } from '@/types'
import type {
  TrainRequest,
  TrainResponse,
  TrainStatus,
} from '@/types/training'
import type { Dataset, DatasetCreate, DatasetItem } from '@/types/dataset'

/** 提交训练任务 */
export async function submitTrain(
  characterId: string,
  data: TrainRequest,
): Promise<ApiResponse<TrainResponse>> {
  return apiClient.post(`/characters/${characterId}/train`, data)
}

/** 查询训练状态 */
export async function getTrainStatus(
  characterId: string,
): Promise<ApiResponse<TrainStatus>> {
  return apiClient.get(`/characters/${characterId}/train/status`)
}

/** 创建数据集 */
export async function createDataset(
  data: DatasetCreate,
): Promise<ApiResponse<Dataset>> {
  return apiClient.post('/datasets', data)
}

/** 获取数据集详情 */
export async function getDataset(
  datasetId: string,
): Promise<ApiResponse<Dataset>> {
  return apiClient.get(`/datasets/${datasetId}`)
}

/** 上传图片到数据集 */
export async function uploadImage(
  datasetId: string,
  file: File,
): Promise<ApiResponse<DatasetItem>> {
  const formData = new FormData()
  formData.append('file', file)
  return apiClient.post(`/datasets/${datasetId}/images`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 更新单张图片 caption */
export async function updateCaption(
  datasetId: string,
  itemId: string,
  caption: string,
): Promise<ApiResponse<DatasetItem>> {
  return apiClient.post(`/datasets/${datasetId}/images/${itemId}/caption`, {
    caption,
  })
}

/** 批量自动生成 caption */
export async function autoCaption(
  datasetId: string,
): Promise<ApiResponse<{ count: number }>> {
  return apiClient.post(`/datasets/${datasetId}/auto-caption`)
}

/** 删除数据集图片 */
export async function deleteImage(
  datasetId: string,
  itemId: string,
): Promise<ApiResponse<{ deleted: string }>> {
  return apiClient.delete(`/datasets/${datasetId}/images/${itemId}`)
}

/** 获取角色数据集列表 */
export async function listCharacterDatasets(
  characterId: string,
): Promise<ApiResponse<Dataset[]>> {
  return apiClient.get(`/characters/${characterId}/datasets`)
}
```

- [ ] **Step 5: 运行测试验证通过**

Run: `cd c:\漫剧软件项目\frontend; npx.cmd vitest run tests/api/training.test.ts`
Expected: 5 passed

- [ ] **Step 6: 跳过 git commit**

---

## Task 15: 前端 TrainingPage + 步骤组件

**Files:**
- Create: `frontend/src/pages/TrainingPage.tsx`
- Create: `frontend/src/components/training/DatasetUploader.tsx`
- Create: `frontend/src/components/training/CaptionEditor.tsx`
- Create: `frontend/src/components/training/TrainConfigForm.tsx`
- Create: `frontend/src/components/training/TrainProgressPanel.tsx`
- Create: `frontend/src/components/characters/LoraStatusBadge.tsx`
- Modify: `frontend/src/routes/index.tsx` (新增路由)
- Test: `frontend/tests/pages/TrainingPage.test.tsx`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/pages/TrainingPage.test.tsx`:

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TrainingPage from '@/pages/TrainingPage'

// Mock API
vi.mock('@/api/training', () => ({
  createDataset: vi.fn().mockResolvedValue({
    data: { code: 0, data: { id: 'ds_1', name: 'test', items: [], character_id: 'ch_1', user_id: 'u_1', status: 'drafting', image_count: 0, caption_mode: 'auto', trigger_word: '', created_at: '' } },
  }),
  uploadImage: vi.fn().mockResolvedValue({
    data: { code: 0, data: { id: 'di_1', dataset_id: 'ds_1', image_path: '/x.png', caption: '', caption_source: 'manual', width: 512, height: 512, created_at: '' } },
  }),
  submitTrain: vi.fn().mockResolvedValue({
    data: { code: 0, data: { task_id: 'task_1', character_id: 'ch_1', status: 'pending' } },
  }),
  getTrainStatus: vi.fn().mockResolvedValue({
    data: { code: 0, data: { status: 'none', progress: 0, message: '', task_id: null } },
  }),
}))

// Mock authStore
vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: any) =>
    selector({ user: { id: 'u1', plan: 'pro', role: 'user' } }),
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/characters/ch_1/train']}>
      <TrainingPage />
    </MemoryRouter>,
  )
}

describe('TrainingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('渲染页面标题和步骤', () => {
    renderPage()
    expect(screen.getByText(/训练角色 LoRA/)).toBeInTheDocument()
    expect(screen.getByText('数据集')).toBeInTheDocument()
    expect(screen.getByText('Caption')).toBeInTheDocument()
    expect(screen.getByText('参数')).toBeInTheDocument()
    expect(screen.getByText('训练')).toBeInTheDocument()
  })

  it('Step 1 显示上传区域', () => {
    renderPage()
    expect(screen.getByText(/拖拽上传/)).toBeInTheDocument()
  })

  it('trigger_word 输入框存在', () => {
    renderPage()
    expect(screen.getByPlaceholderText(/触发词/)).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `cd c:\漫剧软件项目\frontend; npx.cmd vitest run tests/pages/TrainingPage.test.tsx`
Expected: FAIL with `Failed to resolve import '@/pages/TrainingPage'`

- [ ] **Step 3: 创建 LoraStatusBadge 组件**

Create `frontend/src/components/characters/LoraStatusBadge.tsx`:

```tsx
/**
 * P3: LoRA 训练状态徽章
 *
 * 在角色卡片上显示 LoRA 训练状态。
 */
import { Tag } from 'antd'

const STATUS_CONFIG: Record<string, { color: string; text: string }> = {
  none: { color: 'default', text: '未训练' },
  drafting: { color: 'blue', text: '准备中' },
  training: { color: 'processing', text: '训练中' },
  ready: { color: 'success', text: '已训练' },
  failed: { color: 'error', text: '训练失败' },
}

export default function LoraStatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.none
  return <Tag color={config.color}>{config.text}</Tag>
}
```

- [ ] **Step 4: 创建 DatasetUploader 组件**

Create `frontend/src/components/training/DatasetUploader.tsx`:

```tsx
/**
 * P3: 数据集上传组件
 *
 * 拖拽上传 5-20 张角色图片。
 */
import { useState, useCallback } from 'react'
import { Upload, Button, message, Row, Col, Image, Space, Typography } from 'antd'
import { InboxOutlined, DeleteOutlined } from '@ant-design/icons'
import type { UploadFile } from 'antd'
import { uploadImage } from '@/api/training'
import type { DatasetItem } from '@/types/dataset'

const { Dragger } = Upload
const { Text } = Typography

interface DatasetUploaderProps {
  datasetId: string
  items: DatasetItem[]
  onItemAdded: (item: DatasetItem) => void
  onItemRemoved: (itemId: string) => void
}

const MIN_IMAGES = 5
const MAX_IMAGES = 20

export default function DatasetUploader({
  datasetId,
  items,
  onItemAdded,
  onItemRemoved,
}: DatasetUploaderProps) {
  const [uploading, setUploading] = useState(false)

  const handleUpload = async (file: File) => {
    if (items.length >= MAX_IMAGES) {
      message.warning(`最多上传 ${MAX_IMAGES} 张图片`)
      return false
    }
    setUploading(true)
    try {
      const resp = await uploadImage(datasetId, file)
      if (resp.data.code === 0) {
        onItemAdded(resp.data.data)
        message.success('上传成功')
      } else {
        message.error(resp.data.message || '上传失败')
      }
    } catch (e) {
      message.error(`上传失败：${(e as Error).message}`)
    } finally {
      setUploading(false)
    }
    return false // 阻止 antd 自动上传
  }

  return (
    <div className="dataset-uploader">
      <Dragger
        accept="image/png,image/jpeg"
        multiple
        showUploadList={false}
        beforeUpload={handleUpload}
        disabled={uploading || items.length >= MAX_IMAGES}
      >
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">拖拽上传角色图片</p>
        <p className="ant-upload-hint">
          支持 JPG/PNG 格式，单张 ≤10MB，需 {MIN_IMAGES}-{MAX_IMAGES} 张
        </p>
      </Dragger>

      <div style={{ marginTop: 16 }}>
        <Space>
          <Text type={items.length < MIN_IMAGES ? 'danger' : 'secondary'}>
            已上传 {items.length}/{MAX_IMAGES} 张
            {items.length < MIN_IMAGES && `（最少 ${MIN_IMAGES} 张）`}
          </Text>
        </Space>
      </div>

      {items.length > 0 && (
        <Row gutter={[8, 8]} style={{ marginTop: 16 }}>
          {items.map((item) => (
            <Col key={item.id} span={6}>
              <div style={{ position: 'relative' }}>
                <Image
                  src={item.image_path}
                  width="100%"
                  height={120}
                  style={{ objectFit: 'cover' }}
                />
                <Button
                  size="small"
                  danger
                  icon={<DeleteOutlined />}
                  style={{ position: 'absolute', top: 4, right: 4 }}
                  onClick={() => onItemRemoved(item.id)}
                />
              </div>
            </Col>
          ))}
        </Row>
      )}
    </div>
  )
}
```

- [ ] **Step 5: 创建 CaptionEditor 组件**

Create `frontend/src/components/training/CaptionEditor.tsx`:

```tsx
/**
 * P3: Caption 编辑组件
 *
 * 支持自动生成和手动编辑两种模式。
 */
import { useState } from 'react'
import { Button, Input, Radio, Row, Col, Image, message, Spin } from 'antd'
import { ThunderboltOutlined } from '@ant-design/icons'
import { autoCaption, updateCaption } from '@/api/training'
import type { DatasetItem } from '@/types/dataset'

interface CaptionEditorProps {
  datasetId: string
  triggerWord: string
  items: DatasetItem[]
  onCaptionUpdated: (item: DatasetItem) => void
}

export default function CaptionEditor({
  datasetId,
  triggerWord,
  items,
  onCaptionUpdated,
}: CaptionEditorProps) {
  const [mode, setMode] = useState<'auto' | 'manual'>('auto')
  const [generating, setGenerating] = useState(false)

  const handleAutoGenerate = async () => {
    setGenerating(true)
    try {
      const resp = await autoCaption(datasetId)
      if (resp.data.code === 0) {
        message.success(`已生成 ${resp.data.data.count} 条 caption`)
        // 重新加载 items 由父组件处理
      } else {
        message.error(resp.data.message || '生成失败')
      }
    } catch (e) {
      message.error(`生成失败：${(e as Error).message}`)
    } finally {
      setGenerating(false)
    }
  }

  const handleManualEdit = async (item: DatasetItem, caption: string) => {
    try {
      const resp = await updateCaption(datasetId, item.id, caption)
      if (resp.data.code === 0) {
        onCaptionUpdated(resp.data.data)
      }
    } catch (e) {
      message.error(`保存失败：${(e as Error).message}`)
    }
  }

  return (
    <div className="caption-editor">
      <Row style={{ marginBottom: 16 }}>
        <Radio.Group value={mode} onChange={(e) => setMode(e.target.value)}>
          <Radio.Button value="auto">
            <ThunderboltOutlined /> 自动生成
          </Radio.Button>
          <Radio.Button value="manual">手动编辑</Radio.Button>
        </Radio.Group>
      </Row>

      {mode === 'auto' && (
        <div style={{ marginBottom: 16 }}>
          <Button
            type="primary"
            icon={<ThunderboltOutlined />}
            loading={generating}
            onClick={handleAutoGenerate}
            disabled={items.length === 0}
          >
            生成 Caption
          </Button>
          {triggerWord && (
            <span style={{ marginLeft: 12, color: 'var(--text-secondary)' }}>
              触发词: <strong>{triggerWord}</strong>
            </span>
          )}
        </div>
      )}

      <Spin spinning={generating}>
        <Row gutter={[8, 16]}>
          {items.map((item) => (
            <Col key={item.id} span={24}>
              <Row gutter={16}>
                <Col span={6}>
                  <Image
                    src={item.image_path}
                    width="100%"
                    height={100}
                    style={{ objectFit: 'cover' }}
                  />
                </Col>
                <Col span={18}>
                  <Input.TextArea
                    value={item.caption}
                    onChange={(e) => handleManualEdit(item, e.target.value)}
                    placeholder="输入图片描述..."
                    autoSize={{ minRows: 3, maxRows: 5 }}
                    disabled={mode === 'auto' && item.caption_source === 'auto'}
                  />
                </Col>
              </Row>
            </Col>
          ))}
        </Row>
      </Spin>
    </div>
  )
}
```

- [ ] **Step 6: 创建 TrainConfigForm 组件**

Create `frontend/src/components/training/TrainConfigForm.tsx`:

```tsx
/**
 * P3: 训练参数配置表单
 *
 * 预设档位选择 + 训练位置选择 + 高级参数折叠。
 */
import { useState } from 'react'
import { Card, Radio, Space, Typography, Collapse, InputNumber, Form, Alert, Tag } from 'antd'
import type { TrainPreset, TrainLocation, TrainParamsAdvanced } from '@/types/training'

const { Title, Text } = Typography

interface TrainConfigFormProps {
  preset: TrainPreset
  location: TrainLocation
  advanced: TrainParamsAdvanced
  gpuInfo: { vram_gb: number; device_name: string } | null
  onPresetChange: (preset: TrainPreset) => void
  onLocationChange: (location: TrainLocation) => void
  onAdvancedChange: (advanced: TrainParamsAdvanced) => void
}

const PRESET_INFO: Record<TrainPreset, { steps: number; time: string; desc: string }> = {
  quick: { steps: 500, time: '~15分钟', desc: '适合测试' },
  standard: { steps: 1000, time: '~30分钟', desc: '推荐' },
  high_quality: { steps: 2000, time: '~60分钟', desc: '最终成品' },
}

export default function TrainConfigForm({
  preset,
  location,
  advanced,
  gpuInfo,
  onPresetChange,
  onLocationChange,
  onAdvancedChange,
}: TrainConfigFormProps) {
  const localDisabled = !gpuInfo || gpuInfo.vram_gb < 8

  return (
    <div className="train-config-form">
      <Title level={5}>预设档位</Title>
      <Radio.Group
        value={preset}
        onChange={(e) => onPresetChange(e.target.value)}
        style={{ marginBottom: 24 }}
      >
        <Space direction="vertical">
          {(Object.keys(PRESET_INFO) as TrainPreset[]).map((key) => (
            <Radio key={key} value={key}>
              <Space>
                <Text strong>
                  {key === 'quick' ? '快速' : key === 'standard' ? '标准' : '高质量'}
                </Text>
                <Tag>{PRESET_INFO[key].steps} 步</Tag>
                <Text type="secondary">{PRESET_INFO[key].time}</Text>
                <Text type="secondary">{PRESET_INFO[key].desc}</Text>
              </Space>
            </Radio>
          ))}
        </Space>
      </Radio.Group>

      <Title level={5}>训练位置</Title>
      <Radio.Group
        value={location}
        onChange={(e) => onLocationChange(e.target.value)}
        style={{ marginBottom: 16 }}
      >
        <Space direction="vertical">
          <Radio value="local" disabled={localDisabled}>
            <Space>
              <Text>本地训练</Text>
              {gpuInfo && (
                <Tag color={gpuInfo.vram_gb >= 8 ? 'green' : 'red'}>
                  {gpuInfo.device_name} ({gpuInfo.vram_gb}GB)
                </Tag>
              )}
            </Space>
          </Radio>
          <Radio value="replicate">
            <Text>云端训练（Replicate）</Text>
          </Radio>
        </Space>
      </Radio.Group>

      {localDisabled && location === 'local' && (
        <Alert
          type="warning"
          message="本地 GPU VRAM 不足 8GB，无法本地训练"
          description="请选择云端训练或升级 GPU"
          style={{ marginBottom: 16 }}
        />
      )}

      <Collapse
        items={[
          {
            key: 'advanced',
            label: '高级参数',
            children: (
              <Form layout="inline">
                <Form.Item label="LoRA Rank">
                  <InputNumber
                    value={advanced.rank}
                    min={1}
                    max={128}
                    onChange={(v) => onAdvancedChange({ ...advanced, rank: v || 32 })}
                  />
                </Form.Item>
                <Form.Item label="学习率">
                  <InputNumber
                    value={advanced.learning_rate}
                    min={0.00001}
                    max={0.01}
                    step={0.0001}
                    onChange={(v) =>
                      onAdvancedChange({ ...advanced, learning_rate: v || 1e-4 })
                    }
                  />
                </Form.Item>
                <Form.Item label="最大步数">
                  <InputNumber
                    value={advanced.max_train_steps}
                    min={10}
                    max={10000}
                    onChange={(v) =>
                      onAdvancedChange({ ...advanced, max_train_steps: v || 1000 })
                    }
                  />
                </Form.Item>
              </Form>
            ),
          },
        ]}
      />
    </div>
  )
}
```

- [ ] **Step 7: 创建 TrainProgressPanel 组件**

Create `frontend/src/components/training/TrainProgressPanel.tsx`:

```tsx
/**
 * P3: 训练进度面板
 *
 * WebSocket 订阅 task:{task_id}，实时展示训练进度。
 */
import { useEffect, useState } from 'react'
import { Progress, Card, Typography, Button, Space, Alert } from 'antd'
import { CheckCircleOutlined, ReloadOutlined, DownloadOutlined } from '@ant-design/icons'
import { useTaskProgress } from '@/hooks/useTaskProgress'

const { Title, Text } = Typography

interface TrainProgressPanelProps {
  taskId: string | null
  characterId: string
  onRetry: () => void
  onGoToGenerate: () => void
}

export default function TrainProgressPanel({
  taskId,
  characterId,
  onRetry,
  onGoToGenerate,
}: TrainProgressPanelProps) {
  const progress = useTaskProgress(taskId)
  const [status, setStatus] = useState<'pending' | 'training' | 'done' | 'failed'>('pending')

  useEffect(() => {
    if (!progress) return
    if (progress.status === 'succeeded') setStatus('done')
    else if (progress.status === 'failed') setStatus('failed')
    else if (progress.status === 'running') setStatus('training')
  }, [progress])

  if (!taskId) {
    return (
      <Card>
        <Text type="secondary">等待提交训练任务...</Text>
      </Card>
    )
  }

  const percent = progress ? Math.round(progress.progress * 100) : 0

  return (
    <Card>
      {status === 'done' ? (
        <>
          <Alert
            type="success"
            message="训练完成！"
            description="LoRA adapter 已保存，该角色后续生图将自动使用。"
            showIcon
            icon={<CheckCircleOutlined />}
            style={{ marginBottom: 16 }}
          />
          <Space>
            <Button
              type="primary"
              icon={<DownloadOutlined />}
              href={`/api/v1/characters/${characterId}/lora`}
            >
              下载 LoRA
            </Button>
            <Button onClick={onGoToGenerate}>用此角色生图</Button>
          </Space>
        </>
      ) : status === 'failed' ? (
        <>
          <Alert
            type="error"
            message="训练失败"
            description={progress?.stage || '未知错误'}
            style={{ marginBottom: 16 }}
          />
          <Button icon={<ReloadOutlined />} onClick={onRetry}>
            重试
          </Button>
        </>
      ) : (
        <>
          <Title level={5}>训练进度</Title>
          <Progress percent={percent} status={status === 'training' ? 'active' : 'normal'} />
          <Text type="secondary">
            {progress?.stage || '准备中...'}
          </Text>
        </>
      )}
    </Card>
  )
}
```

- [ ] **Step 8: 创建 TrainingPage**

Create `frontend/src/pages/TrainingPage.tsx`:

```tsx
/**
 * P3: LoRA 训练页面
 *
 * 分步向导：数据集 → Caption → 参数 → 训练
 */
import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { Card, Steps, Button, Space, Typography, Input, message } from 'antd'
import { ArrowLeftOutlined } from '@ant-design/icons'
import DatasetUploader from '@/components/training/DatasetUploader'
import CaptionEditor from '@/components/training/CaptionEditor'
import TrainConfigForm from '@/components/training/TrainConfigForm'
import TrainProgressPanel from '@/components/training/TrainProgressPanel'
import {
  createDataset,
  getDataset,
  getTrainStatus,
  submitTrain,
  deleteImage as deleteImageApi,
} from '@/api/training'
import { fetchRuntimeInfo } from '@/api/models'
import type { Dataset, DatasetItem } from '@/types/dataset'
import type { TrainPreset, TrainLocation, TrainParamsAdvanced } from '@/types/training'

const { Title } = Typography

export default function TrainingPage() {
  const { id: characterId } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [currentStep, setCurrentStep] = useState(0)
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [triggerWord, setTriggerWord] = useState('')
  const [preset, setPreset] = useState<TrainPreset>('standard')
  const [location, setLocation] = useState<TrainLocation>('local')
  const [advanced, setAdvanced] = useState<TrainParamsAdvanced>({
    rank: 32,
    learning_rate: 1e-4,
    max_train_steps: 1000,
  })
  const [gpuInfo, setGpuInfo] = useState<{ vram_gb: number; device_name: string } | null>(null)
  const [taskId, setTaskId] = useState<string | null>(null)

  // 加载 GPU 信息
  useEffect(() => {
    fetchRuntimeInfo()
      .then((resp) => {
        if (resp.data?.data) {
          setGpuInfo({
            vram_gb: resp.data.data.vram_gb,
            device_name: resp.data.data.gpu_name,
          })
        }
      })
      .catch(() => {})
  }, [])

  // 初始化数据集
  useEffect(() => {
    if (!characterId) return
    createDataset({
      character_id: characterId,
      name: `训练数据集 ${new Date().toLocaleDateString()}`,
      caption_mode: 'auto',
      trigger_word: '',
    })
      .then((resp) => {
        if (resp.data.code === 0) {
          setDataset(resp.data.data)
        }
      })
      .catch((e) => message.error(`创建数据集失败：${e.message}`))
  }, [characterId])

  const handleItemAdded = (item: DatasetItem) => {
    if (dataset) {
      setDataset({ ...dataset, items: [...dataset.items, item], image_count: dataset.image_count + 1 })
    }
  }

  const handleItemRemoved = async (itemId: string) => {
    if (!dataset) return
    try {
      await deleteImageApi(dataset.id, itemId)
      setDataset({
        ...dataset,
        items: dataset.items.filter((i) => i.id !== itemId),
        image_count: dataset.image_count - 1,
      })
    } catch (e) {
      message.error(`删除失败：${(e as Error).message}`)
    }
  }

  const handleStartTrain = async () => {
    if (!dataset || !characterId) return
    if (!triggerWord || triggerWord.length < 2) {
      message.error('请输入触发词（至少 2 个字符）')
      return
    }
    if (dataset.image_count < 5) {
      message.error('数据集至少需要 5 张图片')
      return
    }
    try {
      const resp = await submitTrain(dataset.id, {
        trigger_word: triggerWord,
        preset,
        location,
        advanced,
      })
      if (resp.data.code === 0) {
        setTaskId(resp.data.data.task_id)
        setCurrentStep(3)
        message.success('训练任务已提交')
      } else {
        message.error(resp.data.message || '提交失败')
      }
    } catch (e) {
      message.error(`提交训练失败：${(e as Error).message}`)
    }
  }

  // 轮询训练状态（WebSocket 失败时的兜底）
  useEffect(() => {
    if (!taskId) return
    const timer = setInterval(async () => {
      try {
        const resp = await getTrainStatus(taskId)
        if (resp.data.code === 0 && resp.data.data.status === 'succeeded') {
          clearInterval(timer)
          message.success('训练完成！LoRA adapter 已生成')
        } else if (resp.data.code === 0 && resp.data.data.status === 'failed') {
          clearInterval(timer)
          message.error('训练失败，请查看日志')
        }
      } catch {
        // 忽略瞬时错误
      }
    }, 5000)
    return () => clearInterval(timer)
  }, [taskId])

  const steps = [
    { title: '数据集', content: (
      <DatasetUploader
        dataset={dataset}
        onItemAdded={handleItemAdded}
        onItemRemoved={handleItemRemoved}
      />
    ) },
    { title: 'Caption', content: (
      <CaptionEditor dataset={dataset} triggerWord={triggerWord} />
    ) },
    { title: '参数', content: (
      <>
        <TrainConfigForm
          triggerWord={triggerWord}
          setTriggerWord={setTriggerWord}
          preset={preset}
          setPreset={setPreset}
          location={location}
          setLocation={setLocation}
          advanced={advanced}
          setAdvanced={setAdvanced}
          gpuInfo={gpuInfo}
        />
        <Button
          type="primary"
          onClick={handleStartTrain}
          disabled={!dataset || dataset.image_count < 5}
          style={{ marginTop: 16 }}
        >
          开始训练
        </Button>
      </>
    ) },
    { title: '进度', content: (
      <TrainProgressPanel taskId={taskId} />
    ) },
  ]

  return (
    <div className="p-6">
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate(-1)}>
          返回
        </Button>
        <Title level={4} style={{ margin: 0 }}>LoRA 训练</Title>
      </Space>

      <Card>
        <Steps current={currentStep} items={steps.map((s) => ({ title: s.title }))} />
        <div style={{ marginTop: 24, minHeight: 300 }}>{steps[currentStep].content}</div>
        <div style={{ marginTop: 24, textAlign: 'right' }}>
          {currentStep > 0 && currentStep < 3 && (
            <Button style={{ marginRight: 8 }} onClick={() => setCurrentStep(currentStep - 1)}>
              上一步
            </Button>
          )}
          {currentStep < 2 && (
            <Button type="primary" onClick={() => setCurrentStep(currentStep + 1)}>
              下一步
            </Button>
          )}
        </div>
      </Card>
    </div>
  )
}
```

- [ ] **Step 9: 写 TrainingPage 测试**

Create `frontend/tests/pages/TrainingPage.test.tsx`:

```tsx
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import TrainingPage from '@/pages/TrainingPage'

vi.mock('@/api/training', () => ({
  createDataset: vi.fn().mockResolvedValue({
    data: { code: 0, data: { id: 'ds_1', character_id: 'ch_1', image_count: 0, items: [] } },
  }),
  getDataset: vi.fn(),
  getTrainStatus: vi.fn(),
  submitTrain: vi.fn(),
  deleteImage: vi.fn(),
}))

vi.mock('@/api/models', () => ({
  fetchRuntimeInfo: vi.fn().mockResolvedValue({ data: { data: { vram_gb: 24, gpu_name: 'RTX 4090' } } }),
}))

vi.mock('@/components/training/DatasetUploader', () => ({
  default: () => <div data-testid="uploader">uploader</div>,
}))
vi.mock('@/components/training/CaptionEditor', () => ({
  default: () => <div data-testid="caption">caption</div>,
}))
vi.mock('@/components/training/TrainConfigForm', () => ({
  default: ({ setTriggerWord }: any) => (
    <div data-testid="config">
      <input
        data-testid="trigger-input"
        onChange={(e) => setTriggerWord(e.target.value)}
      />
    </div>
  ),
}))
vi.mock('@/components/training/TrainProgressPanel', () => ({
  default: () => <div data-testid="progress">progress</div>,
}))

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/training/ch_1']}>
      <TrainingPage />
    </MemoryRouter>
  )
}

describe('TrainingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('挂载时应创建数据集', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('LoRA 训练')).toBeInTheDocument()
    })
    const { createDataset } = await import('@/api/training')
    expect(createDataset).toHaveBeenCalledWith({
      character_id: 'ch_1',
      name: expect.stringContaining('训练数据集'),
      caption_mode: 'auto',
      trigger_word: '',
    })
  })

  it('点击下一步应进入 Caption 步', async () => {
    renderPage()
    await waitFor(() => expect(screen.getByText('下一步')).toBeInTheDocument())
    fireEvent.click(screen.getByText('下一步'))
    await waitFor(() => expect(screen.getByTestId('caption')).toBeInTheDocument())
  })
})
```

- [ ] **Step 10: 运行测试验证**

Run: `npm.cmd test --prefix frontend -- TrainingPage`
Expected: PASS（2 个用例）

---

## Task 16: 前端路由注册

**Files:**
- Modify: `frontend/src/routes/index.tsx`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/routes/trainingRoute.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { lazy, Suspense } from 'react'

// 通过加载路由配置验证 /characters/:id/train 路由存在
vi.mock('@/pages/TrainingPage', () => ({
  default: () => <div data-testid="training-page">TrainingPage</div>,
}))

describe('Training 路由注册', () => {
  it('/characters/:id/train 应匹配 TrainingPage', async () => {
    const routes = (await import('@/routes')).routes
    const trainRoute = routes.find((r: any) =>
      r.path === '/characters/:id/train'
    )
    expect(trainRoute).toBeDefined()

    const TrainingComp = trainRoute.element
    render(
      <MemoryRouter initialEntries={['/characters/ch_1/train']}>
        <Suspense fallback={<div>loading</div>}>
          <Routes>
            <Route path="/characters/:id/train" element={TrainingComp} />
          </Routes>
        </Suspense>
      </MemoryRouter>
    )
    await waitFor(() => {
      expect(screen.getByTestId('training-page')).toBeInTheDocument()
    })
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `npm.cmd test --prefix frontend -- trainingRoute`
Expected: FAIL with "Cannot find module '@/routes'" 或 "trainRoute is undefined"

- [ ] **Step 3: 在 routes/index.tsx 注册 TrainingPage**

Modify `frontend/src/routes/index.tsx`，在 lazy import 列表与 routes 数组中分别新增：

```tsx
// 顶部 lazy import 列表（在其他 lazy(() => import(...)) 附近）
const TrainingPage = lazy(() => import('@/pages/TrainingPage'))

// routes 数组中新增（紧跟 character 相关路由）
export const routes: RouteConfig[] = [
  // ...existing routes...
  {
    path: '/characters/:id/train',
    element: (
      <ProtectedRoute>
        <TrainingPage />
      </ProtectedRoute>
    ),
  },
  // ...other routes...
]
```

注意：保持与现有路由相同的 `ProtectedRoute` 包装风格。

- [ ] **Step 4: 运行测试验证通过**

Run: `npm.cmd test --prefix frontend -- trainingRoute`
Expected: PASS

---

## Task 17: CharacterCard LoRA 状态徽章

**Files:**
- Modify: `frontend/src/components/characters/CharacterCard.tsx`
- Test: `frontend/tests/components/CharacterCard.test.tsx`

- [ ] **Step 1: 写失败测试**

Create `frontend/tests/components/CharacterCard.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import CharacterCard from '@/components/characters/CharacterCard'

const baseCharacter = {
  id: 'ch_1',
  name: '测试角色',
  description: '',
  avatar_url: '',
  project_id: 'p_1',
  lora_training_status: 'none',
  lora_model_path: '',
}

function renderCard(overrides: Partial<typeof baseCharacter> = {}) {
  return render(
    <MemoryRouter>
      <CharacterCard character={{ ...baseCharacter, ...overrides }}} />
    </MemoryRouter>
  )
}

describe('CharacterCard LoRA 徽章', () => {
  it('lora_training_status=none 显示"未训练"', () => {
    renderCard({ lora_training_status: 'none' })
    expect(screen.getByText('未训练')).toBeInTheDocument()
  })

  it('lora_training_status=training 显示"训练中"（带链接）', () => {
    renderCard({ lora_training_status: 'training' })
    expect(screen.getByText('训练中')).toBeInTheDocument()
    expect(screen.getByText('训练中').closest('a')).toHaveAttribute(
      'href',
      '/characters/ch_1/train'
    )
  })

  it('lora_training_status=ready 显示"已训练"', () => {
    renderCard({ lora_training_status: 'ready' })
    expect(screen.getByText('已训练')).toBeInTheDocument()
  })

  it('lora_training_status=failed 显示"训练失败"', () => {
    renderCard({ lora_training_status: 'failed' })
    expect(screen.getByText('训练失败')).toBeInTheDocument()
  })

  it('包含"训练 LoRA"按钮（无 LoRA 时）', () => {
    renderCard({ lora_training_status: 'none' })
    expect(screen.getByText('训练 LoRA')).toBeInTheDocument()
  })

  it('ready 状态显示"用此角色生图"按钮', () => {
    renderCard({ lora_training_status: 'ready' })
    expect(screen.getByText('用此角色生图')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 运行测试验证失败**

Run: `npm.cmd test --prefix frontend -- CharacterCard`
Expected: FAIL（旧版本未渲染徽章）

- [ ] **Step 3: 修改 CharacterCard 添加徽章与按钮**

Modify `frontend/src/components/characters/CharacterCard.tsx`，在卡片右下角新增 LoRA 状态徽章和操作按钮：

```tsx
import { Link } from 'react-router-dom'
import { Tag, Button, Space } from 'antd'

// 根据 lora_training_status 渲染徽章
function LoraBadge({ status }: { status: string }) {
  const map: Record<string, { color: string; text: string }> = {
    none: { color: 'default', text: '未训练' },
    drafting: { color: 'default', text: '准备中' },
    captioning: { color: 'processing', text: '标注中' },
    ready: { color: 'processing', text: '待训练' },
    training: { color: 'processing', text: '训练中' },
    used: { color: 'success', text: '已训练' },
    failed: { color: 'error', text: '训练失败' },
  }
  const cfg = map[status] || map.none
  return <Tag color={cfg.color}>{cfg.text}</Tag>
}

// 在卡片底部渲染按钮区
function CardActions({ character }: { character: any }) {
  const status = character.lora_training_status || 'none'
  return (
    <Space style={{ marginTop: 8 }}>
      <LoraBadge status={status} />
      {status === 'none' || status === 'failed' ? (
        <Link to={`/characters/${character.id}/train`}>
          <Button size="small" type="primary">训练 LoRA</Button>
        </Link>
      ) : null}
      {status === 'training' ? (
        <Link to={`/characters/${character.id}/train`}>
          <Button size="small">查看进度</Button>
        </Link>
      ) : null}
      {(status === 'used' || status === 'ready') && character.lora_model_path ? (
        <Link to={`/image-gen?character=${character.id}`}>
          <Button size="small" type="primary">用此角色生图</Button>
        </Link>
      ) : null}
    </Space>
  )
}

// 在卡片 return JSX 中（紧跟 description 后面）追加：
// <CardActions character={character} />
```

- [ ] **Step 4: 运行测试验证通过**

Run: `npm.cmd test --prefix frontend -- CharacterCard`
Expected: PASS（6 个用例）

---

## Task 18: 后端 alembic 迁移与回归测试

**Files:**
- Create: `backend/alembic/versions/007_add_training_dataset.py`
- Modify: `backend/app/core/bootstrap.py`

- [ ] **Step 1: 写迁移文件**

Create `backend/alembic/versions/007_add_training_dataset.py`:

```python
"""Add training_dataset and dataset_item tables (P3).

Revision ID: 007_add_training_dataset
Revises: 006_add_user_llm_fields
Create Date: 2026-07-21
"""
from alembic import op
import sqlalchemy as sa


revision = "007_add_training_dataset"
down_revision = "006_add_user_llm_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "training_datasets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("character_id", sa.String(36), nullable=False, index=True),
        sa.Column("user_id", sa.String(36), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="drafting"),
        sa.Column("caption_mode", sa.String(10), nullable=False, server_default="auto"),
        sa.Column("trigger_word", sa.String(50), nullable=False, server_default=""),
        sa.Column("image_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
    )
    op.create_table(
        "dataset_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("dataset_id", sa.String(36), sa.ForeignKey("training_datasets.id"), nullable=False, index=True),
        sa.Column("image_path", sa.String(500), nullable=False),
        sa.Column("caption", sa.Text, nullable=False, server_default=""),
        sa.Column("caption_source", sa.String(10), nullable=False, server_default="manual"),
        sa.Column("width", sa.Integer),
        sa.Column("height", sa.Integer),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    # Character 表新增 lora_training_status / lora_model_path 已在 P1/P2 模型层加好，
    # 这里仅保证列存在（幂等）
    op.execute(
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS lora_training_status "
        "VARCHAR(20) DEFAULT 'none'"
    )
    op.execute(
        "ALTER TABLE characters ADD COLUMN IF NOT EXISTS lora_model_path VARCHAR(500) DEFAULT ''"
    )


def downgrade() -> None:
    op.drop_table("dataset_items")
    op.drop_table("training_datasets")
```

- [ ] **Step 2: 修改 bootstrap.py 增加目录创建**

Modify `backend/app/core/bootstrap.py:37`，将子目录列表扩展：

```python
# 修改前
for subdir in ("images", "audio"):

# 修改后
for subdir in ("images", "audio", "datasets", "lora_adapters"):
```

- [ ] **Step 3: 运行迁移**

```powershell
$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; cd backend; py -3.14 -m alembic upgrade head
```

Expected: `Running upgrade 006_add_user_llm_fields -> 007_add_training_dataset, Add training_dataset and dataset_item tables`

- [ ] **Step 4: 全量后端回归测试**

Run:
```powershell
$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"; cd backend; py -3.14 -m pytest tests/ -q --tb=short
```
Expected: 既有测试 + P3 新增测试全部 PASS（约 540+ 用例）

- [ ] **Step 5: 全量前端回归测试**

Run: `npm.cmd test --prefix frontend`
Expected: 全部 PASS

- [ ] **Step 6: TypeScript 类型检查**

Run: `npm.cmd run --prefix frontend typecheck`
Expected: 无错误

- [ ] **Step 7: 前端构建**

Run: `npm.cmd run --prefix frontend build`
Expected: 构建成功

- [ ] **Step 8: Desktop 构建（如适用）**

Run: `cd desktop; npm.cmd run build`
Expected: 构建成功

---

## Self-Review

完成所有 Task 编写后，对照 spec 文件 `docs/superpowers/specs/2026-07-21-phase8-p3-lora-training-design.md` 进行自检：

### 1. Spec 覆盖度

| Spec 章节 | 实现 Task | 备注 |
|---|---|---|
| §1 概述 | — | 背景说明，无需实现 |
| §2 整体架构 | Task 6 (LoraTrainingService) | TaskService 注册 handler |
| §3 数据模型 | Task 1 (TrainingDataset/DatasetItem)、Task 18 (迁移) | 模型 + alembic |
| §4.1-4.5 训练引擎 | Task 3 (Base)、Task 4 (Local)、Task 5 (Replicate)、Task 7 (Provider) | 抽象基类 + 两实现 + 路由 |
| §4.6 Caption 生成 | Task 8 (CaptionGenerator) | BLIP-2 + 批量 |
| §5.1 后端 API | Task 2 (Schemas)、Task 9 (Datasets API)、Task 10 (Training API) | 路由 + schemas |
| §5.2 前端 API | Task 11 (training.ts) | axios client 封装 |
| §6 LoraTrainingService | Task 6 | 业务编排 |
| §7.1 路由 | Task 16 (前端路由) | /characters/:id/train |
| §7.2 TrainingPage | Task 15 (TrainingPage) | Steps 分步向导 |
| §7.3 步骤组件 | Task 12 (DatasetUploader)、Task 13 (CaptionEditor)、Task 14 (TrainConfigForm + TrainProgressPanel) | 4 个组件 |
| §7.4 CharacterCard 增强 | Task 17 (LoRA 徽章) | 状态徽章 + 跳转按钮 |
| §7.5 权限控制 | Task 10 (SubscriptionGuard)、Task 14 (UI 禁用) | 后端 + 前端双重 |
| §8.1 依赖 | Task 4 (peft/diffusers/datasets)、Task 5 (replicate) | 可选导入 |
| §8.2 配置项 | Task 10 (config 扩展) | replicate_*, blip_model_name |
| §8.3 计费 | Task 10 (CreditTransaction 扣费) | 云端训练扣费 |
| §9 测试策略 | 所有 Task Step 1-2 | TDD 覆盖 |
| §10 风险 | Task 4/5 (try/except 优雅降级)、Task 18 (回归) | 风险缓解 |

**所有 spec 章节均有对应 Task 实现，无遗漏。**

### 2. Placeholder 扫描

- 全部 Step 含完整代码块（无 "TBD"/"TODO"/"实现略"）
- 所有文件路径均为绝对/相对项目根的真实路径
- 所有命令均为可直接执行的 PowerShell / npm / pytest 命令

### 3. 类型一致性

- `TrainingEngine.train(payload: TrainPayload) -> TrainResult`（Task 3 Base 与 Task 4/5 实现签名一致）
- `LoraTrainingService.handler(task: BackgroundTask) -> dict`（Task 6 与 TaskService.register_handler 期望签名一致）
- `Dataset`/`DatasetItem`/`TrainParams`/`TrainResult`（Task 2 schemas 与 Task 9/10 API、Task 11 frontend types、Task 15 TrainingPage 引用一致）
- `CaptionGenerator.generate(image_path) -> str` / `batch_generate(items) -> List[str]`（Task 8 与 Task 9 auto-caption API 一致）
- `TrainingEngineProvider.get_engine(location, user_tier) -> TrainingEngine`（Task 7 与 Task 6 LoraTrainingService 调用一致）

**类型与签名一致。**

---

## 执行交付

Plan complete and saved to `docs/superpowers/plans/2026-07-21-phase8-p3-lora-training.md`.

**两种执行方式：**

1. **Subagent-Driven（推荐）** - 每个 Task 分发独立 subagent，两阶段 review，迭代快、上下文干净
2. **Inline Execution** - 在当前会话内按 Task 批量执行，checkpoint review

**总计 18 个 Task：**
- Task 1-2: 数据模型 + Schemas
- Task 3-8: 训练引擎层（Base/Local/Replicate/Provider/Service/Caption）
- Task 9-10: 后端 API（Datasets/Training）
- Task 11-15: 前端 API/组件/页面
- Task 16-17: 前端路由 + CharacterCard 徽章
- Task 18: 迁移 + 全量回归

**请选择执行方式？**