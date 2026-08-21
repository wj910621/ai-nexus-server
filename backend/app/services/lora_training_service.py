"""LoraTrainingService — LoRA 训练任务服务

Phase 8 P3: LoRA 训练 UI

注册为 TaskService 的 lora_train handler，协调 TrainingEngine 执行训练。
"""
import logging
from datetime import datetime
from typing import Optional

from app.core.storage import storage
from app.engines.training import TrainingEngineProvider
from app.engines.training.base import TrainingParams
from app.services.character_service import CharacterService
from app.services.task_service import task_service

logger = logging.getLogger(__name__)


class LoraTrainingService:
    """LoRA 训练服务

    使用方式：
        svc = LoraTrainingService()  # 自动注册到 task_service
        # 之后通过 task_service.submit(db, user_id, "lora_train", payload) 提交
    """

    def __init__(self):
        task_service.register_handler("lora_train", self._handle_train_task)

    async def _handle_train_task(self, task, db):
        """处理 lora_train 任务（由 TaskService 调用）

        Args:
            task: BackgroundTask 实例
            db: AsyncSession

        Returns:
            dict 训练结果（写入 BackgroundTask.result）
        """
        payload = task.payload
        character_id = payload["character_id"]
        dataset_id = payload["dataset_id"]

        # 更新 Character 状态为 training
        char_svc = CharacterService(db)
        character = await char_svc.get_by_id(character_id)
        if character is None:
            raise ValueError(f"Character not found: {character_id}")

        await char_svc.update(character_id, {
            "lora_training_status": "training",
        })

        try:
            # 选择引擎
            engine = TrainingEngineProvider.select(payload["location"])

            # 构建参数
            params = self._build_params(payload)

            # 准备路径
            dataset_path = self._get_dataset_image_dir(dataset_id)
            output_dir = self._get_output_dir(character_id)

            # 执行训练
            result = await engine.train(
                dataset_path=dataset_path,
                output_dir=output_dir,
                params=params,
                progress_callback=lambda p, m: task_service.update_progress(
                    db, task.id, p, m,
                ),
            )

            # 更新 Character
            await char_svc.update(character_id, {
                "lora_model_path": result.adapter_path,
                "lora_training_status": "ready",
            })

            return {
                "adapter_path": result.adapter_path,
                "metrics": result.metrics,
            }

        except Exception:
            # 训练失败，更新 Character 状态
            await char_svc.update(character_id, {
                "lora_training_status": "failed",
            })
            raise

    def _build_params(self, payload: dict) -> TrainingParams:
        """从任务 payload 构建训练参数"""
        preset = payload.get("preset", "standard")
        trigger_word = payload.get("trigger_word", "")

        params = TrainingParams.from_preset(preset, trigger_word=trigger_word)

        # 高级参数覆盖
        advanced = payload.get("advanced")
        if advanced:
            if "rank" in advanced:
                params.rank = advanced["rank"]
            if "learning_rate" in advanced:
                params.learning_rate = advanced["learning_rate"]
            if "max_train_steps" in advanced:
                params.max_train_steps = advanced["max_train_steps"]
            if "batch_size" in advanced:
                params.batch_size = advanced["batch_size"]
            if "gradient_accumulation" in advanced:
                params.gradient_accumulation = advanced["gradient_accumulation"]

        return params

    def _get_dataset_image_dir(self, dataset_id: str) -> str:
        """获取数据集图片目录路径"""
        return str(storage.get_full_path(f"/uploads/datasets/{dataset_id}") / "images")

    def _get_output_dir(self, character_id: str) -> str:
        """获取 LoRA 产物输出目录"""
        date_str = datetime.now().strftime("%Y%m%d")
        return str(storage.get_full_path(
            f"/uploads/lora_adapters/{character_id}/{date_str}"
        ))


# 模块级单例（延迟初始化，避免循环导入）
_lora_training_service: Optional[LoraTrainingService] = None


def get_lora_training_service() -> LoraTrainingService:
    """获取 LoraTrainingService 单例"""
    global _lora_training_service
    if _lora_training_service is None:
        _lora_training_service = LoraTrainingService()
    return _lora_training_service
