# 生产环境部署指南

> Phase 8 最终生产部署指南 —— 阿里云 ACK（托管版 Kubernetes）
>
> 适用版本：v0.8.0+
>
> 前置条件：已完成 P4 K8s 容器化、P6 监控可观测性、P7 安全加固、P8 CI/CD 流水线，且 dev / staging 环境已成功部署运行。

---

## 一、部署前准备

### 1.1 基础设施准备

#### 1.1.1 阿里云 ACK 集群创建

- **集群版本**：Kubernetes 1.28+（ACK 托管版 Pro 版推荐）
- **网络模型**：Terway（共享 ENI 模式，性能更优）
- **容器运行时**：containerd
- **Pod CIDR**：192.168.0.0/16
- **Service CIDR**：172.21.0.0/20
- **API Server 公网暴露**：开启（仅限发布期，部署完成后可关闭）

#### 1.1.2 节点池规划

| 节点池 | 实例规格 | 数量 | 用途 | 污点 / 标签 |
|--------|----------|------|------|-------------|
| `cpu-pool` | ecs.g7.xlarge（4C16G） | 3+ | web / frontend / PG / Redis | 默认 |
| `gpu-pool` | ecs.gn7i-c8g1.2xlarge（8C32G + A10） | 2+ | worker（GPU 推理） | `nvidia.com/gpu=true` |

- **CPU 节点池**：承载 web、frontend、内置 PG/Redis（如未使用云数据库）
- **GPU 节点池**：承载 worker，需安装 NVIDIA 驱动 + GPU Operator
- **系统盘**：ESSD PL1 100Gi；**数据盘**：ESSD PL1 200Gi

#### 1.1.3 VPC 与安全组配置

- **VPC**：`10.0.0.0/8`，划分子网 `10.0.0.0/24`（ACK）、`10.0.1.0/24`（RDS）、`10.0.2.0/24`（Redis）
- **ACK 安全组入方向**：
  - 80 / 443（公网 Ingress）
  - 6443（API Server，运维网段）
  - 全部端口（VPC 内网，节点互通）
- **RDS 安全组**：仅允许 ACK 节点网段访问 5432
- **Redis 安全组**：仅允许 ACK 节点网段访问 6379

#### 1.1.4 OSS Bucket 创建

- **Bucket 名称**：`comic-prod-oss`（全局唯一）
- **区域**：cn-hangzhou（与 ACK 同区域）
- **存储类型**：标准存储
- **读写权限**：私有
- **防盗链**：Referer 白名单（生产域名）
- **生命周期**：uploads/ 30 天后转 IA，models/ 永久存储

#### 1.1.5 RDS PostgreSQL（可选，生产推荐）

- **实例规格**：pg.x4.medium.2c（4C16G）或更高
- **存储**：ESSD PL1 200Gi
- **版本**：PostgreSQL 15
- **高可用**：主备双机 + 异地备份
- **白名单**：ACK 节点网段
- **数据库名 / 用户**：`comic` / `comic`
- 内置 PG（StatefulSet）仅建议用于 dev / staging 环境

#### 1.1.6 Redis 实例（可选，生产推荐）

- **实例规格**：redis.master.small.default（2G）或更高
- **版本**：Redis 7.0
- **架构**：主从（标准版）
- **白名单**：ACK 节点网段
- **密码**：通过 RAM 控制台生成
- 内置 Redis（StatefulSet）仅建议用于 dev / staging 环境

### 1.2 集群组件安装

#### 1.2.1 Nginx Ingress Controller

```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm upgrade --install ingress-nginx ingress-nginx/ingress-nginx \
  --namespace ingress-nginx \
  --create-namespace \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/alibaba-cloud-loadbalancer-spec"="slb.s1.medium" \
  --set controller.service.annotations."service\.beta\.kubernetes\.io/alibaba-cloud-loadbalancer-address-type"="internet" \
  --atomic --timeout 10m --wait
```

获取 Ingress 外网 IP（用于 DNS A 记录）：

```bash
kubectl get svc -n ingress-nginx ingress-nginx-controller \
  -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

#### 1.2.2 cert-manager + Let's Encrypt ClusterIssuer

```bash
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm upgrade --install cert-manager jetstack/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --set crds.enabled=true \
  --atomic --timeout 5m --wait
```

创建 Let's Encrypt 生产 ClusterIssuer：

```yaml
# letsencrypt-prod.yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: ops@example.com  # 替换为真实邮箱
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
      - http01:
          ingress:
            class: nginx
