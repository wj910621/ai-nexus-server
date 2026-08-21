"""Regression tests for production deployment blockers."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "deploy" / "helm" / "comic-platform"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_web_image_uses_ci_python_and_console_script_path():
    content = read(ROOT / "backend" / "Dockerfile.web")
    assert "python:3.13-slim" in content
    assert "python:3.14" not in content
    assert "PATH=/app/.deps/bin:$PATH" in content


def test_worker_image_pins_ci_python_and_cuda_torch():
    content = read(ROOT / "backend" / "Dockerfile.worker")
    assert "python3.13" in content
    assert "python3.14" not in content
    assert "torch==2.6.0" in content
    assert "PATH=/app/.deps/bin:$PATH" in content


def test_migration_job_gates_install_and_upgrade():
    content = read(CHART / "templates" / "migration-job.yaml")
    assert '"post-install" "pre-upgrade"' in content
    assert '"python", "-m", "alembic", "upgrade", "head"' in content
    assert "hook-succeeded" in content
    assert "activeDeadlineSeconds" in content


def test_secret_uses_application_setting_names_and_preserves_existing_values():
    content = read(CHART / "templates" / "secret.yaml")
    for key in (
        "APP_SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "RATE_LIMIT_REDIS_URL",
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
    ):
        assert key in content
    assert 'lookup "v1" "Secret"' in content
    assert "$(POSTGRES_PASSWORD)" not in content


def test_first_install_runs_migration_before_scaling_application():
    content = read(ROOT / "deploy" / "scripts" / "deploy.sh")
    assert "helm status" in content
    assert "--set backend.web.replicas=0" in content
    assert "--set backend.worker.replicas=0" in content
    assert "--wait-for-jobs" in content
    assert "IMAGE_REGISTRY" in content


def test_cd_waits_for_real_web_label_and_dependency_readiness():
    content = read(ROOT / ".github" / "workflows" / "deploy.yml")
    assert "app.kubernetes.io/component=backend-web" in content
    assert "http://localhost:8000/ready" in content
    assert "kill %1" not in content
    assert "port_forward_pid=$!" in content
    assert "ghcr.io/${{ github.repository }}/" in content

    deployment = read(CHART / "templates" / "deployment-web.yaml")
    assert "path: /ready" in deployment

    helm_test = read(CHART / "templates" / "tests" / "test-connection.yaml")
    assert "busybox:latest" not in helm_test
    assert "busybox@sha256:" in helm_test
    assert "-web:8000/ready" in helm_test


def test_production_deploy_requires_recent_traceable_database_backup():
    content = read(ROOT / ".github" / "workflows" / "deploy.yml")
    assert "backup_evidence_id:" in content
    assert "backup_evidence_utc:" in content
    assert "age_seconds" in content
    assert '"${age_seconds}" -gt 3600' in content
    assert "Production database backup gate" in content


def test_production_deploy_requires_recent_manual_pricing_approval():
    content = read(ROOT / ".github" / "workflows" / "deploy.yml")
    assert "pricing_evidence_id:" in content
    assert "pricing_approved_utc:" in content
    assert "Y.NEX manual pricing approval" in content
    assert 'age_seconds}" -gt 86400' in content


def test_staging_and_production_helm_tests_use_their_own_namespaces():
    content = read(ROOT / ".github" / "workflows" / "deploy.yml")
    assert "helm test comic-platform -n comic-staging --logs" in content
    assert "helm test comic-platform -n comic-production --logs" in content


def test_production_workflow_runs_fail_closed_infrastructure_preflight():
    workflow = read(ROOT / ".github" / "workflows" / "deploy.yml")
    preflight = read(ROOT / "deploy" / "scripts" / "pre-deploy-check.sh")
    assert "bash deploy/scripts/pre-deploy-check.sh" in workflow
    assert "kubectl apply --dry-run=server" in preflight
    assert "docker manifest inspect" in preflight
    assert "Prometheus Operator CRDs are missing" in preflight
    assert "Production TLS Secret" in preflight
    for key in (
        "APP_SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "JARVIS_GATEWAY_SERVICE_TOKEN",
        "YNEX_SSO_SECRET",
        "YNEX_BILLING_SERVICE_TOKEN",
        "ALERTING_WEBHOOK_URL",
    ):
        assert key in preflight
    assert "JWT_SECRET " not in preflight


def test_shared_ynex_domain_uses_non_conflicting_story_paths():
    production_values = read(CHART / "values-prod.yaml")
    default_values = read(CHART / "values.yaml")
    ingress = read(CHART / "templates" / "ingress.yaml")
    frontend_image = read(ROOT / "frontend" / "Dockerfile")
    release = read(ROOT / ".github" / "workflows" / "release.yml")

    assert "host: ynexai.cn" in production_values
    for path in ("/story/", "/story-api/", "/story-ws/"):
        assert path in default_values
    for rewrite in ('"rewrite" "/$2"', '"rewrite" "/api/$2"', '"rewrite" "/ws/$2"'):
        assert rewrite in ingress
    assert '"frontend"' in ingress
    assert '"api"' in ingress
    assert '"ws"' in ingress
    for setting in (
        "VITE_BASE_PATH=/story/",
        "VITE_ROUTER_BASE=/story",
        "VITE_API_BASE_URL=/story-api",
        "VITE_WS_BASE_URL=/story-ws",
    ):
        assert setting in frontend_image
        assert setting in release

    runtime = read(ROOT / "frontend" / "src" / "utils" / "runtime.ts")
    assert "VITE_API_BASE_URL || '/api'" in runtime
    assert "path.startsWith('/api/')" in runtime


def test_production_redis_dependencies_fail_closed_and_snippets_are_forbidden():
    main = read(ROOT / "backend" / "app" / "main.py")
    cache = read(ROOT / "backend" / "app" / "core" / "cache.py")
    ingress = read(CHART / "templates" / "ingress.yaml")
    assert "Production rate limiter initialization failed" in main
    assert "Production cache initialization failed" in main
    assert "Production Redis cache is unavailable" in cache
    assert "configuration-snippet" not in ingress


def test_production_runs_public_shared_domain_acceptance():
    workflow = read(ROOT / ".github" / "workflows" / "deploy.yml")
    main = read(ROOT / "backend" / "app" / "main.py")
    assert '@app.get("/api/ready", include_in_schema=False)' in main
    assert '@app.get("/api/health", include_in_schema=False)' in main
    assert "helm test comic-platform -n comic-production --logs" in workflow
    assert "https://ynexai.cn/story/" in workflow
    assert "https://ynexai.cn/story-api/ready" in workflow
    assert "https://ynexai.cn/story-ws/" in workflow
    assert "strict-transport-security" in workflow


def test_monitoring_uses_operator_config_and_secret_webhook():
    alerting = read(CHART / "templates" / "alertmanager-config.yaml")
    workflow = read(ROOT / ".github" / "workflows" / "deploy.yml")
    preflight = read(ROOT / "deploy" / "scripts" / "pre-deploy-check.sh")
    assert "kind: AlertmanagerConfig" in alerting
    assert "monitoring.coreos.com/v1beta1" in alerting
    assert "urlSecret:" in alerting
    assert "key: ALERTING_WEBHOOK_URL" in alerting
    assert "ALERTING_WEBHOOK_URL" in workflow
    assert "alertmanagerconfigs.monitoring.coreos.com" in preflight


def test_migration_upgrades_do_not_destroy_schema_objects():
    """Expand-only upgrades keep the previous application version rollback-safe."""
    forbidden_calls = {
        "drop_table",
        "drop_column",
        "drop_constraint",
        "drop_index",
        "drop_table_comment",
    }
    migration_dir = ROOT / "backend" / "alembic" / "versions"
    violations: list[str] = []

    for path in sorted(migration_dir.glob("*.py")):
        tree = ast.parse(read(path), filename=str(path))
        upgrade = next(
            (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "upgrade"
            ),
            None,
        )
        assert upgrade is not None, f"{path.name} has no upgrade()"
        for node in ast.walk(upgrade):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else None
            if name in forbidden_calls:
                violations.append(f"{path.name}:{node.lineno}:{name}")

    assert not violations, "destructive migration upgrade calls: " + ", ".join(violations)
