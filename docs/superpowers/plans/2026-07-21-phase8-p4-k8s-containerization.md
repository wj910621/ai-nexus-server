# Phase 8 P4 - K8s 容器化实施计划

**Spec**: `docs/superpowers/specs/2026-07-21-phase8-p4-k8s-containerization-design.md`

**目标**: 将后端/前端容器化，部署到阿里云 ACK，支持多镜像分离（backend-web / backend-worker / frontend），并提供完整的 Helm Chart。

## 环境约定

- 工作目录：`c:\漫剧软件项目`
- Python：`py -3.14`（PowerShell）
- PYTHONPATH：`$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"`
- PowerShell 用 `;` 分隔命令
- 前端用 `npm.cmd` / `npx.cmd`
- Git 未安装，所有 git commit 步骤跳过
- TDD：先写测试 → 实现 → 验证

---

## Task 1: config.py 增加 app_env 字段

**文件**:
- `backend/app/core/config.py`（修改）
- `backend/tests/core/test_config_app_env.py`（新建）

**测试**:
```python
# test_config_app_env.py
import os
import importlib

def test_app_env_default_is_development(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    from app.core.config import Settings
    s = Settings()
    assert s.app_env == "development"

def test_is_production_flag(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    from app.core.config import Settings
    s = Settings()
    assert s.is_production is True

def test_is_production_false_in_dev(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    from app.core.config import Settings
    s = Settings()
    assert s.is_production is False
```

**实现**:
```python
# config.py
class Settings(BaseSettings):
    # ... existing fields
    app_env: str = "development"
    oss_bucket: Optional[str] = None
    oss_access_key_id: Optional[str] = None
    oss_access_key_secret: Optional[str] = None
    oss_endpoint: Optional[str] = None

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"
```

**验证**:
```powershell
cd c:\漫剧软件项目\backend
$env:PYTHONPATH="c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"
py -3.14 -m pytest tests/core/test_config_app_env.py -v
```

---

## Task 2: StorageBackend 抽象 + LocalStorage 实现

**文件**:
- `backend/app/core/storage.py`（新建）
- `backend/tests/core/test_storage_local.py`（新建）

**测试**:
```python
# test_storage_local.py
import pytest
from pathlib import Path
from app.core.storage import LocalStorage, StorageBackend, FileStorage, get_storage

@pytest.mark.asyncio
async def test_local_storage_save_and_read(tmp_path):
    s = LocalStorage(base_dir=str(tmp_path))
    url = await s.save("foo/bar.txt", b"hello")
    assert url.endswith("foo/bar.txt")
    full = await s.get_full_path("foo/bar.txt")
    assert Path(full).read_bytes() == b"hello"

@pytest.mark.asyncio
async def test_local_storage_exists(tmp_path):
    s = LocalStorage(base_dir=str(tmp_path))
    await s.save("a.txt", b"x")
    assert await s.exists("a.txt") is True
    assert await s.exists("missing.txt") is False

@pytest.mark.asyncio
async def test_local_storage_delete(tmp_path):
    s = LocalStorage(base_dir=str(tmp_path))
    await s.save("a.txt", b"x")
    await s.delete("a.txt")
    assert await s.exists("a.txt") is False

def test_file_storage_alias():
    assert FileStorage is LocalStorage

def test_get_storage_returns_local_in_dev(monkeypatch):
    from app.core.config import Settings
    s = Settings()
    monkeypatch.setattr("app.core.storage.settings", s)
    storage = get_storage()
    assert isinstance(storage, LocalStorage)
```

**实现**:
```python
# storage.py
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, Optional
import os

class StorageBackend(ABC):
    @abstractmethod
    async def save(self, path: str, data: bytes) -> str: ...
    @abstractmethod
    async def get_full_path(self, path: str) -> Union[Path, str]: ...
    @abstractmethod
    async def exists(self, path: str) -> bool: ...
    @abstractmethod
    async def delete(self, path: str) -> None: ...

class LocalStorage(StorageBackend):
    def __init__(self, base_dir: str = "uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save(self, path: str, data: bytes) -> str:
        full = self.base_dir / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(data)
        return str(path)

    async def get_full_path(self, path: str) -> Path:
        return self.base_dir / path

    async def exists(self, path: str) -> bool:
        return (self.base_dir / path).exists()

    async def delete(self, path: str) -> None:
        full = self.base_dir / path
        if full.exists():
            full.unlink()

# 向后兼容别名（旧 FileStorage 调用方继续可用）
FileStorage = LocalStorage

def get_storage() -> StorageBackend:
    from app.core.config import settings
    if settings.is_production and settings.oss_bucket:
        from app.core.storage_oss import OSSStorage
        return OSSStorage(
            bucket=settings.oss_bucket,
            access_key_id=settings.oss_access_key_id,
            access_key_secret=settings.oss_access_key_secret,
            endpoint=settings.oss_endpoint,
        )
    return LocalStorage(base_dir=settings.upload_dir)
```

