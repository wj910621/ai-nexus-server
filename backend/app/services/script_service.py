"""剧本服务"""
from typing import List
from uuid import UUID

from sqlalchemy import select

from app.models.script import Dialogue, Scene, Script
from app.services.base_service import BaseService


class ScriptService(BaseService[Script]):
    model = Script

    async def list_by_project(self, project_id: UUID | str) -> List[Script]:
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(Script)
            .where(Script.project_id == project_id)
            .order_by(Script.updated_at.desc())
        )
        return list(result.scalars().all())


class SceneService(BaseService[Scene]):
    model = Scene

    async def list_by_script(self, script_id: UUID | str) -> List[Scene]:
        if isinstance(script_id, str):
            script_id = UUID(script_id)
        result = await self.db.execute(
            select(Scene)
            .where(Scene.script_id == script_id)
            .order_by(Scene.order_index, Scene.scene_number)
        )
        return list(result.scalars().all())


class DialogueService(BaseService[Dialogue]):
    model = Dialogue

    async def list_by_scene(self, scene_id: UUID | str) -> List[Dialogue]:
        if isinstance(scene_id, str):
            scene_id = UUID(scene_id)
        result = await self.db.execute(
            select(Dialogue)
            .where(Dialogue.scene_id == scene_id)
            .order_by(Dialogue.order_index)
        )
        return list(result.scalars().all())
