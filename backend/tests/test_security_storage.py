"""A8: 路径穿越防护测试 - Phase 8 P7"""
import os
import tempfile
import pytest
from pathlib import Path

from app.core.storage import FileStorage


@pytest.fixture
def storage(tmp_path):
    """临时 base_dir 的 FileStorage"""
    return FileStorage(base_dir=str(tmp_path))


def test_normal_path(storage):
    """正常相对路径应返回完整路径"""
    # 先创建文件
    rel = storage.save(b"hello", filename="a.png", subdir="x", extension="png")
    full = storage.get_full_path(rel)
    assert full.exists()
    assert full.read_bytes() == b"hello"


def test_path_traversal_rejected(storage):
    """../ 直接前缀应被拒绝"""
    with pytest.raises(ValueError, match="escapes base_dir|Invalid path"):
        storage.get_full_path("../etc/passwd")


def test_double_dot_rejected(storage):
    """中间包含 ../ 应被拒绝"""
    with pytest.raises(ValueError, match="escapes base_dir|Invalid path"):
        storage.get_full_path("uploads/../../etc/passwd")


def test_absolute_path_rejected(storage):
    """绝对路径应被拒绝（或被规范化到 base_dir 之外则抛错）"""
    # /etc/passwd 在 Linux 下是真实文件，Windows 下是 C:\etc\passwd
    # 无论哪种，resolve 后都不在 base_dir 内
    with pytest.raises(ValueError, match="escapes base_dir|Invalid path"):
        storage.get_full_path("/etc/passwd")


def test_existing_file_accessible(storage):
    """已存在的文件应正常访问"""
    rel = storage.save(b"data", filename="b.jpg", subdir="y", extension="jpg")
    assert storage.exists(rel) is True
    full = storage.get_full_path(rel)
    assert full.is_relative_to(storage.base_dir.resolve())


def test_storage_async_path_traversal_rejected(tmp_path):
    """异步 LocalStorage 同样拒绝路径穿越"""
    import asyncio
    from app.core.storage_async import LocalStorage

    async def run():
        s = LocalStorage(base_dir=str(tmp_path))
        with pytest.raises(ValueError, match="escapes base_dir|Invalid path"):
            await s.get_full_path("../etc/passwd")

    # Python 3.10+ 中 asyncio.get_event_loop() 在无事件循环时会报错，
    # 使用 asyncio.run() 创建新事件循环执行协程
    asyncio.run(run())


def test_uploads_prefix_normalized(storage):
    """带 /uploads/ 前缀的路径应被正确规范化"""
    rel = storage.save(b"hi", filename="c.png", extension="png")
    # get_full_path 应能处理 /uploads/ 前缀
    full = storage.get_full_path(rel)
    assert full.exists()
