"""Tests for TaskService — async task state machine."""
import pytest
import asyncio
from datetime import datetime, timezone

from app.services.task_service import TaskService
from app.models.background_task import BackgroundTask


@pytest.fixture
def task_service():
    return TaskService()


@pytest.mark.asyncio
async def test_submit_task_creates_pending_record(db_session, task_service):
    """Submitting a task creates a DB record with status=pending."""
    task = await task_service.submit(
        db_session,
        user_id=1,
        task_type="video_compose",
        payload={"frames": ["url1", "url2"], "fps": 30},
    )
    assert task.id.startswith("task_")
    assert task.status == "pending"
    assert task.progress == 0
    assert task.user_id == "1"
    assert task.task_type == "video_compose"


@pytest.mark.asyncio
async def test_get_task_returns_record(db_session, task_service):
    """Get task by ID returns the record."""
    submitted = await task_service.submit(
        db_session, user_id=1, task_type="video_compose", payload={}
    )
    fetched = await task_service.get(db_session, submitted.id)
    assert fetched is not None
    assert fetched.id == submitted.id


@pytest.mark.asyncio
async def test_get_task_returns_none_for_missing(db_session, task_service):
    """Get non-existent task returns None."""
    fetched = await task_service.get(db_session, "task_nonexistent")
    assert fetched is None


@pytest.mark.asyncio
async def test_list_tasks_by_user(db_session, task_service):
    """List tasks for a specific user."""
    await task_service.submit(db_session, user_id=1, task_type="t1", payload={})
    await task_service.submit(db_session, user_id=1, task_type="t2", payload={})
    await task_service.submit(db_session, user_id=2, task_type="t3", payload={})

    tasks = await task_service.list_by_user(db_session, user_id=1)
    assert len(tasks) == 2
    assert all(t.user_id == "1" for t in tasks)


@pytest.mark.asyncio
async def test_list_tasks_pagination(db_session, task_service):
    """List tasks with pagination."""
    for i in range(15):
        await task_service.submit(db_session, user_id=1, task_type="t", payload={})

    page1 = await task_service.list_by_user(db_session, user_id=1, page=1, page_size=10)
    page2 = await task_service.list_by_user(db_session, user_id=1, page=2, page_size=10)
    assert len(page1) == 10
    assert len(page2) == 5


@pytest.mark.asyncio
async def test_mark_running_updates_status(db_session, task_service):
    """Mark task as running sets started_at."""
    task = await task_service.submit(db_session, user_id=1, task_type="t", payload={})
    updated = await task_service.mark_running(db_session, task.id)
    assert updated.status == "running"
    assert updated.started_at is not None


@pytest.mark.asyncio
async def test_mark_succeeded_sets_result(db_session, task_service):
    """Mark task succeeded sets result and completed_at."""
    task = await task_service.submit(db_session, user_id=1, task_type="t", payload={})
    updated = await task_service.mark_succeeded(
        db_session, task.id, result={"video_url": "/uploads/video.mp4"}
    )
    assert updated.status == "succeeded"
    assert updated.result == {"video_url": "/uploads/video.mp4"}
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_mark_failed_sets_error(db_session, task_service):
    """Mark task failed sets error message."""
    task = await task_service.submit(db_session, user_id=1, task_type="t", payload={})
    updated = await task_service.mark_failed(db_session, task.id, error="FFmpeg crashed")
    assert updated.status == "failed"
    assert updated.error == "FFmpeg crashed"


@pytest.mark.asyncio
async def test_cancel_pending_task(db_session, task_service):
    """Cancel a pending task."""
    task = await task_service.submit(db_session, user_id=1, task_type="t", payload={})
    updated = await task_service.cancel(db_session, task.id)
    assert updated.status == "cancelled"


@pytest.mark.asyncio
async def test_update_progress(db_session, task_service):
    """Update progress percentage."""
    task = await task_service.submit(db_session, user_id=1, task_type="t", payload={})
    await task_service.update_progress(db_session, task.id, progress=45)
    fetched = await task_service.get(db_session, task.id)
    assert fetched.progress == 45


@pytest.mark.asyncio
async def test_submit_executes_handler_async(db_session, task_service):
    """Submitted task runs handler asynchronously."""
    handler_called = asyncio.Event()

    async def fake_handler(task):
        handler_called.set()
        return {"output": "done"}

    task_service.register_handler("test_type", fake_handler)
    task = await task_service.submit(
        db_session, user_id=1, task_type="test_type", payload={}
    )
    # Wait for handler to complete
    await asyncio.wait_for(handler_called.wait(), timeout=2.0)
    # Allow DB state to settle
    await asyncio.sleep(0.1)
    fetched = await task_service.get(db_session, task.id)
    assert fetched.status == "succeeded"
    assert fetched.result == {"output": "done"}


@pytest.mark.asyncio
async def test_handler_failure_marks_task_failed(db_session, task_service):
    """Handler exception marks task as failed."""
    async def failing_handler(task):
        raise RuntimeError("Handler crashed")

    task_service.register_handler("failing_type", failing_handler)
    task = await task_service.submit(
        db_session, user_id=1, task_type="failing_type", payload={}
    )
    await asyncio.sleep(0.5)  # Wait for handler to fail
    fetched = await task_service.get(db_session, task.id)
    assert fetched.status == "failed"
    assert "Handler crashed" in fetched.error
