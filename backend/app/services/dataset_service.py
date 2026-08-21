"""DatasetService — 数据集 CRUD 服务

Phase 8 P3: LoRA 训练 UI
"""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.character import Character
from app.models.storage_cleanup import PendingStorageDeletion
from app.models.training_dataset import DatasetItem, TrainingDataset

logger = logging.getLogger(__name__)


class DatasetService:
    """数据集服务"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def owns_character(self, character_id: str, user_id: str) -> bool:
        """检查角色是否属于用户，并排除已软删除记录。"""
        result = await self.db.execute(
            select(Character.id).where(
                Character.id == character_id,
                Character.user_id == user_id,
                Character.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(
        self,
        character_id: str,
        user_id: str,
        name: str,
        caption_mode: str = "auto",
        trigger_word: str = "",
    ) -> TrainingDataset:
        """创建数据集"""
        ds = TrainingDataset(
            character_id=character_id,
            user_id=user_id,
            name=name,
            status="drafting",
            image_count=0,
            caption_mode=caption_mode,
            trigger_word=trigger_word,
        )
        self.db.add(ds)
        await self.db.commit()
        await self.db.refresh(ds)
        return ds

    async def get_by_id(
        self, dataset_id: str, user_id: str | None = None
    ) -> Optional[TrainingDataset]:
        """按 ID 获取数据集，可选地强制限定所有者。"""
        filters = [TrainingDataset.id == dataset_id]
        if user_id is not None:
            filters.append(TrainingDataset.user_id == str(user_id))
        result = await self.db.execute(
            select(TrainingDataset)
            .where(*filters)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def list_by_character(
        self, character_id: str, user_id: str
    ) -> List[TrainingDataset]:
        """列出当前用户在指定角色下的数据集。"""
        result = await self.db.execute(
            select(TrainingDataset)
            .where(
                TrainingDataset.character_id == character_id,
                TrainingDataset.user_id == str(user_id),
            )
            .order_by(TrainingDataset.created_at.desc())
        )
        return list(result.scalars().all())

    async def add_image(
        self,
        dataset_id: str,
        image_path: str,
        width: Optional[int] = None,
        height: Optional[int] = None,
    ) -> DatasetItem:
        """添加图片到数据集"""
        item = DatasetItem(
            dataset_id=dataset_id,
            image_path=image_path,
            caption="",
            caption_source="manual",
            width=width,
            height=height,
        )
        self.db.add(item)

        # 更新数据集 image_count
        await self.db.execute(
            update(TrainingDataset)
            .where(TrainingDataset.id == dataset_id)
            .values(image_count=TrainingDataset.image_count + 1)
        )
        await self.db.commit()
        await self.db.refresh(item)
        return item

    async def update_caption(
        self,
        dataset_id: str,
        item_id: str,
        user_id: str,
        caption: str,
        source: str = "manual",
    ) -> Optional[DatasetItem]:
        """仅更新属于当前用户及指定数据集的条目 caption。"""
        result = await self.db.execute(
            update(DatasetItem)
            .where(
                DatasetItem.id == item_id,
                DatasetItem.dataset_id == dataset_id,
                DatasetItem.dataset_id.in_(
                    select(TrainingDataset.id).where(
                        TrainingDataset.user_id == str(user_id)
                    )
                ),
            )
            .values(caption=caption, caption_source=source)
        )
        if result.rowcount == 0:
            await self.db.rollback()
            return None
        await self.db.commit()

        result = await self.db.execute(
            select(DatasetItem).where(DatasetItem.id == item_id)
        )
        return result.scalar_one_or_none()

    async def delete_image(
        self, dataset_id: str, item_id: str, user_id: str
    ) -> Optional[tuple[DatasetItem, str]]:
        """Delete the DB item and enqueue its file deletion atomically."""
        item_result = await self.db.execute(
            select(DatasetItem).where(
                DatasetItem.id == item_id,
                DatasetItem.dataset_id == dataset_id,
                DatasetItem.dataset_id.in_(
                    select(TrainingDataset.id).where(
                        TrainingDataset.user_id == str(user_id)
                    )
                ),
            )
        )
        item = item_result.scalar_one_or_none()
        if item is None:
            return None

        cleanup = PendingStorageDeletion(path=item.image_path)
        self.db.add(cleanup)
        await self.db.execute(delete(DatasetItem).where(DatasetItem.id == item_id))
        await self.db.execute(
            update(TrainingDataset)
            .where(TrainingDataset.id == dataset_id)
            .values(image_count=TrainingDataset.image_count - 1)
        )
        await self.db.commit()
        await self.db.refresh(cleanup)
        return item, str(cleanup.id)

    async def complete_storage_deletion(self, cleanup_id: str) -> None:
        """Remove an outbox record after the file was deleted successfully."""
        await self.db.execute(
            delete(PendingStorageDeletion).where(
                PendingStorageDeletion.id == UUID(cleanup_id)
            )
        )
        await self.db.commit()

    async def record_storage_deletion_failure(
        self, cleanup_id: str, error: str
    ) -> None:
        """Retain a failed deletion for startup retry without failing the API."""
        await self.db.execute(
            update(PendingStorageDeletion)
            .where(PendingStorageDeletion.id == UUID(cleanup_id))
            .values(
                attempts=PendingStorageDeletion.attempts + 1,
                last_error=error[:2000],
            )
        )
        await self.db.commit()

    async def update_status(self, dataset_id: str, status: str) -> None:
        """更新数据集状态"""
        await self.db.execute(
            update(TrainingDataset)
            .where(TrainingDataset.id == dataset_id)
            .values(status=status)
        )
        await self.db.commit()
