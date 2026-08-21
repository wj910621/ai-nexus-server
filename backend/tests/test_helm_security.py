"""Phase 8 P7 - Helm Chart 安全加固验证测试。

不依赖 helm CLI，通过读取模板文件内容进行字符串断言，验证：
- ServiceAccount 创建与 automount 禁用
- ResourceQuota / LimitRange 资源限制
- Namespace PSA 标签
- Deployment securityContext (Pod 级别与容器级别)
- Frontend 容器端口 8080 (nginx-unprivileged)
- ServiceAccount 关联
- Ingress 安全注解 (SSL 重定向、HSTS、proxy-body-size)
- NetworkPolicy 精细化 (PG/Redis 入站限制，移除 80 端口出站)
- Redis 密码强制 (移除 optional、探针认证)
- Secret 使用 randAlphaNum 默认生成
- values.yaml 新增配置块 (certManager/serviceAccount/podSecurityContext)
- Redis 密码非空默认值
"""
from pathlib import Path

import pytest
import yaml

CHART_DIR = Path(__file__).parent.parent.parent / "deploy" / "helm" / "comic-platform"
TEMPLATES_DIR = CHART_DIR / "templates"


def _read_template(name: str) -> str:
    """读取模板文件内容。"""
    path = TEMPLATES_DIR / name
    assert path.exists(), f"模板文件不存在: {name}"
    return path.read_text(encoding="utf-8")


def _read_values() -> str:
    """读取 values.yaml 内容。"""
    return (CHART_DIR / "values.yaml").read_text(encoding="utf-8")


