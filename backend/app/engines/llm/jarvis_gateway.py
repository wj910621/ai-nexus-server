"""YNEX/Jarvis OpenAI-compatible service-to-service LLM provider."""
from app.core.config import settings
from app.engines.llm.deepseek import DeepSeekProvider


class JarvisGatewayProvider(DeepSeekProvider):
    """Routes LLM requests through Jarvis without sharing databases or user JWTs."""

    name = "jarvis-gateway"
    display_name = "YNEX AI Gateway"
    is_local = False

    def __init__(self) -> None:
        base_url = settings.jarvis_gateway_base_url.rstrip("/")
        if base_url.endswith("/v1"):
            base_url = base_url[:-3]
        super().__init__(
            api_key=settings.jarvis_gateway_service_token,
            api_base=base_url,
            timeout=settings.jarvis_gateway_timeout_seconds,
        )
        # 主站 /v1/chat/completions 服务间认证:必须携带 x-internal-token(本机/内网 IP 白名单)
        self._extra_headers = {
            "x-internal-token": settings.jarvis_gateway_service_token,
        }
        self.DEFAULT_MODEL = settings.jarvis_gateway_default_model
        self.AVAILABLE_MODELS = [self.DEFAULT_MODEL] if self.DEFAULT_MODEL else []

    async def chat(self, messages: list[dict], model: str = "", **kwargs):
        selected_model = model or self.DEFAULT_MODEL
        if not selected_model:
            from app.engines.base import GenerationResult
            return GenerationResult(
                success=False,
                data="",
                content_type="text/plain",
                metadata={},
                error="Jarvis gateway default model is not configured",
            )
        return await super().chat(messages=messages, model=selected_model, **kwargs)


try:
    from app.engines.registry import provider_registry
    provider_registry.register("llm", "jarvis-gateway", JarvisGatewayProvider)
except Exception:
    pass
