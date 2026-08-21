"""Phase 8 P4 - Helm Chart 结构与 YAML 语法验证。

不依赖 helm CLI，使用 PyYAML 解析所有 YAML 文件确保语法正确。
验证 Chart 关键结构：Chart.yaml、values.yaml、templates/。
"""
import re
from pathlib import Path

import pytest
import yaml

CHART_DIR = Path(__file__).parent.parent.parent / "deploy" / "helm" / "comic-platform"


def _read_text(path: Path) -> str:
    """Read a UTF-8 text file so parsing is locale-independent on Windows."""
    return path.read_text(encoding="utf-8")


def _load_yaml(path: Path):
    """Load and parse a UTF-8 YAML file independent of the OS locale."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _list_yaml_files(directory: Path) -> list:
    """递归列出目录下所有 .yaml/.yml 文件。"""
    if not directory.exists():
        return []
    return sorted(directory.rglob("*.yaml")) + sorted(directory.rglob("*.yml"))


def _strip_helm_template(content: str) -> str:
    """简化 Helm 模板语法，便于 YAML 解析。

    Helm 模板中 {{ ... }} 表达式会导致 YAML 解析失败，
    用占位符替换以验证纯 YAML 语法。支持多行表达式和注释。

    注意：此函数仅用于基础语法检查，无法处理所有 Helm 模板场景
    （如 {{ include }}-suffix 这种字符串拼接）。完整验证应使用 helm template。
    """
    # 先处理多行注释 {{/* ... */}}（DOTALL 让 . 匹配换行）
    content = re.sub(r"\{\{/\*.*?\*/\}\}", "", content, flags=re.DOTALL)
    # 处理多行表达式 {{- ... -}} / {{- ... }} / {{ ... -}} / {{ ... }}
    content = re.sub(r"\{\{-?\s[\s\S]*?-?\}\}", 'PLACEHOLDER', content)
    # 处理简单的单行 {{ .Values.x }}
    content = re.sub(r"\{\{[^}]*\}\}", 'PLACEHOLDER', content)
    return content


# ===== Chart 目录结构 =====


def test_chart_directory_exists():
    """Chart 目录存在。"""
    assert CHART_DIR.exists(), f"Chart dir not found: {CHART_DIR}"


def test_chart_yaml_exists():
    """Chart.yaml 存在。"""
    assert (CHART_DIR / "Chart.yaml").exists()


def test_values_yaml_exists():
    """values.yaml 存在。"""
    assert (CHART_DIR / "values.yaml").exists()


def test_values_prod_yaml_exists():
    """values-prod.yaml 存在。"""
    assert (CHART_DIR / "values-prod.yaml").exists()


def test_values_staging_yaml_exists():
    """values-staging.yaml 存在。"""
    assert (CHART_DIR / "values-staging.yaml").exists()


def test_templates_dir_exists():
    """templates/ 目录存在。"""
    assert (CHART_DIR / "templates").is_dir()


def test_helpers_tpl_exists():
    """templates/_helpers.tpl 存在。"""
    assert (CHART_DIR / "templates" / "_helpers.tpl").exists()


# ===== Chart.yaml 内容 =====


def test_chart_yaml_valid():
    """Chart.yaml 语法有效。"""
    data = _load_yaml(CHART_DIR / "Chart.yaml")
    assert data["apiVersion"] == "v2"
    assert data["name"] == "comic-platform"
    assert "version" in data
    assert "appVersion" in data


def test_chart_yaml_has_maintainers():
    """Chart.yaml 包含 maintainers 字段。"""
    data = _load_yaml(CHART_DIR / "Chart.yaml")
    assert "maintainers" in data
    assert len(data["maintainers"]) >= 1


# ===== values.yaml 内容 =====


def test_values_yaml_valid():
    """values.yaml 语法有效。"""
    data = _load_yaml(CHART_DIR / "values.yaml")
    assert data is not None
    assert "namespace" in data
    assert "backend" in data
    assert "frontend" in data


def test_values_yaml_has_namespace():
    """values.yaml 包含 namespace 配置。"""
    data = _load_yaml(CHART_DIR / "values.yaml")
    assert "create" in data["namespace"]
    assert "name" in data["namespace"]


def test_values_yaml_has_backend_web():
    """values.yaml 包含 backend.web 配置。"""
    data = _load_yaml(CHART_DIR / "values.yaml")
    assert "web" in data["backend"]
    assert "replicas" in data["backend"]["web"]
    assert "image" in data["backend"]["web"]
    assert "repository" in data["backend"]["web"]["image"]
    assert "tag" in data["backend"]["web"]["image"]


def test_values_yaml_has_backend_worker():
    """values.yaml 包含 backend.worker 配置。"""
    data = _load_yaml(CHART_DIR / "values.yaml")
    assert "worker" in data["backend"]
    assert "replicas" in data["backend"]["worker"]
    assert "gpu" in data["backend"]["worker"]


def test_values_yaml_has_postgresql():
    """values.yaml 包含 postgresql 配置。"""
    data = _load_yaml(CHART_DIR / "values.yaml")
    assert "postgresql" in data
    assert "enabled" in data["postgresql"]
    assert "external" in data["postgresql"]


def test_values_yaml_has_redis():
    """values.yaml 包含 redis 配置。"""
    data = _load_yaml(CHART_DIR / "values.yaml")
    assert "redis" in data


def test_values_yaml_has_oss():
    """values.yaml 包含 OSS 配置。"""
    data = _load_yaml(CHART_DIR / "values.yaml")
    assert "oss" in data
    assert "enabled" in data["oss"]


# ===== values-prod.yaml 内容 =====


def test_values_prod_yaml_valid():
    """values-prod.yaml 语法有效。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data is not None


