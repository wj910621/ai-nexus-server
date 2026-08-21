"""渲染服务"""
from typing import List
from uuid import UUID

from sqlalchemy import select

from app.models.render import RenderTask
from app.services.base_service import BaseService


class RenderService(BaseService[RenderTask]):
    model = RenderTask

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 20) -> List[RenderTask]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(RenderTask)
            .where(RenderTask.user_id == user_id)
            .order_by(RenderTask.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_project(self, project_id: UUID | str) -> List[RenderTask]:
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(RenderTask)
            .where(RenderTask.project_id == project_id)
            .order_by(RenderTask.created_at.desc())
        )
        return list(result.scalars().all())
