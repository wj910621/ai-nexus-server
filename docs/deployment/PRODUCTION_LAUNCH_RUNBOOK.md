# Y路NEX Story Studio 商业化上线运行手册（Production Launch Runbook）

> 版本：2026-08（本机评审后整理）
> 关联日期：COMMERCIAL_RELEASE_GATE.md 更新于 2026-07-30，状态为 **NO-GO**
> 本文档把 Codex 评审遗留的、必须在**真实生产环境**完成的 10 项生产验收，整理为可逐步执行的清单，并记录本机已完成的代码级工作，明确边界。

---

## 0. 结论摘要

- **代码级门禁（本机已尽量验证）**：后端 1076 passed / Ruff 通过 / 前端 63 tests + 构建 + lint + typecheck 通过 / 桌面 75 tests + 构建通过 / Helm Chart 82 结构校验通过 / npm audit（桌面）0 漏洞。
- **现状仍为 NO-GO**：以下 10 项属于真实生产环境的操作与验收，**不依赖代码修改**，需要操作方提供：Kubernetes 集群 + kubeconfig、托管 PostgreSQL、Redis、对象存储、DNS/TLS、Y.NEX SSO/计费凭证、支付沙箱、法务复核。**本机无这些资源，无法伪造占位值代替验收**（评审已明文禁止）。

---

## 1. 前置：一键检查本地代码级门禁

在推送任何 tag 前，先在 CI 上确认绿色。CI 工作流已位于仓库根 .github/workflows/ 下（ci.yml / release.yml / deploy.yml / dependabot.yml）。

| 门禁 | 本地本机观测 |
|---|---|
| 后端测试 pytest -q | 1076 passed；10 个 e2e_packaged 被本机应用控制策略拦截（见 §5） |
| 后端 Ruff ruff check app/ | 通过 |
| 前端 tsc + vitest + build + eslint | 通过（63 tests） |
| 桌面 typecheck + test + build | 通过（75 tests）；npm audit 0 漏洞 |
| Helm lint + template + kubeconform | CI 内执行（本机无 helm/docker/kubectl） |

---

## 2. 商业化上线 10 项生产验收逐项执行清单

> 以下每项必须保存**时间戳、命令、退出码、脱敏输出**，可留存于 .artifacts/launch/ 下作为证据。

### ① 真实 PostgreSQL：备份 / 迁移 / 回滚演练
- 在托管 PostgreSQL 上执行备份；DATABASE_URL=<prod-url> alembic upgrade head；执行回滚与恢复演练（deploy/scripts/rollback.sh）。
- 交付：托管快照/备份证据 ID + UTC 完成时间（供 deploy.yml 的 backup_evidence_id/utc 门禁）。

### ② 真实 Redis 限流在多副本下原子生效
- 确认生产限流/缓存 Redis 初始化失败时应用启动**终止**（fail-closed），不得静默绕过或回退单 Pod 内存；Redis 故障时生产请求返回 503。
- 工序：kubectl 关闭 Redis → 观察 /ready 与 API 返回 503 → 恢复 Redis。

### ③ Y.NEX SSO 服务令牌 / audience / 价格清单 验证
- 配置主站签发的 JARVIS_GATEWAY_SERVICE_TOKEN、aud=story-studio、STORY_CREDIT_PRICING_JSON，验证过期、重放、错 audience、跨用户访问均被拒绝。
- Secret comic-platform（namespace comic-production）需含：APP_SECRET_KEY、JWT_SECRET_KEY、DATABASE_URL、REDIS_URL、RATE_LIMIT_REDIS_URL、CELERY_BROKER_URL、CELERY_RESULT_BACKEND、JARVIS_GATEWAY_SERVICE_TOKEN、YNEX_SSO_SECRET、YNEX_BILLING_SERVICE_TOKEN、ALERTING_WEBHOOK_URL。
- 主站 .env 需配置 STORY_SERVICE_TOKEN 与 STORY_SSO_SECRET（与 YNEX_BILLING_SERVICE_TOKEN / YNEX_SSO_SECRET 对齐）。

### ④ 真实主站积分计费对账
- 用真实主站积分完成 charge，含幂等重试、余额不足、上游超时、任务失败补偿、refund；核对主账本仅记一次且余额守恒。

### ⑤ 供应商目录与价格版本（运营决策，非自动抓取）
- 由 Y.NEX/Jarvis 后台维护模型成本、售价、币种、计费单位、启停状态、审核记录；production 晋级前 24 小时内由管理员发布价格版本并提供 pricing_evidence_id + pricing_approved_utc。
- 未审核或成本不可计算的模型保持下架。

### ⑥ staging 冒烟与压测（同一不可变镜像）
- 用同一 vX.Y.Z tag 部署 staging，执行 API / WebSocket / worker / 对象存储 / GPU 调度 / 告警 / 备份 / 并发压测。

### ⑦ production Helm server-side dry-run + 人工审批
- 对同一镜像执行 helm template 输出后 kubectl apply --dry-run=server（pre-deploy-check.sh 已实现），再由受保护 environment 人工审批晋级。

