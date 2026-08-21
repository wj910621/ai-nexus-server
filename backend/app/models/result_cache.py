"""结果缓存模型 - 持久化 AI 生成结果到数据库"""
import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, utc_now


class ResultCacheEntry(Base):
    """AI 生成结果缓存条目

    缓存键: SHA256(engine_type + sorted params + user_id)
    用于在相同请求时直接返回缓存结果，减少 AI API 调用。

    Note: user_id is String(64) to be compatible with User.id (UUID stored as
    string). SQLite tests can pass any string; PostgreSQL accepts UUID strings.
    """

    __tablename__ = "result_cache"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    cache_key: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    user_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True
    )  # NULL = 全局缓存; String(64) to hold UUID strings
    engine_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True
    )
    result_payload: Mapped[str] = mapped_column(
        Text, nullable=False
    )  # JSON-serialized
    hit_count: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utc_now, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )

    __table_args__ = (
        Index("ix_result_cache_key_user", "cache_key", "user_id"),
        Index("ix_result_cache_expires", "expires_at"),
    )

    @staticmethod
    def build_cache_key(
        engine_type: str,
        params: dict,
        user_id: str | int | None = None,
    ) -> str:
        """构建缓存键 - SHA256 of engine_type + sorted params + user_id

        Accepts str (UUID string) or int (legacy/test) — coerced to str for hash.
        """
        uid_str = str(user_id) if user_id is not None else "None"
        sorted_params = sorted(params.items(), key=lambda x: x[0])
        params_str = "&".join(f"{k}={v}" for k, v in sorted_params)
        key_input = f"{engine_type}:{params_str}:u={uid_str}"
        return hashlib.sha256(key_input.encode("utf-8")).hexdigest()

    def is_expired(self) -> bool:
        return utc_now() >= self.expires_at
