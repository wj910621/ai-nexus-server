"""角色服务"""
from typing import List
from uuid import UUID

from sqlalchemy import select

from app.models.character import Character
from app.services.base_service import BaseService


class CharacterService(BaseService[Character]):
    model = Character

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 50) -> List[Character]:
        """获取用户的角色库"""
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(Character)
            .where(Character.user_id == user_id, Character.is_deleted.is_(False))
            .order_by(Character.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_project(self, project_id: UUID | str) -> List[Character]:
        """获取项目内的角色"""
        if isinstance(project_id, str):
            project_id = UUID(project_id)
        result = await self.db.execute(
            select(Character)
            .where(
                Character.project_id == project_id,
                Character.is_deleted.is_(False),
            )
            .order_by(Character.created_at)
        )
        return list(result.scalars().all())