```

```bash
kubectl apply -f letsencrypt-prod.yaml
```

#### 1.2.3 kube-prometheus-stack（P6 监控）

```bash
bash deploy/monitoring/install.sh monitoring
```

参考：`deploy/monitoring/kube-prometheus-stack-values.yaml`

#### 1.2.4 Loki stack（P6 日志）

随 `install.sh` 一并安装。参考：`deploy/monitoring/loki-stack-values.yaml`

### 1.3 镜像准备

#### 1.3.1 GHCR 镜像（CI 已推送）

三镜像已通过 GitHub Actions 推送到 GHCR：

- `ghcr.io/<owner>/comic-backend-web:<tag>`
- `ghcr.io/<owner>/comic-backend-worker:<tag>`
- `ghcr.io/<owner>/comic-frontend:<tag>`

#### 1.3.2 阿里云容器镜像服务（ACR）同步

国内拉取 GHCR 速度慢，需将镜像同步到 ACR 加速：

1. 在阿里云容器镜像服务创建企业版实例（推荐）或个人版
2. 创建三个仓库：`comic-backend-web` / `comic-backend-worker` / `comic-frontend`
3. 配置 GHCR → ACR 的镜像同步规则（或手动 `docker pull` + `docker push`）

```bash
# 手动同步示例
docker pull ghcr.io/<owner>/comic-backend-web:v0.8.0
docker tag ghcr.io/<owner>/comic-backend-web:v0.8.0 \
  registry.cn-hangzhou.aliyuncs.com/<namespace>/comic-backend-web:v0.8.0
docker push registry.cn-hangzhou.aliyuncs.com/<namespace>/comic-backend-web:v0.8.0
```

### 1.4 Secret 准备

#### 1.4.1 首次部署生成

可使用 `deploy/scripts/migrate-secrets.sh`（从已有环境迁移）或手动生成：

| Secret Key | 生成命令 | 说明 |
|------------|----------|------|
| `JWT_SECRET` | `openssl rand -hex 32` | JWT 签名密钥，≥32 字符随机串 |
| `POSTGRES_PASSWORD` | `openssl rand -hex 16` | PostgreSQL 数据库密码 |
| `REDIS_PASSWORD` | `openssl rand -hex 16` | Redis 密码 |
| `OSS_ACCESS_KEY_ID` | 从阿里云 RAM 控制台获取 | OSS 访问密钥 ID |
| `OSS_ACCESS_KEY_SECRET` | 从阿里云 RAM 控制台获取 | OSS 访问密钥（保密） |
| `STRIPE_API_KEY` | Stripe Dashboard 获取 | 支付 API Key（可选） |

#### 1.4.2 RAM 子账号（推荐）

为 OSS 单独创建 RAM 子账号，仅授予对 `comic-prod-oss` bucket 的 `AliyunOSSFullAccess`（生产可收窄到读写权限）。

---

## 二、配置定制

### 2.1 values-prod.yaml 关键配置项

文件路径：`deploy/helm/comic-platform/values-prod.yaml`

| 配置项 | 取值 | 说明 |
|--------|------|------|
| `global.imageRegistry` | `registry.cn-hangzhou.aliyuncs.com/<namespace>` | ACR 地址 |
| `global.imagePullSecrets` | `[{ name: acr-secret }]` | ACR 认证 Secret 名 |
| `global.imageTag` | `v0.8.0`（或部署时 `--set` 覆盖） | 镜像 tag |
| `ingress.host` | 实际域名（如 `comic.example.com`） | Ingress 域名 |
| `ingress.tls.enabled` | `true` | 启用 TLS |
| `certManager.enabled` | `true` | 启用 cert-manager 自动签发 |
| `certManager.issuerName` | `letsencrypt-prod` | ClusterIssuer 名称 |
| `monitoring.enabled` | `true` | 启用 P6 监控 |
| `oss.enabled` | `true` | 启用阿里云 OSS |
| `postgresql.external` | `true` | 使用 RDS（生产推荐） |
| `redis.external` | `true` | 使用云 Redis（生产推荐） |
| `hpa.web.enabled` | `true` | Web 自动伸缩 |
| `hpa.worker.enabled` | `true` | Worker 自动伸缩 |
| `pdb.enabled` | `true` | 中断预算 |
| `networkPolicy.enabled` | `true` | 网络策略 |

> **重要：所有密码（JWT_SECRET / POSTGRES_PASSWORD / REDIS_PASSWORD / OSS Key）通过 `--set` 或 K8s Secret 注入，绝不写入 values 文件**。

### 2.2 域名与 DNS

1. 在域名服务商添加 A 记录：
   - 主机记录：`comic`（或 `@`）
   - 记录类型：A
   - 记录值：ACK Ingress LoadBalancer 外网 IP（见 1.2.1）
2. TLS 证书由 cert-manager 自动签发，无需手动申请
3. 签发完成后证书存储在 Secret `comic-tls`（由 `ingress.tls.secretName` 指定）

---

## 三、部署步骤

### 3.1 首次部署

```bash
# 1. 创建 namespace
kubectl create namespace comic-production

