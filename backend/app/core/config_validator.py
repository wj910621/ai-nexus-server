"""Fail-closed validation for production configuration."""
import os

from loguru import logger

from app.core.config import Settings

WEAK_SECRETS = {"change-me", "change-me-to-a-jwt-secret", "", "secret", "test-secret"}


def validate_production_settings(settings: Settings) -> None:
    """Reject unsafe production settings before the application starts."""
    if os.environ.get("CS_DESKTOP_MODE", "").lower() in ("1", "true", "yes"):
        return
    if not settings.is_production:
        return

    errors: list[str] = []
    if settings.app_debug:
        errors.append("app_debug must be false in production")
    if settings.jwt_secret_key in WEAK_SECRETS or len(settings.jwt_secret_key) < 32:
        errors.append("jwt_secret_key must be non-default and at least 32 characters")
    if settings.app_secret_key in WEAK_SECRETS or len(settings.app_secret_key) < 32:
        errors.append("app_secret_key must be non-default and at least 32 characters")
    database_url = settings.database_url.lower()
    if "comic_password" in database_url:
        errors.append("database_url cannot contain the default comic_password")
    if not database_url.startswith("postgresql+asyncpg://"):
        errors.append("production database_url must use postgresql+asyncpg")
    if any(host in database_url for host in ("@localhost", "@127.0.0.1", "@host.docker.internal")):
        errors.append("production database_url cannot use a local host")
    if settings.billing_mode not in {"jarvis", "standalone"}:
        errors.append("billing_mode must be jarvis or standalone")
    if settings.billing_mode == "standalone":
        if not settings.stripe_enabled:
            errors.append("standalone production payments cannot use the mock provider")
        if not settings.stripe_secret_key:
            errors.append("stripe_secret_key is required for standalone billing")
        if not settings.stripe_webhook_secret:
            errors.append("stripe_webhook_secret is required for standalone billing")
    if settings.billing_mode == "jarvis":
        if not settings.jarvis_billing_portal_url.startswith("https://"):
            errors.append("jarvis_billing_portal_url must use HTTPS")
        if not settings.jarvis_gateway_enabled:
            errors.append("jarvis_gateway_enabled is required for shared billing")
        if len(settings.ynex_sso_secret) < 32:
            errors.append("ynex_sso_secret is required and must be at least 32 characters")
        if not settings.ynex_billing_base_url.startswith("https://"):
            errors.append("ynex_billing_base_url must use HTTPS")
        if len(settings.ynex_billing_service_token) < 32:
            errors.append("ynex_billing_service_token is required and must be at least 32 characters")
    effective_rate_redis = (settings.rate_limit_redis_url or settings.redis_url).lower()
    if not settings.rate_limit_enabled or effective_rate_redis == "none":
        errors.append("distributed rate limiting is required in production")
    if not effective_rate_redis.startswith(("redis://", "rediss://")):
        errors.append("production rate limiting requires a Redis URL")
    if any(host in effective_rate_redis for host in ("localhost", "127.0.0.1", "host.docker.internal")):
        errors.append("production Redis cannot use a local host")
    if not settings.cors_origins_list or any(
        not origin.startswith("https://") for origin in settings.cors_origins_list
    ):
        errors.append("production CORS origins must be non-empty HTTPS origins")
    if settings.run_migrations_on_startup:
        errors.append("run_migrations_on_startup must be false in production")
    if settings.jarvis_gateway_enabled:
        _gw = (settings.jarvis_gateway_base_url or "").lower()
        _internal_hosts = ("host.docker.internal", "localhost", "127.0.0.1", "172.", "10.", "192.168.")
        _is_internal = any(h in _gw for h in _internal_hosts)
        if not (_gw.startswith("https://") or (_gw.startswith("http://") and _is_internal)):
            errors.append(
                "jarvis_gateway_base_url must use HTTPS in production "
                "(internal/loopback HTTP allowed for sidecar services)"
            )
        if len(settings.jarvis_gateway_service_token) < 32:
            errors.append(
                "jarvis_gateway_service_token is required and must be at least 32 characters"
            )
        if not settings.jarvis_gateway_default_model:
            errors.append("jarvis_gateway_default_model is required when enabled")

    if errors:
        raise RuntimeError("Production configuration validation failed: " + "; ".join(errors))
    logger.info("Production configuration validation passed")
