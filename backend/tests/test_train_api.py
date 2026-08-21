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
    assert fake_ts.submit.await_args.kwargs["user_id"] == "u_test"


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
        fake_char.user_id = "u_test"
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
        fake_char.user_id = "u_test"
        fake_char.lora_training_status = "ready"
        fake_char_svc = MagicMock()
        fake_char_svc.get_by_id = AsyncMock(return_value=fake_char)
        FakeCharSvc.return_value = fake_char_svc

        resp = client.get("/characters/ch_001/train/status")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["status"] == "ready"
    assert body["progress"] == 100