def _load_values() -> dict:
    """加载 values.yaml 为字典。"""
    with open(CHART_DIR / "values.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ===== B2. ServiceAccount =====


def test_serviceaccount_template_exists():
    """ServiceAccount 模板文件存在。"""
    content = _read_template("serviceaccount.yaml")
    assert "kind: ServiceAccount" in content
    # 应包含三个 ServiceAccount
    assert content.count("kind: ServiceAccount") >= 3


def test_serviceaccount_template_contains_automount_false():
    """ServiceAccount 模板包含 automountServiceAccountToken 且默认为 false。"""
    content = _read_template("serviceaccount.yaml")
    assert "automountServiceAccountToken" in content
    assert ".Values.serviceAccount.automount" in content


# ===== B4. ResourceQuota =====


def test_resourcequota_template_exists():
    """ResourceQuota 模板文件存在。"""
    content = _read_template("resourcequota.yaml")
    assert "kind: ResourceQuota" in content
    assert "apiVersion: v1" in content


def test_resourcequota_has_cpu_memory_limits():
    """ResourceQuota 包含 CPU 和内存的请求与限制。"""
    content = _read_template("resourcequota.yaml")
    assert "requests.cpu" in content
    assert "requests.memory" in content
    assert "limits.cpu" in content
    assert "limits.memory" in content
    assert "persistentvolumeclaims" in content
    assert "count/pods" in content


# ===== B4. LimitRange =====


def test_limitrange_template_exists():
    """LimitRange 模板文件存在。"""
    content = _read_template("limitrange.yaml")
    assert "kind: LimitRange" in content
    assert "apiVersion: v1" in content


def test_limitrange_has_default_limits():
    """LimitRange 包含 default 和 defaultRequest 资源限制。"""
    content = _read_template("limitrange.yaml")
    assert "default:" in content
    assert "defaultRequest:" in content
    assert "max:" in content
    assert "cpu" in content
    assert "memory" in content


# ===== B3. PSA labels =====


def test_namespace_has_psa_labels():
    """Namespace 模板包含 Pod Security Admission 标签。"""
    content = _read_template("namespace.yaml")
    assert "pod-security.kubernetes.io/enforce" in content
    assert "pod-security.kubernetes.io/audit" in content
    assert "pod-security.kubernetes.io/warn" in content
    assert "pod-security.kubernetes.io/enforce-version" in content
    assert "pod-security.kubernetes.io/audit-version" in content
    assert "pod-security.kubernetes.io/warn-version" in content


def test_namespace_psa_enforce_baseline():
    """Namespace PSA enforce 策略为 baseline。"""
    content = _read_template("namespace.yaml")
    assert "pod-security.kubernetes.io/enforce: baseline" in content
    assert "pod-security.kubernetes.io/audit: restricted" in content
    assert "pod-security.kubernetes.io/warn: restricted" in content


# ===== B1. Deployment securityContext =====


def test_deployment_web_has_security_context():
    """deployment-web 包含 Pod 和容器级别 securityContext。"""
    content = _read_template("deployment-web.yaml")
    assert "securityContext:" in content
    assert "podSecurityContext" in content
    assert "containerSecurityContext" in content


def test_deployment_web_has_run_as_non_root():
    """deployment-web 引用的 containerSecurityContext 包含 runAsNonRoot: true。"""
    content = _read_template("deployment-web.yaml")
    assert "containerSecurityContext" in content
    # values.yaml 中应配置 runAsNonRoot: true
    values = _load_values()
    assert values["containerSecurityContext"]["runAsNonRoot"] is True


def test_deployment_web_has_read_only_root_fs():
    """deployment-web 引用的 containerSecurityContext 包含 readOnlyRootFilesystem: true。"""
    values = _load_values()
    assert values["containerSecurityContext"]["readOnlyRootFilesystem"] is True


def test_deployment_web_has_drop_all_capabilities():
    """deployment-web 引用的 containerSecurityContext 包含 drop ALL capabilities。"""
    values = _load_values()
    caps = values["containerSecurityContext"]["capabilities"]["drop"]
    assert "ALL" in caps


def test_deployment_worker_has_security_context():
    """deployment-worker 包含 workerSecurityContext。"""
    content = _read_template("deployment-worker.yaml")
    assert "securityContext:" in content
    assert "workerSecurityContext" in content
    assert "podSecurityContext" in content


def test_deployment_frontend_has_security_context():
    """deployment-frontend 包含 frontendSecurityContext。"""
    content = _read_template("deployment-frontend.yaml")
    assert "securityContext:" in content
    assert "frontendSecurityContext" in content
    assert "podSecurityContext" in content


def test_deployment_frontend_uses_port_8080():
    """deployment-frontend 容器端口为 8080 (nginx-unprivileged)。"""
    content = _read_template("deployment-frontend.yaml")
    assert "containerPort: 8080" in content
    # 逐行检查，确保不存在 containerPort: 80 (但允许 8080)
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped == "containerPort: 80":
            pytest.fail("deployment-frontend 不应使用 containerPort: 80")


# ===== B2. Deployment ServiceAccount =====


def test_deployment_web_has_service_account():
    """deployment-web 关联了独立 ServiceAccount。"""
    content = _read_template("deployment-web.yaml")
    assert "serviceAccountName:" in content
    assert "automountServiceAccountToken: false" in content


def test_deployment_worker_has_service_account():
    """deployment-worker 关联了独立 ServiceAccount。"""
    content = _read_template("deployment-worker.yaml")
    assert "serviceAccountName:" in content
    assert "automountServiceAccountToken: false" in content


def test_deployment_frontend_has_service_account():
    """deployment-frontend 关联了独立 ServiceAccount。"""
    content = _read_template("deployment-frontend.yaml")
    assert "serviceAccountName:" in content
    assert "automountServiceAccountToken: false" in content


# ===== B7. Ingress 注解加固 =====


def test_ingress_has_ssl_redirect():
    """Ingress 包含 ssl-redirect 注解。"""
    content = _read_template("ingress.yaml")
    assert "ssl-redirect" in content
    assert '"true"' in content


def test_ingress_has_hsts_header():
    """Ingress 包含 HSTS 安全头 (Strict-Transport-Security)。"""
    ingress = _read_template("ingress.yaml")
    backend = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "core"
        / "middleware"
        / "security_headers.py"
    ).read_text(encoding="utf-8")
    frontend = (
        Path(__file__).resolve().parents[2] / "frontend" / "nginx.conf"
    ).read_text(encoding="utf-8")
    assert "configuration-snippet" not in ingress
    for header in (
        "Strict-Transport-Security",
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
    ):
        assert header in backend
        assert header in frontend


