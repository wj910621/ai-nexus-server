# Y·NEX Story Studio 商业发布门禁

更新时间：2026-08（本机复核记录）｜原始评审定稿：2026-07-30（Asia/Shanghai）

## 当前结论

**状态：NO-GO（禁止公开生产流量）**

代码仓库已达到“可进入真实预发布验收”的状态，但当前工作区没有生产
Kubernetes、PostgreSQL、Redis、对象存储、DNS/TLS、Y·NEX 生产密钥和真实
支付环境的访问证据。任何人不得把本地测试或 Helm 离线渲染描述为已经上线。

品牌与系统边界固定为：

- 产品名：**Y·NEX Story Studio**
- 主站是唯一身份源和唯一积分账本；本项目不得建立第二套可充值余额。
- 主站入口：`/story/`；桌面下载：`/download/story/`
- 本项目 API：`/story-api/`；WebSocket：`/story-ws/`
- `BILLING_MODE=jarvis`，生产环境配置不完整时必须启动失败。

## 已通过并留有命令证据

| 门禁 | 结果 |
| --- | --- |
| 后端回归 | 1083 passed；积分流水排序额外连续 20 次通过 |
| 后端 Ruff | 全部通过 |
| 关键商业链路 mypy | 鉴权、配置、限流、Y·NEX 计费、Jarvis 网关 5 个模块 0 error |
| 全量类型债务防回退 | 194/194，新增错误即阻断；后续迁移 SQLAlchemy 2 `Mapped` |
| Python 依赖漏洞 | `pip-audit --strict`：No known vulnerabilities |
| 前端 | lint、typecheck、63 tests、production build 通过 |
| 桌面端 | typecheck、75 tests、build 通过 |
| Node 依赖 | 桌面端 0 vulnerability；前端仅保留有时限且不适用 RSC 的例外 |
| Helm | default/prod lint 通过，production 30 resources 渲染成功 |
| Kubernetes schema | kubeconform：33 resources，29 valid、0 invalid/error、4 个 Prometheus Operator CRD schema skipped |
| 数据库迁移静态链 | Alembic 001 → 013 单 head、连续 |
| 主站本地接入 | `story_bridge.js` 已挂载；欢迎页和 Nginx 路由已存在 |
| 训练安全 | 未完成的本地 LoRA 占位循环已 fail-closed，禁止生成伪 adapter；仅允许完成配置的 Replicate 路径 |
| 发布安全 | production 改为手动晋级；禁止 `latest`，只接受版本或 commit tag |
| 备份安全 | 加密依赖已纳入清单；生产缺少持久化密钥时 fail-closed |
| 生产配置 | 禁止 debug、本地数据库/Redis、HTTP CORS、启动时迁移和短服务令牌 |
| Helm 密钥注入 | 修复 ConfigMap 中 `$(PASSWORD)` 不会展开的问题；数据库/Redis 完整 URL 改由 Secret 注入 |
| CD Secret 门禁 | 生产部署逐项验证 11 个必需 Secret key，只检查存在性、不输出值 |
| 数据库发布迁移 | 首次安装以 0 副本引导并执行 post-install Alembic Job；后续升级由 pre-upgrade Job 阻断 |
| 容器可启动性 | Web/Worker 统一 Python 3.13；修复 `/app/.deps/bin` 未进入 PATH；CUDA Torch 固定为 2.6.0 |
| 镜像扫描 | Web、Worker、Frontend 三个发布镜像均以 Trivy HIGH/CRITICAL 阻断 |
| 数据库备份发布门禁 | production 手工晋级必须提供可追溯的托管 PostgreSQL 备份证据 ID 和不超过 60 分钟的 UTC 完成时间 |
| 迁移回滚兼容性 | CI 静态门禁禁止 Alembic `upgrade()` 删除表、列、约束或索引；收缩迁移必须拆分到后续独立发布 |
| 共享域名路由 | 生产统一使用 `ynexai.cn`；前端 `/story/`、API `/story-api/`、WebSocket `/story-ws/` 分离转发且不占用主站根路径 |
| 生产基础设施预检 | 晋级前强制检查集群、Secret 契约、不可变镜像、server-side dry-run、监控 CRD、TLS Secret 与 DNS；任一不可计算即阻断 |
| Ingress 准入兼容性 | 已移除 ingress-nginx `configuration-snippet` Critical 风险注解；安全响应头由前端 Nginx 与后端中间件直接输出 |
| Redis 多副本一致性 | 生产限流 Redis 或缓存 Redis 初始化失败时终止应用启动，不允许静默绕过或回退到单 Pod 内存 |
| 公开链路验收 | production 部署后自动执行 Helm test，并验证 `ynexai.cn/story/`、`/story-api/ready`、安全响应头及 `/story-ws/` 握手路由；失败自动进入回滚步骤 |
| 运营告警 | 使用 Prometheus Operator `AlertmanagerConfig`，Webhook 仅通过生产 Secret `ALERTING_WEBHOOK_URL` 引用；空接收器或缺少 CRD 时阻断晋级 |

