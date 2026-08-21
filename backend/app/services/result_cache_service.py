"""结果缓存服务 - 持久化 AI 生成结果"""
import json
from datetime import timedelta
from typing import Any, Optional

from sqlalchemy import delete, select

from app.models.base import utc_now
from app.models.result_cache import ResultCacheEntry


class ResultCacheService:
    """持久化结果缓存 - 减少 AI API 调用

    TTL策略:
    - image/tts/character: 24h (静态资产)
    - video: 7d (合成昂贵)
    - llm: 30min (可能有变化)
    """

    DEFAULT_TTL_SECONDS = 3600
    IMAGE_TTL_SECONDS = 86400
    VIDEO_TTL_SECONDS = 604800
    LLM_TTL_SECONDS = 1800

    async def get(
        self,
        engine_type: str,
        params: dict,
        user_id: Optional[int] = None,
    ) -> Optional[Any]:
        """获取缓存结果，未命中或已过期返回 None"""
        # Import inside method so tests' monkeypatch on database.AsyncSessionLocal
        # takes effect (module-level import would capture the original reference).
        from app.core.database import AsyncSessionLocal

        cache_key = ResultCacheEntry.build_cache_key(engine_type, params, user_id)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(ResultCacheEntry).where(
                    ResultCacheEntry.cache_key == cache_key,
                    ResultCacheEntry.expires_at > utc_now(),
                )
            )
            entry = result.scalar_one_or_none()
            if entry is None:
                return None

            entry.hit_count += 1
            await db.commit()
            return json.loads(entry.result_payload)

    async def set(
        self,
        engine_type: str,
        params: dict,
        result: Any,
        user_id: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
    ) -> None:
        """写入缓存 (Upsert)"""
        from app.core.database import AsyncSessionLocal

        if ttl_seconds is None:
            ttl_seconds = self._default_ttl(engine_type)

        cache_key = ResultCacheEntry.build_cache_key(engine_type, params, user_id)
        expires_at = utc_now() + timedelta(seconds=ttl_seconds)
        payload_str = json.dumps(result, ensure_ascii=False, default=str)

        async with AsyncSessionLocal() as db:
            existing = await db.execute(
                select(ResultCacheEntry).where(
                    ResultCacheEntry.cache_key == cache_key
                )
            )
            entry = existing.scalar_one_or_none()
            if entry:
                entry.result_payload = payload_str
                entry.expires_at = expires_at
                entry.user_id = user_id
            else:
                entry = ResultCacheEntry(
                    cache_key=cache_key,
                    user_id=user_id,
                    engine_type=engine_type,
                    result_payload=payload_str,
                    hit_count=0,
                    expires_at=expires_at,
                )
                db.add(entry)
            await db.commit()

    async def invalidate_user(self, user_id: str) -> int:
        """失效某用户的所有缓存"""
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(ResultCacheEntry).where(
                    ResultCacheEntry.user_id == user_id
                )
            )
            await db.commit()
            return result.rowcount

    async def cleanup_expired(self) -> int:
        """清理已过期缓存，返回清理条数"""
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                delete(ResultCacheEntry).where(
                    ResultCacheEntry.expires_at <= utc_now()
                )
            )
            await db.commit()
            return result.rowcount

    def _default_ttl(self, engine_type: str) -> int:
        return {
            "image": self.IMAGE_TTL_SECONDS,
            "video": self.VIDEO_TTL_SECONDS,
            "llm": self.LLM_TTL_SECONDS,
            "tts": self.IMAGE_TTL_SECONDS,
            "character": self.IMAGE_TTL_SECONDS,
        }.get(engine_type, self.DEFAULT_TTL_SECONDS)


result_cache_service = ResultCacheService()
