"""分镜服务"""
from typing import List
from uuid import UUID

from sqlalchemy import select

from app.models.storyboard import StoryboardFrame
from app.services.base_service import BaseService


class StoryboardService(BaseService[StoryboardFrame]):
    model = StoryboardFrame

    async def list_by_script(self, script_id: UUID | str) -> List[StoryboardFrame]:
        if isinstance(script_id, str):
            script_id = UUID(script_id)
        result = await self.db.execute(
            select(StoryboardFrame)
            .where(StoryboardFrame.script_id == script_id)
            .order_by(StoryboardFrame.frame_number)
        )
        return list(result.scalars().all())

    async def list_by_scene(self, scene_id: UUID | str) -> List[StoryboardFrame]:
        if isinstance(scene_id, str):
            scene_id = UUID(scene_id)
        result = await self.db.execute(
            select(StoryboardFrame)
            .where(StoryboardFrame.scene_id == scene_id)
            .order_by(StoryboardFrame.frame_number)
        )
        return list(result.scalars().all())