def test_values_prod_has_production_namespace():
    """values-prod.yaml 配置了生产 namespace。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data["namespace"]["name"] == "comic-production"


def test_values_prod_has_ingress_enabled():
    """values-prod.yaml 启用了 ingress。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data["ingress"]["enabled"] is True


def test_values_prod_has_hpa_enabled():
    """values-prod.yaml 启用了 HPA。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data["hpa"]["web"]["enabled"] is True
    assert data["hpa"]["worker"]["enabled"] is True


def test_values_prod_has_pdb_enabled():
    """values-prod.yaml 启用了 PDB。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data["pdb"]["enabled"] is True


def test_values_prod_has_network_policy_enabled():
    """values-prod.yaml 启用了 NetworkPolicy。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data["networkPolicy"]["enabled"] is True


def test_values_prod_has_oss_enabled():
    """values-prod.yaml 启用了 OSS。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data["oss"]["enabled"] is True


def test_values_prod_has_persistence_enabled():
    """values-prod.yaml 启用了持久化存储。"""
    data = _load_yaml(CHART_DIR / "values-prod.yaml")
    assert data["persistence"]["enabled"] is True


# ===== values-staging.yaml 内容 =====


def test_values_staging_yaml_valid():
    """values-staging.yaml 语法有效。"""
    data = _load_yaml(CHART_DIR / "values-staging.yaml")
    assert data is not None
    assert data["namespace"]["name"] == "comic-staging"


# ===== 所有模板 YAML 语法验证 =====


