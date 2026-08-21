# Phase 8 P4: K8s 容器化设计 Spec

> **状态**: 待实施
> **创建日期**: 2026-07-21
> **前置**: P1（多 Provider）、P2（AMD/Intel GPU）、P3（LoRA 训练）已完成
> **目标云厂商**: 阿里云 ACK
> **生产部署状态**: 首次部署（无历史生产环境兼容负担）

## 1. 概述

将漫剧创作平台容器化部署到 K8s（阿里云 ACK），实现：
- 多镜像分离（backend-web / backend-worker / frontend），独立伸缩
- Helm Chart 管理，支持开发/预发布/生产多环境
- GPU 节点池隔离，worker 独占 GPU 资源
- 配置与密钥分离，支持 KMS/Sealed Secret
- 滚动更新与零停机部署

**兼容性策略**：首次生产部署无历史兼容负担，但为未来扩展预留：
- 数据库迁移始终向后兼容（alembic 链式升级）
- API 版本化（v1 扩展，不破坏现有契约）
- 配置项默认值保持现有开发行为
- Helm Chart 版本化，支持 `helm upgrade`

## 2. 整体架构

### 2.1 镜像划分

| 镜像 | 基础镜像 | 运行进程 | GPU |
|---|---|---|---|
| `comicstudio-backend-web` | `python:3.14-slim` | `uvicorn app.main:app` | 无 |
| `comicstudio-backend-worker` | `nvidia/cuda:12.4.1-runtime-ubuntu22.04` | `celery -A app.celery_app worker` | 需要 |
| `comicstudio-frontend` | `nginx:alpine`（多阶段） | `nginx -g 'daemon off;'` | 无 |

### 2.2 Deployment 拓扑

```
Ingress (SLB + Nginx Ingress)
    │
    ├── frontend (2 replicas, Nginx 静态 + 反代 /api/*)
    │
    └── backend-web (2-10 replicas, FastAPI, HPA CPU>70%)
            │
            │ Redis（任务队列）
            ▼
        backend-worker (1-5 replicas, Celery + GPU, HPA 队列深度>10)
            │
            ├── GPU 节点池（nvidia.com/gpu）
            └── nodeSelector: accelerator=nvidia

外部依赖:
    - PostgreSQL: 开发集群内 StatefulSet / 生产阿里云 RDS
    - Redis: 开发集群内 / 生产阿里云 Tair
    - 对象存储: 开发本地 PVC / 生产阿里云 OSS
    - 文件共享: NAS（datasets/lora_adapters 多 Pod 共享）
```

### 2.3 命名空间与标签

- Namespace: `comicstudio-{env}`（dev/staging/prod）
- 标签规范: `app.kubernetes.io/name=comicstudio`, `app.kubernetes.io/component={web,worker,frontend}`, `app.kubernetes.io/environment={dev,staging,prod}`

## 3. Dockerfile 设计

### 3.1 `backend/Dockerfile.web`

```dockerfile
# Stage 1: builder
FROM python:3.14-slim AS builder
WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt \
    --extra-index-url https://download.pytorch.org/whl/cpu

# Stage 2: runtime
FROM python:3.14-slim AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
WORKDIR /app
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini .
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### 3.2 `backend/Dockerfile.worker`

```dockerfile
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS builder
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y python3.14 python3-pip libpq-dev build-essential
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.14 libpq5 curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
WORKDIR /app
COPY app/ ./app/
HEALTHCHECK --interval=60s --timeout=10s --retries=3 \
    CMD celery -A app.celery_app inspect ping -d celery@$(hostname) || exit 1
CMD ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
```

### 3.3 `frontend/Dockerfile`

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /build
COPY package*.json ./
RUN npm ci --no-audit
COPY . .
RUN npm run build

FROM nginx:alpine AS runtime
COPY --from=builder /build/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -q --spider http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
```

### 3.4 `frontend/nginx.conf`

```nginx
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    client_max_body_size 100m;

    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    location /api/ {
        proxy_pass http://backend-web:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 300s;
    }

    location /api/v1/llm/stream {
        proxy_pass http://backend-web:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 600s;
    }

    location / {
        try_files $uri $uri/ /index.html;
    }
}
```

## 4. Helm Chart 结构

### 4.1 目录结构

