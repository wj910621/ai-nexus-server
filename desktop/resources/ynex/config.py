import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # LLM 配置
    use_local_first: bool = False
    local_model: str = "qwen2.5:7b"
    local_base_url: str = "http://localhost:11434"
    local_backend: str = "ollama"  # 可选: ollama / vllm / tensorrt / llama.cpp
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    online_model: str = "deepseek-chat"

    # 本地 LLM 推理参数优化
    llm_num_ctx: int = 4096        # 上下文长度（显存小可设 2048）
    llm_num_gpu: int = -1          # -1 表示自动分配所有 GPU 层
    llm_temperature: float = 0.7
    llm_top_p: float = 0.9
    llm_top_k: int = 40
    llm_repeat_penalty: float = 1.1
    llm_quant_preference: str = "auto"  # auto / q2 / q4 / q8 / fp16

    # 唤醒词配置
    wake_word: str = "Y·NEX"
    wake_word_model_path: str = ""
    wake_word_access_key: str = ""

    # 语音识别配置
    asr_model: str = "base"
    asr_use_local: bool = True

    # 语音合成
    tts_voice: str = "zh-CN-YunxiNeural"

    # 记忆设置（SQLite）
    memory_db: str = "data/memory.db"
    max_history: int = 20

    # 知识库（RAG）
    knowledge_dir: str = "data/knowledge"
    vector_db_path: str = "data/vectors"

    # 智能家居 Home Assistant
    home_assistant_url: str = ""
    home_assistant_token: str = ""

    # Telegram Bot（全球通用遥控）
    telegram_bot_token: str = ""

    # 远程访问与安全
    # 默认仅监听本地回环，避免局域网/公网任意访问。如需局域网访问，请显式配置为 0.0.0.0 并配合防火墙。
    api_bind_host: str = "127.0.0.1"
    # 默认仅信任本机。如需局域网免认证，请显式收窄到具体网段，切勿保留整个 RFC1918。
    trusted_subnets: str = "127.0.0.1/32"
    api_key_required: bool = True  # 生产环境强制所有请求携带 API Key
    # 生产环境必须改为具体域名，如 "http://localhost:3000,https://ynexai.cn"
    cors_origins: str = "http://localhost:3000,http://localhost:3001,http://localhost:7777,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:7777"
    max_content_length_mb: int = 64  # 最大请求体大小（MB）
    request_timeout_seconds: int = 120  # 请求超时（秒）

    # API 限流
    rate_limit_enabled: bool = True
    rate_limit_requests_per_minute: int = 60  # 默认每个 IP/API Key 每分钟 60 次
    rate_limit_burst: int = 10  # 突发请求缓冲

    # 运维与备份
    backup_dir: str = "backups"
    backup_interval_hours: int = 24  # 自动备份间隔
    backup_keep_count: int = 7  # 保留最近备份份数

    # 自托管服务
    # Paperless-ngx 文档管理
    paperless_url: str = ""
    paperless_token: str = ""
    # Immich 相册
    immich_url: str = ""
    immich_api_key: str = ""
    # n8n 工作流
    n8n_url: str = ""
    n8n_api_key: str = ""


def validate_config():
    """配置校验，返回问题列表"""
    issues = []

    if not settings.deepseek_api_key and not settings.use_local_first:
        issues.append("未配置 DEEPSEEK_API_KEY，且未启用本地模型（USE_LOCAL_FIRST=false），真实 LLM 模式不可用。")

    if settings.use_local_first:
        # 本地模式只需检查基础 URL，不强制 Ollama 正在运行
        if not settings.local_base_url.startswith("http"):
            issues.append(f"LOCAL_BASE_URL 格式不正确：{settings.local_base_url}")

    if settings.wake_word_model_path and not os.path.exists(settings.wake_word_model_path):
        issues.append(f"自定义唤醒词模型不存在：{settings.wake_word_model_path}")

    return issues


settings = Settings()