def test_all_template_yaml_files_are_valid():
    """所有模板 YAML 文件存在且非空，并包含基本 Helm 指令。

    由于 Helm 模板包含 `{{ include "x" . }}-suffix` 等字符串拼接，
    纯 YAML 解析无法验证。这里仅检查：
    1. 文件存在且非空
    2. 包含 apiVersion / kind 等 K8s 资源必需字段
    3. 包含 Helm 模板指令（{{ ... }}）

    完整的模板渲染验证应使用 `helm template` 命令在 CI 中执行。
    """
    yaml_files = _list_yaml_files(CHART_DIR / "templates")
    assert len(yaml_files) >= 15, f"Expected >=15 template files, got {len(yaml_files)}"

    errors = []
    for yaml_file in yaml_files:
        try:
            content = _read_text(yaml_file)
            if not content.strip():
                errors.append(f"{yaml_file.name}: empty file")
                continue
            # _helpers.tpl and validation-only templates do not render resources.
            if yaml_file.name == "_helpers.tpl":
                if "define" not in content:
                    errors.append(f"{yaml_file.name}: missing define directives")
                continue
            if yaml_file.name.startswith("validate-"):
                if "fail " not in content:
                    errors.append(f"{yaml_file.name}: missing fail directive")
                continue
            # 检查 K8s 资源必需字段（允许在 Helm 注释后）
            if "apiVersion" not in content:
                errors.append(f"{yaml_file.name}: missing apiVersion")
            if "kind" not in content:
                errors.append(f"{yaml_file.name}: missing kind")
        except Exception as e:
            errors.append(f"{yaml_file.name}: {e}")

    assert not errors, "模板文件验证错误:\n" + "\n".join(errors)


def test_all_template_files_contain_helm_directives():
    """所有模板文件（除 _helpers.tpl 外）包含 Helm 模板指令。"""
    yaml_files = _list_yaml_files(CHART_DIR / "templates")
    for yaml_file in yaml_files:
        if yaml_file.name == "_helpers.tpl":
            continue
        content = _read_text(yaml_file)
        # 至少包含一个 Helm 模板表达式
        assert "{{" in content, f"{yaml_file.name}: no Helm directives found"


# ===== 关键模板存在性 =====


@pytest.mark.parametrize("template_name", [
    "_helpers.tpl",
    "namespace.yaml",
    "configmap.yaml",
    "secret.yaml",
    "deployment-web.yaml",
    "service-web.yaml",
    "deployment-worker.yaml",
    "deployment-frontend.yaml",
    "service-frontend.yaml",
    "pvc.yaml",
    "ingress.yaml",
    "networkpolicy.yaml",
    "hpa-web.yaml",
    "hpa-worker.yaml",
    "pdb.yaml",
    "postgresql-statefulset.yaml",
    "redis-statefulset.yaml",
    # P6: 监控模板
    "servicemonitor-web.yaml",
    "servicemonitor-worker.yaml",
    "prometheus-rules.yaml",
    "alertmanager-config.yaml",
    "grafana-dashboard-configmap.yaml",
])
def test_required_template_exists(template_name):
    """必需的模板文件存在。"""
    path = CHART_DIR / "templates" / template_name
    assert path.exists(), f"Template not found: {template_name}"


def test_helm_test_exists():
    """Helm test pod 配置存在。"""
    test_path = CHART_DIR / "templates" / "tests" / "test-connection.yaml"
    assert test_path.exists()


# ===== _helpers.tpl 内容 =====


def test_helpers_defines_comic_name():
    """_helpers.tpl 定义了 comic.name 模板。"""
    content = _read_text(CHART_DIR / "templates" / "_helpers.tpl")
    assert 'define "comic.name"' in content


def test_helpers_defines_comic_fullname():
    """_helpers.tpl 定义了 comic.fullname 模板。"""
    content = _read_text(CHART_DIR / "templates" / "_helpers.tpl")
    assert 'define "comic.fullname"' in content


def test_helpers_defines_comic_labels():
    """_helpers.tpl 定义了 comic.labels 模板。"""
    content = _read_text(CHART_DIR / "templates" / "_helpers.tpl")
    assert 'define "comic.labels"' in content


def test_helpers_defines_comic_selector_labels():
    """_helpers.tpl 定义了 comic.selectorLabels 模板。"""
    content = _read_text(CHART_DIR / "templates" / "_helpers.tpl")
    assert 'define "comic.selectorLabels"' in content


# ===== 部署脚本 =====


def test_deploy_script_exists():
    """deploy.sh 存在。"""
    script = Path(__file__).parent.parent.parent / "deploy" / "scripts" / "deploy.sh"
    assert script.exists()


