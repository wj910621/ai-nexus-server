"""LocalTrainingEngine — 本地 peft + diffusers 训练

Phase 8 P3: LoRA 训练 UI
"""
import logging
from pathlib import Path
from typing import Awaitable, Callable

from app.core.device_manager import DeviceManager
from app.engines.training.base import TrainingEngine, TrainingParams, TrainingResult

logger = logging.getLogger(__name__)


def _check_peft_installed() -> bool:
    """检查 peft 是否安装"""
    try:
        import peft  # noqa: F401
        return True
    except ImportError:
        return False


class LocalTrainingEngine(TrainingEngine):
    """本地训练引擎（peft + diffusers）"""

    def check_available(self) -> tuple[bool, str]:
        """检查本地训练是否可用"""
        dm = DeviceManager.get_instance()
        gpu = dm.get_gpu_info()
        if gpu is None or gpu.vram_gb < 8:
            vram = gpu.vram_gb if gpu else 0.0
            return False, f"VRAM 不足: {vram}GB < 8GB (SDXL LoRA 最低要求)"
        if not _check_peft_installed():
            return False, "peft 未安装，请安装 peft>=0.10.0"
        return False, "本地 LoRA 训练尚未完成生产实现，请使用 replicate 云端训练"

    async def train(
        self,
        dataset_path: str,
        output_dir: str,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> TrainingResult:
        """执行本地训练"""
        raise RuntimeError(
            "本地 LoRA 训练尚未完成生产实现，已阻止生成无效 adapter；"
            "请使用 replicate 云端训练"
        )

        # The implementation below is retained as development scaffolding and
        # is intentionally unreachable until a real optimization/data-loading
        # loop and artifact validation are implemented.
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        adapter_path = output_path / "adapter.safetensors"

        # 阶段 1: 加载模型
        await progress_callback(5, "加载 SDXL 基模...")

        # 阶段 2: 训练循环
        metrics = await self._run_training_loop(
            dataset_path, output_path, params, progress_callback,
        )

        # 阶段 3: 保存 LoRA
        await progress_callback(95, "保存 LoRA adapter...")
        if not adapter_path.exists():
            # _run_training_loop 应已写入，这里兜底
            adapter_path.write_bytes(b"")

        await progress_callback(100, "训练完成")

        return TrainingResult(
            adapter_path=str(adapter_path),
            metrics=metrics,
        )

    async def _run_training_loop(
        self,
        dataset_path: str,
        output_dir: Path,
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> dict:
        """实际训练循环（peft + diffusers）

        生产实现参考 diffusers 的 train_dreambooth_lora_sdxl.py 核心逻辑。
        此处为可 mock 的独立方法，便于测试。
        """
        # 1. 加载 SDXL base pipeline（通过 ModelManager 复用缓存）
        # 2. 构造 dataset（datasets.load_dataset 图片+caption）
        # 3. 配置 peft LoraConfig (rank=params.rank)
        # 4. diffusers 训练循环
        # 5. 每 50 步调用 progress_callback
        # 6. 保存 adapter.safetensors 到 output_dir
        try:
            import torch
            from diffusers import StableDiffusionXLPipeline
            from peft import LoraConfig
        except ImportError as e:
            raise RuntimeError(f"训练依赖缺失: {e}")

        dm = DeviceManager.get_instance()
        device = dm.get_device_string("image")

        # 加载基模
        pipeline = StableDiffusionXLPipeline.from_pretrained(
            params.base_model,
            torch_dtype=torch.float16,
        ).to(device)

        # 配置 LoRA
        lora_config = LoraConfig(
            r=params.rank,
            lora_alpha=params.rank * 2,
            target_modules=["to_q", "to_k", "to_v", "to_out.0"],
            lora_dropout=0.05,
        )
        pipeline.unet.add_adapter(lora_config)

        # 训练循环（简化版，生产环境需完整实现）
        torch.optim.AdamW(
            pipeline.unet.parameters(),
            lr=params.learning_rate,
        )

        total_steps = params.max_train_steps
        for step in range(total_steps):
            # ... 实际训练步骤 ...
            if step % 50 == 0:
                progress = int((step / total_steps) * 90) + 5  # 5-95
                await progress_callback(
                    progress, f"训练中 {step}/{total_steps}"
                )

        # 保存 adapter
        pipeline.unet.save_attn_procs(str(output_dir))

        return {
            "final_loss": 0.1,  # 实际应记录最终 loss
            "steps": total_steps,
            "train_time_sec": 1800,
        }
