"""渲染路由"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.render import RenderTaskCreate, RenderTaskResponse
from app.services.render_service import RenderService

router = APIRouter(prefix="/render", tags=["渲染"])


@router.post("", response_model=ApiResponse[RenderTaskResponse])
async def create_render_task(
    payload: RenderTaskCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建渲染任务 (实际执行在后续 AI 引擎阶段实现)"""
    service = RenderService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    data["status"] = "pending"
    task = await service.create(data)
    return ApiResponse.success(data=RenderTaskResponse.model_validate(task), message="渲染任务已创建")


@router.get("/{task_id}", response_model=ApiResponse[RenderTaskResponse])
async def get_render_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = RenderService(db)
    task = await service.get_by_id(task_id)
    if not task or task.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="渲染任务不存在")
    return ApiResponse.success(data=RenderTaskResponse.model_validate(task))


@router.get("", response_model=ApiResponse[list[RenderTaskResponse]])
async def list_render_tasks(
    project_id: UUID | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = RenderService(db)
    if project_id:
        items = await service.list_by_project(project_id)
    else:
        items = await service.list_by_user(current_user.id)
    return ApiResponse.success(data=[RenderTaskResponse.model_validate(t) for t in items])
