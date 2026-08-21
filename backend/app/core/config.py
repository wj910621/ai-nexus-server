"""应用配置 - 基于 Pydantic Settings"""
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类，从环境变量加载"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        protected_namespaces=("settings_",),
    )

    # 应用配置
    app_name: str = "Y·NEX Story Studio"
    app_env: str = "development"
    app_debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_secret_key: str = "change-me"

    # 数据库 (overridden to SQLite when desktop mode + no explicit DATABASE_URL)
    database_url: str = "postgresql+asyncpg://comic_user:comic_password@localhost:5432/comic_studio"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # MinIO
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False

    # JWT
    jwt_secret_key: str = "change-me-to-a-jwt-secret"
    jwt_algorithm: str = "HS256"
    # JWT (Task 7, CHANGED default)
    jwt_access_token_expire_minutes: int = 30  # was 1440
    # (refresh_token_expire_days already exists, kept at 7)
    jwt_refresh_token_expire_days: int = 7
    jwt_refresh_token_enabled: bool = True

    # Rate limiting (disabled in desktop mode)
    rate_limit_enabled: bool = True  # Master switch
    rate_limit_redis_url: str = ""  # Empty = use redis_url; "none" = force disable

    # WebSocket abuse protection (per process/connection).
    ws_max_connections_per_user: int = Field(default=5, ge=1, le=100)
    ws_max_subscriptions_per_connection: int = Field(default=20, ge=1, le=1000)
    ws_max_messages_per_minute: int = Field(default=120, ge=1, le=10000)
    ws_max_channel_length: int = Field(default=256, ge=16, le=2048)
    ws_max_message_bytes: int = Field(default=1_048_576, ge=1024, le=16_777_216)
    storage_cleanup_interval_seconds: int = Field(default=300, ge=10, le=86400)

    # Metadata cache (Task 1)
    cache_enabled: bool = True
    cache_ttl_default: int = 300  # 5 min
    cache_redis_url: str = ""  # Empty = use redis_url; "memory" = force in-memory
    cache_key_prefix: str = "cs:"
    cache_max_size_memory: int = 10000  # Max entries in TTLCache

    # Email (for verification and password reset)
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = "noreply@comicstudio.local"
    smtp_use_tls: bool = True

    # Stripe (payment)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_enabled: bool = False  # Master switch; mock provider when False
    # Commercial ledger owner: "jarvis" (shared YNEX account/credits) or
    # "standalone" (legacy independent Stripe deployment).
    billing_mode: str = "standalone"
    jarvis_billing_portal_url: str = "https://ynexai.cn/"
    # Commercial model work is fail-closed in production until an approved
    # Y.NEX price version is published by an operator.
    commercial_operations_enabled: bool = False

    # Admin
    admin_bootstrap_email: str = ""  # Email of initial admin user (set on first run)

    # CORS
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Async task engine (Task 2)
    max_concurrent_tasks: int = 4

    # Engine concurrency (Task 3)
    engine_max_concurrent_image: int = 5
    engine_max_concurrent_llm: int = 10
    engine_max_concurrent_tts: int = 8
    engine_max_concurrent_video: int = 2
    engine_max_concurrent_character: int = 3
    engine_acquire_timeout_seconds: int = 30

    # Observability (Task 4)
    sentry_dsn: str = ""  # Empty = disabled
    log_format: str = "text"  # text | json
    log_level: str = "INFO"
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
    access_log_enabled: bool = True

    # AI 模型
    model_cache_dir: str = "./ai-models"
    device: str = "cpu"

    # Migration (Task 6)
    run_migrations_on_startup: bool = True  # dev/desktop only; prod uses CLI

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"

    # YNEX/Jarvis internal AI gateway (OpenAI-compatible phase-1 integration)
    jarvis_gateway_enabled: bool = False
    jarvis_gateway_base_url: str = ""
    jarvis_gateway_service_token: str = ""
    jarvis_gateway_default_model: str = ""
    jarvis_gateway_timeout_seconds: int = Field(default=60, ge=5, le=300)

    # Y·NEX Story Studio shared identity / ledger bridge.  These are injected
    # only in the Story service environment; production startup rejects empty
    # values when billing_mode is jarvis.
    ynex_sso_secret: str = ""
    ynex_sso_issuer: str = "ynexai.cn"
    ynex_sso_audience: str = "story-studio"
    ynex_billing_base_url: str = ""
    ynex_billing_service_token: str = ""

    # Doubao (火山引擎 Ark API) - Task 14
    doubao_api_key: str = ""
    doubao_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"

    # Volcano TTS (火山引擎语音合成) - Task 18
    volcano_tts_api_key: str = ""
    volcano_tts_api_secret: str = ""
    volcano_tts_api_base: str = "https://openspeech.bytedance.com/api/v1"

    # GLM (ZhipuAI)
    glm_api_key: str = ""
    glm_api_base: str = "https://open.bigmodel.cn/api/paas/v4"

    # CDN settings (cloud only; desktop uses local file storage)
    cdn_provider: str = "none"  # "r2" | "qiniu" | "none"
    cdn_r2_account_id: str = ""
    cdn_r2_access_key: str = ""
    cdn_r2_secret_key: str = ""
    cdn_r2_bucket: str = ""
    cdn_r2_public_url: str = ""  # e.g. https://cdn.comicstudio.ai
    cdn_qiniu_access_key: str = ""
    cdn_qiniu_secret_key: str = ""
    cdn_qiniu_bucket: str = ""
    cdn_qiniu_domain: str = ""  # e.g. https://cdn.comicstudio.ai

    # Provider failover
    failover_enabled: bool = True
    failover_circuit_threshold: int = 5  # Consecutive failures to open circuit
    failover_circuit_reset_seconds: int = 60  # How long to stay open

    # Backup & alerting (Task 14)
    backup_dir: str = "/var/backups/comicstudio"
    backup_encryption_key: str = ""  # Fernet key (base64, 32 bytes); empty = ephemeral (dev only)
    uploads_dir: str = "uploads"
    alerting_webhook_url: str = ""  # Feishu/DingTalk webhook URL (Alertmanager target)

    # Local AI inference (desktop mode) — Task 15
    local_inference_enabled: bool = False  # Auto-enabled on desktop
    local_inference_device: str = "auto"  # "auto" | "gpu" | "cpu"
    local_model_dir: str = ""  # Default: ~/.comicstudio/models
    local_gpu_min_vram_gb: int = 6  # Min VRAM to use GPU
    local_cpu_min_ram_gb: int = 8  # Min RAM to use CPU ONNX
    local_diffusers_model: str = "stable-diffusion-xl-base-1.0"
    local_llm_model: str = "Qwen2.5-7B-Instruct-Q4_K_M"
    local_tts_model: str = "en_US-lessac-medium"

    # 14 个 Provider 配置 (Task 20 / Phase 8 P1)
    # 即梦 Volcano 通用（图像 / 视频）
    volcano_api_key: str = ""
    volcano_api_secret: str = ""
    volcano_api_base: str = "https://visual.volcengineapi.com"

    # 快手可灵视频 / 可图图像（共用 key）
    kling_api_key: str = ""
    kling_api_secret: str = ""
    kling_api_base: str = "https://api.kuaishou.com/kling"

    # 快手可图 Kolors 图像
    kolors_api_key: str = ""
    kolors_api_secret: str = ""
    kolors_api_base: str = "https://api.kuaishou.com/kolors"

    # 语义缓存 (Task 20 / Phase 8 P1)
    semantic_cache_enabled: bool = True
    semantic_cache_similarity_threshold: float = 0.90  # cosine similarity ≥ 0.90
    semantic_cache_ttl_seconds: int = 1800  # 30 分钟
    semantic_cache_max_entries_per_user: int = 1000
    semantic_cache_chroma_persist_dir: str = "./.chroma"
    semantic_cache_embedding_model: str = "BAAI/bge-m3"
    semantic_cache_min_max_tokens: int = 100  # max_tokens < 100 时不缓存

    # 订阅验证 (Task 20 / Phase 8 P1)
    subscription_jwt_secret: str = ""  # 空 = 使用 jwt_secret_key
    subscription_jwt_issuer: str = "comicstudio"
    subscription_offline_grace_days: int = 7
    subscription_hardware_profiles: str = "low,mid,high,cpu"  # 逗号分隔

    # 配额管理 (Task 20 / Phase 8 P1)
    quota_redis_url: str = ""  # 空 = 使用 redis_url
    quota_free_daily_limit: int = 10
    quota_pro_monthly_limit: int = 1000
    quota_enterprise_monthly_limit: int = 0  # 0 = 不限
    quota_skip_local: bool = True  # 本地 Provider 不计配额

    # 本地推理模型默认值 (Task 20 / Phase 8 P1)
    local_flux_model: str = "black-forest-labs/FLUX.1-dev"
    local_wan_model: str = "Wan-AI/Wan2.1-T2V-1.3B"
    local_hunyuan_model: str = "tencent/HunyuanVideo"
    local_cosyvoice_model: str = "FunAudioLLM/CosyVoice-300M"
    local_vllm_gpu_memory_utilization: float = 0.85
    local_vllm_max_model_len: int = 8192

    # Phase 8 P2: 基准测试 + llama_cpp 配置
    benchmark_enabled: bool = True           # 是否启用基准测试
    benchmark_cache_ttl: int = 3600          # 基准结果缓存时长（秒）
    llama_cpp_model_path: str = ""            # GGUF 模型路径（空=使用默认）
    llama_cpp_n_gpu_layers: int = -1          # GPU 层数（-1=全部，0=纯 CPU）

    # Phase 8 P3: LoRA 训练配置
    replicate_api_token: str = ""          # Replicate API token（云端训练）
    replicate_train_model: str = ""        # Replicate 上托管的训练模型 ID
    lora_train_local_enabled: bool = True  # 是否启用本地训练
    lora_train_cloud_enabled: bool = True  # 是否启用云端训练
    blip_model_name: str = "Salesforce/blip-image-captioning-large"  # 自动 caption 模型

    # Phase 8 P4: K8s 容器化 - 阿里云 OSS 对象存储
    oss_enabled: bool = False                # 是否启用 OSS（生产环境）
    oss_bucket: str = ""                     # OSS bucket 名称
    oss_access_key_id: str = ""              # OSS AccessKey ID
    oss_access_key_secret: str = ""          # OSS AccessKey Secret
    oss_endpoint: str = ""                   # OSS endpoint，如 oss-cn-hangzhou.aliyuncs.com

    @field_validator("cors_origins")
    @classmethod
    def parse_cors_origins(cls, v: str) -> str:
        """保留原始字符串，通过属性访问解析后的列表"""
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """获取 CORS 来源列表"""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"


# 全局配置单例
def _build_settings() -> "Settings":
    """Build settings, applying desktop-mode overrides if CS_DESKTOP_MODE=1."""
    import os
    s = Settings()
    if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
        # In desktop mode: if DATABASE_URL is the default postgres URL or unset,
        # use SQLite. If user explicitly set DATABASE_URL, honor it.
        explicit_url = os.environ.get("DATABASE_URL")
        if not explicit_url or s.database_url.startswith("postgresql+asyncpg://comic_user:comic_password@localhost"):
            from app.core.desktop_config import get_desktop_database_url
            s.database_url = get_desktop_database_url()
        # Auto-generate JWT secret if not set
        if not os.environ.get("JWT_SECRET_KEY") or s.jwt_secret_key == "change-me-to-a-jwt-secret":
            from app.core.desktop_config import get_desktop_jwt_secret
            s.jwt_secret_key = get_desktop_jwt_secret()
    return s


settings = _build_settings()
