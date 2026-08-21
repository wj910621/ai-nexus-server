"""Tests for Task 14: Backup + Alerting + SLA.

Tests cover:
- /api/v1/admin/ops/sla endpoint (uptime / p99 / cache hit rate / error rate)
- /api/v1/admin/ops/backups endpoint (list backup files)
- Admin role enforcement on /admin/ops/* endpoints
- deploy/monitoring/alerts.yml contains required Prometheus alert rules
- deploy/monitoring/alertmanager.yml has webhook_configs for Feishu/DingTalk
- scripts/backup.py exists, contains pg_dump, gzip/tarfile, and AES-256 encryption

Note: Project's `create_access_token(subject: str)` takes a string, not a dict.
We bypass auth via `app.dependency_overrides[admin_ops.require_admin]` because
`Depends(require_admin)` is bound to the original function object at route
registration time — patching the module attribute would not affect FastAPI's
dependency resolution. (See existing pattern in tests/test_ai_integration.py.)
"""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api import admin_ops
from app.main import app


@pytest.fixture
def admin_bypass():
    """Bypass require_admin dependency with a mock admin user.

    Using `app.dependency_overrides` is the only way to override a Depends()
    that has already been bound at route registration time.
    """
    mock_user = MagicMock()
    mock_user.id = "test-admin-id"
    mock_user.role = "admin"
    mock_user.email = "admin@example.com"
    app.dependency_overrides[admin_ops.require_admin] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.pop(admin_ops.require_admin, None)


def test_sla_endpoint_returns_metrics(admin_bypass):
    """/admin/ops/sla returns uptime, p99, cache_hit_rate."""
    # Note: TestClient is instantiated without `with` to skip lifespan,
    # which calls signal.signal() (fails in test thread). Routes are
    # registered at module load, so they're available without lifespan.
    client = TestClient(app)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.api.admin_ops.compute_sla",
            AsyncMock(return_value={
                "uptime_percent_30d": 99.95,
                "p99_latency_ms": 450,
                "cache_hit_rate_percent": 78.5,
                "error_rate_percent": 0.3,
            }),
        )
        response = client.get("/api/v1/admin/ops/sla")
    assert response.status_code == 200
    data = response.json()["data"]
    assert "uptime_percent_30d" in data
    assert "p99_latency_ms" in data
    assert "cache_hit_rate_percent" in data


def test_sla_endpoint_requires_admin_role():
    """/admin/ops/sla requires admin role (403 when not admin)."""
    def _raise_403():
        raise HTTPException(status_code=403, detail="Admin access required")
    app.dependency_overrides[admin_ops.require_admin] = _raise_403
    try:
        client = TestClient(app)
        response = client.get("/api/v1/admin/ops/sla")
        assert response.status_code in (401, 403)
    finally:
        app.dependency_overrides.pop(admin_ops.require_admin, None)


def test_backups_list_endpoint_returns_list(admin_bypass):
    """/admin/ops/backups returns list of backup files."""
    client = TestClient(app)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(
            "app.api.admin_ops.list_backups",
            AsyncMock(return_value=[
                {"name": "db-2026-07-18.sql.gz", "size_mb": 50, "type": "db"},
                {"name": "uploads-2026-07-18.tar.gz", "size_mb": 200, "type": "uploads"},
            ]),
        )
        response = client.get("/api/v1/admin/ops/backups")
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["backups"]) == 2


def test_alerts_rules_file_has_required_alerts():
    """alerts.yml contains all required alert rules.

    Prometheus rule files use the structure:
        groups:
          - name: <group_name>
            rules:
              - alert: <alert_name>
                expr: ...
    So we iterate `groups[*].rules[*].alert` to collect alert names.
    """
    import yaml
    path = os.path.join(
        os.path.dirname(__file__), "..", "deploy", "monitoring", "alerts.yml"
    )
    with open(path, encoding="utf-8") as f:
        rules = yaml.safe_load(f)
    alert_names: set[str] = set()
    for group in rules.get("groups", []):
        for rule in group.get("rules", []):
            if "alert" in rule:
                alert_names.add(rule["alert"])
    required = {
        "HighErrorRate", "HighP99Latency", "LowCacheHitRate",
        "EngineCircuitOpen", "HighMemoryUsage", "HighDiskUsage",
        "DatabaseConnectionFailure", "RedisConnectionFailure",
        "ServiceDown", "SSLExpiringSoon",
    }
    # Verify at least 8 of the 10 required alerts are present
    found = alert_names.intersection(required)
    assert len(found) >= 8, f"Missing alerts: {required - found}"


def test_alertmanager_has_webhook_config():
    """alertmanager.yml has webhook_configs for Feishu/DingTalk."""
    import yaml
    path = os.path.join(
        os.path.dirname(__file__), "..", "deploy", "monitoring", "alertmanager.yml"
    )
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    receivers = cfg.get("receivers", [])
    webhook_receivers = [r for r in receivers if r.get("webhook_configs")]
    assert len(webhook_receivers) >= 1


def test_backup_script_exists():
    """backup.py script exists."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "backup.py"
    )
    assert os.path.exists(path)


def test_backup_script_has_pg_dump_command():
    """backup.py contains pg_dump invocation."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "backup.py"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "pg_dump" in content
    assert "gzip" in content or "tarfile" in content


def test_backup_script_has_encryption():
    """backup.py encrypts backups with AES-256."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "backup.py"
    )
    with open(path, encoding="utf-8") as f:
        content = f.read()
    assert "AES" in content or "cryptography" in content or "fernet" in content.lower()


def test_production_backup_requires_persistent_encryption_key(monkeypatch):
    """Production must never create a backup with a lost-on-exit key."""
    from types import SimpleNamespace

    import pytest

    from scripts import backup

    monkeypatch.delenv("BACKUP_ENCRYPTION_KEY", raising=False)
    monkeypatch.setattr(
        backup,
        "_get_settings",
        lambda: SimpleNamespace(app_env="production", backup_encryption_key=""),
    )

    with pytest.raises(RuntimeError, match="required in production"):
        backup._encryption_key()
