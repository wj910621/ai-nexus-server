"""文件存储抽象 - MinIO/S3 兼容"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.core.paths import get_uploads_dir


class FileStorage:
    """本地文件存储（开发环境默认）

    生产环境可替换为 MinIO/S3 实现。
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir is None:
            self.base_dir = get_uploads_dir()
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        data: bytes,
        filename: Optional[str] = None,
        subdir: str = "",
        extension: str = "bin",
    ) -> str:
        """保存文件，返回相对路径（作为 URL）"""
        if not filename:
            filename = f"{uuid.uuid4().hex}.{extension}"

        # 按日期分目录
        date_dir = datetime.now().strftime("%Y%m%d")
        target_dir = self.base_dir / subdir / date_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / filename
        file_path.write_bytes(data)

        # 返回相对路径作为 URL
        return f"/uploads/{subdir}/{date_dir}/{filename}".replace("//", "/")

    def get_full_path(self, relative_path: str) -> Path:
        """根据相对路径获取完整路径

        A8: 路径穿越防护 - resolve 后必须仍在 base_dir 内，否则抛 ValueError。
        """
        # 移除开头的 /uploads/
        if relative_path.startswith("/uploads/"):
            relative_path = relative_path[len("/uploads/"):]
        elif relative_path.startswith("uploads/"):
            relative_path = relative_path[len("uploads/"):]

        full = (self.base_dir / relative_path).resolve()
        base = self.base_dir.resolve()
        if not full.is_relative_to(base):
            raise ValueError("Invalid path: escapes base_dir")
        return full

    def exists(self, relative_path: str) -> bool:
        """检查文件是否存在"""
        return self.get_full_path(relative_path).exists()

    def delete(self, relative_path: str) -> bool:
        """删除文件"""
        path = self.get_full_path(relative_path)
        if path.exists():
            path.unlink()
            return True
        return False


# 全局单例
storage = FileStorage()
