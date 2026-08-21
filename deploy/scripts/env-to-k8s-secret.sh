#!/bin/bash
# env-to-k8s-secret.sh - 将 .env 文件转换为 Kubernetes Secret
#
# 用法：
#   ./env-to-k8s-secret.sh .env production comic-platform-secret
#
# 参数：
#   $1 - .env 文件路径
#   $2 - Kubernetes namespace
#   $3 - Secret 名称
#
# 示例 .env 文件内容：
#   JWT_SECRET=your-jwt-secret
#   OSS_ACCESS_KEY_ID=LTAIxxxx
#   OSS_ACCESS_KEY_SECRET=xxxxxxxx
#   POSTGRES_PASSWORD=pg-password
#   REDIS_PASSWORD=redis-password
set -e

ENV_FILE=$1
NAMESPACE=$2
SECRET_NAME=$3

if [ -z "$ENV_FILE" ] || [ -z "$NAMESPACE" ] || [ -z "$SECRET_NAME" ]; then
  echo "用法: $0 <env-file> <namespace> <secret-name>"
  echo "示例: $0 .env production comic-platform-secret"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ .env 文件不存在: $ENV_FILE"
  exit 1
fi

echo "🔐 从 ${ENV_FILE} 创建 Secret ${SECRET_NAME} 在 namespace ${NAMESPACE}"

# 过滤空行和注释，--from-env-file 自动解析 KEY=VALUE 格式
kubectl create secret generic "${SECRET_NAME}" \
  --namespace "${NAMESPACE}" \
  --from-env-file="${ENV_FILE}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo "✅ Secret ${SECRET_NAME} 已创建/更新"
echo ""
echo "查看 Secret："
echo "  kubectl -n ${NAMESPACE} get secret ${SECRET_NAME}"
echo "  kubectl -n ${NAMESPACE} get secret ${SECRET_NAME} -o jsonpath='{.data}'"
