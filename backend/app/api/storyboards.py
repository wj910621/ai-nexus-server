"""分镜路由"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.storyboard import (
    StoryboardFrameCreate,
    StoryboardFrameResponse,
    StoryboardFrameUpdate,
)
from app.services.storyboard_service import StoryboardService

router = APIRouter(prefix="/storyboards", tags=["分镜"])


@router.post("", response_model=ApiResponse[StoryboardFrameResponse])
async def create_frame(
    payload: StoryboardFrameCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    frame = await service.create(payload.model_dump())
    return ApiResponse.success(data=StoryboardFrameResponse.model_validate(frame), message="创建成功")


@router.get("/{frame_id}", response_model=ApiResponse[StoryboardFrameResponse])
async def get_frame(
    frame_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    frame = await service.get_by_id(frame_id)
    if not frame:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return ApiResponse.success(data=StoryboardFrameResponse.model_validate(frame))


@router.put("/{frame_id}", response_model=ApiResponse[StoryboardFrameResponse])
async def update_frame(
    frame_id: UUID,
    payload: StoryboardFrameUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    updated = await service.update(frame_id, payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="分镜不存在")
    return ApiResponse.success(data=StoryboardFrameResponse.model_validate(updated), message="更新成功")


@router.get("/by-script/{script_id}", response_model=ApiResponse[list[StoryboardFrameResponse]])
async def list_frames_by_script(
    script_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = StoryboardService(db)
    items = await service.list_by_script(script_id)
    return ApiResponse.success(data=[StoryboardFrameResponse.model_validate(f) for f in items])
