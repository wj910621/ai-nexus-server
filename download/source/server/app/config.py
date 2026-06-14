from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    database_url: str = 'sqlite+aiosqlite:///./nexus.db'
    redis_url: str = 'redis://localhost:6379/0'
    jwt_secret: str = 'nexus-ai-studio-secret-change-in-production'
    jwt_algorithm: str = 'HS256'
    jwt_expire_minutes: int = 1440
    openai_api_key: str = ''
    api_base_url: str = 'https://j3trisheng.com'

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'


settings = Settings()