```
deploy/helm/comicstudio/
├── Chart.yaml
├── values.yaml                 # 开发默认
├── values-prod.yaml            # 生产覆盖
├── values-staging.yaml         # 预发布覆盖
├── templates/
│   ├── _helpers.tpl
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secret.yaml
│   ├── backend-web/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   ├── hpa.yaml
│   │   └── pdb.yaml
│   ├── backend-worker/
│   │   ├── deployment.yaml
│   │   ├── hpa.yaml
│   │   └── pdb.yaml
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── hpa.yaml
│   ├── postgresql/
│   │   ├── statefulset.yaml    # 仅开发环境
│   │   └── service.yaml
│   ├── redis/
│   │   ├── statefulset.yaml    # 仅开发环境
│   │   └── service.yaml
│   ├── ingress.yaml
│   ├── pvc.yaml
│   ├── networkpolicy.yaml
│   └── tests/
│       └── test-connection.yaml
└── README.md
```

### 4.2 Chart.yaml

```yaml
apiVersion: v2
name: comicstudio
description: 漫剧创作平台 K8s 部署 Chart
type: application
version: 0.1.0
appVersion: "0.4.0"
keywords: [comic, ai, lora]
maintainers:
  - name: ComicStudio Team
```

### 4.3 values.yaml 核心配置

```yaml
global:
  env: development
  imageRegistry: registry.cn-hangzhou.aliyuncs.com
  imagePullSecrets:
    - name: aliyun-registry-secret
  storageClass: alicloud-disk-ssd
  domain: comicstudio.local

backendWeb:
  enabled: true
  image: { repository: comicstudio/backend-web, tag: "0.4.0", pullPolicy: IfNotPresent }
  replicas: 2
  resources:
    requests: { cpu: "250m", memory: "512Mi" }
    limits:   { cpu: "1000m", memory: "1Gi" }
  hpa:
    enabled: true
    minReplicas: 2
    maxReplicas: 5
    targetCPUUtilizationPercentage: 70

backendWorker:
  enabled: true
  image: { repository: comicstudio/backend-worker, tag: "0.4.0", pullPolicy: IfNotPresent }
  replicas: 1
  resources:
    requests: { cpu: "500m", memory: "2Gi", nvidia.com/gpu: 1 }
    limits:   { cpu: "2000m", memory: "8Gi", nvidia.com/gpu: 1 }
  hpa:
    enabled: true
    minReplicas: 1
    maxReplicas: 3
    queueDepth: 10
  nodeSelector:
    accelerator: nvidia
  tolerations:
    - key: "nvidia.com/gpu"
      operator: "Exists"
      effect: "NoSchedule"

frontend:
  enabled: true
  image: { repository: comicstudio/frontend, tag: "0.4.0", pullPolicy: IfNotPresent }
  replicas: 2
  resources:
    requests: { cpu: "100m", memory: "128Mi" }
    limits:   { cpu: "500m", memory: "256Mi" }

ingress:
  enabled: true
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
  tls:
    enabled: true
    secretName: comicstudio-tls
    hosts: ["{{ .Values.global.domain }}"]

persistence:
  uploads:    { enabled: true, size: 50Gi,  mountPath: /app/uploads }
  datasets:   { enabled: true, size: 100Gi, mountPath: /app/uploads/datasets }
  loraAdapters: { enabled: true, size: 50Gi, mountPath: /app/uploads/lora_adapters }

postgresql:
  enabled: true  # true=集群内, false=外部 RDS
  external: { host: "", port: 5432, database: comicstudio, existingSecret: "", secretKey: password }

redis:
  enabled: true
  external: { host: "", port: 6379, existingSecret: "", secretKey: password }

oss:
  enabled: false  # 生产启用
  bucket: ""
  region: ""
  endpoint: ""

secrets:
  databaseUrl: "postgresql+asyncpg://comicstudio:devpass@postgres:5432/comicstudio"
  redisUrl: "redis://redis:6379/0"
  jwtSecret: "dev-jwt-secret-change-in-prod"
  stripeSecretKey: ""
  stripeWebhookSecret: ""
  deepseekApiKey: ""
  replicateApiToken: ""
  ossAccessKeyId: ""
  ossAccessKeySecret: ""
  smtpPassword: ""
```

### 4.4 values-prod.yaml

