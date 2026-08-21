"""数据集 API 路由

Phase 8 P3: LoRA 训练 UI
"""
import io
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db
from app.core.response import ApiResponse
from app.core.storage import storage
from app.engines.training.caption import CaptionGenerator
from app.models.user import User
from app.schemas.training_dataset import (
    CaptionUpdate,
    DatasetCreate,
    DatasetItemResponse,
    DatasetResponse,
)
from app.services.dataset_service import DatasetService

router = APIRouter(tags=["数据集"])


@router.post("/datasets", response_model=ApiResponse[DatasetResponse])
async def create_dataset(
    payload: DatasetCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建数据集"""
    svc = DatasetService(db)
    if not await svc.owns_character(payload.character_id, str(current_user.id)):
        raise HTTPException(status_code=404, detail="角色不存在")
    ds = await svc.create(
        character_id=payload.character_id,
        user_id=str(current_user.id),
        name=payload.name,
        caption_mode=payload.caption_mode,
        trigger_word=payload.trigger_word,
    )
    return ApiResponse.success(data=DatasetResponse.model_validate(ds), message="数据集创建成功")


@router.get("/datasets/{dataset_id}", response_model=ApiResponse[DatasetResponse])
async def get_dataset(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取数据集详情"""
    svc = DatasetService(db)
    ds = await svc.get_by_id(dataset_id, user_id=str(current_user.id))
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")
    return ApiResponse.success(data=DatasetResponse.model_validate(ds))


@router.post("/datasets/{dataset_id}/images", response_model=ApiResponse[DatasetItemResponse])
async def upload_image(
    dataset_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """上传图片到数据集

    A4: 文件上传安全 - 类型/大小/magic bytes 校验 + 文件名净化。
    """
    svc = DatasetService(db)
    ds = await svc.get_by_id(dataset_id, user_id=str(current_user.id))
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")

    # A4: 上传安全校验（扩展名/MIME/大小/magic bytes），返回净化后的 bytes
    from app.core.upload_security import validate_upload
    data = await validate_upload(file)

    # Use an opaque storage name so retries for an old deletion can never
    # collide with a later upload that reused the same client filename.
    from uuid import uuid4
    extension = (file.filename or "image.png").rsplit(".", 1)[-1].lower()
    storage_filename = f"{uuid4().hex}.{extension}"

    # 获取图片尺寸
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(data))
        width, height = img.size
    except Exception:
        width, height = None, None

    # 保存文件
    image_path = storage.save(
        data=data,
        filename=storage_filename,
        subdir=f"datasets/{dataset_id}",
        extension=extension,
    )

    # 创建条目
    item = await svc.add_image(
        dataset_id=dataset_id,
        image_path=image_path,
        width=width,
        height=height,
    )
    return ApiResponse.success(data=DatasetItemResponse.model_validate(item), message="上传成功")


@router.post(
    "/datasets/{dataset_id}/images/{item_id}/caption",
    response_model=ApiResponse[DatasetItemResponse],
)
async def update_caption(
    dataset_id: str,
    item_id: str,
    payload: CaptionUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新单张图片 caption"""
    svc = DatasetService(db)
    item = await svc.update_caption(
        dataset_id=dataset_id,
        item_id=item_id,
        user_id=str(current_user.id),
        caption=payload.caption,
        source="manual",
    )
    if not item:
        raise HTTPException(status_code=404, detail="条目不存在")
    return ApiResponse.success(data=DatasetItemResponse.model_validate(item))


@router.post("/datasets/{dataset_id}/auto-caption", response_model=ApiResponse[dict])
async def auto_caption(
    dataset_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """批量自动生成 caption"""
    svc = DatasetService(db)
    ds = await svc.get_by_id(dataset_id, user_id=str(current_user.id))
    if not ds:
        raise HTTPException(status_code=404, detail="数据集不存在")

    # 收集需要 caption 的图片
    items = [i for i in ds.items if i.caption_source != "manual"]
    if not items:
        return ApiResponse.success(data={"count": 0}, message="无待处理图片")

    # 生成 caption
    cg = CaptionGenerator()
    image_paths = [
        str(storage.get_full_path(i.image_path)) for i in items
    ]
    captions = await cg.batch_generate(image_paths, trigger_word=ds.trigger_word)

    # 更新条目
    for item, caption in zip(items, captions):
        await svc.update_caption(
            dataset_id=dataset_id,
            item_id=item.id,
            user_id=str(current_user.id),
            caption=caption,
            source="auto",
        )

    return ApiResponse.success(
        data={"count": len(captions)},
        message=f"已生成 {len(captions)} 条 caption",
    )


@router.delete("/datasets/{dataset_id}/images/{item_id}", response_model=ApiResponse[dict])
async def delete_image(
    dataset_id: str,
    item_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除数据集图片"""
    svc = DatasetService(db)
    deletion = await svc.delete_image(
        dataset_id=dataset_id,
        item_id=item_id,
        user_id=str(current_user.id),
    )
    if deletion is None:
        raise HTTPException(status_code=404, detail="条目不存在")
    item, cleanup_id = deletion
    try:
        storage.delete(item.image_path)
        await svc.complete_storage_deletion(cleanup_id)
    except (OSError, ValueError) as exc:
        await svc.record_storage_deletion_failure(cleanup_id, str(exc))
    return ApiResponse.success(data={"deleted": item_id})


@router.get(
    "/characters/{character_id}/datasets",
    response_model=ApiResponse[List[DatasetResponse]],
)
async def list_character_datasets(
    character_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取角色的数据集列表"""
    svc = DatasetService(db)
    datasets = await svc.list_by_character(
        character_id=character_id,
        user_id=str(current_user.id),
    )
    return ApiResponse.success(
        data=[DatasetResponse.model_validate(ds) for ds in datasets],
    )
