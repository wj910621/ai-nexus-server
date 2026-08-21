# Phase 8 P7 - 安全加固 (Security Hardening) 设计文档

**日期**：2026-07-21
**阶段**：Phase 8 P7
**前置依赖**：P4 K8s 容器化（已完成）、P6 监控可观测性（已完成）
**后续**：P8 CI/CD 流水线、最终生产部署

---

## 1. 背景与目标

### 1.1 背景

P4 完成了 K8s 容器化部署能力，P6 完成了监控告警体系。但当前系统在应用层、容器层、集群层、依赖层均存在多处安全缺口，需在 P7 阶段系统性加固，使其达到生产可上线水平。

### 1.2 目标

- **应用层**：补齐 token 撤销闭环、限流落地、文件上传安全、CORS 收敛、密码策略、WebSocket 加固
- **集群层**：Pod securityContext、ServiceAccount、PSA、ResourceQuota、NetworkPolicy 精细化、cert-manager、Secret 治理
- **容器层**：Dockerfile 非 root 化、镜像不可变标签
- **依赖层**：修复 python-jose / python-multipart CVE、迁移 passlib、依赖锁定
- **测试层**：补齐安全测试套件
- **向后兼容**：已部署版本（dev/staging）可平滑升级，不破坏现有数据与登录态

### 1.3 非目标

- 不引入 Vault / Sealed Secrets / ExternalSecrets 等外部密钥管理系统（保留为 P9+ 选项）
- 不引入 Casbin 等 RBAC 框架（现有 admin/user 两档足够）
- 不实现 OAuth2 第三方登录
- 不实现镜像签名（cosign）— 留待 P8
- 不实现依赖漏洞扫描 CI step — 留待 P8

---

## 2. 设计原则

1. **纵深防御**：应用层 + 容器层 + 集群层多层独立防护
2. **最小权限**：Pod 无特权、SA 最小权限、NetworkPolicy 默认拒绝
3. **向后兼容优先**：所有变更通过 Helm 滚动更新平滑生效
4. **可验证**：每项加固配套测试用例
5. **零停机**：Deployment 滚动更新策略，健康探针保障

---

## 3. 模块划分

### 模块 A：应用层安全加固

#### A1. Token 撤销闭环

**问题**：`get_current_user` 解码 JWT 后未查询 `RevokedToken` 表，logout 后 access token 在 30 分钟自然过期前仍可用。WebSocket 同样未校验撤销。

**方案**：
- 在 `get_current_user` 与 `get_optional_user` 中增加 `RevokedToken` 查询，按 `jti` 检查
- WebSocket `_authenticate` 同步增加撤销检查
- 增加 Redis 缓存层：`revoked:{jti}` key，TTL = token 剩余有效期
- 失败时返回标准 401

**向后兼容**：现有未撤销 token 不受影响；表已存在无 schema 变更

#### A2. CORS 收敛

**问题**：同时开启 `allow_credentials=True` + `allow_methods=["*"]` + `allow_headers=["*"]`，违反 OWASP 建议。

**方案**：
- `allow_methods` 改为显式白名单：`["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]`
- `allow_headers` 改为显式白名单：`["Authorization", "Content-Type", "X-Request-ID", "X-Subscription-JWT"]`
- `expose_headers` 增加：`["X-Request-ID", "X-Subscription-JWT"]`
- 生产环境禁止 `*` 来源 + credentials 组合

**向后兼容**：前端使用的标准头均在白名单内

#### A3. 限流落地

**问题**：`@rate_limit` 装饰器实际是 no-op，从未调用 `fastapi_limiter`。

**方案**：
- 重写 `rate_limit` 装饰器，实际调用 `fastapi_limiter.limiter.limit()`
- 在登录端点 `/api/auth/login` 增加 IP 级限流（5 次/分钟）
- 在注册、密码重置、邮箱验证码端点增加 IP 级限流（3 次/分钟）
- 桌面模式维持禁用
- Redis 不可用时降级为内存限流

**向后兼容**：装饰器 API 不变；新增端点级限流不影响现有调用

#### A4. 文件上传安全

**问题**：上传端点无类型白名单、无大小限制、filename 未 sanitize。