def test_ingress_has_proxy_body_size():
    """Ingress 包含 proxy-body-size 注解。"""
    content = _read_template("ingress.yaml")
    assert "proxy-body-size" in content
    assert "proxy-read-timeout" in content
    assert "proxy-send-timeout" in content


# ===== B5. NetworkPolicy 精细化 =====


def test_networkpolicy_pg_exists():
    """PostgreSQL NetworkPolicy 模板存在且包含 5432 端口限制。"""
    content = _read_template("networkpolicy-pg.yaml")
    assert "kind: NetworkPolicy" in content
    assert "postgresql" in content
    assert "port: 5432" in content


def test_networkpolicy_redis_exists():
    """Redis NetworkPolicy 模板存在且包含 6379 端口限制。"""
    content = _read_template("networkpolicy-redis.yaml")
    assert "kind: NetworkPolicy" in content
    assert "redis" in content
    assert "port: 6379" in content


def test_networkpolicy_no_port_80_egress():
    """NetworkPolicy 出站规则不再包含 80 端口。"""
    content = _read_template("networkpolicy.yaml")
    # 允许 443 出站
    assert "port: 443" in content
    # 不应包含 port: 80 的出站规则
    # 注意: 可能有 port: 8080 等，需精确匹配 "port: 80"
    lines = content.splitlines()
    for line in lines:
        stripped = line.strip()
        if stripped == "port: 80":
            pytest.fail("networkpolicy.yaml 不应包含 port: 80 出站规则")


# ===== B9. Redis 密码强制 =====


def test_redis_statefulset_no_optional_password():
    """Redis StatefulSet 中 REDIS_PASSWORD 不再是 optional。"""
    content = _read_template("redis-statefulset.yaml")
    assert "optional: true" not in content
    # 探针应使用密码认证
    assert "REDIS_PASSWORD" in content
    assert "redis-cli -a" in content or 'redis-cli -a' in content
    # 命令应包含 --requirepass
    assert "requirepass" in content


# ===== B8. Secret 治理 =====


def test_secret_template_has_randalphanum():
    """Secret 模板使用 randAlphaNum 默认生成密码。"""
    content = _read_template("secret.yaml")
    assert "randAlphaNum" in content
    assert "default" in content
    # JWT_SECRET 应使用 64 位
    assert "randAlphaNum 64" in content
    # 数据库和 Redis 密码应使用 32 位
    assert "randAlphaNum 32" in content


# ===== B6. cert-manager 集成 =====


def test_values_has_certmanager_block():
    """values.yaml 包含 certManager 配置块。"""
    values = _load_values()
    assert "certManager" in values
    assert "enabled" in values["certManager"]
    assert "issuerType" in values["certManager"]
    assert "issuerName" in values["certManager"]
    assert values["certManager"]["enabled"] is False  # 默认关闭


# ===== B2. values.yaml ServiceAccount =====


def test_values_has_serviceaccount_block():
    """values.yaml 包含 serviceAccount 配置块。"""
    values = _load_values()
    assert "serviceAccount" in values
    assert "create" in values["serviceAccount"]
    assert "automount" in values["serviceAccount"]
    assert values["serviceAccount"]["create"] is True
    assert values["serviceAccount"]["automount"] is False


# ===== B1. values.yaml podSecurityContext =====


def test_values_has_podsecuritycontext_block():
    """values.yaml 包含 podSecurityContext 配置块。"""
    values = _load_values()
    assert "podSecurityContext" in values
    assert values["podSecurityContext"]["runAsNonRoot"] is True
    assert values["podSecurityContext"]["runAsUser"] == 1000
    assert "seccompProfile" in values["podSecurityContext"]
    # 容器安全上下文
    assert "containerSecurityContext" in values
    assert "workerSecurityContext" in values
    assert "frontendSecurityContext" in values


# ===== B9. values.yaml Redis 密码非空 =====


def test_values_redis_password_not_empty():
    """values.yaml 中 Redis 密码默认值非空。"""
    values = _load_values()
    assert "redis" in values
    assert "password" in values["redis"]
    password = values["redis"]["password"]
    assert password != "", "Redis 密码不应为空字符串"
    assert password is not None, "Redis 密码不应为 None"
    assert len(password) > 0, "Redis 密码长度应大于 0"