# 2. 创建 registry pull secret（ACR 认证）
kubectl create secret docker-registry acr-secret \
  --namespace comic-production \
  --docker-server=registry.cn-hangzhou.aliyuncs.com \
  --docker-username=<user> \
  --docker-password=<password>

# 3. 创建应用 Secret
kubectl create secret generic comic-platform \
  --namespace comic-production \
  --from-literal=JWT_SECRET=$(openssl rand -hex 32) \
  --from-literal=POSTGRES_PASSWORD=$(openssl rand -hex 16) \
  --from-literal=REDIS_PASSWORD=$(openssl rand -hex 16) \
  --from-literal=OSS_ACCESS_KEY_ID=<key> \
  --from-literal=OSS_ACCESS_KEY_SECRET=<secret>

# 4. 部署（原子部署，失败自动回滚）
helm upgrade --install comic-platform \
  deploy/helm/comic-platform \
  -f deploy/helm/comic-platform/values-prod.yaml \
  --namespace comic-production \
  --atomic --timeout 15m --wait
```

> 提示：也可使用 `bash deploy/scripts/deploy.sh production v0.8.0` 一键部署。

### 3.2 升级部署（向后兼容）

从已部署的 dev / staging 环境首次升级到 P7 版本时，需迁移已有 Secret：

```bash
# 1. 迁移 Secret（仅首次升级 P7 版本时需要）
bash deploy/scripts/migrate-secrets.sh comic-production comic-platform

# 2. 合并迁移输出到 values-prod.yaml
cat /tmp/p7-secrets.yaml >> deploy/helm/comic-platform/values-prod.yaml

# 3. 升级
helm upgrade --install comic-platform \
  deploy/helm/comic-platform \
  -f deploy/helm/comic-platform/values-prod.yaml \
  --namespace comic-production \
  --atomic --timeout 15m --wait
```

> ⚠️ 迁移完成后，请人工核对 `/tmp/p7-secrets.yaml` 内容，并从 values 文件中移除明文密码（改用 Secret 注入）后再提交到仓库。

### 3.3 CD 自动部署

CI/CD 流水线（`.github/workflows/deploy.yml`）自动触发：

- **自动触发**：push tag `v*` → Release workflow → Deploy workflow（staging → production 灰度）
- **手动触发**：GitHub Actions → Deploy workflow → 选择 `environment`（staging / production）+ `image_tag`

CD 流水线关键步骤：

1. 从 GitHub Secrets 读取 `KUBE_CONFIG_PRODUCTION` 配置 kubectl
2. 校验 Secret `comic-platform` 已存在
3. 调用 `deploy/scripts/deploy.sh production <image_tag>`
4. Smoke test：rollout status + `/health` 健康检查
5. 失败自动回滚：`deploy/scripts/rollback.sh production`

---

## 四、验证清单

部署完成后，逐项验证：

- [ ] 所有 Pod Running：`kubectl get pods -n comic-production`
- [ ] Ingress 可访问：`curl https://<域名>/health` 返回 200
- [ ] TLS 证书有效：浏览器查看证书（签发方 Let's Encrypt）
- [ ] Prometheus 目标就绪：`kubectl get servicemonitor -n comic-production`
- [ ] Grafana 可访问：`kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80`
- [ ] 日志收集正常：Loki 查看应用日志
- [ ] 告警通道：飞书 webhook 测试（AlertManager）
- [ ] 文件上传：测试上传图片到 OSS
- [ ] 数据库连接：测试注册 / 登录流程
- [ ] Redis 连接：测试缓存命中
- [ ] GPU 节点：worker Pod 调度到 GPU 节点（`kubectl describe pod -l app.kubernetes.io/component=worker -n comic-production | grep nvidia`）
- [ ] 备份任务：cronjob 正常调度（`kubectl get cronjob -n comic-production`）

---

## 五、回滚策略

### 5.1 Helm Release 回滚

```bash
# 查看历史版本
helm history comic-platform -n comic-production

# 回滚到上一版本
helm rollback comic-platform -n comic-production

# 回滚到指定版本
helm rollback comic-production 5 -n comic-production
```

> 也可使用 `bash deploy/scripts/rollback.sh production`（上一版本）或 `bash deploy/scripts/rollback.sh production 5`（指定版本）。

### 5.2 回滚注意事项

- `helm rollback` 仅回滚 Helm 模板，**不会回滚数据库 schema**
- 若本次部署包含数据库 migration，回滚前需人工评估 schema 兼容性
- CD 流水线在部署失败时自动触发回滚（见 `deploy.yml` 的 `Rollback on failure` 步骤）

---

## 六、监控与运维

### 6.1 Prometheus 告警规则（P6）

