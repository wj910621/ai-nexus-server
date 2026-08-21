"""软一致性 Provider - LLM 提示词增强 + 相同 Seed 锁定

设计理念：
- 沙盒环境无 GPU，无法运行真正的 IP-Adapter/LoRA
- 通过 LLM 提示词增强（如 DeepSeek）+ 相同 seed 实现角色一致性
- 同一角色使用同一 seed，保证多次生成保持视觉特征
- 无需 GPU，零成本方案

适用场景：
- 角色一致性要求中等的漫画/漫剧生成
- 快速原型开发与测试
- 无 GPU 部署环境
"""
import hashlib
import time
from typing import Optional

from app.engines.base import CharacterConsistencyProvider, GenerationResult


class SoftConsistencyProvider(CharacterConsistencyProvider):
    """软一致性 Provider

    通过 LLM 提示词增强 + Seed 锁定实现角色一致性，无需 GPU。
    """

    name = "soft-consistency"
    display_name = "软一致性 (LLM提示词增强 + Seed锁定)"

    def __init__(
        self,
        image_provider=None,
        llm_provider=None,
        consistency_seed: int = 42,
    ):
        """
        初始化软一致性 Provider

        Args:
            image_provider: 图像生成 Provider 实例（默认 None，使用时延迟创建 PollinationsProvider）
            llm_provider: LLM Provider 实例（默认 None，使用时延迟创建 DeepSeekProvider）
            consistency_seed: 默认种子 42，相同角色使用相同 seed 保证一致性
        """
        self.image_provider = image_provider
        self.llm_provider = llm_provider
        self.consistency_seed = consistency_seed
        self._initialized = False

    async def initialize(self) -> None:
        """初始化 - 延迟创建 image_provider 和 llm_provider（如果未提供）

        - image_provider 为 None 时创建 PollinationsProvider 并 initialize
        - llm_provider 为 None 时创建 DeepSeekProvider 并 initialize（不强制要求 api_key，可降级）
        """
        if self.image_provider is None:
            from app.engines.image.pollinations import PollinationsProvider

            self.image_provider = PollinationsProvider()
            await self.image_provider.initialize()

        if self.llm_provider is None:
            from app.engines.llm.deepseek import DeepSeekProvider

            self.llm_provider = DeepSeekProvider()
            await self.llm_provider.initialize()  # 不强制要求 api_key，可降级

        self._initialized = True

    async def extract_features(self, image: bytes) -> list[float]:
        """提取角色特征向量（软方案：基于图像字节 hash 的伪特征向量）

        实现方式：sha256(image) → 转 int → 拆分为 64 个 float（每个 4 字节范围归一化到 [0, 1]）

        注意：这是简化方案，生产环境可替换为 CLIP 特征
        """
        if not image:
            return [0.0] * 64

        # sha256(image) → 转 int → 链式哈希累积 256 字节，拆分为 64 个 4 字节段
        current = hashlib.sha256(image).digest()
        all_bytes = bytearray()
        for _ in range(8):
            all_bytes.extend(current)
            current = hashlib.sha256(current).digest()

        # 256 字节拆分为 64 个 4 字节段，归一化到 [0, 1]
        features: list[float] = []
        max_val = float(2**32 - 1)
        for i in range(64):
            chunk = bytes(all_bytes[i * 4 : (i + 1) * 4])
            val = int.from_bytes(chunk, "big")
            features.append(val / max_val)
        return features

    async def _enhance_prompt(
        self,
        prompt: str,
        character_description: Optional[str] = None,
        mood: Optional[str] = None,
    ) -> str:
        """增强提示词

        如果有 llm_provider 且可用：使用 LLM 增强提示词
        - 系统消息："你是漫画提示词增强助手，根据用户提示词生成详细的画面描述，保持角色一致性。"
        - 用户消息：原 prompt + 角色描述 + 情绪
        - 调用 llm_provider.chat，temperature=0.5
        - 如果 LLM 失败，回退到规则增强

        如果无 LLM：使用规则增强
        - 拼接 prompt + character_description + mood 标签 + "masterpiece, best quality, detailed"

        Args:
            prompt: 原始提示词
            character_description: 角色描述（可选）
            mood: 情绪（可选）

        Returns:
            增强后的 prompt 字符串
        """
        if self.llm_provider is not None:
            try:
                system_message = (
                    "你是漫画提示词增强助手，根据用户提示词生成详细的画面描述，"
                    "保持角色一致性。"
                )
                user_content = prompt
                if character_description:
                    user_content += f"\n角色描述: {character_description}"
                if mood:
                    user_content += f"\n情绪: {mood}"

                messages = [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_content},
                ]

                result = await self.llm_provider.chat(
                    messages=messages,
                    temperature=0.5,
                )

                if result.success and result.data:
                    return result.data
                # LLM 失败，回退到规则增强
            except Exception:
                pass  # 回退到规则增强

        # 规则增强
        enhanced = prompt
        if character_description:
            enhanced += f", {character_description}"
        if mood:
            enhanced += f", {mood}"
        enhanced += ", masterpiece, best quality, detailed"
        return enhanced

    async def generate_consistent(
        self,
        prompt: str,
        reference_image: bytes,
        consistency_weight: float = 0.8,
        character_description: Optional[str] = None,
        mood: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        **kwargs,
    ) -> GenerationResult:
        """基于参考图生成一致性角色

        软一致性方案：
        1. 提取参考图特征（伪特征向量，仅记录）
        2. 增强提示词（LLM 或规则）
        3. 使用 consistency_seed 锁定相同角色
        4. 调用 image_provider.text2img 生成图像

        Args:
            prompt: 提示词
            reference_image: 参考图像字节
            consistency_weight: 一致性权重（软方案中实际不使用，仅记录到 metadata）
            character_description: 角色描述（可选）
            mood: 情绪（可选）
            width: 宽度
            height: 高度
            seed: 随机种子（如果为 None，使用 self.consistency_seed）
            **kwargs: 其他参数（传递给 image_provider.text2img）
        """
        start_time = time.time()

        # 验证 reference_image 非空
        if not reference_image:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={"provider": self.name},
                error="reference_image 不能为空",
            )

        # 使用 consistency_seed（如果 seed 参数为 None）
        effective_seed = seed if seed is not None else self.consistency_seed

        try:
            # 确保已初始化
            if not self._initialized:
                await self.initialize()

            # 提取参考图特征（软方案仅记录）
            features = await self.extract_features(reference_image)

            # 增强提示词
            enhanced_prompt = await self._enhance_prompt(
                prompt, character_description, mood
            )

            # 调用 image_provider.text2img 生成图像
            image_result = await self.image_provider.text2img(
                prompt=enhanced_prompt,
                width=width,
                height=height,
                seed=effective_seed,
                **kwargs,
            )

            elapsed = time.time() - start_time

            # 合并 image_provider 的 metadata，再添加/覆盖我们的字段
            merged_metadata = dict(image_result.metadata or {})
            merged_metadata.update(
                {
                    "provider": self.name,
                    "image_provider": getattr(self.image_provider, "name", "unknown"),
                    "consistency_seed": effective_seed,
                    "consistency_weight": consistency_weight,
                    "character_description_provided": character_description is not None,
                    "mood": mood,
                    "enhanced_prompt": enhanced_prompt,
                    "feature_vector_length": len(features),
                    "elapsed_seconds": round(elapsed, 2),
                }
            )

            if not image_result.success:
                return GenerationResult(
                    success=False,
                    data=image_result.data,
                    content_type=image_result.content_type,
                    metadata=merged_metadata,
                    error=image_result.error,
                )

            return GenerationResult(
                success=True,
                data=image_result.data,
                content_type="image/png",
                metadata=merged_metadata,
            )
        except Exception as e:
            elapsed = time.time() - start_time
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={
                    "provider": self.name,
                    "consistency_seed": effective_seed,
                    "elapsed_seconds": round(elapsed, 2),
                },
                error=f"{type(e).__name__}: {str(e)}",
            )

    async def health_check(self) -> bool:
        """健康检查

        - 检查 image_provider 是否可用（health_check）
        - 不强制要求 llm_provider（可降级）
        """
        try:
            if self.image_provider is None:
                return False
            return await self.image_provider.health_check()
        except Exception:
            return False

    def get_info(self) -> dict:
        """获取引擎信息"""
        info = super().get_info()
        info["strategy"] = "soft"
        info["requires_gpu"] = False
        info["supports_llm_enhancement"] = self.llm_provider is not None
        info["consistency_seed"] = self.consistency_seed
        return info
