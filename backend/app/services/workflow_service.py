"""工作流服务"""
from typing import List
from uuid import UUID

from sqlalchemy import select, update

from app.models.base import utc_now
from app.models.workflow import Workflow, WorkflowExecution
from app.services.base_service import BaseService


class WorkflowService(BaseService[Workflow]):
    model = Workflow

    async def list_by_user(self, user_id: UUID | str, skip: int = 0, limit: int = 50) -> List[Workflow]:
        if isinstance(user_id, str):
            user_id = UUID(user_id)
        result = await self.db.execute(
            select(Workflow)
            .where(Workflow.user_id == user_id, Workflow.is_deleted.is_(False))
            .order_by(Workflow.updated_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_templates(self, category: str = None) -> List[Workflow]:
        """获取公开模板"""
        stmt = select(Workflow).where(
            Workflow.is_template.is_(True),
            Workflow.is_deleted.is_(False),
        )
        if category:
            stmt = stmt.where(Workflow.category == category)
        result = await self.db.execute(stmt.order_by(Workflow.created_at.desc()))
        return list(result.scalars().all())


class WorkflowExecutionService(BaseService[WorkflowExecution]):
    model = WorkflowExecution

    async def get_owned(
        self, execution_id: UUID | str, user_id: UUID | str
    ) -> WorkflowExecution | None:
        """Fetch an execution by its public ID while enforcing ownership."""
        if isinstance(execution_id, str):
            try:
                execution_id = UUID(execution_id)
            except ValueError:
                return None
        if isinstance(user_id, str):
            try:
                user_id = UUID(user_id)
            except ValueError:
                return None
        result = await self.db.execute(
            select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id,
                WorkflowExecution.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def recover_interrupted(self) -> int:
        """Mark executions left running by a previous process as failed."""
        result = await self.db.execute(
            update(WorkflowExecution)
            .where(WorkflowExecution.status == "running")
            .values(
                status="failed",
                completed_at=utc_now(),
                errors={"system": "Execution interrupted by process restart"},
            )
        )
        await self.db.commit()
        return result.rowcount

    async def list_by_workflow(self, workflow_id: UUID | str) -> List[WorkflowExecution]:
        if isinstance(workflow_id, str):
            workflow_id = UUID(workflow_id)
        result = await self.db.execute(
            select(WorkflowExecution)
            .where(WorkflowExecution.workflow_id == workflow_id)
            .order_by(WorkflowExecution.created_at.desc())
        )
        return list(result.scalars().all())
