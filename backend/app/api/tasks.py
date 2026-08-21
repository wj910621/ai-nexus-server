"""Task management endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.task import TaskResponse
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=ApiResponse)
async def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List current user's tasks."""
    tasks = await task_service.list_by_user(
        db, user.id, page=page, page_size=page_size, status=status
    )
    total = await task_service.count_by_user(db, user.id, status=status)
    return ApiResponse.success(
        data={
            "items": [TaskResponse.model_validate(t).model_dump() for t in tasks],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    )


@router.get("/{task_id}", response_model=ApiResponse)
async def get_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Get task by ID."""
    task = await task_service.get(db, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    return ApiResponse.success(data=TaskResponse.model_validate(task).model_dump())


@router.post("/{task_id}/cancel", response_model=ApiResponse)
async def cancel_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Cancel a task."""
    task = await task_service.get(db, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.status not in ("pending", "running"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task in '{task.status}' state",
        )
    cancelled = await task_service.cancel(db, task_id)
    return ApiResponse.success(
        data=TaskResponse.model_validate(cancelled).model_dump(),
        message="Task cancelled",
    )