```yaml
global:
  env: production
  domain: comicstudio.example.com

backendWeb:
  replicas: 3
  resources:
    requests: { cpu: "500m", memory: "1Gi" }
    limits:   { cpu: "2000m", memory: "2Gi" }
  hpa: { maxReplicas: 10 }

backendWorker:
  replicas: 2
  resources:
    requests: { cpu: "1000m", memory: "4Gi", nvidia.com/gpu: 1 }
    limits:   { cpu: "4000m", memory: "16Gi", nvidia.com/gpu: 1 }
  hpa: { maxReplicas: 5 }

postgresql:
  enabled: false
  external:
    host: "rm-xxxx.pg.rds.aliyuncs.com"
    existingSecret: "rds-postgres-secret"
    secretKey: password

redis:
  enabled: false
  external:
    host: "r-xxxx.redis.rds.aliyuncs.com"
    existingSecret: "tair-redis-secret"
    secretKey: password

oss:
  enabled: true
  bucket: "comicstudio-uploads"
  region: "cn-hangzhou"
  endpoint: "https://oss-cn-hangzhou.aliyuncs.com"
```

## 5. 配置与密钥管理

### 5.1 ConfigMap（非敏感）

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "comicstudio.fullname" . }}-config
data:
  APP_ENV: {{ .Values.global.env | quote }}
  LOG_LEVEL: "info"
  DATABASE_HOST: {{ .Values.postgresql.external.host | default (include "comicstudio.postgresql.fullname" .) | quote }}
  DATABASE_PORT: "5432"
  DATABASE_NAME: "comicstudio"
  REDIS_HOST: {{ .Values.redis.external.host | default (include "comicstudio.redis.fullname" .) | quote }}
  REDIS_PORT: "6379"
  LORA_TRAIN_LOCAL_ENABLED: "true"
  LORA_TRAIN_CLOUD_ENABLED: "true"
  BLIP_MODEL_NAME: "Salesforce/blip-image-captioning-large"
  OSS_BUCKET: {{ .Values.oss.bucket | quote }}
  OSS_REGION: {{ .Values.oss.region | quote }}
  OSS_ENDPOINT: {{ .Values.oss.endpoint | quote }}
```

### 5.2 Secret（敏感）

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "comicstudio.fullname" . }}-secret
type: Opaque
stringData:
  DATABASE_URL: {{ .Values.secrets.databaseUrl | quote }}
  REDIS_URL: {{ .Values.secrets.redisUrl | quote }}
  JWT_SECRET: {{ .Values.secrets.jwtSecret | quote }}
  STRIPE_SECRET_KEY: {{ .Values.secrets.stripeSecretKey | quote }}
  STRIPE_WEBHOOK_SECRET: {{ .Values.secrets.stripeWebhookSecret | quote }}
  DEEPSEEK_API_KEY: {{ .Values.secrets.deepseekApiKey | quote }}
  REPLICATE_API_TOKEN: {{ .Values.secrets.replicateApiToken | quote }}
  OSS_ACCESS_KEY_ID: {{ .Values.secrets.ossAccessKeyId | quote }}
  OSS_ACCESS_KEY_SECRET: {{ .Values.secrets.ossAccessKeySecret | quote }}
  SMTP_PASSWORD: {{ .Values.secrets.smtpPassword | quote }}
```

### 5.3 密钥注入方式

| 方式 | 场景 | 说明 |
|---|---|---|
| `--set` | 开发 | 简单但会留在 shell history |
| External Secrets Operator + KMS | 生产 | 对接阿里云 KMS，自动轮换 |
| Sealed Secrets | GitOps | 加密后可提交 Git |

### 5.4 Deployment 引用

```yaml
spec:
  template:
    spec:
      containers:
        - name: backend-web
          envFrom:
            - configMapRef:
                name: {{ include "comicstudio.fullname" . }}-config
            - secretRef:
                name: {{ include "comicstudio.fullname" . }}-secret
```

### 5.5 config.py 适配

现有 Pydantic BaseSettings 原生支持环境变量。仅追加 `app_env` 字段：

```python
# backend/app/core/config.py 追加
app_env: str = "development"  # development / staging / production

@property
def is_production(self) -> bool:
    return self.app_env == "production"
```

## 6. 存储与外部依赖

### 6.1 存储抽象层

扩展现有 `backend/app/core/storage.py` 的 FileStorage 为抽象基类 + 双实现：