## 仍然阻断公开上线的生产验收

以下每项必须保存时间戳、命令、退出码和脱敏输出：

1. 在真实 PostgreSQL 上执行备份、`alembic upgrade head`、回滚演练和恢复演练。
2. 验证 Redis 限流在多副本下原子生效，并确认 Redis 故障时生产请求返回 503。
3. 配置 Y·NEX SSO 服务令牌、`aud=story-studio`、价格清单及
   `STORY_CREDIT_PRICING_JSON`；验证过期、重放、错 audience 和跨用户访问均拒绝。
4. 用真实主站积分完成 charge、同幂等键重试、余额不足、上游超时、任务失败补偿
   refund；核对主账本仅记一次且余额守恒。
5. 不要求自动或每日巡检供应商官方目录。由 Y·NEX/Jarvis 后台维护模型成本、
   售价、币种、计费单位、启停状态和审核记录；production 晋级必须引用 24 小时内
   由管理员发布的价格版本证据。未审核或成本不可计算的模型保持下架。
6. 使用真实不可变镜像 tag 部署 staging，执行 API、WebSocket、worker、对象存储、
   GPU 调度、告警、备份和并发压测。
7. 对同一不可变镜像执行 production Helm server-side dry-run，再经受保护环境人工审批晋级。
8. 验证 `ynexai.cn/story/`、`/story-api/`、`/story-ws/` 和
   `/download/story/` 的 DNS、TLS、反代、CSP/CORS、缓存和健康检查。
9. 对购买确认、虚拟商品履行证据、客服争议流程和“不支持无理由退款”的适用边界完成
   法务复核；不得用页面文案排除法律强制退款、重复扣款或未履行退款。
10. 完成真实支付沙箱和至少一笔小额生产验收，并核对支付回调签名、幂等、对账和告警。

### 2026-07-30 当前环境与公网探测

当前执行机器没有 `kubectl`、Docker、PostgreSQL/Redis 客户端或 kubeconfig，也没有
生产 `DATABASE_URL`、`REDIS_URL`、Y·NEX Story SSO/服务令牌、价格清单或 Stripe
配置。主站现有 `.env` 同样没有 `STORY_SERVICE_TOKEN`、
`STORY_SSO_SECRET`、`STORY_CREDIT_PRICING_JSON`。因此上述真实环境验收尚无可连接
目标，不能通过生成本地占位值代替。

对 `ynexai.cn` 的无凭据公网探测进一步确认当前反向代理尚未接入 Story 服务：

- `/story/`、`/story-api/ready`、`/story-ws/` 均返回 `200 text/html`，响应体
  SHA-256 完全相同，标题均为主站 `Y·NEX — 亿界互联·无界未来`。
- `/story-api/ready` 未返回约定的 readiness JSON。
- 带标准 WebSocket Upgrade 请求的 `/story-ws/` 仍返回 `200` 和主站 HTML，
  未返回 `101 Switching Protocols`。
