"""音频服务"""
from typing import List
from uuid import UUID

from sqlalchemy import select

from app.models.audio import AudioTrack, VoiceProfile
from app.services.base_service import BaseService


class VoiceProfileService(BaseService[VoiceProfile]):
    model = VoiceProfile

    async def list_by_user(self, user_id: UUID | str) -> List[VoiceProfile]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(VoiceProfile)
            .where(VoiceProfile.user_id == user_id, VoiceProfile.is_deleted.is_(False))
            .order_by(VoiceProfile.created_at.desc())
        )
        return list(result.scalars().all())


class AudioTrackService(BaseService[AudioTrack]):
    model = AudioTrack

    async def list_by_project(self, project_id: UUID | str) -> List[AudioTrack]:
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(AudioTrack)
            .where(AudioTrack.project_id == project_id, AudioTrack.is_deleted.is_(False))
            .order_by(AudioTrack.start_time)
        )
        return list(result.scalars().all())


# 统一服务类，兼容外部调用
class AudioService:
    """音频服务统一入口"""

    def __init__(self, db):
        self.voice_profile = VoiceProfileService(db)
        self.track = AudioTrackService(db)