```python
from abc import ABC, abstractmethod
from pathlib import Path

class StorageBackend(ABC):
    @abstractmethod
    async def save(self, path: str, data: bytes) -> str: ...
    @abstractmethod
    async def get_full_path(self, path: str) -> Path: ...
    @abstractmethod
    async def exists(self, path: str) -> bool: ...
    @abstractmethod
    async def delete(self, path: str) -> None: ...

class LocalStorage(StorageBackend):
    """本地文件系统（现有实现保持不变）"""
    # ...

class OSSStorage(StorageBackend):
    """阿里云 OSS 存储"""
    def __init__(self, bucket, access_key, secret, endpoint):
        import oss2
        self.auth = oss2.Auth(access_key, secret)
        self.bucket = oss2.Bucket(self.auth, endpoint, bucket)
    # ...

def get_storage() -> StorageBackend:
    if settings.is_production and settings.oss_bucket:
        return OSSStorage(...)
    return LocalStorage(...)
```

### 6.2 PVC 定义

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "comicstudio.fullname" . }}-uploads
spec:
  accessModes: [ReadWriteMany]  # NAS 支持多 Pod 共享
  storageClassName: alicloud-nas
  resources:
    requests:
      storage: {{ .Values.persistence.uploads.size }}
```

### 6.3 数据库分层

| 环境 | 方案 | 规格 |
|---|---|---|
| 开发 | 集群内 StatefulSet | postgres:16-alpine, 20Gi |
| 预发布 | 阿里云 RDS 基础版 | 1C2G, 50GB SSD |
| 生产 | 阿里云 RDS 高可用版 | 主备, 2C4G, 100GB SSD |

### 6.4 数据迁移路径

```bash
# 开发 → 生产
pg_dump -h dev-postgres -U comicstudio comicstudio > dev-backup.sql
psql -h rm-xxxx.pg.rds.aliyuncs.com -U comicstudio < dev-backup.sql
ossutil cp /app/uploads/ oss://comicstudio-uploads/ --recursive
```

## 7. 健康检查与探针

### 7.1 探针配置

| 组件 | readinessProbe | livenessProbe | startupProbe |
|---|---|---|---|
| backend-web | HTTP GET /health, 10s delay | HTTP GET /health, 30s delay | HTTP GET /health, 60s timeout |
| backend-worker | celery inspect ping, 30s delay | celery inspect ping, 60s delay | 120s timeout |
| frontend | wget /, 5s delay | wget /, 30s delay | 30s timeout |

### 7.2 后端健康端点

```python
# backend/app/main.py 已有 /health 端点，扩展为检查依赖
@app.get("/health")
async def health():
    checks = {
        "status": "healthy",
        "database": await check_db_connection(),
        "redis": await check_redis_connection(),
    }
    all_healthy = all(v == "ok" for v in checks.values() if v != "status")
    return JSONResponse(
        status_code=200 if all_healthy else 503,
        content=checks,
    )
```

## 8. 弹性伸缩策略

### 8.1 HPA 配置

**backend-web HPA**（按 CPU）:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "comicstudio.fullname" . }}-web
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "comicstudio.fullname" . }}-web
  minReplicas: {{ .Values.backendWeb.hpa.minReplicas }}
  maxReplicas: {{ .Values.backendWeb.hpa.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.backendWeb.hpa.targetCPUUtilizationPercentage }}
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300  # 缩容稳定窗口 5 分钟
      policies:
        - type: Percent
          value: 50  # 每次最多缩 50%
          periodSeconds: 60
```

**backend-worker HPA**（按队列深度，需 Prometheus Adapter）:

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "comicstudio.fullname" . }}-worker
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "comicstudio.fullname" . }}-worker
  minReplicas: {{ .Values.backendWorker.hpa.minReplicas }}
  maxReplicas: {{ .Values.backendWorker.hpa.maxReplicas }}
  metrics:
    - type: Pods
      pods:
        metric:
          name: celery_queue_length
        target:
          type: AverageValue
          averageValue: {{ .Values.backendWorker.hpa.queueDepth }}
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 1  # 每次最多扩 1 个（GPU 资源昂贵）
          periodSeconds: 120
```

### 8.2 PDB（Pod Disruption Budget）

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: {{ include "comicstudio.fullname" . }}-web
spec:
  minAvailable: 1  # 至少保持 1 个可用
  selector:
    matchLabels:
      app.kubernetes.io/component: backend-web
```

### 8.3 Redis 队列深度指标导出

