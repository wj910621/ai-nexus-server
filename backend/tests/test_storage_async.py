"""Phase 8 P4 - 异步存储后端测试。

测试 StorageBackend 抽象 + LocalStorage 实现 + get_storage() 工厂。
OSSStorage 单独在 test_storage_oss.py 测试（mock oss2）。
"""
import pytest
from pathlib import Path
from unittest.mock import patch


# ===== StorageBackend 抽象 =====


def test_storage_backend_is_abstract():
    """StorageBackend 是抽象基类，不能直接实例化。"""
    from app.core.storage_async import StorageBackend
    with pytest.raises(TypeError):
        StorageBackend()


# ===== LocalStorage 异步实现 =====


@pytest.mark.asyncio
async def test_local_storage_save_and_read(tmp_path):
    """LocalStorage 保存后能读取到正确内容。"""
    from app.core.storage_async import LocalStorage
    s = LocalStorage(base_dir=str(tmp_path))
    url = await s.save("foo/bar.txt", b"hello")
    assert "foo/bar.txt" in url
    full = await s.get_full_path("foo/bar.txt")
    assert Path(full).read_bytes() == b"hello"


@pytest.mark.asyncio
async def test_local_storage_exists(tmp_path):
    """LocalStorage exists() 正确返回 True/False。"""
    from app.core.storage_async import LocalStorage
    s = LocalStorage(base_dir=str(tmp_path))
    await s.save("a.txt", b"x")
    assert await s.exists("a.txt") is True
    assert await s.exists("missing.txt") is False


@pytest.mark.asyncio
async def test_local_storage_delete(tmp_path):
    """LocalStorage delete() 删除文件。"""
    from app.core.storage_async import LocalStorage
    s = LocalStorage(base_dir=str(tmp_path))
    await s.save("a.txt", b"x")
    await s.delete("a.txt")
    assert await s.exists("a.txt") is False


@pytest.mark.asyncio
async def test_local_storage_delete_nonexistent_is_noop(tmp_path):
    """LocalStorage delete() 不存在的文件不报错。"""
    from app.core.storage_async import LocalStorage
    s = LocalStorage(base_dir=str(tmp_path))
    await s.delete("missing.txt")  # should not raise


@pytest.mark.asyncio
async def test_local_storage_get_full_path_strips_uploads_prefix(tmp_path):
    """LocalStorage get_full_path() 处理 /uploads/ 前缀。"""
    from app.core.storage_async import LocalStorage
    s = LocalStorage(base_dir=str(tmp_path))
    full = await s.get_full_path("/uploads/foo/bar.txt")
    assert "foo" in str(full)
    assert "bar.txt" in str(full)


@pytest.mark.asyncio
async def test_local_storage_creates_subdirs(tmp_path):
    """LocalStorage save() 自动创建子目录。"""
    from app.core.storage_async import LocalStorage
    s = LocalStorage(base_dir=str(tmp_path))
    await s.save("deep/nested/path/file.txt", b"deep")
    full = await s.get_full_path("deep/nested/path/file.txt")
    assert Path(full).exists()


# ===== get_storage() 工厂 =====


def test_get_storage_returns_local_in_dev():
    """开发环境返回 LocalStorage。"""
    from app.core.storage_async import get_storage, LocalStorage
    storage = get_storage()
    assert isinstance(storage, LocalStorage)


def test_get_storage_returns_oss_in_production_when_enabled(monkeypatch):
    """生产环境 + OSS 启用时返回 OSSStorage。"""
    from app.core.config import Settings
    s = Settings(
        app_env="production",
        oss_enabled=True,
        oss_bucket="test-bucket",
        oss_access_key_id="key-id",
        oss_access_key_secret="key-secret",
        oss_endpoint="oss-cn-hangzhou.aliyuncs.com",
    )
    monkeypatch.setattr("app.core.config.settings", s)

    # Mock oss2 模块，避免实际依赖
    import sys
    from types import ModuleType
    from unittest.mock import MagicMock
    mock_oss2 = MagicMock()
    mock_oss2.Auth = MagicMock(return_value=MagicMock())
    mock_oss2.Bucket = MagicMock(return_value=MagicMock())
    monkeypatch.setitem(sys.modules, "oss2", mock_oss2)
    # 同时 patch storage_oss 中已 import 的 oss2
    monkeypatch.setattr("app.core.storage_oss.oss2", mock_oss2)

    # 不使用 importlib.reload，因为 get_storage() 在函数体内读取 settings
    from app.core.storage_async import get_storage
    storage = get_storage()
    assert storage.__class__.__name__ == "OSSStorage"


def test_get_storage_returns_local_in_production_when_oss_disabled(monkeypatch):
    """生产环境但 OSS 未启用时返回 LocalStorage。"""
    from app.core.config import Settings
    s = Settings(app_env="production", oss_enabled=False)
    monkeypatch.setattr("app.core.config.settings", s)
    from app.core.storage_async import get_storage
    storage = get_storage()
    assert storage.__class__.__name__ == "LocalStorage"


# ===== 向后兼容：现有 FileStorage 仍可用 =====


def test_existing_file_storage_still_works():
    """现有 sync FileStorage 保持向后兼容。"""
    from app.core.storage import FileStorage, storage
    assert FileStorage is not None
    assert storage is not None
    # 应有 sync API（不带 await）
    assert callable(getattr(storage, "save", None))
    assert callable(getattr(storage, "get_full_path", None))