告警规则定义在 `deploy/helm/comic-platform/templates/prometheus-rules.yaml`，关键告警：

- `ComicBackendDown`：Web / Worker Pod 不可用
- `ComicHighLatency`：API 延迟 > 2s
- `ComicGPUUsageHigh`：GPU 利用率 > 90%
- `ComicDBConnectionFailed`：数据库连接失败

### 6.2 Grafana 仪表盘（P6）

仪表盘 ConfigMap：`deploy/helm/comic-platform/templates/grafana-dashboard-configmap.yaml`

包含面板：API 性能、GPU 利用率、Pod 资源、队列深度、错误率。

### 6.3 日志查询（Loki）

```bash
# Grafana → Explore → Loki
# 查询示例
{namespace="comic-production"} |= "ERROR"
{namespace="comic-production", app="comic-backend-web"} |= "exception"
```

### 6.4 审计日志（AuditLog 模型）

- 模型定义：`backend/app/models/audit.py`
- 关键操作（登录 / 充值 / 模型训练 / 渲染）自动记录到数据库
- 通过 `/api/admin/audit` 接口查询（管理员权限）

### 6.5 备份策略

- 备份脚本：`backend/scripts/backup.py` + `backend/deploy/backup-cron.sh`
- K8s CronJob 定时执行：每日 02:00 全量备份
- 备份内容：PostgreSQL 全量 + OSS uploads/ 增量
- 备份存储：独立 OSS bucket `comic-prod-backup`

---

## 七、向后兼容说明

本次 P7 / P8 升级与已部署的 dev / staging 环境完全向后兼容：

1. **数据库**：无 schema 变更，P7 不需要数据迁移。现有 dev / staging 数据可直接被新版本读写
2. **Token**：PyJWT 迁移后仍使用 HS256 算法，旧 token 与新 token 互通，无需用户重新登录
3. **WebSocket**：服务端新增 30s ping 心跳，客户端需响应 ping（未响应会被断开重连）；旧客户端不会立即失效
4. **Secret**：首次升级使用 `migrate-secrets.sh` 从已有 Secret 提取值并合并到 values；之后的升级无需再次迁移
5. **镜像**：新镜像与旧镜像共用 PVC（uploads / models），数据无缝衔接；ImagePullPolicy 保持 `IfNotPresent`

---

## 八、灾难恢复

### 8.1 数据库备份恢复

```bash
# 1. 从 OSS 下载最近备份
ossutil cp oss://comic-prod-backup/pg/$(date +%Y%m%d).sql.gz /tmp/

# 2. 解压并恢复到 RDS
gunzip -c /tmp/$(date +%Y%m%d).sql.gz | \
  PGPASSWORD=<rds_password> psql -h <rds_host> -U comic -d comic
```

### 8.2 PVC 快照回滚

```bash
# 1. 列出 PVC 快照
kubectl get volumesnapshot -n comic-production

# 2. 从快照恢复 PVC
kubectl apply -f - <<EOF
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshotRestore
metadata:
  name: uploads-restore
  namespace: comic-production
spec:
  volumeSnapshotClassName: alicloud-disk-snapshot
  volumeSnapshot:
    name: uploads-snapshot-20260720
  targetPersistentVolumeClaim:
    name: comic-platform-uploads
EOF
```

### 8.3 镜像版本回滚

若新镜像存在严重 bug，可通过 Helm 回滚到上一镜像版本（见第五章）。如需回滚到任意历史版本：

```bash
# 指定历史镜像 tag 重新部署
helm upgrade --install comic-platform \
  deploy/helm/comic-platform \
  -f deploy/helm/comic-platform/values-prod.yaml \
  --set global.imageTag=v0.7.0 \
  --namespace comic-production \
  --atomic --timeout 15m --wait
```

---

## 附录：相关文件索引

| 文件 | 说明 |
|------|------|
| `deploy/helm/comic-platform/Chart.yaml` | Helm Chart 定义 |
| `deploy/helm/comic-platform/values.yaml` | 默认（dev）配置 |
| `deploy/helm/comic-platform/values-staging.yaml` | staging 配置 |
| `deploy/helm/comic-platform/values-prod.yaml` | 生产配置 |
| `deploy/scripts/deploy.sh` | 一键部署脚本 |
| `deploy/scripts/rollback.sh` | Helm 回滚脚本 |
| `deploy/scripts/migrate-secrets.sh` | Secret 迁移脚本 |
| `deploy/scripts/env-to-k8s-secret.sh` | .env → K8s Secret 转换 |
| `deploy/scripts/pre-deploy-check.sh` | 部署前检查脚本 |
| `deploy/monitoring/install.sh` | 监控栈安装脚本 |
| `.github/workflows/deploy.yml` | CD 流水线 |
| `backend/scripts/backup.py` | 数据库备份脚本 |
