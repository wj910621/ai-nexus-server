"""Durable workflow execution ownership and recovery tests."""
from datetime import datetime, UTC
from uuid import uuid4

import pytest

from app.services.workflow_service import WorkflowExecutionService


@pytest.mark.asyncio
async def test_inline_execution_is_persisted_and_owner_scoped(db_session):
    service = WorkflowExecutionService(db_session)
    execution_id = uuid4()
    owner_id = uuid4()
    await service.create({
        "id": execution_id,
        "workflow_id": None,
        "user_id": owner_id,
        "status": "running",
        "inputs": {},
        "results": {},
        "errors": {},
        "started_at": datetime.now(UTC).replace(tzinfo=None),
        "node_executions": [],
    })
    await db_session.commit()

    assert await service.get_owned(execution_id, owner_id) is not None
    assert await service.get_owned(execution_id, uuid4()) is None


@pytest.mark.asyncio
async def test_interrupted_execution_is_failed_on_recovery(db_session):
    service = WorkflowExecutionService(db_session)
    execution_id = uuid4()
    owner_id = uuid4()
    await service.create({
        "id": execution_id,
        "workflow_id": None,
        "user_id": owner_id,
        "status": "running",
        "inputs": {},
        "results": {},
        "errors": {},
        "started_at": datetime.now(UTC).replace(tzinfo=None),
        "node_executions": [],
    })
    await db_session.commit()

    assert await service.recover_interrupted() == 1
    recovered = await service.get_owned(execution_id, owner_id)
    assert recovered.status == "failed"
    assert recovered.errors["system"]
