"""服务基类 - 提供通用 CRUD 操作"""
from abc import ABC
from typing import Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base, utc_now

ModelType = TypeVar("ModelType", bound=Base)


class BaseService(Generic[ModelType], ABC):
    """业务服务基类，提供异步 CRUD 操作"""

    model: Type[ModelType]

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: dict) -> ModelType:
        """创建实体"""
        entity = self.model(**data)
        self.db.add(entity)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def get_by_id(self, entity_id: UUID | str) -> Optional[ModelType]:
        """根据 ID 获取实体"""
        if isinstance(entity_id, str):
            entity_id = UUID(entity_id)
        result = await self.db.execute(
            select(self.model).where(self.model.id == entity_id)
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        skip: int = 0,
        limit: int = 20,
        filters: Optional[dict] = None,
        eager_load: Optional[List[str]] = None,
    ) -> List[ModelType]:
        """列表查询

        Args:
            eager_load: List of relationship attribute names to eager-load
                        (prevents N+1 queries when accessing relationships).
        """
        stmt = select(self.model)

        # Apply eager loading to prevent N+1 queries (Task 6)
        if eager_load:
            from sqlalchemy.orm import selectinload
            for rel_name in eager_load:
                rel_attr = getattr(self.model, rel_name, None)
                if rel_attr is not None:
                    stmt = stmt.options(selectinload(rel_attr))

        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    stmt = stmt.where(getattr(self.model, key) == value)
        # 软删除过滤
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted.is_(False))
        stmt = stmt.offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: Optional[dict] = None) -> int:
        """计数"""
        stmt = select(func.count(self.model.id))
        if filters:
            for key, value in filters.items():
                if hasattr(self.model, key) and value is not None:
                    stmt = stmt.where(getattr(self.model, key) == value)
        if hasattr(self.model, "is_deleted"):
            stmt = stmt.where(self.model.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def update(self, entity_id: UUID | str, data: dict) -> Optional[ModelType]:
        """更新实体"""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return None
        for key, value in data.items():
            if hasattr(entity, key) and value is not None:
                setattr(entity, key, value)
        await self.db.flush()
        await self.db.refresh(entity)
        return entity

    async def delete(self, entity_id: UUID | str, soft: bool = True) -> bool:
        """删除实体（默认软删除）"""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False
        if soft and hasattr(entity, "is_deleted"):
            entity.is_deleted = True
            entity.deleted_at = utc_now()
        else:
            await self.db.delete(entity)
        await self.db.flush()
        return True
