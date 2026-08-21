"""Tests for Docker and deployment config."""
import os
import pytest
import yaml


def test_dockerfile_exists():
    """Dockerfile exists at expected path."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "deploy", "Dockerfile"
    )
    assert os.path.exists(path)


def test_dockerfile_is_multi_stage():
    """Dockerfile uses multi-stage build."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "deploy", "Dockerfile"
    )
    with open(path) as f:
        content = f.read()
    assert "AS builder" in content
    assert "AS runtime" in content
    assert "COPY --from=builder" in content


def test_dockerfile_runs_as_non_root():
    """Dockerfile creates non-root user."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "deploy", "Dockerfile"
    )
    with open(path) as f:
        content = f.read()
    assert "useradd" in content or "adduser" in content
    assert "USER" in content


def test_docker_compose_has_required_services():
    """docker-compose.yml includes all required services."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "deploy", "docker-compose.yml"
    )
    with open(path) as f:
        compose = yaml.safe_load(f)
    services = compose.get("services", {})
    required = ["backend", "postgres", "redis", "nginx"]
    for svc in required:
        assert svc in services, f"Missing service: {svc}"
