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
    app.include_router(router)
    app.dependency_overrides[get_current_user] = lambda: fake_user
    return app, fake_user


def test_create_dataset(app_with_datasets_router):
    """POST /datasets 创建数据集"""
    app, fake_user = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_ds = MagicMock(
            id="ds_new",
            character_id="ch_001",
            user_id="u_test",
            status="drafting",
            image_count=0,
            caption_mode="auto",
            trigger_word="zkq",
            items=[],
        )
        fake_ds.name = "新数据集"
        fake_instance = MagicMock()
        fake_instance.owns_character = AsyncMock(return_value=True)
        fake_instance.create = AsyncMock(return_value=fake_ds)
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
        fake_ds = MagicMock(
            id="ds_001",
            character_id="ch_001",
            user_id="u_test",
            status="ready",
            image_count=5,
            caption_mode="auto",
            trigger_word="zkq",
            items=[],
        )
        fake_ds.name = "测试"
        fake_instance = MagicMock()
        fake_instance.get_by_id = AsyncMock(return_value=fake_ds)
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
        fake_instance.delete_image = AsyncMock(return_value=(
            MagicMock(image_path="/uploads/missing.png"),
            "12345678-1234-5678-1234-567812345678",
        ))
        fake_instance.complete_storage_deletion = AsyncMock()
        fake_instance.record_storage_deletion_failure = AsyncMock()
        FakeSvc.return_value = fake_instance

        resp = client.delete("/datasets/ds_001/images/di_001")

    assert resp.status_code == 200


def test_update_caption_rejects_unowned_item(app_with_datasets_router):
    """不存在或不属于当前用户的条目统一返回 404。"""
    app, _ = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.update_caption = AsyncMock(return_value=None)
        FakeSvc.return_value = fake_instance

        resp = client.post(
            "/datasets/ds_other/images/di_other/caption",
            json={"caption": "tampered"},
        )

    assert resp.status_code == 404
    fake_instance.update_caption.assert_awaited_once_with(
        dataset_id="ds_other",
        item_id="di_other",
        user_id="u_test",
        caption="tampered",
        source="manual",
    )


def test_delete_image_rejects_unowned_item(app_with_datasets_router):
    """删除操作不得越过数据集所有权边界。"""
    app, _ = app_with_datasets_router
    client = TestClient(app)

    with patch("app.api.datasets.DatasetService") as FakeSvc:
        fake_instance = MagicMock()
        fake_instance.delete_image = AsyncMock(return_value=None)
        FakeSvc.return_value = fake_instance

        resp = client.delete("/datasets/ds_other/images/di_other")

    assert resp.status_code == 404


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
        ds1 = MagicMock(
            id="ds_1", character_id="ch_1", user_id="u_test",
            status="ready", image_count=0, caption_mode="auto", trigger_word="", items=[],
        )
        ds1.name = "ds1"
        ds2 = MagicMock(
            id="ds_2", character_id="ch_1", user_id="u_test",
            status="drafting", image_count=0, caption_mode="auto", trigger_word="", items=[],
        )
        ds2.name = "ds2"
        fake_instance = MagicMock()
        fake_instance.list_by_character = AsyncMock(return_value=[ds1, ds2])
        FakeSvc.return_value = fake_instance

        resp = client.get("/characters/ch_1/datasets")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 2
    fake_instance.list_by_character.assert_awaited_once_with(
        character_id="ch_1", user_id="u_test"
    )
