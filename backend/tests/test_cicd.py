"""Phase 8 P8: CI/CD 流水线配置测试"""
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
GITHUB_DIR = REPO_ROOT / ".github"
WORKFLOWS_DIR = GITHUB_DIR / "workflows"


class TestCIWorkflows:
    """CI 工作流配置测试"""

    def test_workflows_dir_exists(self):
        assert WORKFLOWS_DIR.exists(), ".github/workflows 目录必须存在"

    def test_ci_yml_exists(self):
        assert (WORKFLOWS_DIR / "ci.yml").exists()

    def test_release_yml_exists(self):
        assert (WORKFLOWS_DIR / "release.yml").exists()

    def test_deploy_yml_exists(self):
        assert (WORKFLOWS_DIR / "deploy.yml").exists()

    def test_ci_yml_has_backend_test_job(self):
        content = (WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
        assert "backend-test" in content
        assert "pytest" in content

    def test_ci_yml_has_frontend_test_job(self):
        content = (WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
        assert "frontend-test" in content
        assert "vitest" in content or "npm test" in content

    def test_ci_yml_has_helm_lint_job(self):
        content = (WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
        assert "helm-lint" in content
        assert "helm lint" in content

    def test_ci_yml_has_security_scan_job(self):
        content = (WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
        assert "security-scan" in content
        assert "pip-audit" in content
        assert "gitleaks" in content

    def test_ci_yml_triggers_on_push_and_pr(self):
        content = (WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
        assert "on:" in content
        assert "push:" in content
        assert "pull_request:" in content

    def test_ci_yml_uses_python_matrix(self):
        content = (WORKFLOWS_DIR / "ci.yml").read_text(encoding="utf-8")
        assert "matrix" in content
        assert "3.11" in content
        assert "3.13" in content


class TestReleaseWorkflow:
    def test_release_yml_builds_three_images(self):
        content = (WORKFLOWS_DIR / "release.yml").read_text(encoding="utf-8")
        assert "build-backend-web" in content
        assert "build-backend-worker" in content
        assert "build-frontend" in content

    def test_release_yml_uses_ghcr(self):
        content = (WORKFLOWS_DIR / "release.yml").read_text(encoding="utf-8")
        assert "ghcr.io" in content

    def test_release_yml_generates_sbom(self):
        content = (WORKFLOWS_DIR / "release.yml").read_text(encoding="utf-8")
        assert "sbom" in content.lower()

    def test_release_yml_triggers_on_tag(self):
        content = (WORKFLOWS_DIR / "release.yml").read_text(encoding="utf-8")
        assert "tags:" in content
        assert "v*" in content

    def test_release_yml_has_trivy_scan(self):
        content = (WORKFLOWS_DIR / "release.yml").read_text(encoding="utf-8")
        assert "trivy" in content.lower()

    def test_release_yml_builds_desktop(self):
        content = (WORKFLOWS_DIR / "release.yml").read_text(encoding="utf-8")
        assert "build-desktop" in content


class TestDeployWorkflow:
    def test_deploy_yml_has_staging_and_production(self):
        content = (WORKFLOWS_DIR / "deploy.yml").read_text(encoding="utf-8")
        assert "deploy-staging" in content
        assert "deploy-production" in content

    def test_deploy_yml_uses_helm(self):
        content = (WORKFLOWS_DIR / "deploy.yml").read_text(encoding="utf-8")
        assert "helm" in content.lower() or "deploy.sh" in content

    def test_deploy_yml_has_rollback(self):
        content = (WORKFLOWS_DIR / "deploy.yml").read_text(encoding="utf-8")
        assert "rollback" in content.lower()

    def test_deploy_yml_has_smoke_test(self):
        content = (WORKFLOWS_DIR / "deploy.yml").read_text(encoding="utf-8")
        assert "smoke" in content.lower() or "health" in content.lower()

    def test_deploy_yml_requires_environment(self):
        content = (WORKFLOWS_DIR / "deploy.yml").read_text(encoding="utf-8")
        assert "environment:" in content


class TestDependabot:
    def test_dependabot_yml_exists(self):
        assert (GITHUB_DIR / "dependabot.yml").exists()

    def test_dependabot_has_pip_ecosystem(self):
        content = (GITHUB_DIR / "dependabot.yml").read_text(encoding="utf-8")
        assert "pip" in content
        assert "/backend" in content

    def test_dependabot_has_npm_ecosystem(self):
        content = (GITHUB_DIR / "dependabot.yml").read_text(encoding="utf-8")
        assert "npm" in content

    def test_dependabot_has_github_actions_ecosystem(self):
        content = (GITHUB_DIR / "dependabot.yml").read_text(encoding="utf-8")
        assert "github-actions" in content

    def test_dependabot_has_docker_ecosystem(self):
        content = (GITHUB_DIR / "dependabot.yml").read_text(encoding="utf-8")
        assert "docker" in content


class TestDeployScript:
    def test_deploy_script_exists(self):
        assert (REPO_ROOT / "deploy" / "scripts" / "deploy.sh").exists()

    def test_deploy_script_supports_image_tag(self):
        content = (REPO_ROOT / "deploy" / "scripts" / "deploy.sh").read_text(encoding="utf-8")
        # 应支持 IMAGE_TAG 参数
        assert "IMAGE_TAG" in content or "image_tag" in content.lower() or "imageTag" in content

    def test_pre_deploy_check_fails_closed_without_image_inspector(self):
        content = (REPO_ROOT / "deploy" / "scripts" / "pre-deploy-check.sh").read_text(
            encoding="utf-8"
        )
        assert "require_command docker" in content
        assert 'fail "$1 is unavailable"' in content
        assert "docker manifest inspect" in content
        assert 'print_pass "镜像引用已解析' not in content