```python
# backend/app/core/metrics.py（新增）
from prometheus_client import Gauge

celery_queue_length = Gauge(
    'celery_queue_length',
    'Number of tasks in Celery queue',
    ['queue_name']
)

# 定期更新
async def update_queue_metrics(redis_client):
    for queue in ['default', 'lora_train', 'image_gen']:
        length = await redis_client.llen(queue)
        celery_queue_length.labels(queue_name=queue).set(length)
```

## 9. 网络与 Ingress

### 9.1 Ingress 配置

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: {{ include "comicstudio.fullname" . }}
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: "100m"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "600"
    nginx.ingress.kubernetes.io/websocket-services: "frontend"
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
    - hosts: ["{{ .Values.global.domain }}"]
      secretName: {{ .Values.ingress.tls.secretName }}
  rules:
    - host: {{ .Values.global.domain }}
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: frontend
                port: { number: 80 }
```

### 9.2 NetworkPolicy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: {{ include "comicstudio.fullname" . }}-default
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/part-of: comicstudio
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app.kubernetes.io/part-of: comicstudio
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: ingress-nginx
  egress:
    - to:
        - podSelector:
            matchLabels:
              app.kubernetes.io/part-of: comicstudio
    - to: []  # 允许出站到外部（DB/Redis/OSS/API）
      ports:
        - { protocol: TCP, port: 443 }
        - { protocol: TCP, port: 5432 }
        - { protocol: TCP, port: 6379 }
```

## 10. 测试策略

### 10.1 Dockerfile 测试

```bash
# 构建测试
docker build -t comicstudio-backend-web:test -f backend/Dockerfile.web backend/
docker build -t comicstudio-backend-worker:test -f backend/Dockerfile.worker backend/
docker build -t comicstudio-frontend:test -f frontend/Dockerfile frontend/

# 运行测试
docker run --rm comicstudio-backend-web:test pytest tests/ -q
docker run --rm comicstudio-frontend:test npm test

# 安全扫描
trivy image comicstudio-backend-web:test
trivy image comicstudio-backend-worker:test
```

### 10.2 Helm Chart 测试

```yaml
# templates/tests/test-connection.yaml
apiVersion: v1
kind: Pod
metadata:
  name: "{{ include "comicstudio.fullname" . }}-test"
  annotations:
    "helm.sh/hook": test
spec:
  restartPolicy: Never
  containers:
    - name: wget
      image: busybox
      command: ['wget']
      args: ['{{ include "comicstudio.fullname" . }}-web:8000/health']
```

```bash
# Helm 测试
helm lint deploy/helm/comicstudio
helm template deploy/helm/comicstudio -f values-prod.yaml | kubectl apply --dry-run=client -f -
helm install comicstudio deploy/helm/comicstudio -n comicstudio-dev
helm test comicstudio -n comicstudio-dev
```

### 10.3 Kind 集成测试

```yaml
# .github/workflows/k8s-test.yml（或 CI 脚本）
- 使用 kind 创建本地 K8s 集群
- helm install comicstudio
- 等待所有 Pod Ready
- curl health 端点
- helm uninstall
```

## 11. 部署流程与回滚

### 11.1 首次部署流程

```bash
# 1. 构建并推送镜像
docker build -t registry.cn-hangzhou.aliyuncs.com/comicstudio/backend-web:0.4.0 -f backend/Dockerfile.web backend/
docker push registry.cn-hangzhou.aliyuncs.com/comicstudio/backend-web:0.4.0
# ... worker, frontend 类似

# 2. 创建命名空间
kubectl create namespace comicstudio-prod

# 3. 创建镜像拉取 Secret
kubectl create secret docker-registry aliyun-registry-secret \
  --docker-server=registry.cn-hangzhou.aliyuncs.com \
  --docker-username=xxx --docker-password=xxx \
  -n comicstudio-prod

# 4. 创建敏感配置 Secret（生产用外部 KMS 注入）
kubectl create secret generic comicstudio-secret \
  --from-literal=database-url="postgresql+asyncpg://..." \
  --from-literal=jwt-secret="$(openssl rand -hex 32)" \
  ... -n comicstudio-prod

# 5. 运行数据库迁移
kubectl run alembic-migrate --rm -i --restart=Never \
  --image=registry.cn-hangzhou.aliyuncs.com/comicstudio/backend-web:0.4.0 \
  --env-from="secret/comicstudio-secret" \
  --command -- alembic upgrade head

# 6. Helm 部署
helm install comicstudio deploy/helm/comicstudio \
  -f values-prod.yaml \
  -n comicstudio-prod

# 7. 验证
kubectl get pods -n comicstudio-prod
kubectl logs -f deployment/comicstudio-web -n comicstudio-prod
helm test comicstudio -n comicstudio-prod
```

