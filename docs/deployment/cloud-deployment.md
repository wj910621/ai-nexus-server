# 云端部署指南

> 本文档说明生产环境的云端部署方案，支持SaaS化运营。

---

## 一、部署架构

```
                    ┌─────────────┐
                    │   CDN/DNS   │
                    │ CloudFlare  │
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Load Balancer │
                    │   (Nginx)    │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼───────┐ ┌────────▼────────┐ ┌───────▼───────┐
│  Web Frontend  │ │   API Server    │ │  GPU Server   │
│  (Nginx + SPA) │ │  (FastAPI x N)  │ │ (AI Inference)│
│                │ │                  │ │               │
│  Static Files  │ │  Business Logic │ │  SD/SDXL      │
│                │ │                  │ │  ControlNet   │
└───────────────┘ └────────┬────────┘ └───────┬───────┘
                           │                  │
        ┌──────────────────┼──────────────────┤
        │                  │                  │
┌───────▼───────┐ ┌────────▼────────┐ ┌───────▼───────┐
│  PostgreSQL    │ │     Redis       │ │  Object Store │
│  (Primary +    │ │   (Cluster)     │ │  (MinIO/S3)   │
│   Replica)     │ │                  │ │               │
└───────────────┘ └──────────────────┘ └───────────────┘
```

---

## 二、云服务商选择

### 2.1 推荐方案

| 服务商 | GPU服务器 | 对象存储 | CDN | 适用场景 |
|--------|----------|----------|-----|----------|
| **阿里云** | GN10x/GN10Xp | OSS | 阿里CDN | 国内用户为主 |
| **腾讯云** | GN7/GN10X | COS | 腾讯CDN | 国内+社交生态 |
| **AWS** | P4d/P5 | S3 | CloudFront | 海外用户 |
| **自建** | RTX 4090服务器 | MinIO | CloudFlare | 成本敏感 |

### 2.2 配置建议

| 组件 | 规格 | 数量 | 说明 |
|------|------|------|------|
| API服务器 | 4核8G | 2+ | 业务逻辑 |
| GPU服务器 | 8核32G + RTX4090 | 1+ | AI推理 |
| 数据库 | 4核16G | 2 | 主从 |
| Redis | 2核4G | 1 | 缓存 |
| 对象存储 | - | 1 | 素材存储 |
| 负载均衡 | - | 1 | 流量分发 |

---

## 三、Docker化部署

### 3.1 生产Docker Compose

```yaml
# docker/docker-compose.prod.yml
version: '3.8'

services:
  # API服务
  api:
    build:
      context: ../backend
      dockerfile: Dockerfile.prod
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/comic_studio
      - REDIS_URL=redis://redis:6379
      - MINIO_ENDPOINT=minio:9000
      - APP_ENV=production
    depends_on:
      - postgres
      - redis
      - minio
    deploy:
      replicas: 2
      resources:
        limits:
          cpus: '4'
          memory: 8G
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # GPU推理服务（独立部署）
  gpu_worker:
    build:
      context: ../backend
      dockerfile: Dockerfile.gpu
    environment:
      - NVIDIA_VISIBLE_DEVICES=all
      - MODEL_BASE_PATH=/models
    volumes:
      - ../ai-models:/models
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
  
  # Celery Worker（CPU任务）
  celery_worker:
    build: ../backend
    command: celery -A app.celery worker --loglevel=info --concurrency=8
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/comic_studio
      - REDIS_URL=redis://redis:6379
    deploy:
      replicas: 2

  # 前端
  frontend:
    build:
      context: ../frontend
      dockerfile: Dockerfile
    ports:
      - "80:80"
      - "443:443"

  # 数据库
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: comic_studio
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 16G

  # Redis
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 4gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data

  # 对象存储
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD}
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  redis_data:
  minio_data:
```

### 3.2 生产Dockerfile

```dockerfile
# backend/Dockerfile.prod
FROM python:3.11-slim as builder

WORKDIR /app

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# 运行阶段
FROM python:3.11-slim

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libpq5 \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制Python包
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

WORKDIR /app
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

---

## 四、Nginx配置

```nginx
# /etc/nginx/conf.d/comic-studio.conf

# API负载均衡
upstream api_backend {
    server api1:8000 weight=5;
    server api2:8000 weight=5;
    keepalive 32;
}

