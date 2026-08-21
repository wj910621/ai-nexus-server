"""ReplicateTrainingEngine — 云端 Replicate API 训练

Phase 8 P3: LoRA 训练 UI
"""
import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable

from app.core.config import settings
from app.engines.training.base import TrainingEngine, TrainingParams, TrainingResult

logger = logging.getLogger(__name__)

# 轮询间隔（秒）
POLL_INTERVAL = 5
# 超时（秒）= 30 分钟
POLL_TIMEOUT = 1800


class ReplicateTrainingEngine(TrainingEngine):
    """Replicate 云端训练引擎"""

    def check_available(self) -> tuple[bool, str]:
        # 方法内导入 settings，避免 test_database_fallback.py 的 importlib.reload(config)
        # 替换全局 settings 实例后，模块级旧引用失效导致 patch 失效的问题。
        from app.core.config import settings
        if not settings.replicate_api_token:
            return False, "Replicate API token 未配置"
        return True, "ok"

    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> TrainingResult:
        """执行云端训练"""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 阶段 1: 上传数据集图片
        await progress_callback(5, "上传数据集到 Replicate...")
        images = self._collect_images(dataset_path)
        prediction_id = await self._submit_prediction(images, params)

        # 阶段 2: 轮询训练进度
        await progress_callback(10, f"云端训练已提交 (ID: {prediction_id})")
        result = await self._poll_until_complete(prediction_id, progress_callback)

        # 阶段 3: 下载产物
        await progress_callback(95, "下载 LoRA adapter...")
        adapter_path = await self._download_adapter(
            result["output_url"], output_path,
        )

        await progress_callback(100, "训练完成")

        return TrainingResult(
            adapter_path=adapter_path,
            metrics={
                "prediction_id": prediction_id,
                "status": result["status"],
            },
        )

    def _collect_images(self, dataset_path: str) -> list[str]:
        """收集数据集目录下的图片路径"""
        path = Path(dataset_path)
        extensions = {".png", ".jpg", ".jpeg", ".webp"}
        return [
            str(p) for p in path.iterdir()
            if p.suffix.lower() in extensions
        ]

    async def _submit_prediction(
        self, images: list[str], params: TrainingParams,
    ) -> str:
        """提交训练 prediction 到 Replicate

        生产实现使用 replicate SDK:
            import replicate
            output = replicate.predictions.create(
                model=settings.replicate_train_model,
                input={"images": images, "trigger_word": params.trigger_word, ...},
            )
        """
        try:
            import replicate
        except ImportError:
            raise RuntimeError("replicate SDK 未安装，请安装 replicate>=0.25.0")

        output = replicate.predictions.create(
            model=settings.replicate_train_model,
            input={
                "images": images,
                "trigger_word": params.trigger_word,
                "rank": params.rank,
                "learning_rate": params.learning_rate,
                "max_train_steps": params.max_train_steps,
            },
        )
        return output.id

    async def _poll_until_complete(
        self,
        prediction_id: str,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> dict:
        """轮询 prediction 状态直到完成或超时"""
        elapsed = 0
        while elapsed < POLL_TIMEOUT:
            try:
                import replicate
            except ImportError:
                raise RuntimeError("replicate SDK 未安装")

            pred = replicate.predictions.get(prediction_id)
            if pred.status == "succeeded":
                return {"status": "succeeded", "output_url": pred.output}
            if pred.status == "failed":
                raise RuntimeError(f"Replicate prediction failed: {pred.error}")

            # 进度映射：10-90
            progress = 10 + int(elapsed / POLL_TIMEOUT * 80)
            await progress_callback(progress, f"云端训练中 ({pred.status})")

            await asyncio.sleep(POLL_INTERVAL)
            elapsed += POLL_INTERVAL

        raise RuntimeError(
            f"Replicate prediction timed out after {POLL_TIMEOUT}s"
        )

    async def _download_adapter(self, url: str, dest_dir: Path) -> str:
        """下载训练产物到本地"""
        import aiohttp
        adapter_path = dest_dir / "adapter.safetensors"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                resp.raise_for_status()
                adapter_path.write_bytes(await resp.read())
        return str(adapter_path)
