"""音频路由"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.audio import (
    AudioTrackCreate,
    AudioTrackResponse,
    VoiceProfileCreate,
    VoiceProfileResponse,
)
from app.services.audio_service import AudioTrackService, VoiceProfileService

router = APIRouter(prefix="/audio", tags=["音频"])


# === 音色配置 ===
@router.get("/voices", response_model=ApiResponse[list[VoiceProfileResponse]])
async def list_voice_profiles(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = VoiceProfileService(db)
    items = await service.list_by_user(current_user.id)
    return ApiResponse.success(data=[VoiceProfileResponse.model_validate(v) for v in items])


@router.post("/voices", response_model=ApiResponse[VoiceProfileResponse])
async def create_voice_profile(
    payload: VoiceProfileCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = VoiceProfileService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    voice = await service.create(data)
    return ApiResponse.success(data=VoiceProfileResponse.model_validate(voice), message="创建成功")


# === 音频轨道 ===
@router.get("/tracks/{project_id}", response_model=ApiResponse[list[AudioTrackResponse]])
async def list_tracks(
    project_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioTrackService(db)
    items = await service.list_by_project(project_id)
    return ApiResponse.success(data=[AudioTrackResponse.model_validate(t) for t in items])


@router.post("/tracks", response_model=ApiResponse[AudioTrackResponse])
async def create_track(
    payload: AudioTrackCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = AudioTrackService(db)
    track = await service.create(payload.model_dump())
    return ApiResponse.success(data=AudioTrackResponse.model_validate(track), message="创建成功")
