# Phase 8 P8 - CI/CD 流水线 (CI/CD Pipeline) 设计文档

**日期**：2026-07-21
**阶段**：Phase 8 P8
**前置依赖**：P4 K8s 容器化、P6 监控、P7 安全加固（均已完成）
**后续**：最终生产部署

---

## 1. 背景与目标

### 1.1 现状问题

1. **工作流位置错误**：CI 配置位于 `backend/.github/workflows/`，GitHub Actions 只识别仓库根 `.github/workflows/`，导致所有 CI **实际未触发**
2. **无前端 CI**：前端无 lint/test/build 流水线
3. **无安全扫描**：缺少 pip-audit、npm audit、gitleaks、trivy 镜像扫描
4. **无 SBOM**：无软件物料清单生成
5. **镜像构建不完整**：docker-publish.yml 只构建 backend，缺 worker/frontend
6. **无 CD 流水线**：无自动部署到 K8s
7. **无 Helm lint**：Chart 无 CI 校验
8. **无 Dependabot**：依赖无自动更新

### 1.2 目标

- 将工作流迁移到仓库根 `.github/workflows/`
- 建立完整 CI：后端 + 前端 + Helm Chart
- 建立安全扫描：依赖扫描 + 密钥扫描 + 镜像扫描 + SBOM
- 建立多镜像构建发布：backend-web / backend-worker / frontend
- 建立 CD 流水线：tag 触发自动部署到 K8s（staging/prod）
- 配置 Dependabot

### 1.3 非目标

- 不实现镜像签名（cosign）— 需 KMS/Bare key，留待后续
- 不实现蓝绿部署 — 当前用 Helm 滚动更新足够
- 不实现 E2E 测试 — 留待后续

---

## 2. 工作流设计

### 2.1 ci.yml（持续集成）

**触发**：push main/develop，PR to main

**Jobs**：

1. **backend-test**（矩阵 Python 3.11/3.12/3.13）
   - Lint (ruff)
   - Type check (mypy, continue-on-error)
   - pytest + coverage
   - PostgreSQL 16 + Redis 7 service containers

2. **frontend-test**
   - Node 20
   - npm ci
   - Lint (tsc --noEmit)
   - Test (vitest)
   - Build (vite build)

3. **helm-lint**
   - Install helm CLI
   - helm lint deploy/helm/comic-platform
   - helm template + kubeconform 校验

4. **security-scan**
   - pip-audit（后端依赖 CVE 扫描）
   - npm audit（前端依赖）
   - gitleaks（密钥泄露扫描）
   - 允许失败（warning only），高危才阻断

### 2.2 release.yml（发布与镜像构建）

**触发**：push tag `v*`，workflow_dispatch

**Jobs**：

1. **build-backend-web**
   - docker/build-push-action 构建 backend/Dockerfile.web
   - 推送到 ghcr.io
   - 生成 SBOM（syft）
   - Trivy 镜像扫描

2. **build-backend-worker**
   - 构建 backend/Dockerfile.worker
   - 推送 + SBOM + Trivy

3. **build-frontend**
   - 构建 frontend/Dockerfile
   - 推送 + SBOM + Trivy

4. **build-desktop**（矩阵 windows/linux × gpu/cpu）
   - PyInstaller 打包
   - 上传 artifact

### 2.3 deploy.yml（持续部署）

**触发**：release.yml 完成后（workflow_run trigger），或手动

**Jobs**：

1. **deploy-staging**
   - 触发条件：tag 匹配 `v*-rc*` 或手动
   - helm upgrade --install 到 staging namespace
   - 使用 values-staging.yaml
   - 烟雾测试

2. **deploy-production**
   - 触发条件：tag 匹配 `v*`（非 rc）+ 手动审批
   - 需 environment: production
   - helm upgrade --install 到 production namespace
   - 使用 values-prod.yaml
   - 烟雾测试

### 2.4 dependabot.yml

- backend pip 依赖（每周）
- frontend npm 依赖（每周）
- github actions 版本（每周）
- docker base 镜像（每月）

---

## 3. 文件清单

### 新增文件（仓库根 `.github/`）

| 文件 | 用途 |
|---|---|
| `.github/workflows/ci.yml` | 持续集成 |
| `.github/workflows/release.yml` | 镜像构建发布 |
| `.github/workflows/deploy.yml` | 持续部署 |
| `.github/dependabot.yml` | 依赖自动更新 |
| `.github/workflows/helm-test.yml` | Helm Chart 测试（作为 ci.yml 的 reusable workflow） |

### 保留/迁移的文件

- `backend/.github/workflows/*.yml` 保留为历史参考（不再触发），实际工作流在仓库根

### 测试文件

| 文件 | 用途 |
|---|---|
| `backend/tests/test_cicd.py` | CI 配置文件校验测试 |

---

## 4. 向后兼容

- 现有 `backend/.github/workflows/` 保留不删除（避免破坏性变更）
- 新工作流在仓库根 `.github/workflows/`，GitHub Actions 自动识别
- CD 流水线使用 Helm 滚动更新，不破坏现有部署
- Secrets 通过 GitHub Actions secrets 配置，不写入代码

---

## 5. 验收标准

- [ ] CI 配置 YAML 语法正确
- [ ] `backend/tests/test_cicd.py` 通过
- [ ] 工作流文件位于 `.github/workflows/`
- [ ] Dependabot 配置存在
- [ ] 所有现有测试无回归