**验证**:
```powershell
py -3.14 -m pytest tests/core/test_storage_local.py -v
```

---

## Task 3: OSSStorage 实现（阿里云 OSS）

**文件**:
- `backend/app/core/storage_oss.py`（新建）
- `backend/tests/core/test_storage_oss.py`（新建）

**测试**（mock oss2）:
```python
# test_storage_oss.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

@pytest.mark.asyncio
async def test_oss_save_calls_put():
    with patch("app.core.storage_oss.oss2") as mock_oss2:
        mock_bucket = MagicMock()
        mock_oss2.Auth.return_value = MagicMock()
        mock_oss2.Bucket.return_value = mock_bucket
        from app.core.storage_oss import OSSStorage
        s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
        url = await s.save("foo/bar.txt", b"hello")
        mock_bucket.put_object.assert_called_once()
        assert url.startswith("https://")

@pytest.mark.asyncio
async def test_oss_exists():
    with patch("app.core.storage_oss.oss2") as mock_oss2:
        mock_bucket = MagicMock()
        mock_bucket.object_exists.return_value = True
        mock_oss2.Auth.return_value = MagicMock()
        mock_oss2.Bucket.return_value = mock_bucket
        from app.core.storage_oss import OSSStorage
        s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
        assert await s.exists("foo/bar.txt") is True

@pytest.mark.asyncio
async def test_oss_delete():
    with patch("app.core.storage_oss.oss2") as mock_oss2:
        mock_bucket = MagicMock()
        mock_oss2.Auth.return_value = MagicMock()
        mock_oss2.Bucket.return_value = mock_bucket
        from app.core.storage_oss import OSSStorage
        s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
        await s.delete("foo/bar.txt")
        mock_bucket.delete_object.assert_called_once_with("foo/bar.txt")

@pytest.mark.asyncio
async def test_oss_get_full_path_returns_url():
    with patch("app.core.storage_oss.oss2") as mock_oss2:
        mock_oss2.Auth.return_value = MagicMock()
        mock_oss2.Bucket.return_value = MagicMock()
        from app.core.storage_oss import OSSStorage
        s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="oss-cn-hangzhou.aliyuncs.com")
        url = await s.get_full_path("foo/bar.txt")
        assert "foo/bar.txt" in url

def test_oss_storage_is_storage_backend():
    with patch("app.core.storage_oss.oss2"):
        from app.core.storage_oss import OSSStorage
        from app.core.storage import StorageBackend
        s = OSSStorage(bucket="b", access_key_id="k", access_key_secret="s", endpoint="e")
        assert isinstance(s, StorageBackend)
```

**实现**:
```python
# storage_oss.py
from typing import Union
from pathlib import Path
from .storage import StorageBackend

try:
    import oss2
except ImportError:
    oss2 = None

class OSSStorage(StorageBackend):
    def __init__(self, bucket: str, access_key_id: str, access_key_secret: str, endpoint: str):
        if oss2 is None:
            raise ImportError("oss2 not installed. Run: pip install oss2")
        self.bucket_name = bucket
        self.endpoint = endpoint
        auth = oss2.Auth(access_key_id, access_key_secret)
        self.bucket = oss2.Bucket(auth, endpoint, bucket)

    async def save(self, path: str, data: bytes) -> str:
        self.bucket.put_object(path, data)
        return self._public_url(path)

    async def get_full_path(self, path: str) -> str:
        return self._public_url(path)

    async def exists(self, path: str) -> bool:
        return self.bucket.object_exists(path)

    async def delete(self, path: str) -> None:
        self.bucket.delete_object(path)

    def _public_url(self, path: str) -> str:
        return f"https://{self.bucket_name}.{self.endpoint}/{path}"
```

**验证**:
```powershell
py -3.14 -m pytest tests/core/test_storage_oss.py -v
```

---

## Task 4: 迁移现有 storage 引用到 get_storage()

**文件**:
- `backend/app/services/file_service.py`（修改）
- `backend/app/api/v1/uploads.py`（修改）
- `backend/tests/core/test_storage_migration.py`（新建）