**方案**：
- 新增 `backend/app/core/upload_security.py`：
  - `ALLOWED_MIME_TYPES = {"image/png", "image/jpeg", "image/webp", "image/gif"}`
  - `ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}`
  - `MAX_UPLOAD_SIZE = 20 * 1024 * 1024`  # 20MB
  - `sanitize_filename(name) -> str`：剥离路径、替换特殊字符、限制长度
  - `validate_magic_bytes(data) -> bool`：校验文件头 magic bytes
  - `validate_upload(file: UploadFile, max_size: int) -> bytes`：流式读取+校验
- 修改 `datasets.py` 上传端点使用上述工具
- 修改 `storage.save`：使用 `Path.resolve()` + `is_relative_to(base_dir)` 防路径穿越
- Nginx `client_max_body_size` 同步调整为 20M

**向后兼容**：现有已上传文件不受影响；合法图片文件可继续上传

#### A5. 密码策略强化

**问题**：仅 `min_length=6`，无复杂度要求。

**方案**：
- `UserCreate.password`：`min_length=8, max_length=128`
- 新增 `validate_password_complexity(password: str) -> str` Pydantic validator：
  - 至少 8 字符
  - 至少包含一个字母
  - 至少包含一个数字
  - 不在常见弱密码列表（top 1000）
- 密码重置端点同步应用该 validator
- 登录端点不强制复杂度（仅长度 ≥1，避免信息泄露）

**向后兼容**：现有用户密码不变；新注册或修改密码时应用新策略

#### A6. WebSocket 加固

**问题**：未校验 token type、无 origin 校验、无心跳超时、资源频道未校验所有权。

**方案**：
- `_authenticate` 增加 `token_type == "access"` 校验
- 增加 origin 校验：从 `settings.cors_origins_list` 提取允许的 host，拒绝跨站连接
- 增加心跳机制：服务端每 30s 发 `{"type":"ping"}`，客户端 60s 内未响应则关闭连接
- 资源频道 `task:{id}` / `image:{id}` / `video:{id}` 订阅前查询资源所有权（best-effort）

**向后兼容**：现有 WS 客户端需响应 ping；Electron 桌面端 origin 为 `file://` 加入白名单

#### A7. 配置启动校验

**问题**：默认值 `jwt_secret_key="change-me-to-a-jwt-secret"`、`app_secret_key="change-me"`，生产环境未强校验。

**方案**：
- 新增 `Settings.validate_production()` 方法，在 `app_env == "production"` 时检查：
  - `jwt_secret_key` 不在黑名单（`change-me-to-a-jwt-secret`、空、长度 < 32）
  - `app_secret_key` 不在黑名单
  - `database_url` 不包含默认弱密码 `comic_password`
  - `stripe_secret_key` 非空（若启用支付）
- 在 `app/main.py` lifespan 启动阶段调用，校验失败抛 `RuntimeError` 拒绝启动
- 桌面模式跳过校验

**向后兼容**：已正确配置的生产环境不受影响；未正确配置的环境会启动失败（预期行为）

#### A8. 路径穿越防护

**问题**：`storage.get_full_path` 未校验 `../`。

**方案**：
- 修改 `get_full_path`：使用 `Path.resolve()` 后 `is_relative_to(self.base_dir.resolve())` 校验
- 失败时抛 `ValueError("Invalid path")`
- 同步修改 `storage_async.py` 的 `LocalStorage.get_full_path`

**向后兼容**：合法路径不受影响

---

### 模块 B：K8s/Helm 集群层加固

#### B1. Pod securityContext 全套

**问题**：所有 Deployment 模板均无 securityContext。

**方案**：
- 在 `values.yaml` 增加 `podSecurityContext` 与 `containerSecurityContext` 默认配置：
  ```yaml
  podSecurityContext:
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
    seccompProfile:
      type: RuntimeDefault

  containerSecurityContext:
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true
    capabilities:
      drop: ["ALL"]
    runAsNonRoot: true
    runAsUser: 1000
    runAsGroup: 1000
  ```
- 三个 Deployment 模板增加 `spec.template.spec.securityContext` 与 `containers[].securityContext`
- Worker（GPU）特殊处理：`runAsUser: 0` 不可避免（NVIDIA 驱动要求），但 `allowPrivilegeEscalation: false` + `capabilities.drop: ["ALL"]` + `readOnlyRootFilesystem: false`（需写入 /tmp）
- 前端 nginx 容器：改用 `nginxinc/nginx-unprivileged:alpine` 镜像，监听 8080 端口，`runAsUser: 101`

