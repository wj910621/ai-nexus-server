"""Audit service - records and queries audit logs."""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.services.base_service import BaseService


class AuditService(BaseService[AuditLog]):
    """Audit log recording and querying."""

    model = AuditLog

    def __init__(self, db: AsyncSession):
        super().__init__(db)

    async def log(
        self,
        actor_id: Optional[UUID],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[UUID] = None,
        metadata: Optional[dict] = None,
    ) -> AuditLog:
        """Record an audit log entry."""
        entry = AuditLog(
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
        )
        self.db.add(entry)
        await self.db.flush()
        await self.db.refresh(entry)
        return entry

    async def list_by_actor(
        self, actor_id: UUID, limit: int = 50, offset: int = 0,
    ) -> List[AuditLog]:
        """List logs by actor, newest first."""
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.actor_id == actor_id)
            .order_by(AuditLog.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def list_by_action(
        self, action: str, limit: int = 50, offset: int = 0,
    ) -> List[AuditLog]:
        """List logs by action type, newest first."""
        result = await self.db.execute(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def list_all(
        self, limit: int = 50, offset: int = 0,
    ) -> List[AuditLog]:
        """List all logs, newest first."""
        result = await self.db.execute(
            select(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .offset(offset).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """Total log count."""
        result = await self.db.execute(select(func.count(AuditLog.id)))
        return result.scalar_one()
