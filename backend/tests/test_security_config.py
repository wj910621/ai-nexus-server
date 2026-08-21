"""E1: 配置校验测试 - Phase 8 P7 A7"""
import pytest

from app.core.config import Settings
from app.core.config_validator import validate_production_settings


@pytest.fixture(autouse=True)
def _isolate_desktop_mode_env(monkeypatch):
    """清理 CS_DESKTOP_MODE 环境变量，确保生产环境校验测试不被其他测试污染。

    某些测试（如 test_runtime_setup_desktop_env）会通过 os.environ.setdefault
    永久设置 CS_DESKTOP_MODE=1，导致后续测试的环境状态被污染。
    此 fixture 在每个测试运行前清理该变量，保证测试隔离。
    """
    monkeypatch.delenv("CS_DESKTOP_MODE", raising=False)


def _make_settings(**overrides) -> Settings:
    """构造测试用 Settings 实例，默认为生产环境 + 强密钥。"""
    base = {
        "app_env": "production",
        "app_debug": False,
        "jwt_secret_key": "x" * 64,  # 强密钥
        "app_secret_key": "strong-app-secret-key-1234567890-abcdef",
        "database_url": "postgresql+asyncpg://user:strongpass@db:5432/comic",
        "stripe_enabled": True,
        "stripe_secret_key": "sk_live_strong_key_xxxxxxxxxxxxx",
        "stripe_webhook_secret": "whsec_strong_secret_xxxxxxxxxxxxx",
        "billing_mode": "standalone",
        "cors_origins": "https://comic.example.com",
        "redis_url": "redis://redis.internal:6379/0",
        "rate_limit_redis_url": "redis://redis.internal:6379/0",
        "run_migrations_on_startup": False,
    }
    base.update(overrides)
    return Settings(**base)


def test_production_rejects_default_jwt_secret():
    """生产环境拒绝默认 JWT 密钥"""
    s = _make_settings(jwt_secret_key="change-me-to-a-jwt-secret")
    with pytest.raises(RuntimeError, match="jwt_secret_key"):
        validate_production_settings(s)


def test_production_rejects_short_jwt_secret():
    """生产环境拒绝长度 <32 的 JWT 密钥"""
    s = _make_settings(jwt_secret_key="shortkey-only-28-chars-long")
    assert len(s.jwt_secret_key) < 32
    with pytest.raises(RuntimeError, match="jwt_secret_key"):
        validate_production_settings(s)


def test_production_rejects_default_db_password():
    """生产环境拒绝默认数据库密码 comic_password"""
    s = _make_settings(
        database_url="postgresql+asyncpg://comic_user:comic_password@localhost:5432/db"
    )
    with pytest.raises(RuntimeError, match="database_url"):
        validate_production_settings(s)


def test_production_rejects_empty_stripe_key_when_enabled():
    """生产环境启用 stripe 但 secret_key 为空时拒绝启动"""
    s = _make_settings(stripe_enabled=True, stripe_secret_key="")
    with pytest.raises(RuntimeError, match="stripe"):
        validate_production_settings(s)


def test_production_rejects_mock_payments():
    s = _make_settings(stripe_enabled=False)
    with pytest.raises(RuntimeError, match="mock provider"):
        validate_production_settings(s)


def test_production_rejects_missing_webhook_secret():
    s = _make_settings(stripe_webhook_secret="")
    with pytest.raises(RuntimeError, match="webhook"):
        validate_production_settings(s)


def test_development_skips_validation():
    """开发环境跳过校验（即使密钥弱也不报错）"""
    s = _make_settings(app_env="development", jwt_secret_key="change-me-to-a-jwt-secret")
    # 不应抛出异常
    validate_production_settings(s)


def test_desktop_mode_skips_validation(monkeypatch):
    """桌面模式跳过校验"""
    monkeypatch.setenv("CS_DESKTOP_MODE", "1")
    s = _make_settings(jwt_secret_key="change-me-to-a-jwt-secret")
    # 不应抛出异常
    validate_production_settings(s)


def test_production_accepts_strong_config():
    """生产环境 + 全部强配置应通过校验"""
    s = _make_settings(
        stripe_enabled=True,
        stripe_secret_key="sk_live_strong_key_xxxxxxxxxxxxx",
    )
    validate_production_settings(s)


def test_production_accepts_jarvis_shared_billing_without_stripe():
    s = _make_settings(
        billing_mode="jarvis",
        stripe_enabled=False,
        stripe_secret_key="",
        stripe_webhook_secret="",
        jarvis_gateway_enabled=True,
        jarvis_gateway_base_url="https://ynexai.cn",
        jarvis_gateway_service_token="g" * 32,
        jarvis_gateway_default_model="nx_gpt5mini",
        jarvis_billing_portal_url="https://ynexai.cn/",
        ynex_sso_secret="s" * 32,
        ynex_billing_base_url="https://ynexai.cn",
        ynex_billing_service_token="t" * 32,
    )
    validate_production_settings(s)


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"app_debug": True}, "app_debug"),
        ({"database_url": "sqlite:///local.db"}, "postgresql"),
        (
            {"database_url": "postgresql+asyncpg://user:pass@localhost/db"},
            "local host",
        ),
        ({"redis_url": "redis://localhost:6379/0", "rate_limit_redis_url": ""}, "Redis"),
        ({"cors_origins": "http://comic.example.com"}, "HTTPS"),
        ({"run_migrations_on_startup": True}, "run_migrations_on_startup"),
    ],
)
def test_production_rejects_infrastructure_shortcuts(override, message):
    s = _make_settings(**override)
    with pytest.raises(RuntimeError, match=message):
        validate_production_settings(s)


def test_jarvis_gateway_requires_strong_service_token():
    s = _make_settings(
        billing_mode="jarvis",
        stripe_enabled=False,
        stripe_secret_key="",
        stripe_webhook_secret="",
        jarvis_gateway_enabled=True,
        jarvis_gateway_base_url="https://ynexai.cn",
        jarvis_gateway_service_token="short",
        jarvis_gateway_default_model="nx_gpt5mini",
        jarvis_billing_portal_url="https://ynexai.cn/",
        ynex_sso_secret="s" * 32,
        ynex_billing_base_url="https://ynexai.cn",
        ynex_billing_service_token="t" * 32,
    )
    with pytest.raises(RuntimeError, match="jarvis_gateway_service_token"):
        validate_production_settings(s)
