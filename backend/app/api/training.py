"""训练 API 路由

Phase 8 P3: LoRA 训练 UI
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.models.user import User
from app.schemas.training import TrainRequest, TrainResponse, TrainStatusResponse
from app.services.character_service import CharacterService
from app.services.dataset_service import DatasetService
from app.services.lora_training_service import LoraTrainingService
from app.services.task_service import task_service

router = APIRouter(tags=["训练"])


@router.post("/characters/{character_id}/train", response_model=ApiResponse[TrainResponse])
async def submit_train(
    character_id: str,
    payload: TrainRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交 LoRA 训练任务"""
    # 确保训练服务已初始化（handler 已注册）
    LoraTrainingService()

    # 验证数据集
    ds_svc = DatasetService(db)
    dataset = await ds_svc.get_by_id(
        payload.dataset_id, user_id=str(current_user.id)
    )
    if not dataset:
        raise HTTPException(status_code=404, detail="数据集不存在")
    if dataset.status != "ready":
        raise HTTPException(
            status_code=400,
            detail=f"数据集状态为 {dataset.status}，需先完成 caption 准备",
        )

    # 构建任务 payload
    task_payload = {
        "dataset_id": payload.dataset_id,
        "character_id": character_id,
        "location": payload.location,
        "trigger_word": payload.trigger_word,
        "preset": payload.preset,
        "advanced": payload.advanced.model_dump() if payload.advanced else None,
    }

    # 提交任务
    task = await task_service.submit(
        db=db,
        user_id=str(current_user.id),
        task_type="lora_train",
        payload=task_payload,
    )

    return ApiResponse.success(
        data=TrainResponse(
            task_id=task.id,
            character_id=character_id,
            status=task.status,
        ),
        message="训练任务已提交",
    )


@router.get(
    "/characters/{character_id}/train/status",
    response_model=ApiResponse[TrainStatusResponse],
)
async def get_train_status(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """查询角色训练状态"""
    char_svc = CharacterService(db)
    character = await char_svc.get_by_id(character_id)
    if not character or str(character.user_id) != str(current_user.id):
        raise HTTPException(status_code=404, detail="角色不存在")

    status = character.lora_training_status or "none"

    # 如果正在训练，查询最新任务
    if status == "training":
        tasks = await task_service.list_by_user(
            db,
            user_id=str(current_user.id),
        )
        if tasks:
            task = tasks[0]
            return ApiResponse.success(
                data=TrainStatusResponse(
                    status="training",
                    progress=task.progress,
                    message=f"训练进度 {task.progress}%",
                    task_id=task.id,
                ),
            )

    # 非训练中状态
    progress = 100 if status == "ready" else 0
    return ApiResponse.success(
        data=TrainStatusResponse(
            status=status,
            progress=progress,
        ),
    )