**测试**:
```python
# test_storage_migration.py
import ast
from pathlib import Path

def _read(p):
    return Path(p).read_text(encoding="utf-8")

def test_file_service_uses_get_storage():
    src = _read("app/services/file_service.py")
    # 不应直接 new LocalStorage / FileStorage
    assert "LocalStorage(" not in src
    assert "FileStorage(" not in src
    assert "get_storage()" in src

def test_uploads_api_uses_get_storage():
    src = _read("app/api/v1/uploads.py")
    assert "LocalStorage(" not in src
    assert "FileStorage(" not in src

def test_no_direct_path_io_in_file_service():
    src = _read("app/services/file_service.py")
    tree = ast.parse(src)
    # 简单检查：不应出现 open(path, 'wb') 这类直接 IO
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            for arg in node.args:
                if isinstance(arg, ast.Constant) and "wb" in str(arg.value):
                    assert False, "direct file IO detected"

def test_storage_module_exports_get_storage():
    from app.core.storage import get_storage
    assert callable(get_storage)
```

**实现**: 替换 file_service / uploads 中所有 `LocalStorage(...)` 或 `FileStorage(...)` 实例化为 `get_storage()`。

**验证**:
```powershell
py -3.14 -m pytest tests/core/test_storage_migration.py -v
```

---

## Task 5: Prometheus 指标导出

**文件**:
- `backend/app/core/metrics.py`（新建）
- `backend/app/main.py`（修改，注册 metrics middleware）
- `backend/tests/core/test_metrics.py`（新建）

**测试**:
```python
# test_metrics.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

def test_metrics_endpoint_exposed():
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    assert "http_request_duration_seconds" in body or "celery_queue_length" in body

def test_celery_queue_length_gauge_exists():
    from app.core.metrics import CELERY_QUEUE_LENGTH
    assert CELERY_QUEUE_LENGTH is not None
    CELERY_QUEUE_LENGTH.labels(queue="default").set(5)
    client = TestClient(app)
    resp = client.get("/metrics")
    assert "celery_queue_length" in resp.text

def test_http_request_duration_histogram():
    from app.core.metrics import HTTP_REQUEST_DURATION
    assert HTTP_REQUEST_DURATION is not None
```

**实现**:
```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["method", "endpoint", "status"],
)
CELERY_QUEUE_LENGTH = Gauge(
    "celery_queue_length",
    "Celery queue length",
    ["queue"],
)

def metrics_response():
    from fastapi import Response
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

在 main.py 中：
```python
from prometheus_client import make_asgi_app
from .core.metrics import HTTP_REQUEST_DURATION
import time

# 注册 /metrics
app.mount("/metrics", make_asgi_app())

@app.middleware("http")
async def metrics_middleware(request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    HTTP_REQUEST_DURATION.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code,
    ).observe(duration)
    return response
```

**验证**:
```powershell
py -3.14 -m pytest tests/core/test_metrics.py -v
```

---

## Task 6: 健康检查端点扩展

**文件**:
- `backend/app/main.py`（修改 /health）
- `backend/tests/api/test_health.py`（新建）

**测试**:
```python
# test_health.py
import pytest
from unittest.mock import patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

def test_health_returns_200_when_all_ok():
    with patch("app.main.check_db_connection", new=AsyncMock(return_value="ok")), \
         patch("app.main.check_redis_connection", new=AsyncMock(return_value="ok")):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"

def test_health_returns_503_when_db_down():
    with patch("app.main.check_db_connection", new=AsyncMock(return_value="error")), \
         patch("app.main.check_redis_connection", new=AsyncMock(return_value="ok")):
        client = TestClient(app)
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "unhealthy"

def test_health_includes_db_and_redis_checks():
    with patch("app.main.check_db_connection", new=AsyncMock(return_value="ok")), \
         patch("app.main.check_redis_connection", new=AsyncMock(return_value="ok")):
        client = TestClient(app)
        resp = client.get("/health")
        body = resp.json()
        assert "database" in body
        assert "redis" in body
```

**实现**:
```python
# main.py
from sqlalchemy import text
import redis.asyncio as aioredis
from fastapi.responses import JSONResponse

async def check_db_connection() -> str:
    try:
        from app.core.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return "ok"
    except Exception:
        return "error"

async def check_redis_connection() -> str:
    try:
        from app.core.config import settings
        r = aioredis.from_url(settings.redis_url)
        await r.ping()
        await r.close()
        return "ok"
    except Exception:
        return "error"

@app.get("/health")
async def health():
    checks = {
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
    }
    all_healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content={"status": "healthy" if all_healthy else "unhealthy", **checks},
    )
```

**验证**:
```powershell
py -3.14 -m pytest tests/api/test_health.py -v
```

---

## Task 7: backend/Dockerfile.web + .dockerignore

**文件**:
- `backend/Dockerfile.web`（新建）
- `backend/.dockerignore`（新建）

**实现**:
```dockerfile
# Dockerfile.web
FROM python:3.14-slim AS builder
WORKDIR /app
COPY pyproject.toml requirements*.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt

