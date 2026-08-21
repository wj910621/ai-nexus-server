"""Sentry SDK initialization — no-op when DSN is empty."""
from loguru import logger

from app.core.config import settings


def init_sentry(dsn: str = None) -> None:
    """Initialize Sentry SDK. No-op if DSN is empty.

    Args:
        dsn: Sentry DSN. If None, uses settings.sentry_dsn.
    """
    if dsn is None:
        dsn = settings.sentry_dsn

    if not dsn:
        logger.debug("Sentry DSN not configured; error tracking disabled")
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=settings.app_env,
            traces_sample_rate=0.1,  # 10% of transactions traced
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
            before_send=_filter_sensitive_data,
        )
        logger.info(f"Sentry initialized (env={settings.app_env})")
    except ImportError:
        logger.warning("sentry-sdk not installed; skipping Sentry init")
    except Exception as e:
        logger.warning(f"Sentry init failed: {e}")


def _filter_sensitive_data(event, hint):
    """Remove sensitive data from Sentry events."""
    # Filter Authorization headers
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        event["request"]["headers"] = [
            (k, "***" if k.lower() in ("authorization", "x-api-key") else v)
            for k, v in headers
        ]
    return event
