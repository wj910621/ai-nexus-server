"""项目服务"""
from typing import List
from uuid import UUID

from sqlalchemy import select

from app.models.project import Project
from app.services.base_service import BaseService


class ProjectService(BaseService[Project]):
    model = Project

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 20) -> List[Project]:
        """获取用户的项目列表"""
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(Project)
            .where(Project.user_id == user_id, Project.is_deleted.is_(False))
            .order_by(Project.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())