# WebSocket负载均衡
upstream ws_backend {
    server api1:8000;
    server api2:8000;
    hash $arg_token consistent;
}

server {
    listen 80;
    server_name api.comicstudio.ai;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.comicstudio.ai;
    
    # SSL证书
    ssl_certificate /etc/ssl/certs/comic-studio.crt;
    ssl_certificate_key /etc/ssl/private/comic-studio.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    
    # API接口
    location /api/ {
        proxy_pass http://api_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 文件上传大小限制
        client_max_body_size 100M;
    }
    
    # WebSocket
    location /ws {
        proxy_pass http://ws_backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_read_timeout 86400;
    }
    
    # 健康检查
    location /health {
        proxy_pass http://api_backend/health;
    }
}

# 前端静态资源
server {
    listen 443 ssl http2;
    server_name comicstudio.ai www.comicstudio.ai;
    
    root /var/www/comic-studio/dist;
    index index.html;
    
    # SPA路由
    location / {
        try_files $uri $uri/ /index.html;
    }
    
    # 静态资源缓存
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # SSL
    ssl_certificate /etc/ssl/certs/comic-studio.crt;
    ssl_certificate_key /etc/ssl/private/comic-studio.key;
}
```

---

## 五、Kubernetes部署（高级）

### 5.1 Deployment配置

```yaml
# k8s/api-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: comic-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: comic-api
  template:
    metadata:
      labels:
        app: comic-api
    spec:
      containers:
      - name: api
        image: registry.cn-hangzhou.aliyuncs.com/comic-studio/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: url
        resources:
          requests:
            cpu: "1"
            memory: "2Gi"
          limits:
            cpu: "4"
            memory: "8Gi"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
---
# GPU推理节点
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gpu-worker
spec:
  replicas: 1
  template:
    spec:
      nodeSelector:
        accelerator: nvidia-gpu
      containers:
      - name: gpu-worker
        image: registry.cn-hangzhou.aliyuncs.com/comic-studio/gpu-worker:latest
        resources:
          limits:
            nvidia.com/gpu: 1
            memory: "32Gi"
```

---

## 六、监控与日志

### 6.1 Prometheus + Grafana

```yaml
# docker/monitoring.yml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"
  
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    volumes:
      - grafana_data:/var/lib/grafana
```

### 6.2 关键监控指标

| 指标 | 告警阈值 | 说明 |
|------|----------|------|
| API响应时间 P99 | > 500ms | 接口性能 |
| GPU利用率 | > 95% | 需扩容 |
| GPU显存使用 | > 90% | 需优化 |
| 队列积压 | > 100 | 需扩容Worker |
| 磁盘使用率 | > 80% | 需清理 |
| 错误率 | > 1% | 需排查 |

---

## 七、数据备份

### 7.1 自动备份脚本

```bash
#!/bin/bash
# scripts/backup.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR=/backups

# PostgreSQL备份
pg_dump $DATABASE_URL | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# 对象存储备份（MinIO）
mc mirror minio/assets $BACKUP_DIR/assets_$DATE/
mc mirror minio/generated $BACKUP_DIR/generated_$DATE/

# 保留最近7天备份
find $BACKUP_DIR -mtime +7 -delete

# 上传到远程存储
rclone sync $BACKUP_DIR remote:comic-studio-backups/
```

### 7.2 定时任务

```bash
# crontab -e
# 每天凌晨3点备份
0 3 * * * /opt/comic-studio/scripts/backup.sh
```

---

## 八、安全加固

### 8.1 SSL/TLS配置

```bash
# 使用Let's Encrypt免费证书
certbot certonly --webroot -w /var/www/html -d comicstudio.ai -d api.comicstudio.ai

# 自动续期
echo "0 12 * * * /usr/bin/certbot renew --quiet" | crontab -
```

### 8.2 防火墙配置

```bash
# 只开放必要端口
ufw allow 22/tcp      # SSH
ufw allow 80/tcp      # HTTP
ufw allow 443/tcp     # HTTPS
ufw deny 5432/tcp     # 禁止外部访问数据库
ufw deny 6379/tcp     # 禁止外部访问Redis
ufw enable
```

---

*本文档最后更新：2026-07-18*
