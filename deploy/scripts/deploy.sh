#!/bin/bash
# deploy.sh - Phase 8 P4 一键部署脚本
#
# 用法：
#   ./deploy.sh dev                      # 部署到 dev 环境
#   ./deploy.sh staging                  # 部署到 staging 环境
#   ./deploy.sh prod                     # 部署到 production 环境
#   ./deploy.sh staging v0.8.0           # 部署到 staging 环境并指定镜像 tag
#   ./deploy.sh production v0.8.0        # 部署到 production 环境并指定镜像 tag
#
# 参数：
#   $1 - 环境名称 (dev|staging|prod|production)
#   $2 - 可选，镜像 tag（如 v0.8.0）。未传入则使用 Chart values 中的默认 tag
#
# 前置条件：
#   - 已安装 helm 3.x
#   - 已配置 kubectl 上下文（指向阿里云 ACK 集群）
#   - 镜像已推送到镜像仓库
set -e

ENV=${1:-dev}
# 第二个参数为可选的镜像 tag，未传入时为空字符串，保持现有行为
IMAGE_TAG="${2:-}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
CHART_DIR="$(dirname "$0")/../helm/comic-platform"
RELEASE_NAME="comic-platform"

case $ENV in
  dev)
    VALUES_FILE="values.yaml"
    TIMEOUT="5m"
    NAMESPACE="comic-dev"
    ;;
  staging)
    VALUES_FILE="values-staging.yaml"
    TIMEOUT="10m"
    NAMESPACE="comic-staging"
    ;;
  prod|production)
    # 同时接受 prod 与 production 两种写法，CD 流水线使用 production
    VALUES_FILE="values-prod.yaml"
    TIMEOUT="15m"
    NAMESPACE="comic-production"
    ;;
  *)
    echo "❌ 未知环境: $ENV"
    echo "用法: $0 {dev|staging|prod|production} [image_tag]"
    exit 1
    ;;
esac

IMAGE_TAG_ARGS=()
if [ -n "${IMAGE_TAG}" ]; then
  if [[ ! "${IMAGE_TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]] \
    && [[ ! "${IMAGE_TAG}" =~ ^sha-[0-9a-f]{7,64}$ ]]; then
    echo "❌ 非法镜像 tag: ${IMAGE_TAG}"
    echo "仅接受语义版本 vX.Y.Z（可带预发布后缀）或 sha-<commit>"
    exit 1
  fi
  IMAGE_TAG_ARGS=(--set-string "global.imageTag=${IMAGE_TAG}")
  echo "   ImageTag: ${IMAGE_TAG}（覆盖默认 tag）"
fi

IMAGE_REGISTRY_ARGS=()
if [ -n "${IMAGE_REGISTRY}" ]; then
  if [[ ! "${IMAGE_REGISTRY}" =~ ^[a-z0-9.-]+(/[a-z0-9._-]+)+/$ ]]; then
    echo "❌ 非法镜像仓库前缀: ${IMAGE_REGISTRY}"
    exit 1
  fi
  IMAGE_REGISTRY_ARGS=(--set-string "global.imageRegistry=${IMAGE_REGISTRY}")
fi

if [[ "${ENV}" == "prod" || "${ENV}" == "production" ]]; then
  if [ -z "${IMAGE_TAG}" ] || [ "${IMAGE_TAG}" = "latest" ]; then
    echo "❌ 生产部署必须显式指定不可变镜像 tag，禁止 latest"
    exit 1
  fi
  if [ -z "${IMAGE_REGISTRY}" ]; then
    echo "❌ 生产部署必须通过 IMAGE_REGISTRY 指定不可变镜像所在仓库"
    exit 1
  fi
fi

echo "🚀 部署 comic-platform 到 ${ENV} 环境"
echo "   Namespace: ${NAMESPACE}"
echo "   Values:    ${VALUES_FILE}"
echo "   Timeout:   ${TIMEOUT}"
echo ""

# First installation creates ConfigMap/Secret with zero application replicas;
# the post-install migration hook then upgrades the empty database before any
# API or worker can accept traffic. Subsequent releases use the pre-upgrade
# migration hook.
if ! helm status "${RELEASE_NAME}" --namespace "${NAMESPACE}" >/dev/null 2>&1; then
  echo "首次安装：先创建基础资源并执行数据库迁移"
  helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
    -f "${CHART_DIR}/${VALUES_FILE}" \
    --namespace "${NAMESPACE}" \
    --create-namespace \
    --atomic \
    --timeout "${TIMEOUT}" \
    --wait \
    --wait-for-jobs \
    --set backend.web.replicas=0 \
    --set backend.worker.replicas=0 \
    --set frontend.replicas=0 \
    --set hpa.web.enabled=false \
    --set hpa.worker.enabled=false \
    "${IMAGE_TAG_ARGS[@]}" \
    "${IMAGE_REGISTRY_ARGS[@]}"
fi

# Helm upgrade --install（原子部署，失败自动回滚）
helm upgrade --install "${RELEASE_NAME}" "${CHART_DIR}" \
  -f "${CHART_DIR}/${VALUES_FILE}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --atomic \
  --timeout "${TIMEOUT}" \
  --wait \
  --wait-for-jobs \
  "${IMAGE_TAG_ARGS[@]}" \
  "${IMAGE_REGISTRY_ARGS[@]}"

echo ""
echo "✅ 部署成功！"
echo ""
echo "查看资源："
echo "  kubectl -n ${NAMESPACE} get pods"
echo "  kubectl -n ${NAMESPACE} get svc"
echo "  kubectl -n ${NAMESPACE} get ingress"
echo ""
echo "查看日志："
echo "  kubectl -n ${NAMESPACE} logs -l app.kubernetes.io/component=backend-web --tail=50"
echo ""
echo "运行 Helm 测试："
echo "  helm test ${RELEASE_NAME} -n ${NAMESPACE}"
