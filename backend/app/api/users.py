"""用户路由"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.user import (
    FirstLaunchUpdate,
    UserPreferencesResponse,
    UserPreferencesUpdate,
    UserResponse,
    UserUpdate,
)
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["用户"])


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return ApiResponse.success(data=UserResponse.model_validate(current_user))


@router.put("/me", response_model=ApiResponse[UserResponse])
async def update_current_user(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新当前用户信息"""
    service = UserService(db)
    updated = await service.update(current_user.id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=UserResponse.model_validate(updated), message="更新成功")


@router.put("/me/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    payload: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """更新当前用户偏好设置"""
    if payload.preferred_provider is not None:
        current_user.preferred_provider = payload.preferred_provider
    if payload.telemetry_enabled is not None:
        current_user.telemetry_enabled = payload.telemetry_enabled
    if payload.cloud_sync_enabled is not None:
        current_user.cloud_sync_enabled = payload.cloud_sync_enabled
    await db.commit()
    await db.refresh(current_user)
    return UserPreferencesResponse.model_validate(current_user)


@router.put("/me/first-launch", response_model=UserPreferencesResponse)
async def update_first_launch(
    payload: FirstLaunchUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """标记首启动完成（幂等）"""
    if payload.completed:
        current_user.first_launch_completed = True
    await db.commit()
    await db.refresh(current_user)
    return UserPreferencesResponse.model_validate(current_user)


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
) -> UserPreferencesResponse:
    """获取当前用户偏好设置"""
    return UserPreferencesResponse.model_validate(current_user)