def test_env_to_k8s_secret_script_exists():
    """env-to-k8s-secret.sh 存在。"""
    script = Path(__file__).parent.parent.parent / "deploy" / "scripts" / "env-to-k8s-secret.sh"
    assert script.exists()


def test_rollback_script_exists():
    """rollback.sh 存在。"""
    script = Path(__file__).parent.parent.parent / "deploy" / "scripts" / "rollback.sh"
    assert script.exists()


# ===== Dockerfile =====


def test_backend_dockerfile_web_exists():
    """backend/Dockerfile.web 存在。"""
    path = Path(__file__).parent.parent.parent / "backend" / "Dockerfile.web"
    assert path.exists()


def test_backend_dockerfile_worker_exists():
    """backend/Dockerfile.worker 存在。"""
    path = Path(__file__).parent.parent.parent / "backend" / "Dockerfile.worker"
    assert path.exists()


def test_backend_dockerignore_exists():
    """backend/.dockerignore 存在。"""
    path = Path(__file__).parent.parent.parent / "backend" / ".dockerignore"
    assert path.exists()


def test_frontend_dockerfile_exists():
    """frontend/Dockerfile 存在。"""
    path = Path(__file__).parent.parent.parent / "frontend" / "Dockerfile"
    assert path.exists()


def test_frontend_nginx_conf_exists():
    """frontend/nginx.conf 存在。"""
    path = Path(__file__).parent.parent.parent / "frontend" / "nginx.conf"
    assert path.exists()


def test_frontend_dockerignore_exists():
    """frontend/.dockerignore 存在。"""
    path = Path(__file__).parent.parent.parent / "frontend" / ".dockerignore"
    assert path.exists()


def test_backend_dockerfile_web_has_healthcheck():
    """Dockerfile.web 包含 HEALTHCHECK 指令。"""
    content = _read_text(Path(__file__).parent.parent.parent / "backend" / "Dockerfile.web")
    assert "HEALTHCHECK" in content
    assert "/health" in content


def test_backend_dockerfile_worker_has_gpu_base():
    """Dockerfile.worker 基于 nvidia/cuda 镜像。"""
    content = _read_text(Path(__file__).parent.parent.parent / "backend" / "Dockerfile.worker")
    assert "nvidia/cuda" in content


def test_frontend_dockerfile_is_multistage():
    """frontend/Dockerfile 是多阶段构建。"""
    content = _read_text(Path(__file__).parent.parent.parent / "frontend" / "Dockerfile")
    assert "FROM node:" in content
    # P7: 兼容 nginx-unprivileged 镜像
    assert "FROM nginx:" in content or "nginx-unprivileged" in content
    assert "AS builder" in content or "as builder" in content


def test_nginx_conf_has_api_proxy():
    """nginx.conf 配置了 /api/ 反向代理。"""
    content = _read_text(Path(__file__).parent.parent.parent / "frontend" / "nginx.conf")
    assert "/api/" in content or "location /api" in content
    assert "proxy_pass" in content


def test_nginx_conf_has_ws_proxy():
    """nginx.conf 配置了 /ws/ WebSocket 代理。"""
    content = _read_text(Path(__file__).parent.parent.parent / "frontend" / "nginx.conf")
    assert "/ws" in content
    assert "Upgrade" in content or "upgrade" in content


# ===== P6: 监控模板 =====


def test_servicemonitor_web_template_has_correct_endpoints():
    """servicemonitor-web.yaml 配置了 /metrics 端点和 30s 间隔。"""
    content = _read_text(CHART_DIR / "templates" / "servicemonitor-web.yaml")
    assert "/metrics" in content
    assert "30s" in content
    assert "backend-web" in content


def test_servicemonitor_worker_template_exists():
    """servicemonitor-worker.yaml 存在且包含 backend-worker。"""
    content = _read_text(CHART_DIR / "templates" / "servicemonitor-worker.yaml")
    assert "backend-worker" in content


