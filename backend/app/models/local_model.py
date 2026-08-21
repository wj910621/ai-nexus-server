"""本地模型注册表 - 持久化已下载模型信息

Task 15 / Task 22 (Phase 8 P1): Local AI Inference + 多用户隔离

记录用户已下载/可用的本地 AI 模型（image/llm/tts/character）。
在桌面模式下用于离线推理。Task 22 扩展：增加 user_id、hardware_profile、md5、
download_url、original_size_mb 字段以支持多用户与下载管理。
"""
from sqlalchemy import Boolean, Column, DateTime, Integer, String

from app.models.base import Base, utc_now


class LocalModel(Base):
    """本地模型注册表

    记录用户已下载/可用的本地 AI 模型。
    """

    __tablename__ = "local_models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(128), unique=True, nullable=False, index=True)
    model_type = Column(String(32), nullable=False)  # image|llm|tts|character
    repo_id = Column(String(256), nullable=False)  # HuggingFace repo ID
    local_path = Column(String(512), nullable=True)  # Local file path
    size_mb = Column(Integer, default=0, nullable=False)
    is_downloaded = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)  # Currently selected
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now)

    # Task 22 新增字段
    user_id = Column(Integer, nullable=False, default=0, index=True)  # 0 = 平台默认
    hardware_profile = Column(String(16), nullable=True, index=True)  # low|mid|high|cpu
    md5 = Column(String(64), nullable=True)  # 模型文件 MD5 校验
    download_url = Column(String(512), nullable=True)  # 镜像/直链 URL
    original_size_mb = Column(Integer, default=0, nullable=False)  # 原始仓库大小

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "model_type": self.model_type,
            "repo_id": self.repo_id,
            "local_path": self.local_path,
            "size_mb": self.size_mb,
            "is_downloaded": self.is_downloaded,
            "is_active": self.is_active,
            "user_id": self.user_id,
            "hardware_profile": self.hardware_profile,
            "md5": self.md5,
            "download_url": self.download_url,
            "original_size_mb": self.original_size_mb,
        }
