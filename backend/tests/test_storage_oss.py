"""Phase 8 P4 - OSS 存储后端测试（mock oss2）。"""
import pytest
from unittest.mock import MagicMock, patch
from types import ModuleType


@pytest.fixture
def mock_oss2(monkeypatch):
    """Mock oss2 模块，避免实际依赖。"""
    mock = MagicMock()
    mock.Auth = MagicMock(return_value=MagicMock())
    mock_bucket = MagicMock()
    mock.Bucket = MagicMock(return_value=mock_bucket)
    monkeypatch.setattr("app.core.storage_oss.oss2", mock)
    return mock, mock_bucket


# ===== OSSStorage 实例化 =====


def test_oss_storage_init_requires_oss2(monkeypatch):
    """无 oss2 模块时实例化抛 ImportError。"""
    monkeypatch.setattr("app.core.storage_oss.oss2", None)
    from app.core.storage_oss import OSSStorage
    with pytest.raises(ImportError, match="oss2 not installed"):
        OSSStorage(
            bucket="b",
            access_key_id="k",
            access_key_secret="s",
            endpoint="e",
        )


def test_oss_storage_init_requires_all_fields(mock_oss2):
    """缺少必要字段抛 ValueError。"""
    from app.core.storage_oss import OSSStorage
    mock, _ = mock_oss2
    with pytest.raises(ValueError):
        OSSStorage(bucket="", access_key_id="k", access_key_secret="s", endpoint="e")
    with pytest.raises(ValueError):
        OSSStorage(bucket="b", access_key_id="", access_key_secret="s", endpoint="e")


def test_oss_storage_is_storage_backend(mock_oss2):
    """OSSStorage 是 StorageBackend 子类。"""
    from app.core.storage_oss import OSSStorage
    from app.core.storage_async import StorageBackend
    s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
    assert isinstance(s, StorageBackend)


# ===== OSS save =====


@pytest.mark.asyncio
async def test_oss_save_calls_put_object(mock_oss2):
    """save() 调用 bucket.put_object 并返回 URL。"""
    from app.core.storage_oss import OSSStorage
    mock, mock_bucket = mock_oss2
    s = OSSStorage(bucket="my-bucket", access_key_id="k", access_key_secret="s", endpoint="oss-cn-hangzhou.aliyuncs.com")
    url = await s.save("foo/bar.txt", b"hello")
    mock_bucket.put_object.assert_called_once_with("foo/bar.txt", b"hello")
    assert "foo/bar.txt" in url
    assert "my-bucket" in url
    assert url.startswith("https://")


# ===== OSS exists =====


@pytest.mark.asyncio
async def test_oss_exists_true(mock_oss2):
    """exists() 返回 True 当对象存在。"""
    from app.core.storage_oss import OSSStorage
    _, mock_bucket = mock_oss2
    mock_bucket.object_exists.return_value = True
    s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
    assert await s.exists("foo/bar.txt") is True


@pytest.mark.asyncio
async def test_oss_exists_false(mock_oss2):
    """exists() 返回 False 当对象不存在。"""
    from app.core.storage_oss import OSSStorage
    _, mock_bucket = mock_oss2
    mock_bucket.object_exists.return_value = False
    s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
    assert await s.exists("foo/bar.txt") is False


@pytest.mark.asyncio
async def test_oss_exists_strips_uploads_prefix(mock_oss2):
    """exists() 处理 /uploads/ 前缀。"""
    from app.core.storage_oss import OSSStorage
    _, mock_bucket = mock_oss2
    mock_bucket.object_exists.return_value = True
    s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
    await s.exists("/uploads/foo/bar.txt")
    mock_bucket.object_exists.assert_called_once_with("foo/bar.txt")


# ===== OSS delete =====


@pytest.mark.asyncio
async def test_oss_delete_calls_delete_object(mock_oss2):
    """delete() 调用 bucket.delete_object。"""
    from app.core.storage_oss import OSSStorage
    _, mock_bucket = mock_oss2
    s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
    await s.delete("foo/bar.txt")
    mock_bucket.delete_object.assert_called_once_with("foo/bar.txt")


@pytest.mark.asyncio
async def test_oss_delete_strips_uploads_prefix(mock_oss2):
    """delete() 处理 /uploads/ 前缀。"""
    from app.core.storage_oss import OSSStorage
    _, mock_bucket = mock_oss2
    s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
    await s.delete("/uploads/foo/bar.txt")
    mock_bucket.delete_object.assert_called_once_with("foo/bar.txt")


# ===== OSS get_full_path =====


@pytest.mark.asyncio
async def test_oss_get_full_path_returns_url(mock_oss2):
    """get_full_path() 返回 OSS URL。"""
    from app.core.storage_oss import OSSStorage
    s = OSSStorage(bucket="my-bucket", access_key_id="k", access_key_secret="s", endpoint="oss-cn-hangzhou.aliyuncs.com")
    url = await s.get_full_path("foo/bar.txt")
    assert "my-bucket" in url
    assert "foo/bar.txt" in url
    assert url.startswith("https://")


@pytest.mark.asyncio
async def test_oss_get_full_path_strips_uploads_prefix(mock_oss2):
    """get_full_path() 处理 /uploads/ 前缀。"""
    from app.core.storage_oss import OSSStorage
    s = OSSStorage(bucket="my-bucket", access_key_id="k", access_key_secret="s", endpoint="oss-cn-hangzhou.aliyuncs.com")
    url = await s.get_full_path("/uploads/foo/bar.txt")
    assert "foo/bar.txt" in url
    assert "/uploads/uploads/" not in url