### ⑧ 共享域名验收（ynexai.cn）
- 验证 ynexai.cn/story/、/story-api/、/story-ws/、/download/story/ 的 DNS、TLS、反代、CSP/CORS、缓存、健康检查。
- 验收当前**失败**（2026-07-30 无证据探测）：三路径返回一致主站 HTML，缺 readiness JSON、101 握手与 HSTS/CSP/X-Frame-Options/X-Content-Type-Options。
- 修复目标（deploy.yml 的 Public shared-domain acceptance 已硬性检查）：/story-api/ready 返回 .data.status=ready；WebSocket 握手返回 400/401/403/426 之一；三个安全响应头必须出现。

### ⑨ 法务复核
- 对购买确认、虚拟商品履行证据、客服纠纷流程、不支持无理由退款的适用边界完成法务复核；页面文案不得排除法律强制退款、重复扣款或未履行退款。

### ⑩ 真实支付沙箱 + 首笔小额定单
- 配置支付沙箱；完成至少一笔小额定单生产收费，核对支付回调签名、订单、对账与告警。
- 注：BILLING_MODE=jarvis 下不使用 Stripe 独立收款，禁止 ComicStudio 创建第二套余额/订单账本。

---

## 3. 放行判定（GO 条件）

仅当上面 10 项均具备**可复核证据**且无未关闭的 P0/P1 缺陷，才可将 COMMERCIAL_RELEASE_GATE 状态改为 **GO**。在此之前主站可保留入口代码，但生产反代应维持关闭或仅对白名单预发布用户开放。

---

## 4. 商业化开关（本机已修复）

frontend/src/config/commercialOperations.ts 的 commercialOperationsEnabled 是**构建期**开关（import.meta.env.VITE_COMMERCIAL_OPERATIONS_ENABLED === 'true'）。此前生产构建缺乏注入途径导致前端永远暂未开放。

- 已修复：frontend/Dockerfile 新增 ARG VITE_COMMERCIAL_OPERATIONS_ENABLED=false；.github/workflows/release.yml 前端构建注入 VITE_COMMERCIAL_OPERATIONS_ENABLED（默认 false）。
- **上线动作**：只有当你已完成 §2 真实接入并通过放行判定后，才把 GitHub 变量 VITE_COMMERCIAL_OPERATIONS_ENABLED 置为 true 并重新触发 release；否则保持 false（安全默认）。
- 安全默认仍为 false，本次修改不破坏现有暂未开放行为。

---

## 5. 本地无法在本机完成的验证（如实说明）

| 项目 | 原因 |
|---|---|
| test_e2e_packaged.py（10 例） | 本机 Windows 应用控制策略拦截 PyInstaller 冻结 exe 启动（WinError 4551）；CI 未构建 exe 时应 skip。 |
| 网络型测试（edge-tts / pollinations / cdn） | 本机外发 HTTPS 被网络策略阻断；需在具网络出口的 CI/环境运行。 |
| npm/pip 在线审计 | 需要 registry 网络出口；CI security-scan job 已配置。 |
| helm lint / kubeconform / docker | 本机无 helm/docker/kubectl；CI helm-lint job 已配置。 |

---

## 6. 本机本次改动清单

- backend/tests/test_helm_chart.py：新增 _read_text / _load_yaml UTF-8 读取助手，替换全部无编码读取（修复 GBK 区域设置下 YAML 解析缺陷）。
- backend/tests/test_desktop_installer.py：open(..., encoding="utf-8") + 消除 E741 歧义变量（Ruff 全绿）。
- frontend/tests/components/CharacterCard.test.tsx：ready 分支断言与商业化门控 UI 一致（默认禁用态按钮）。
- frontend/Dockerfile：新增商业化开关 ARG/ENV。
- .github/workflows/release.yml：前端构建注入商业化开关变量。
- 初始化 Git 仓库并建立可追溯基线（main 分支，649 跟踪文件）：
  - `f38a99f` chore: production readiness baseline（CI/CD, release gate, docs）
  - `69a4a02` chore: add .gitattributes（跨平台行尾一致，CI 在 Linux 运行用）
  - `.gitignore` 增加 vendored 依赖/缓存排除（backend/.deps、.artifacts、*.cache 等），提交集从 8707 精简到 649 源文件；已扫描确认无高熵密钥/私钥/真实 .env。