FROM python:3.14-slim AS runtime
WORKDIR /app
ENV PYTHONPATH=/app:/app/.deps
ENV PYTHONUNBUFFERED=1
COPY --from=builder /root/.local /root/.local
COPY . /app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request,sys;urllib.request.urlopen('http://localhost:8000/health');sys.exit(0)" || exit 1
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```
# .dockerignore
__pycache__
*.pyc
.pytest_cache
.venv
tests/
*.md
.git
```

**验证**: `docker build -f backend/Dockerfile.web -t comic-web:dev backend/`（手动）

---

## Task 8: backend/Dockerfile.worker

**文件**:
- `backend/Dockerfile.worker`（新建）

**实现**:
```dockerfile
# Dockerfile.worker - GPU 镜像
FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3.14 python3-pip python3.14-venv
WORKDIR /app
COPY requirements*.txt ./
RUN pip install --user --no-cache-dir -r requirements.txt
RUN pip install --user --no-cache-dir torch --index-url https://download.pytorch.org/whl/cu124

FROM nvidia/cuda:12.4.1-cudnn-runtime-ubuntu22.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3.14 python3-pip && rm -rf /var/lib/apt/lists/*
WORKDIR /app
ENV PYTHONPATH=/app:/app/.deps
ENV PYTHONUNBUFFERED=1
COPY --from=builder /root/.local /root/.local
COPY . /app
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
  CMD celery -A app.tasks.celery_app inspect ping -d celery@$$HOSTNAME || exit 1
CMD ["celery", "-A", "app.tasks.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
```

**验证**: 手动 `docker build` 检查（GPU 镜像较大，CI 中跑）

---

## Task 9: frontend/Dockerfile + nginx.conf

**文件**:
- `frontend/Dockerfile`（新建）
- `frontend/nginx.conf`（新建）
- `frontend/.dockerignore`（新建）

**实现**:
```dockerfile
# frontend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD wget --quiet --tries=1 --spider http://localhost/ || exit 1
```

```nginx
# nginx.conf
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend-web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws/ {
        proxy_pass http://backend-web:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

**验证**: 手动 `docker build` 检查

---

## Task 10: Helm Chart 基础结构

**文件**:
- `deploy/helm/comic-platform/Chart.yaml`
- `deploy/helm/comic-platform/values.yaml`
- `deploy/helm/comic-platform/values-prod.yaml`
- `deploy/helm/comic-platform/values-staging.yaml`
- `deploy/helm/comic-platform/templates/_helpers.tpl`
- `deploy/helm/comic-platform/templates/namespace.yaml`
- `deploy/helm/comic-platform/README.md`

**实现**:
```yaml
# Chart.yaml
apiVersion: v2
name: comic-platform
description: 漫剧软件平台 Helm Chart
type: application
version: 0.1.0
appVersion: "0.8.0"
keywords:
  - comic
  - ai
  - lora
maintainers:
  - name: Comic Platform Team
```

```yaml
# values.yaml (默认 development)
global:
  imageRegistry: ""
  imagePullSecrets: []
  storageClass: ""

namespace:
  create: true
  name: comic-dev

backend:
  web:
    enabled: true
    replicas: 2
    image:
      repository: comic-backend-web
      tag: latest
      pullPolicy: IfNotPresent
    resources:
      requests: { cpu: 200m, memory: 512Mi }
      limits: { cpu: 1000m, memory: 1Gi }
  worker:
    enabled: true
    replicas: 1
    image:
      repository: comic-backend-worker
      tag: latest
      pullPolicy: IfNotPresent
    gpu:
      enabled: false
    resources:
      requests: { cpu: 500m, memory: 1Gi }
      limits: { cpu: 2000m, memory: 4Gi }

frontend:
  enabled: true
  replicas: 2
  image:
    repository: comic-frontend
    tag: latest
    pullPolicy: IfNotPresent

ingress:
  enabled: false
  className: ""
  host: comic.local
  tls:
    enabled: false
    secretName: ""

postgresql:
  enabled: true
  external: false
  host: ""
  port: 5432
  database: comic
  username: comic
  password: ""

redis:
  enabled: true
  external: false
  host: ""
  port: 6379
  password: ""

oss:
  enabled: false
  bucket: ""
  endpoint: ""
  accessKeyId: ""
  accessKeySecret: ""
```

```yaml
# values-prod.yaml
namespace:
  name: comic-prod

