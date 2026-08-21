# Comic Platform Helm Chart

漫剧软件平台 Helm Chart - Phase 8 P4 K8s 容器化部署方案。

## 简介

本 Helm Chart 用于在 Kubernetes 集群上部署漫剧软件平台,包含以下核心组件:

- **backend-web**: FastAPI Web API 服务,提供 REST API 与 WebSocket 接口
- **backend-worker**: Celery 异步任务服务,负责 AI 推理、图像生成等异步任务(可选 GPU 加速)
- **frontend**: Nginx 静态资源服务,承载前端界面
- **postgresql**: PostgreSQL 16 数据库(可选内置或外部托管)
- **redis**: Redis 7 缓存与消息队列(可选内置或外部托管)

支持环境差异化配置:development / staging / production。

## 环境要求

- Kubernetes 1.19+
- Helm 3.2.0+
- (可选) PV Provisioner(若启用持久化存储)
- (可选) Ingress Controller(如 nginx-ingress)
- (可选) Metrics Server + Prometheus Adapter(若启用 HPA)

## 安装命令

### 开发环境 (默认)

```bash
# 创建命名空间并安装
helm install comic-platform ./deploy/helm/comic-platform \
  --create-namespace \
  --namespace comic-dev

# 或指定 values 文件
helm install comic-platform ./deploy/helm/comic-platform \
  -f deploy/helm/comic-platform/values.yaml \
  --create-namespace \
  --namespace comic-dev
```

### 预发环境

```bash
helm install comic-platform ./deploy/helm/comic-platform \
  -f deploy/helm/comic-platform/values.yaml \
  -f deploy/helm/comic-platform/values-staging.yaml \
  --create-namespace \
  --namespace comic-staging
```

### 生产环境

```bash
# 生产环境必须通过外部方式注入敏感信息
helm install comic-platform ./deploy/helm/comic-platform \
  -f deploy/helm/comic-platform/values.yaml \
  -f deploy/helm/comic-platform/values-prod.yaml \
  --set jwt.secret="<your-jwt-secret>" \
  --set postgresql.password="<your-db-password>" \
  --set redis.password="<your-redis-password>" \
  --set oss.accessKeyId="<your-oss-key-id>" \
  --set oss.accessKeySecret="<your-oss-key-secret>" \
  --create-namespace \
  --namespace comic-prod
```

## 配置覆盖

### 通过 values 文件

复制 `values.yaml` 为自定义文件,修改后通过 `-f` 参数传入:

```bash
helm install comic-platform ./deploy/helm/comic-platform \
  -f my-values.yaml
```

### 通过命令行参数

使用 `--set` 临时覆盖单个配置项:

```bash
helm upgrade comic-platform ./deploy/helm/comic-platform \
  --set backend.web.replicas=4 \
  --set frontend.replicas=4
```

### 主要配置项

| 参数 | 说明 | 默认值 |
| --- | --- | --- |
| `namespace.name` | 命名空间名称 | `comic-dev` |
| `backend.web.replicas` | Web API 副本数 | `2` |
| `backend.worker.replicas` | Worker 副本数 | `1` |
| `backend.worker.gpu.enabled` | Worker 是否启用 GPU | `false` |
| `frontend.replicas` | 前端副本数 | `2` |
| `ingress.enabled` | 是否启用 Ingress | `false` |
| `ingress.host` | Ingress 域名 | `comic.example.com` |
| `postgresql.external` | 是否使用外部 PG | `false` |
| `redis.external` | 是否使用外部 Redis | `false` |
| `oss.enabled` | 是否启用对象存储 | `false` |
| `persistence.enabled` | 是否启用持久化 | `false` |
| `hpa.web.enabled` | Web HPA 自动伸缩 | `false` |
| `hpa.worker.enabled` | Worker HPA 自动伸缩 | `false` |
| `pdb.enabled` | 中断预算 | `false` |
| `networkPolicy.enabled` | 网络策略 | `false` |
| `env` | 环境标识 | `development` |

## 验证部署

```bash
# 查看部署资源
kubectl get all -n comic-dev

# 查看 Pod 日志
kubectl logs -f deployment/comic-platform-web -n comic-dev
kubectl logs -f deployment/comic-platform-worker -n comic-dev

# 执行 Helm 测试
helm test comic-platform -n comic-dev

# 端口转发本地访问 (开发环境)
kubectl port-forward svc/comic-platform-frontend 8080:80 -n comic-dev
```

## 卸载命令

```bash
# 卸载 Release (保留 PVC)
helm uninstall comic-platform -n comic-dev

# 清理命名空间 (会删除所有 PVC 数据)
kubectl delete namespace comic-dev
```

> ⚠️ **警告**: 删除命名空间会永久删除该命名空间下的所有资源,包括 PV 数据。生产环境卸载前请务必做好数据备份。

## 目录结构

```
comic-platform/
├── Chart.yaml                          # Chart 元数据
├── values.yaml                         # 默认配置 (development)
├── values-prod.yaml                    # 生产环境覆盖
├── values-staging.yaml                 # 预发环境覆盖
└── templates/
    ├── _helpers.tpl                   # 模板辅助函数
    ├── namespace.yaml                  # 命名空间
    ├── configmap.yaml                  # 非敏感配置
    ├── secret.yaml                     # 敏感配置
    ├── deployment-web.yaml             # Web Deployment
    ├── service-web.yaml                # Web Service
    ├── deployment-worker.yaml          # Worker Deployment
    ├── deployment-frontend.yaml        # Frontend Deployment
    ├── service-frontend.yaml           # Frontend Service
    ├── pvc.yaml                        # 持久化卷声明
    ├── ingress.yaml                    # Ingress 入口
    ├── networkpolicy.yaml              # 网络策略
    ├── hpa-web.yaml                    # Web 自动伸缩
    ├── hpa-worker.yaml                 # Worker 自动伸缩
    ├── pdb.yaml                        # 中断预算
    ├── postgresql-statefulset.yaml     # PostgreSQL 状态集
    ├── redis-statefulset.yaml          # Redis 状态集
    └── tests/
        └── test-connection.yaml        # 连接测试
```

## 维护

- 维护者: Comic Platform Team
- 版本: 0.1.0
- App 版本: 0.8.0