**向后兼容**：滚动更新会重建 Pod；PVC 数据不受影响；web/worker 镜像需配套添加非 root 用户（见模块 C）

#### B2. ServiceAccount 与 RBAC

**问题**：所有 Deployment 使用 default ServiceAccount，且默认 automount token。

**方案**：
- 新增 `templates/serviceaccount.yaml`：为每个服务创建独立 SA
- 三个 Deployment 增加 `spec.serviceAccountName` + `spec.automountServiceAccountToken: false`
- 不创建额外 RBAC 角色绑定（应用不需要访问 K8s API）

**向后兼容**：新 SA 创建不影响现有 default SA

#### B3. Pod Security Admission (PSA)

**问题**：`namespace.yaml` 未打 PSA label。

**方案**：
- 修改 `namespace.yaml` 增加 labels：
  ```yaml
  labels:
    pod-security.kubernetes.io/enforce: baseline
    pod-security.kubernetes.io/enforce-version: latest
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/audit-version: latest
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: latest
  ```
- 决策：使用 `baseline` 而非 `restricted`（`restricted` 会拒绝 GPU Pod）

**向后兼容**：现有 Pod 不受 labels 影响；新建 Pod 需符合 PSA 级别

#### B4. ResourceQuota 与 LimitRange

**问题**：namespace 无资源配额与默认 limit。

**方案**：
- 新增 `templates/resourcequota.yaml`：限制 CPU/内存/PVC/Deployment/Pod 数量
- 新增 `templates/limitrange.yaml`：默认 request/limit 与最大值

**向后兼容**：现有无 resources 的 Pod 会被自动应用 default limit

#### B5. NetworkPolicy 精细化

**问题**：出站规则过于宽松（允许 0.0.0.0/0 的 80/443）。

**方案**：
- 重写 NetworkPolicy：
  - default-deny：保留
  - allow-internal：保留
  - allow-egress-dns：允许 kube-dns UDP/TCP 53
  - allow-egress-https：允许 0.0.0.0/0 的 TCP 443（OSS、外部 API、Stripe 等）
  - 删除 allow-egress-http（80 端口）— 除非显式配置
- 新增 PG/Redis 独立 NetworkPolicy：
  - PostgreSQL：仅允许 backend-web/backend-worker 入站 5432
  - Redis：仅允许 backend-web/backend-worker 入站 6379
- 新增 Ingress NetworkPolicy：
  - backend-web：仅允许 ingress-nginx namespace 或同 namespace 入站 8000
  - frontend：仅允许 ingress-nginx namespace 入站 8080

**向后兼容**：现有流量模式不变

#### B6. cert-manager 集成

**问题**：TLS secret 需手动创建。

**方案**：
- `values.yaml` 增加 `certManager.enabled: true` + `certManager.issuerType: "cluster-issuer"` + `certManager.issuerName: "letsencrypt-prod"`
- 修改 `ingress.yaml` 增加 annotations
- TLS secret 改为自动生成（cert-manager 创建）
- 文档说明如何安装 cert-manager 与创建 ClusterIssuer

**向后兼容**：`certManager.enabled: false` 时不影响现有手动 TLS secret 流程

#### B7. Ingress 注解加固

**问题**：无 HSTS、无 ssl-redirect、无 proxy-body-size、无 rate-limit。

**方案**：
- 增加 nginx ingress 注解：
  ```yaml
  nginx.ingress.kubernetes.io/ssl-redirect: "true"
  nginx.ingress.kubernetes.io/proxy-body-size: "20m"
  nginx.ingress.kubernetes.io/proxy-read-timeout: "300"
  nginx.ingress.kubernetes.io/proxy-send-timeout: "300"
  nginx.ingress.kubernetes.io/configuration-snippet: |
    more_set_headers "Strict-Transport-Security: max-age=31536000; includeSubDomains; preload";
    more_set_headers "X-Content-Type-Options: nosniff";
    more_set_headers "X-Frame-Options: SAMEORIGIN";
    more_set_headers "Referrer-Policy: strict-origin-when-cross-origin";
  ```

**向后兼容**：注解在 ingress 启用时生效

#### B8. Secret 治理改造

**问题**：
- Secret 密码必须 `--set` 传入，会出现在 helm history
- ConfigMap 中 `DATABASE_URL` 含密码