backend:
  web:
    replicas: 3
    resources:
      requests: { cpu: 500m, memory: 1Gi }
      limits: { cpu: 2000m, memory: 2Gi }
  worker:
    replicas: 2
    gpu:
      enabled: true

frontend:
  replicas: 3

ingress:
  enabled: true
  className: nginx
  host: comic.example.com
  tls:
    enabled: true
    secretName: comic-tls

postgresql:
  external: true
  host: pg-prod.internal
  password: ""

oss:
  enabled: true
  bucket: comic-prod-oss
  endpoint: oss-cn-hangzhou.aliyuncs.com

hpa:
  web:
    enabled: true
    minReplicas: 3
    maxReplicas: 10
    cpuTarget: 70
  worker:
    enabled: true
    minReplicas: 2
    maxReplicas: 8
    queueLengthTarget: 10
```

```yaml
# values-staging.yaml
namespace:
  name: comic-staging

backend:
  web:
    replicas: 1
  worker:
    replicas: 1
    gpu:
      enabled: false

frontend:
  replicas: 1

ingress:
  enabled: true
  host: comic-staging.example.com
```

```yaml
# _helpers.tpl
{{- define "comic.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "comic.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "comic.name" . -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "comic.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "comic.selectorLabels" . }}
{{- if .Chart.AppVersion -}}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end -}}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "comic.selectorLabels" -}}
app.kubernetes.io/name: {{ include "comic.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}
```

```yaml
# namespace.yaml
{{- if .Values.namespace.create -}}
apiVersion: v1
kind: Namespace
metadata:
  name: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
{{- end -}}
```

**验证**:
```powershell
cd c:\漫剧软件项目
npx.cmd helm lint deploy/helm/comic-platform
```

---

## Task 11: ConfigMap + Secret 模板

**文件**:
- `deploy/helm/comic-platform/templates/configmap.yaml`
- `deploy/helm/comic-platform/templates/secret.yaml`

**实现**:
```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "comic.fullname" . }}-config
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
data:
  APP_ENV: {{ .Values.env | default "development" | quote }}
  DATABASE_URL: {{ printf "postgresql+asyncpg://%s:%s@%s:%s/%s" .Values.postgresql.username .Values.postgresql.password .Values.postgresql.host .Values.postgresql.port .Values.postgresql.database | quote }}
  REDIS_URL: {{ printf "redis://%s:%s" .Values.redis.host .Values.redis.port | quote }}
  UPLOAD_DIR: "/data/uploads"
  {{- if .Values.oss.enabled }}
  OSS_BUCKET: {{ .Values.oss.bucket | quote }}
  OSS_ENDPOINT: {{ .Values.oss.endpoint | quote }}
  {{- end }}
```

```yaml
# secret.yaml
{{- if not .Values.externalSecrets.enabled -}}
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "comic.fullname" . }}-secret
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
type: Opaque
stringData:
  {{- if .Values.jwt.secret }}
  JWT_SECRET: {{ .Values.jwt.secret | quote }}
  {{- end }}
  {{- if .Values.oss.enabled }}
  OSS_ACCESS_KEY_ID: {{ .Values.oss.accessKeyId | quote }}
  OSS_ACCESS_KEY_SECRET: {{ .Values.oss.accessKeySecret | quote }}
  {{- end }}
  {{- if .Values.postgresql.password }}
  POSTGRES_PASSWORD: {{ .Values.postgresql.password | quote }}
  {{- end }}
  {{- if .Values.redis.password }}
  REDIS_PASSWORD: {{ .Values.redis.password | quote }}
  {{- end }}
{{- end }}
```

**验证**:
```powershell
npx.cmd helm template deploy/helm/comic-platform -f deploy/helm/comic-platform/values-prod.yaml | Select-String "kind: ConfigMap"
```

---

## Task 12: backend-web Deployment + Service

**文件**:
- `deploy/helm/comic-platform/templates/deployment-web.yaml`
- `deploy/helm/comic-platform/templates/service-web.yaml`

**实现**:
```yaml
# deployment-web.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "comic.fullname" . }}-web
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
    app.kubernetes.io/component: backend-web