### 11.2 滚动更新

```bash
# 更新镜像版本
helm upgrade comicstudio deploy/helm/comicstudio \
  -f values-prod.yaml \
  --set backendWeb.image.tag=0.4.1 \
  --set backendWorker.image.tag=0.4.1 \
  --set frontend.image.tag=0.4.1 \
  -n comicstudio-prod

# K8s 自动滚动更新，零停机
```

### 11.3 回滚

```bash
# Helm 回滚
helm rollback comicstudio 1 -n comicstudio-prod

# 数据库回滚（谨慎）
kubectl run alembic-downgrade --rm -i --restart=Never \
  --image=registry.cn-hangzhou.aliyuncs.com/comicstudio/backend-web:0.4.0 \
  -- alembic downgrade -1
```

### 11.4 部署脚本

```bash
# deploy/scripts/deploy.sh
#!/bin/bash
set -euo pipefail

ENV=${1:-dev}
VERSION=${2:-latest}
NAMESPACE="comicstudio-${ENV}"

echo "Deploying comicstudio ${VERSION} to ${ENV}..."

# 构建推送
docker buildx build --push \
  -t registry.cn-hangzhou.aliyuncs.com/comicstudio/backend-web:${VERSION} \
  -f backend/Dockerfile.web backend/

# ... worker, frontend

# Helm 部署
helm upgrade --install comicstudio deploy/helm/comicstudio \
  -f deploy/helm/comicstudio/values-${ENV}.yaml \
  --set global.imageTag=${VERSION} \
  -n ${NAMESPACE} --create-namespace

# 等待 Rollout
kubectl rollout status deployment/comicstudio-web -n ${NAMESPACE} --timeout=300s
kubectl rollout status deployment/comicstudio-frontend -n ${NAMESPACE} --timeout=300s

# 运行迁移（web pod 内执行）
kubectl exec -n ${NAMESPACE} deployment/comicstudio-web -- \
  alembic upgrade head

echo "Deployment complete."
```

## 12. 兼容性考虑

### 12.1 首次部署的"兼容性"

虽然用户说明"尚未真正部署生产"，但需为未来迭代预留兼容性：

1. **数据库迁移**：所有 alembic 迁移必须向后兼容，不破坏现有 schema
2. **API 版本化**：v1 路由扩展不破坏现有契约，破坏性变更走 v2
3. **配置默认值**：新配置项默认值保持现有开发行为
4. **Helm Chart 版本**：`Chart.yaml` version 遵循 SemVer，升级支持 `helm upgrade`
5. **镜像标签**：使用语义化版本（0.4.0），避免 `latest`

### 12.2 开发到生产的环境差异处理

| 差异点 | 开发 | 生产 | 适配方式 |
|---|---|---|---|
| 数据库 | 集群内 PostgreSQL | 阿里云 RDS | `postgresql.enabled=false` + external 配置 |
| Redis | 集群内 Redis | 阿里云 Tair | `redis.enabled=false` + external 配置 |
| 文件存储 | 本地 PVC | 阿里云 OSS | `oss.enabled=true` + StorageBackend 抽象 |
| 域名/TLS | 无（localhost） | 真实域名 + Let's Encrypt | `ingress.tls.enabled=true` |
| GPU | 无（CPU 推理） | NVIDIA GPU | `nodeSelector: accelerator=nvidia` |
| 日志 | stdout | stdout + Loki | 统一 stdout，日志层聚合 |
| 密钥 | values.yaml | KMS/External Secret | `secrets.*` 通过外部注入 |

### 12.3 回滚安全

- 数据库迁移提供 `downgrade()` 函数
- Helm `rollback` 保留历史版本（`--history-max 10`）
- 镜像保留最近 5 个版本，不立即删除

## 13. 文件清单

### 13.1 新增文件