def test_prometheus_rules_has_critical_and_warning_alerts():
    """prometheus-rules.yaml 包含 critical 和 warning 级别的报警。"""
    content = _read_text(CHART_DIR / "templates" / "prometheus-rules.yaml")
    assert "critical" in content
    assert "warning" in content
    # 关键报警规则
    assert "CrashLoop" in content or "crash_loop" in content.lower()
    assert "CeleryQueue" in content or "celery_queue" in content.lower()


def test_alertmanager_config_has_secret_backed_operations_receiver():
    """AlertmanagerConfig consumes a secret-backed operations webhook."""
    content = _read_text(CHART_DIR / "templates" / "alertmanager-config.yaml")
    assert "kind: AlertmanagerConfig" in content
    assert "operations-webhook" in content
    assert "webhookConfigs" in content
    assert "urlSecret" in content


def test_grafana_dashboard_configmap_has_dashboards():
    """grafana-dashboard-configmap.yaml 包含 3 个 dashboard JSON。"""
    content = _read_text(CHART_DIR / "templates" / "grafana-dashboard-configmap.yaml")
    assert "api-overview.json" in content
    assert "celery-worker.json" in content
    assert "infrastructure.json" in content
    assert "grafana_dashboard" in content


def test_monitoring_templates_gated_by_monitoring_enabled():
    """所有监控模板受 monitoring.enabled 控制。"""
    monitoring_templates = [
        "servicemonitor-web.yaml",
        "servicemonitor-worker.yaml",
        "prometheus-rules.yaml",
        "alertmanager-config.yaml",
        "grafana-dashboard-configmap.yaml",
    ]
    for name in monitoring_templates:
        content = _read_text(CHART_DIR / "templates" / name)
        assert "monitoring.enabled" in content, f"{name} should be gated by monitoring.enabled"


# ===== P6: 监控栈部署文件 =====


def test_monitoring_dir_exists():
    """deploy/monitoring/ 目录存在。"""
    path = Path(__file__).parent.parent.parent / "deploy" / "monitoring"
    assert path.is_dir()


def test_kube_prometheus_stack_values_exists():
    """kube-prometheus-stack-values.yaml 存在。"""
    path = Path(__file__).parent.parent.parent / "deploy" / "monitoring" / "kube-prometheus-stack-values.yaml"
    assert path.exists()


def test_loki_stack_values_exists():
    """loki-stack-values.yaml 存在。"""
    path = Path(__file__).parent.parent.parent / "deploy" / "monitoring" / "loki-stack-values.yaml"
    assert path.exists()


def test_monitoring_install_script_exists():
    """install.sh 监控栈安装脚本存在。"""
    path = Path(__file__).parent.parent.parent / "deploy" / "monitoring" / "install.sh"
    assert path.exists()


def test_kube_prometheus_stack_values_has_grafana_config():
    """kube-prometheus-stack values 包含 Grafana dashboardProviders 配置。"""
    path = Path(__file__).parent.parent.parent / "deploy" / "monitoring" / "kube-prometheus-stack-values.yaml"
    data = _load_yaml(path)
    assert "grafana" in data
    assert data["grafana"].get("enabled") is True


def test_loki_stack_values_has_persistence():
    """loki-stack values 配置了持久化存储。"""
    path = Path(__file__).parent.parent.parent / "deploy" / "monitoring" / "loki-stack-values.yaml"
    data = _load_yaml(path)
    assert "loki" in data
    assert data["loki"].get("persistence", {}).get("enabled") is True


def test_values_yaml_has_monitoring_section():
    """values.yaml 包含 monitoring 配置块。"""
    path = CHART_DIR / "values.yaml"
    data = _load_yaml(path)
    assert "monitoring" in data
    assert "enabled" in data["monitoring"]
    assert data["monitoring"]["enabled"] is False  # 默认关闭


def test_values_prod_yaml_enables_monitoring():
    """values-prod.yaml 启用了 monitoring。"""
    path = CHART_DIR / "values-prod.yaml"
    data = _load_yaml(path)
    assert "monitoring" in data
    assert data["monitoring"]["enabled"] is True