**方案**：
- Secret 随机生成：使用 `randAlphaNum` 生成默认密码，但允许 values 覆盖
- 改造 ConfigMap：移除 `DATABASE_URL` 中的密码部分，改为在 Deployment env 中拼接
- 新增 `templates/secret-registry.yaml`：Docker registry pull secret（如启用私有仓库）

**向后兼容**：
- 首次升级时若未通过 `--set` 传入密码，会生成新密码 — **必须提供迁移脚本**：`deploy/scripts/migrate-secrets.sh`，读取现有 Secret 值写入 values-prod.yaml
- ConfigMap 改造需在升级前确保所有 Deployment 使用新的 env 注入方式

#### B9. Redis 密码强制

**问题**：`REDIS_PASSWORD` `optional: true`。

**方案**：
- 移除 `optional: true`
- 修改 `values.yaml` 默认 `redis.password: ""` 改为 `redis.password: "change-me-in-production"`
- 修改 `redis-statefulset.yaml` 启动命令增加 `-a $(REDIS_PASSWORD)`
- 探针命令同步增加 `-a $(REDIS_PASSWORD)`

**向后兼容**：升级时若现有 Redis 无密码，需先手动设置密码或保持 `password: ""` 但显式声明

---

### 模块 C：Docker 镜像加固

#### C1. 非 root 用户

**问题**：`Dockerfile.web`、`Dockerfile.worker`、`Dockerfile` 均无 USER 指令。

**方案**：
- `Dockerfile.web`：添加 `RUN useradd -m -u 1000 appuser` + `USER appuser`
- `Dockerfile.worker`：GPU 容器需 root 访问 NVIDIA 驱动，保持 root 但 `chmod` 应用目录归属
- `frontend/Dockerfile`：改用 `nginxinc/nginx-unprivileged:alpine`，EXPOSE 8080

**向后兼容**：需同步修改 K8s Deployment 的 containerPort（前端 80→8080）

#### C2. .dockerignore 增强

**问题**：未排除 `.github/`、`deploy/`、证书文件。

**方案**：
- backend/.dockerignore 增加：`.github/`、`deploy/`、`*.pem`、`*.key`、`*.crt`、`secrets/`、`uploads/`、`ai-models/`、`logs/`、`coverage.xml`、`htmlcov/`
- frontend/.dockerignore 增加 `*.pem`、`*.key`、`*.crt`

**向后兼容**：不影响现有构建

#### C3. 镜像不可变标签

**问题**：三个服务 `tag: latest`。

**方案**：
- `values.yaml` 默认 `tag: ""`（空时使用 Chart appVersion）
- `values-prod.yaml` 改为具体版本 `tag: "0.8.0"`
- `values-staging.yaml` 改为 `tag: "0.8.0-rc"`
- Chart 模板 `{{ .Values.image.tag | default .Chart.AppVersion }}`

**向后兼容**：现有 latest 镜像仍可使用，生产强制版本号

---

### 模块 D：依赖安全

#### D1. python-jose CVE 修复

**问题**：`python-jose==3.3.0` 存在 CVE-2024-33663（算法混淆 + DoS）。

**方案**：
- 迁移到 `PyJWT==2.8.0`（更活跃、无已知 CVE）
- 修改 `backend/app/core/security.py`：
  - `from jose import jwt, JWTError` → `from jwt import encode, decode, InvalidTokenError`
  - `jwt.encode(to_encode, key, algorithm="HS256")` 接口不变
  - `jwt.decode(token, key, algorithms=["HS256"])` 接口不变
  - 异常类型：`JWTError` → `InvalidTokenError`
- 修改所有 `from jose` 导入

**向后兼容**：
- PyJWT 与 python-jose 都遵循 JWT 标准，生成的 token 互通
- 现有未过期 token 在迁移后仍可解码
- 算法 HS256 不变，密钥不变

#### D2. python-multipart CVE 修复

**问题**：`python-multipart==0.0.6` 存在 CVE-2024-24762（ReDoS）。

**方案**：升级到 `python-multipart==0.0.9`

#### D3. passlib 移除

**问题**：`passlib==1.7.4` 已停更，且与 bcrypt 4.x 不兼容；代码已直接 `import bcrypt`。

**方案**：
- 从 `requirements.txt` 移除 `passlib[bcrypt]`
- 确认 `bcrypt==4.1.2` 直接依赖
- 代码无 `from passlib` 导入（已确认）