- 三个响应均未观察到本项目要求的 HSTS、CSP、X-Frame-Options 和
  X-Content-Type-Options 响应头。

本次无敏感信息的响应头、响应体和哈希证据保存在
`.artifacts/public-acceptance-20260730/`。该结果为明确的 production 公网验收失败，
不能因 HTTP 状态为 200 而放行。

同日使用真实浏览器渲染供应商当前 `/pricing` 页面，DOM 显示“页面未找到”；
主站现有目录审计共 716 条、可收费模型 0 条。按 2026-07-30 的运营决策，不再把
供应商目录自动抓取或每日巡检作为 Story 上线依赖；首次 production 晋级仍须由
Y·NEX/Jarvis 后台管理员人工录入并发布至少一个可售价格版本。未发布前禁止收费，
上线后的日常价格检查由管理员在主站后台完成。

## 明确的已知风险

- 全量 mypy 仍有 194 项旧式 SQLAlchemy/可选引擎类型债务；关键商业链路必须始终 0 error。
- React Router 的 RSC 公告对当前 BrowserRouter SPA 不可达，例外到
  2026-08-31 自动失效；届时必须升级或重新评估。
- kubeconform 跳过 3 个 Prometheus Operator CRD，生产集群需用实际 CRD
  server-side 校验。
- ~~当前本地目录不能作为有效 Git 发布来源~~：**已解决**——已初始化 Git 仓库（`main`，15 个提交，649 跟踪文件，无高熵密钥/真实 .env），正式发布仍须来自受保护分支、可追溯 commit、CI 产物和不可变镜像摘要。
- 按用户此前决定，桌面安装包正式代码签名、远程哈希/下载验证和既有泄露凭据轮换
  暂不纳入本轮完成项；这些豁免必须在发布审批记录中明确，不能误写成已完成。

## 本机复核记录（2026-08，放行结论未变更：仍为 NO-GO）

在原始评审之后，本机（无生产凭证）已完成如下**代码级**复核与修复，状态**仍为 NO-GO**（10 项真实环境验收未执行）：

- 后端全量测试 1076 passed（10 个 e2e_packaged 因本机 Windows 应用控制策略拦截冻结 exe 启动而 deselected；CI 上无该 exe 时应 skip）；前端 63 / 桌面 75 passed；Ruff 全过；mypy 关键链路 clean、全量债务 193≤194；Helm 结构 82 / CI 配置 29 / 安全·可观测 64 passed。
- 修复：YAML/文件读取 GBK 可移植性（test_helm_chart / test_desktop_installer）；CharacterCard 商业化门控测试；**release.yml build-desktop 改用 `build-variant.js`**（原 `packaging/build.py --variant` 会导致 CI 必然失败）；商业化开关注入生产构建（frontend Dockerfile + release.yml）。
- 运维模板补齐：`backend/.env.example` 覆盖全部 151 个 config 字段；`frontend/.env.example` 覆盖全部 5 个 VITE 变量；`vite-env.d.ts` 补声明 `VITE_COMMERCIAL_OPERATIONS_ENABLED`。
- 已初始化 Git 仓库（`main`，15 提交，无机密），并生成 `docs/deployment/PRODUCTION_LAUNCH_RUNBOOK.md`（10 项验收的可执行命令与凭证清单）。
- 文档一致性：API 域名统一为 `ynexai.cn`、桌面打包指南/README 同步变体构建、主文档品牌统一为 Y·NEX Story Studio。

**结论不变**：上述均为代码/文档层面工作，不等同于完成 10 项真实生产验收；放行仍须满足下列判定。

## 放行判定

只有当上面 10 项均有可复核证据，且没有开放的 P0/P1 缺陷时，才可把状态改为
`GO`。在此之前主站可以保留入口代码，但生产反代应维持关闭或仅对白名单预发布用户开放。
