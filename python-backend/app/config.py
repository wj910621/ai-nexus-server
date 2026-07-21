from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    database_url: str = 'sqlite+aiosqlite:///./nexus.db'
    redis_url: str = 'redis://localhost:6379/0'
    jwt_secret: str = ''
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 1440
    openai_api_key: str = ''
    api_base_url: str = 'https://j3trisheng.com'

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


settings = Settings()

if not settings.jwt_secret:
    raise RuntimeError(
        "JWT_SECRET 未设置。请在 .env 文件中设置 JWT_SECRET 环境变量。\n"
        "建议使用: openssl rand -hex 32 生成安全的随机密钥。"
    )