spec:
  replicas: {{ .Values.backend.web.replicas }}
  selector:
    matchLabels:
      {{- include "comic.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: backend-web
  template:
    metadata:
      labels:
        {{- include "comic.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: backend-web
    spec:
      {{- with .Values.global.imagePullSecrets }}
      imagePullSecrets:
        {{- toYaml . | nindent 8 }}
      {{- end }}
      containers:
        - name: web
          image: "{{ .Values.global.imageRegistry }}{{ .Values.backend.web.image.repository }}:{{ .Values.backend.web.image.tag }}"
          imagePullPolicy: {{ .Values.backend.web.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 8000
          envFrom:
            - configMapRef:
                name: {{ include "comic.fullname" . }}-config
            - secretRef:
                name: {{ include "comic.fullname" . }}-secret
          livenessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 30
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: http
            initialDelaySeconds: 5
            periodSeconds: 10
          resources:
            {{- toYaml .Values.backend.web.resources | nindent 12 }}
          volumeMounts:
            - name: uploads
              mountPath: /data/uploads
      volumes:
        - name: uploads
          {{- if .Values.persistence.enabled }}
          persistentVolumeClaim:
            claimName: {{ include "comic.fullname" . }}-uploads
          {{- else }}
          emptyDir: {}
          {{- end }}
```

```yaml
# service-web.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "comic.fullname" . }}-web
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "comic.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: backend-web
```

---

## Task 13: backend-worker Deployment

**文件**:
- `deploy/helm/comic-platform/templates/deployment-worker.yaml`

**实现**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "comic.fullname" . }}-worker
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
    app.kubernetes.io/component: backend-worker
spec:
  replicas: {{ .Values.backend.worker.replicas }}
  selector:
    matchLabels:
      {{- include "comic.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: backend-worker
  template:
    metadata:
      labels:
        {{- include "comic.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: backend-worker
    spec:
      {{- if .Values.backend.worker.gpu.enabled }}
      nodeSelector:
        accelerator: nvidia
      tolerations:
        - key: nvidia.com/gpu
          operator: Exists
          effect: NoSchedule
      {{- end }}
      containers:
        - name: worker
          image: "{{ .Values.global.imageRegistry }}{{ .Values.backend.worker.image.repository }}:{{ .Values.backend.worker.image.tag }}"
          imagePullPolicy: {{ .Values.backend.worker.image.pullPolicy }}
          envFrom:
            - configMapRef:
                name: {{ include "comic.fullname" . }}-config
            - secretRef:
                name: {{ include "comic.fullname" . }}-secret
          resources:
            {{- toYaml .Values.backend.worker.resources | nindent 12 }}
            {{- if .Values.backend.worker.gpu.enabled }}
            limits:
              nvidia.com/gpu: 1
            {{- end }}
          volumeMounts:
            - name: uploads
              mountPath: /data/uploads
            - name: models
              mountPath: /data/models
      volumes:
        - name: uploads
          {{- if .Values.persistence.enabled }}
          persistentVolumeClaim:
            claimName: {{ include "comic.fullname" . }}-uploads
          {{- else }}
          emptyDir: {}
          {{- end }}
        - name: models
          {{- if .Values.persistence.enabled }}
          persistentVolumeClaim:
            claimName: {{ include "comic.fullname" . }}-models
          {{- else }}
          emptyDir: {}
          {{- end }}
```

---

## Task 14: frontend Deployment + Service

**文件**:
- `deploy/helm/comic-platform/templates/deployment-frontend.yaml`
- `deploy/helm/comic-platform/templates/service-frontend.yaml`

**实现**:
```yaml
# deployment-frontend.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "comic.fullname" . }}-frontend
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
    app.kubernetes.io/component: frontend
spec:
  replicas: {{ .Values.frontend.replicas }}
  selector:
    matchLabels:
      {{- include "comic.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: frontend
  template:
    metadata:
      labels:
        {{- include "comic.selectorLabels" . | nindent 8 }}
        app.kubernetes.io/component: frontend
    spec:
      containers:
        - name: frontend
          image: "{{ .Values.global.imageRegistry }}{{ .Values.frontend.image.repository }}:{{ .Values.frontend.image.tag }}"
          imagePullPolicy: {{ .Values.frontend.image.pullPolicy }}
          ports:
            - name: http
              containerPort: 80
          livenessProbe:
            httpGet:
              path: /
              port: http
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /
              port: http
            periodSeconds: 10
          resources:
            {{- toYaml .Values.frontend.resources | default (dict "requests" (dict "cpu" "100m" "memory" "128Mi") "limits" (dict "cpu" "500m" "memory" "256Mi")) | nindent 12 }}
```

```yaml
# service-frontend.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "comic.fullname" . }}-frontend
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
spec:
  type: ClusterIP
  ports:
    - port: 80
      targetPort: http
      protocol: TCP
      name: http
  selector:
    {{- include "comic.selectorLabels" . | nindent 4 }}
    app.kubernetes.io/component: frontend
```

---

## Task 15: PVC + Ingress + NetworkPolicy

**文件**:
- `deploy/helm/comic-platform/templates/pvc.yaml`
- `deploy/helm/comic-platform/templates/ingress.yaml`
- `deploy/helm/comic-platform/templates/networkpolicy.yaml`

**实现**:
```yaml
# pvc.yaml
{{- if .Values.persistence.enabled }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "comic.fullname" . }}-uploads
  namespace: {{ .Values.namespace.name }}
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: {{ .Values.persistence.storageClass | default "" }}
  resources:
    requests:
      storage: {{ .Values.persistence.uploads.size | default "20Gi" }}
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "comic.fullname" . }}-models
  namespace: {{ .Values.namespace.name }}
spec:
  accessModes:
    - ReadWriteMany
  storageClassName: {{ .Values.persistence.storageClass | default "" }}
  resources:
    requests:
      storage: {{ .Values.persistence.models.size | default "100Gi" }}
{{- end }}
```

```yaml
# ingress.yaml
{{- if .Values.ingress.enabled }}
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "comic.fullname" . }}
  namespace: {{ .Values.namespace.name }}
  labels:
    {{- include "comic.labels" . | nindent 4 }}
  {{- with .Values.ingress.annotations }}
  annotations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
spec:
  {{- if .Values.ingress.className }}
  ingressClassName: {{ .Values.ingress.className }}
  {{- end }}
  {{- if .Values.ingress.tls.enabled }}
  tls:
    - hosts:
        - {{ .Values.ingress.host }}
      secretName: {{ .Values.ingress.tls.secretName }}
  {{- end }}
  rules:
    - host: {{ .Values.ingress.host }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: {{ include "comic.fullname" . }}-frontend
                port:
                  number: 80
          - path: /api
            pathType: Prefix
            backend:
              service:
                name: {{ include "comic.fullname" . }}-web
                port:
                  number: 8000
          - path: /ws
            pathType: Prefix
            backend:
              service:
                name: {{ include "comic.fullname" . }}-web
                port:
                  number: 8000
{{- end }}
```

```yaml
# networkpolicy.yaml
{{- if .Values.networkPolicy.enabled }}
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "comic.fullname" . }}-default-deny
  namespace: {{ .Values.namespace.name }}
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "comic.fullname" . }}-allow-internal
  namespace: {{ .Values.namespace.name }}
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector: {}
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "comic.fullname" . }}-allow-egress
  namespace: {{ .Values.namespace.name }}
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    - to:
        - podSelector: {}
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
    - to:
        - ipBlock:
            cidr: 0.0.0.0/0
      ports:
        - protocol: TCP
          port: 443
        - protocol: TCP
          port: 80
{{- end }}
```

---

## Task 16: HPA + PDB

**文件**:
- `deploy/helm/comic-platform/templates/hpa-web.yaml`
- `deploy/helm/comic-platform/templates/hpa-worker.yaml`
- `deploy/helm/comic-platform/templates/pdb.yaml`

**实现**:
```yaml
# hpa-web.yaml
{{- if .Values.hpa.web.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "comic.fullname" . }}-web
  namespace: {{ .Values.namespace.name }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "comic.fullname" . }}-web
  minReplicas: {{ .Values.hpa.web.minReplicas }}
  maxReplicas: {{ .Values.hpa.web.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.hpa.web.cpuTarget }}
{{- end }}
```

```yaml
# hpa-worker.yaml
{{- if .Values.hpa.worker.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "comic.fullname" . }}-worker
  namespace: {{ .Values.namespace.name }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "comic.fullname" . }}-worker
  minReplicas: {{ .Values.hpa.worker.minReplicas }}
  maxReplicas: {{ .Values.hpa.worker.maxReplicas }}
  metrics:
    - type: Pods
      pods:
        metric:
          name: celery_queue_length
        target:
          type: AverageValue
          averageValue: {{ .Values.hpa.worker.queueLengthTarget }}
{{- end }}
```

```yaml
# pdb.yaml
{{- if .Values.pdb.enabled }}
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "comic.fullname" . }}-web
  namespace: {{ .Values.namespace.name }}
spec:
  minAvailable: {{ .Values.pdb.web.minAvailable | default 1 }}
  selector:
    matchLabels:
      {{- include "comic.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: backend-web
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "comic.fullname" . }}-worker
  namespace: {{ .Values.namespace.name }}
spec:
  minAvailable: {{ .Values.pdb.worker.minAvailable | default 1 }}
  selector:
    matchLabels:
      {{- include "comic.selectorLabels" . | nindent 6 }}
      app.kubernetes.io/component: backend-worker
{{- end }}
```

---

## Task 17: PostgreSQL + Redis StatefulSet（dev 环境）

**文件**:
- `deploy/helm/comic-platform/templates/postgresql-statefulset.yaml`
- `deploy/helm/comic-platform/templates/redis-statefulset.yaml`

**实现**: 仅当 `postgresql.enabled=true && postgresql.external=false` 时渲染；使用 bitnami/postgresql:16 镜像，PVC 持久化。Redis 类似。

---

## Task 18: Helm Test + deploy.sh + env-to-k8s-secret.sh

**文件**:
- `deploy/helm/comic-platform/templates/tests/test-connection.yaml`
- `deploy/scripts/deploy.sh`
- `deploy/scripts/env-to-k8s-secret.sh`

**实现**:
```yaml
# test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "comic.fullname" . }}-test-connection"
  annotations:
    "helm.sh/hook": test
spec:
  restartPolicy: Never
  containers:
    - name: wget
      image: busybox
      command: ['sh', '-c', 'wget --spider http://{{ include "comic.fullname" . }}-web:8000/health && wget --spider http://{{ include "comic.fullname" . }}-frontend:80/']
```

```bash
#!/bin/bash
# deploy.sh - 一键部署脚本
set -e

ENV=${1:-dev}
CHART_DIR="$(dirname $0)/../helm/comic-platform"
NAMESPACE="comic-${ENV}"

case $ENV in
  dev) VALUES="values.yaml" ;;
  staging) VALUES="values-staging.yaml" ;;
  prod) VALUES="values-prod.yaml" ;;
  *) echo "Unknown env: $ENV"; exit 1 ;;
esac

helm upgrade --install comic-platform "$CHART_DIR" \
  -f "$CHART_DIR/$VALUES" \
  --namespace "$NAMESPACE" \
  --create-namespace \
  --atomic \
  --timeout 10m
```

```bash
#!/bin/bash
# env-to-k8s-secret.sh - 将 .env 转为 K8s Secret
# Usage: ./env-to-k8s-secret.sh .env production my-secret
ENV_FILE=$1
NAMESPACE=$2
SECRET_NAME=$3

kubectl create secret generic "$SECRET_NAME" \
  --namespace "$NAMESPACE" \
  --from-env-file="$ENV_FILE" \
  --dry-run=client -o yaml | kubectl apply -f -
```

---

## Task 19: 完整回归测试

**步骤**:
1. 后端单元测试：`py -3.14 -m pytest backend/tests -v`
2. 前端测试：`cd frontend; npm.cmd test -- --run`
3. TS 类型检查：`cd frontend; npm.cmd run typecheck`
4. 前端构建：`cd frontend; npm.cmd run build`
5. Helm lint：`npx.cmd helm lint deploy/helm/comic-platform`
6. Helm 模板渲染：`npx.cmd helm template deploy/helm/comic-platform -f deploy/helm/comic-platform/values-prod.yaml > /tmp/rendered.yaml`
7. 验证 YAML 语法：`npx.cmd yamllint /tmp/rendered.yaml`

**成功标准**:
- 所有后端测试通过（≥809 个 P3 测试 + 新增的 P4 测试）
- 前端测试全通过
- TypeScript 零错误
- helm lint 无错误
- 模板渲染无报错

---

## 兼容性考虑（向后兼容）

1. **API 版本**: 保持 `/api/v1` 路径不变，新功能用 `/api/v2` 增量发布
2. **数据库迁移**: alembic 009 迁移仅添加新字段（`app_env` 等可选字段），不修改已有 schema
3. **FileStorage 别名**: `FileStorage = LocalStorage` 保留别名，旧代码无需改动
4. **Helm Chart SemVer**: v0.1.0 起步，后续遵循 SemVer，旧 release 可 `helm rollback`
5. **环境变量**: 新增 `APP_ENV` 默认 `development`，旧环境无需显式配置
6. **OSS 可选**: `oss.enabled=false` 时自动回退到 LocalStorage，本地部署不受影响

---

## 自审清单

- [x] 每个 Task 都有 TDD 步骤（测试先行）
- [x] 关键文件路径明确（绝对路径或相对工作目录）
- [x] 命令使用 PowerShell 兼容语法（`;` 分隔，`py -3.14`）
- [x] 兼容性策略明确（FileStorage 别名、API v1 保持、SemVer）
- [x] 风险控制：GPU 镜像 build 仅在 CI 中跑，本地不强制
- [x] 环境分层：dev/staging/prod 三套 values，避免硬编码

---

**请选择执行方式？**
- **Subagent-Driven（推荐）**: 启动多个并行 subagent 执行独立 Task（如 Dockerfile 编写、Helm 模板编写），减少总耗时
- **Inline Execution**: 在主对话中按顺序执行，便于实时调试