#### D4. 依赖版本精确化

**问题**：多处使用 `>=`（httpx、Pillow、peft、datasets、replicate）。

**方案**：
- 全部改为精确版本：`httpx==0.27.0`、`Pillow==10.2.0`、`peft==0.10.0`、`datasets==2.18.0`、`replicate==0.25.1`
- 生成 `requirements.lock`（pip-compile 或 uv pip compile）— 留待 P8 CI 集成

**向后兼容**：版本固定不破坏功能

---

### 模块 E：安全测试套件

#### E1. 测试文件清单

新增以下测试文件：

| 文件 | 覆盖内容 |
|---|---|
| `backend/tests/test_security_token_revocation.py` | A1: token 撤销闭环 |
| `backend/tests/test_security_cors.py` | A2: CORS 配置 |
| `backend/tests/test_security_rate_limit.py` | A3: 限流落地 |
| `backend/tests/test_security_upload.py` | A4: 文件上传 |
| `backend/tests/test_security_password.py` | A5: 密码策略 |
| `backend/tests/test_security_websocket.py` | A6: WS 加固 |
| `backend/tests/test_security_config.py` | A7: 启动校验 |
| `backend/tests/test_security_storage.py` | A8: 路径穿越防护 |
| `backend/tests/test_helm_security.py` | B1-B9: Helm 模板安全 |

#### E2. 测试要求

- 每个测试文件至少 5 个测试用例
- 覆盖正向、负向、边界
- 安全测试不依赖外部服务（mock Redis/DB）
- Helm 模板测试延续 P4 的字符串断言策略

---

## 4. 向后兼容性策略

### 4.1 已部署版本升级路径

1. **代码层**：所有变更通过 PR 合入 main 分支
2. **数据库层**：无需 schema 变更（RevokedToken 表已存在）
3. **配置层**：新增字段均有默认值，旧 values.yaml 兼容
4. **镜像层**：新镜像与旧镜像共用同一 PVC（uploads/models）
5. **Secret 层**：
   - 首次升级使用 `deploy/scripts/migrate-secrets.sh` 读取现有 Secret 写入新 values
   - 后续升级正常 `helm upgrade`
6. **Token 层**：
   - PyJWT 迁移：现有 token 仍可解码（HS256 标准）
   - 撤销检查新增：现有未撤销 token 不受影响
7. **WebSocket 层**：
   - 现有客户端需响应 ping（30s 间隔），不响应则 60s 后断开
   - 桌面端 origin `file://` 加入白名单

### 4.2 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| securityContext 导致 Pod 启动失败 | 先在 staging 验证，分阶段滚动 |
| readOnlyRootFilesystem 导致写入失败 | 应用需写入 /tmp 的路径挂载 emptyDir |
| 非 root 用户无法绑定 80 端口 | 前端改用 nginx-unprivileged:8080 |
| ConfigMap 改造破坏现有 Pod | env 注入方式同步更新，分阶段发布 |
| Redis 密码强制导致连接失败 | 升级前手动设置 Redis 密码 |
| PyJWT 迁移引入新 bug | 完整测试覆盖 + staging 验证 |

### 4.3 回滚策略

- Helm `rollback` 命令回滚到上一 revision
- 数据库无需回滚（无 schema 变更）
- 镜像回滚：保留前 N 个版本镜像

---

## 5. 实施顺序

按风险优先级与依赖关系排序：

1. **D1-D4 依赖安全**（独立，无依赖）
2. **A7 配置启动校验**（独立）
3. **A1 token 撤销闭环**（依赖 D1 PyJWT 迁移完成）
4. **A2 CORS 收敛**（独立）
5. **A5 密码策略**（独立）
6. **A8 路径穿越防护**（独立）
7. **A4 文件上传安全**（依赖 A8）
8. **A3 限流落地**（独立）
9. **A6 WebSocket 加固**（依赖 A1）
10. **C1-C3 Docker 加固**（独立）
11. **B1-B9 Helm 加固**（依赖 C1 非 root 用户）
12. **E1-E2 安全测试**（伴随各模块）

---

## 6. 验收标准

