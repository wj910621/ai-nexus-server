"""剧本路由"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.script import (
    DialogueCreate,
    DialogueResponse,
    SceneCreate,
    SceneResponse,
    ScriptCreate,
    ScriptResponse,
    ScriptUpdate,
)
from app.services.script_service import DialogueService, SceneService, ScriptService

router = APIRouter(prefix="/scripts", tags=["剧本"])


# === 剧本 CRUD ===
@router.post("", response_model=ApiResponse[ScriptResponse])
async def create_script(
    payload: ScriptCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScriptService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    script = await service.create(data)
    return ApiResponse.success(data=ScriptResponse.model_validate(script), message="创建成功")


@router.get("/{script_id}", response_model=ApiResponse[ScriptResponse])
async def get_script(
    script_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScriptService(db)
    script = await service.get_by_id(script_id)
    if not script or script.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="剧本不存在")
    return ApiResponse.success(data=ScriptResponse.model_validate(script))


@router.put("/{script_id}", response_model=ApiResponse[ScriptResponse])
async def update_script(
    script_id: UUID,
    payload: ScriptUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = ScriptService(db)
    script = await service.get_by_id(script_id)
    if not script or script.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="剧本不存在")
    updated = await service.update(script_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=ScriptResponse.model_validate(updated), message="更新成功")


# === 场景 ===
@router.post("/scenes", response_model=ApiResponse[SceneResponse])
async def create_scene(
    payload: SceneCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SceneService(db)
    scene = await service.create(payload.model_dump())
    return ApiResponse.success(data=SceneResponse.model_validate(scene), message="创建成功")


@router.get("/{script_id}/scenes", response_model=ApiResponse[list[SceneResponse]])
async def list_scenes(
    script_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = SceneService(db)
    items = await service.list_by_script(script_id)
    return ApiResponse.success(data=[SceneResponse.model_validate(s) for s in items])


# === 对话 ===
@router.post("/dialogues", response_model=ApiResponse[DialogueResponse])
async def create_dialogue(
    payload: DialogueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = DialogueService(db)
    dialogue = await service.create(payload.model_dump())
    return ApiResponse.success(data=DialogueResponse.model_validate(dialogue), message="创建成功")