- 说明：发布流程（git tag v* 触发 release → deploy）此前因**没有 Git 仓库**而无法工作；现已就绪，可直接进入受保护分支 + 版本标签发布流程。
- **修复桌面安装包构建（release.yml build-desktop）**：原 job 错误调用 `python packaging/build.py --variant <v>`（该脚本不支持 --variant，且只构建后端 exe 而非 Electron 安装包），会导致 CI 桌面构建必然失败。已改为正确调用 `node desktop/scripts/build-variant.js --target nsis-gpu|nsis-cpu|appimage-gpu|appimage-cpu`，矩阵 variant 同步为 Electron 目标，并加装核心依赖后构建，上传 desktop/release/*；`test_cicd.py` 新增回归断言（须出现 build-variant.js 与合法 Electron 目标、不得出现 packaging/build.py --variant）。桌面 .gitignore 增加生成的 `.electron-builder.*.yml`。
- **`docs/deployment/desktop-packaging.md` 同步 GPU/CPU 变体打包**：手动打包章节补充 `build-variant.js --target nsis-gpu/cpu|appimage-gpu/cpu`；CI 示例由过时的 `npm run package:win` 修正为 `node scripts/build-variant.js --target nsis-gpu`（与 `release.yml` build-desktop 一致）。
- **`docs/deployment/desktop-packaging.md` 同步 GPU/CPU 变体打包**：手动打包章节补充 `build-variant.js --target nsis-gpu/cpu|appimage-gpu/cpu`；CI 示例由过时的 `npm run package:win` 修正为 `node scripts/build-variant.js --target nsis-gpu`（与 `release.yml` build-desktop 一致）。
- **文档域名/部署模型一致性**：`docs/api/rest-api.md` 与 `websocket-api.md` 的旧域名 `api.comicstudio.ai` 改为生产共享域名 `ynexai.cn/story-api` 与 `ynexai.cn/story-ws`（注明本地地址）；`docs/deployment/cloud-deployment.md` 顶部加横幅：其描述的是早期自建独立部署（`comicstudio.ai`）历史参考，当前生产路径为 K8s+Helm+共享域名 `ynexai.cn`（`BILLING_MODE=jarvis`）。
- **桌面 README 补录 GPU/CPU 变体打包**：`desktop/README.md` 打包章节新增 `build-variant.js --target nsis-gpu/cpu|appimage-gpu/cpu`（与 CI release.yml build-desktop 一致），并注明等价 `npm run build:win-gpu` 等快捷方式（与 package.json 脚本逐条核对一致）。
- **补齐前端 env 类型与模板**：`frontend/src/vite-env.d.ts` 的 `ImportMetaEnv` 补充声明 `VITE_COMMERCIAL_OPERATIONS_ENABLED`（此前缺失、类型为 any）；`frontend/.env.example` 由 3 个变量扩展覆盖全部 5 个 `VITE_*`（新增 `VITE_ROUTER_BASE` 与 `VITE_COMMERCIAL_OPERATIONS_ENABLED`，并注明生产 `/story/` 覆盖项）。复查所有 `import.meta.env` 均已文档化，typecheck 0 错、63 测试通过。
- **补齐环境变量模板（.env.example）**：`backend/.env.example` 由 23 个变量扩展到覆盖**全部 151 个 config 字段**（原先 128 个可配置项缺失，运维按模板无法配置生产关键项），并按类分组给出安全占位值与 fail-closed 注释；根目录 `.env.example` 同步补齐 `COMMERCIAL_OPERATIONS_ENABLED`、`ADMIN_BOOTSTRAP_EMAIL`、`ALERTING_WEBHOOK_URL`、`BACKUP_ENCRYPTION_KEY`、`OSS_*`、`SMTP_*` 等生产关键项。已复查无重复键、config 加载测试 12 通过、安全/商业发布门禁 32 通过。
- **依赖集观察（需在 staging 验证，勿在未验证前改动不可变镜像）**：`backend/requirements.production.txt`（2026-08-01 新增，CPU-only 网关委托画像）剔除了 aiosqlite/flower/pytest/pyinstaller/replicate/peft/datasets/torch 等仅推理/训练/桌面/测试用包；但 `backend/Dockerfile.web` 与 `Dockerfile.worker` 目前均安装全量 `requirements.txt`，且 `Dockerfile.worker` 单独显式安装 `torch==2.6.0`（CUDA 12.4）用于本地 GPU 推理。分析确认去除的包均属惰性/测试/桌面路径（app 内 torch 均为函数内延迟 import）。
  - 建议：在 staging 冒烟（验收项⑥）验证 Web 层若无需 GPU 推理可改用 `requirements.production.txt` 以缩小镜像与 CVE 面；Worker 层因需本地 GPU 推理，应保留 torch+推理依赖。**不可变生产镜像的依赖集变更须在 staging 端到端验证通过后再并入**。

---

## 7. 你需要提供的真实环境凭证（一次性）

1. 生产 Kubernetes kubeconfig（staging/prod 各一），注入 GitHub Secrets KUBE_CONFIG_STAGING / KUBE_CONFIG_PRODUCTION（base64）。
2. 托管 PostgreSQL + Redis + 对象存储的连接与凭证。
3. 域名 ynexai.cn 的 DNS 与 TLS 证书（Secret comic-tls，namespace comic-production）。
4. 主站（Y.NEX）侧 STORY_SERVICE_TOKEN / STORY_SSO_SECRET，与 Story 侧 YNEX_BILLING_SERVICE_TOKEN / YNEX_SSO_SECRET 对齐。
5. 运营告警 webhook ALERTING_WEBHOOK_URL（HTTPS）。
6. 价格版本证据 ID + 审批时间；托管数据库备份证据 ID + UTC 完成时间。
7. 支付沙箱（BILLING_MODE=jarvis 则走主站统一账本）。
8. 法务对退款条款的复核结论。