- [ ] 所有安全测试通过（≥45 个新测试用例）
- [ ] 现有测试全部通过（无回归）
- [ ] `helm lint` 通过
- [ ] Helm 模板渲染测试通过
- [ ] staging 环境部署成功，Pod 全部 Running
- [ ] 安全扫描（pip-audit）无高危 CVE
- [ ] 文档更新：部署指南增加安全配置说明

---

## 7. 文件清单

### 新增文件

| 文件 | 用途 |
|---|---|
| `backend/app/core/upload_security.py` | 文件上传安全工具 |
| `backend/app/core/password_policy.py` | 密码策略 validator |
| `backend/app/core/config_validator.py` | 生产配置启动校验 |
| `deploy/helm/comic-platform/templates/serviceaccount.yaml` | ServiceAccount |
| `deploy/helm/comic-platform/templates/resourcequota.yaml` | ResourceQuota |
| `deploy/helm/comic-platform/templates/limitrange.yaml` | LimitRange |
| `deploy/helm/comic-platform/templates/networkpolicy-pg.yaml` | PostgreSQL NetworkPolicy |
| `deploy/helm/comic-platform/templates/networkpolicy-redis.yaml` | Redis NetworkPolicy |
| `deploy/scripts/migrate-secrets.sh` | Secret 迁移脚本 |
| `backend/tests/test_security_*.py` | 9 个安全测试文件 |

### 修改文件

| 文件 | 修改内容 |
|---|---|
| `backend/requirements.txt` | D1-D4 依赖升级 |
| `backend/app/core/security.py` | PyJWT 迁移 |
| `backend/app/core/deps.py` | A1 token 撤销检查 |
| `backend/app/api/websocket.py` | A6 WS 加固 |
| `backend/app/api/datasets.py` | A4 上传安全 |
| `backend/app/core/storage.py` | A8 路径穿越 |
| `backend/app/core/storage_async.py` | A8 路径穿越 |
| `backend/app/core/rate_limit.py` | A3 限流落地 |
| `backend/app/core/config.py` | A7 启动校验 |
| `backend/app/schemas/user.py` | A5 密码策略 |
| `backend/app/main.py` | A2 CORS + A7 启动校验调用 |
| `backend/Dockerfile.web` | C1 非 root |
| `backend/Dockerfile.worker` | C1 非 root（GPU 特殊） |
| `frontend/Dockerfile` | C1 nginx-unprivileged |
| `backend/.dockerignore` | C2 增强 |
| `frontend/.dockerignore` | C2 增强 |
| `frontend/nginx.conf` | 监听端口 8080 |
| `deploy/helm/comic-platform/values.yaml` | B1-B9 安全配置 |
| `deploy/helm/comic-platform/values-prod.yaml` | B1-B9 生产覆盖 |
| `deploy/helm/comic-platform/values-staging.yaml` | B1-B9 预发覆盖 |
| `deploy/helm/comic-platform/templates/namespace.yaml` | B3 PSA labels |
| `deploy/helm/comic-platform/templates/deployment-web.yaml` | B1 securityContext + B2 SA |
| `deploy/helm/comic-platform/templates/deployment-worker.yaml` | B1 + B2 |
| `deploy/helm/comic-platform/templates/deployment-frontend.yaml` | B1 + B2 + 端口 8080 |
| `deploy/helm/comic-platform/templates/ingress.yaml` | B6 cert-manager + B7 注解 |
| `deploy/helm/comic-platform/templates/networkpolicy.yaml` | B5 精细化 |
| `deploy/helm/comic-platform/templates/secret.yaml` | B8 随机生成 |
| `deploy/helm/comic-platform/templates/configmap.yaml` | B8 移除密码 |
| `deploy/helm/comic-platform/templates/redis-statefulset.yaml` | B9 密码强制 |
| `deploy/helm/comic-platform/templates/postgresql-statefulset.yaml` | B5 NetworkPolicy 引用 |

---

## 8. 风险与开放问题

1. **GPU Pod 与 PSA restricted 冲突**：当前决策使用 PSA `baseline`，若集群强制 `restricted` 需要分离 namespace
2. **ExternalSecrets 集成**：本期不实现，但 Secret 模板保留 `externalSecrets.enabled` 开关
3. **镜像签名 (cosign)**：留待 P8 CI/CD 一起做
4. **依赖漏洞扫描 CI**：留待 P8 CI/CD 一起做
5. **审计日志增强**：现有 AuditLog 已记录关键操作，本期不扩展
