"""Pollinations.ai 免费图像生成 Provider

文档：https://pollinations.ai
- 无需 API Key
- 支持 text2img
- 支持多种模型（flux, turbo 等）
- 限流：每分钟约 50 次
"""
from typing import Optional
from urllib.parse import quote

import httpx

from app.core.http_client import http_client_factory
from app.core.storage import storage
from app.engines.base import GenerationResult, ImageGenProvider


class PollinationsProvider(ImageGenProvider):
    """Pollinations.ai 免费图像生成"""

    name = "pollinations"
    display_name = "Pollinations.ai (免费)"

    BASE_URL = "https://image.pollinations.ai/prompt"
    # Host-only base URL for the shared HTTP/2 client (Task 11).
    CLIENT_BASE_URL = "https://image.pollinations.ai"
    AVAILABLE_MODELS = ["flux", "turbo", "flux-realism", "flux-anime", "flux-3d"]

    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self._initialized = False
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self) -> None:
        """初始化 HTTP 客户端 (Task 11: 共享 HTTP/2 client)"""
        self.client = http_client_factory.get_client(
            self.CLIENT_BASE_URL,
            timeout=self.timeout,
        )
        self._initialized = True

    async def health_check(self) -> bool:
        """健康检查 - 简单测试连接"""
        try:
            if not self.client:
                await self.initialize()
            # 简单测试：请求一个 1x1 图像
            resp = await self.client.get(
                f"{self.BASE_URL}/test",
                params={"width": 1, "height": 1, "nologo": "true"},
            )
            return resp.status_code == 200
        except Exception:
            return False

    async def text2img(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        model: str = "flux",
        nologo: bool = True,
        enhance: bool = False,
        **kwargs,
    ) -> GenerationResult:
        """
        文生图

        Args:
            prompt: 正向提示词
            negative_prompt: 负向提示词（Pollinations 通过 prompt 前缀模拟）
            width: 宽度
            height: 高度
            seed: 随机种子
            model: 模型 (flux, turbo, flux-realism, flux-anime, flux-3d)
            nologo: 是否移除 logo
            enhance: 是否增强提示词
        """
        if not self.client:
            await self.initialize()

        import time
        start_time = time.time()

        # 构造完整 prompt（Pollinations 不支持 negative_prompt，通过前缀模拟）
        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt}. Avoid: {negative_prompt}"

        params = {
            "width": width,
            "height": height,
            "model": model,
            "nologo": "true" if nologo else "false",
            "enhance": "true" if enhance else "false",
        }
        if seed is not None:
            params["seed"] = seed

        try:
            # URL 编码 prompt
            url = f"{self.BASE_URL}/{quote(full_prompt)}"

            resp = await self.client.get(url, params=params)
            resp.raise_for_status()

            image_bytes = resp.content
            elapsed = time.time() - start_time

            # 保存到存储
            url_path = storage.save(image_bytes, extension="png", subdir="images")

            return GenerationResult(
                success=True,
                data=url_path,
                content_type="image/png",
                metadata={
                    "provider": self.name,
                    "model": model,
                    "width": width,
                    "height": height,
                    "seed": seed,
                    "elapsed_seconds": round(elapsed, 2),
                },
            )
        except httpx.HTTPStatusError as e:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error=f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                data=b"",
                content_type="",
                metadata={},
                error=f"{type(e).__name__}: {str(e)}",
            )

    def get_info(self) -> dict:
        """获取引擎信息"""
        info = super().get_info()
        info["available_models"] = self.AVAILABLE_MODELS
        info["default_model"] = "flux"
        return info


# 商业化瘦身（2026-09-02）：默认图像引擎补注册进 ProviderRegistry，
# 使 ProviderRouter / get_engine_routed 能路由到 pollinations（免费默认）。
from app.engines.registry import provider_registry  # noqa: E402

provider_registry.register("image", "pollinations", PollinationsProvider)
