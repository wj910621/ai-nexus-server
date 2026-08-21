"""项目路由"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse, PaginatedData, PaginatedResponse
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["项目"])


@router.get("", response_model=PaginatedResponse[ProjectResponse])
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的项目列表"""
    service = ProjectService(db)
    skip = (page - 1) * page_size
    items = await service.list_by_user(current_user.id, skip=skip, limit=page_size)
    total = await service.count(filters={"user_id": current_user.id})
    return PaginatedResponse(
        data=PaginatedData(
            items=[ProjectResponse.model_validate(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[ProjectResponse])
async def create_project(
    payload: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建项目"""
    service = ProjectService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    project = await service.create(data)
    return ApiResponse.success(data=ProjectResponse.model_validate(project), message="创建成功")


@router.get("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def get_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取项目详情"""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    return ApiResponse.success(data=ProjectResponse.model_validate(project))


@router.put("/{project_id}", response_model=ApiResponse[ProjectResponse])
async def update_project(
    project_id: UUID,
    payload: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新项目"""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    updated = await service.update(project_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=ProjectResponse.model_validate(updated), message="更新成功")


@router.delete("/{project_id}", response_model=ApiResponse)
async def delete_project(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除项目（软删除）"""
    service = ProjectService(db)
    project = await service.get_by_id(project_id)
    if not project or project.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="项目不存在")
    await service.delete(project_id, soft=True)
    return ApiResponse.success(message="删除成功")