```
backend/Dockerfile.web
backend/Dockerfile.worker
frontend/Dockerfile
frontend/nginx.conf
deploy/helm/comicstudio/Chart.yaml
deploy/helm/comicstudio/values.yaml
deploy/helm/comicstudio/values-prod.yaml
deploy/helm/comicstudio/values-staging.yaml
deploy/helm/comicstudio/README.md
deploy/helm/comicstudio/templates/_helpers.tpl
deploy/helm/comicstudio/templates/namespace.yaml
deploy/helm/comicstudio/templates/configmap.yaml
deploy/helm/comicstudio/templates/secret.yaml
deploy/helm/comicstudio/templates/backend-web/deployment.yaml
deploy/helm/comicstudio/templates/backend-web/service.yaml
deploy/helm/comicstudio/templates/backend-web/hpa.yaml
deploy/helm/comicstudio/templates/backend-web/pdb.yaml
deploy/helm/comicstudio/templates/backend-worker/deployment.yaml
deploy/helm/comicstudio/templates/backend-worker/hpa.yaml
deploy/helm/comicstudio/templates/backend-worker/pdb.yaml
deploy/helm/comicstudio/templates/frontend/deployment.yaml
deploy/helm/comicstudio/templates/frontend/service.yaml
deploy/helm/comicstudio/templates/frontend/hpa.yaml
deploy/helm/comicstudio/templates/postgresql/statefulset.yaml
deploy/helm/comicstudio/templates/postgresql/service.yaml
deploy/helm/comicstudio/templates/redis/statefulset.yaml
deploy/helm/comicstudio/templates/redis/service.yaml
deploy/helm/comicstudio/templates/ingress.yaml
deploy/helm/comicstudio/templates/pvc.yaml
deploy/helm/comicstudio/templates/networkpolicy.yaml
deploy/helm/comicstudio/templates/tests/test-connection.yaml
deploy/scripts/deploy.sh
deploy/scripts/env-to-k8s-secret.sh
deploy/kind-test.yaml  # kind 集成测试配置
backend/app/core/storage_oss.py  # OSS 存储实现
backend/app/core/metrics.py  # Prometheus 指标导出
backend/tests/test_storage_oss.py
backend/tests/test_metrics.py
```

### 13.2 修改文件

```
backend/app/core/config.py          # 追加 app_env 字段
backend/app/core/storage.py         # 抽象为 StorageBackend + 工厂函数
backend/app/main.py                 # 扩展 /health 端点检查依赖
backend/requirements.txt            # 追加 oss2、prometheus-client
backend/app/core/__init__.py        # 导出 get_storage
backend/app/api/datasets.py         # storage 引用改为 get_storage()
backend/app/api/training.py         # storage 引用改为 get_storage()
backend/app/services/dataset_service.py  # storage 引用改为 get_storage()
backend/app/services/lora_training_service.py  # storage 引用改为 get_storage()
```

## 14. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| GPU 节点不足 | worker 无法调度 | 预留 GPU 节点池 + HPA maxReplicas 限制 |
| OSS 网络延迟 | 文件上传/下载变慢 | 使用同区域 OSS + CDN 加速静态资源 |
| 镜像体积过大 | 构建慢、拉取慢 | 多阶段构建 + CPU/GPU 分离 + .dockerignore |
| 数据库连接泄漏 | web pod OOM | 连接池配置 + readinessProbe 检查 DB |
| Redis 单点 | 任务队列丢失 | 生产用 Tair 主备 + 持久化 |
| 配置漂移 | 多环境不一致 | Helm values 统一管理 + GitOps |

## 15. 依赖项

### 15.1 K8s 集群组件

- 阿里云 ACK 托管版
- Nginx Ingress Controller
- cert-manager（Let's Encrypt TLS）
- NVIDIA Device Plugin（GPU 节点）
- Prometheus Adapter（自定义指标 HPA）
- External Secrets Operator（可选，KMS 对接）

### 15.2 Python 新增依赖

```python
# backend/requirements.txt 追加
oss2>=2.18.0           # 阿里云 OSS SDK
prometheus-client>=0.20.0  # Prometheus 指标导出
```

### 15.3 外部服务

- 阿里云容器镜像服务（ACR）- 镜像仓库
- 阿里云 RDS PostgreSQL - 生产数据库
- 阿里云 Tair Redis - 生产缓存/队列
- 阿里云 OSS - 对象存储
- 阿里云 NAS - 文件共享（开发环境）
- 阿里云 SLB - 负载均衡
