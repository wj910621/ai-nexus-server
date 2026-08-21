"""Phase 8 P4: 异步存储后端抽象 + 本地实现。

提供与现有同步 `storage.py` (FileStorage) 并行的异步接口，用于：
- K8s 生产环境（OSS 远端存储）
- 不破坏现有 sync 调用方

设计要点：
- `StorageBackend` 为异步抽象基类
- `LocalStorage` 异步实现，包装本地文件操作
- `get_storage()` 根据环境返回合适的后端
- 现有 `FileStorage` 保持不变，新代码可用 `get_storage()` 异步写入
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union

from app.core.paths import get_uploads_dir


class StorageBackend(ABC):
    """异步存储后端抽象基类。"""

    @abstractmethod
    async def save(self, path: str, data: bytes) -> str:
        """保存字节数据到指定路径，返回可访问的 URL 或路径标识。"""

    @abstractmethod
    async def get_full_path(self, path: str) -> Union[Path, str]:
        """返回完整路径（本地为 Path，远端为 URL）。"""

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """检查文件是否存在。"""

    @abstractmethod
    async def delete(self, path: str) -> None:
        """删除文件。"""


class LocalStorage(StorageBackend):
    """本地文件系统异步存储实现（开发环境默认）。"""

    def __init__(self, base_dir: str = None):
        if base_dir is None:
            self.base_dir = get_uploads_dir()
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, path: str, data: bytes) -> str:
        full = self.base_dir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        # 返回相对 URL（与 FileStorage 风格一致）
        return f"/uploads/{path}".replace("//", "/")

    async def get_full_path(self, path: str) -> Path:
        """返回完整路径。

        A8: 路径穿越防护 - resolve 后必须仍在 base_dir 内。
        """
        # 移除可能的 /uploads/ 前缀
        if path.startswith("/uploads/"):
            path = path[len("/uploads/"):]
        elif path.startswith("uploads/"):
            path = path[len("uploads/"):]
        full = (self.base_dir / path).resolve()
        base = self.base_dir.resolve()
        if not full.is_relative_to(base):
            raise ValueError("Invalid path: escapes base_dir")
        return full

    async def exists(self, path: str) -> bool:
        full = await self.get_full_path(path)
        return full.exists()

    async def delete(self, path: str) -> None:
        full = await self.get_full_path(path)
        if full.exists():
            full.unlink()


def get_storage() -> StorageBackend:
    """根据环境返回合适的存储后端。

    - 生产环境 + OSS 已配置 → OSSStorage
    - 其他情况 → LocalStorage（本地文件系统）

    现有 sync `FileStorage` 继续保留，新代码可用此异步接口。
    """
    from app.core.config import settings
    if settings.is_production and settings.oss_enabled and settings.oss_bucket:
        from app.core.storage_oss import OSSStorage
        return OSSStorage(
            bucket=settings.oss_bucket,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            endpoint=settings.oss_endpoint,
        )
    return LocalStorage()
