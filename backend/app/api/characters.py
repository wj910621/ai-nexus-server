"""角色路由"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse, PaginatedData, PaginatedResponse
from app.models.user import User
from app.schemas.character import CharacterCreate, CharacterResponse, CharacterUpdate
from app.services.character_service import CharacterService

router = APIRouter(prefix="/characters", tags=["角色"])


@router.get("", response_model=PaginatedResponse[CharacterResponse])
async def list_characters(
    project_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取角色列表"""
    service = CharacterService(db)
    if project_id:
        items = await service.list_by_project(project_id)
        total = len(items)
    else:
        skip = (page - 1) * page_size
        items = await service.list_by_user(current_user.id, skip=skip, limit=page_size)
        total = await service.count(filters={"user_id": current_user.id})
    return PaginatedResponse(
        data=PaginatedData(
            items=[CharacterResponse.model_validate(c) for c in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("", response_model=ApiResponse[CharacterResponse])
async def create_character(
    payload: CharacterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建角色"""
    service = CharacterService(db)
    data = payload.model_dump()
    data["user_id"] = current_user.id
    character = await service.create(data)
    return ApiResponse.success(data=CharacterResponse.model_validate(character), message="创建成功")


@router.get("/{character_id}", response_model=ApiResponse[CharacterResponse])
async def get_character(
    character_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CharacterService(db)
    character = await service.get_by_id(character_id)
    if not character or character.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    return ApiResponse.success(data=CharacterResponse.model_validate(character))


@router.put("/{character_id}", response_model=ApiResponse[CharacterResponse])
async def update_character(
    character_id: UUID,
    payload: CharacterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CharacterService(db)
    character = await service.get_by_id(character_id)
    if not character or character.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    updated = await service.update(character_id, payload.model_dump(exclude_unset=True))
    return ApiResponse.success(data=CharacterResponse.model_validate(updated), message="更新成功")


@router.delete("/{character_id}", response_model=ApiResponse)
async def delete_character(
    character_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = CharacterService(db)
    character = await service.get_by_id(character_id)
    if not character or character.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="角色不存在")
    await service.delete(character_id, soft=True)
    return ApiResponse.success(message="删除成功")
