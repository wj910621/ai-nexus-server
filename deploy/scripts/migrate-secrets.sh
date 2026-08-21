#!/usr/bin/env bash
# Phase 8 P7: Secret 迁移脚本
# 用途：从现有 K8s Secret 读取值，生成 values-prod.yaml 覆盖片段
# 使用方法：bash migrate-secrets.sh [NAMESPACE] [RELEASE_NAME]
#   NAMESPACE   - Kubernetes 命名空间 (默认: default)
#   RELEASE_NAME - Helm Release 名称 (默认: comic-platform)
set -euo pipefail

NAMESPACE="${1:-default}"
RELEASE_NAME="${2:-comic-platform}"
SECRET_NAME="${RELEASE_NAME}"

echo "# P7 Secret 迁移输出 - $(date)" > /tmp/p7-secrets.yaml
echo "# 请将以下内容合并到 values-prod.yaml" >> /tmp/p7-secrets.yaml

JWT_SECRET=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.JWT_SECRET}' 2>/dev/null | base64 -d || echo "")
PG_PWD=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.POSTGRES_PASSWORD}' 2>/dev/null | base64 -d || echo "")
REDIS_PWD=$(kubectl get secret "$SECRET_NAME" -n "$NAMESPACE" -o jsonpath='{.data.REDIS_PASSWORD}' 2>/dev/null | base64 -d || echo "")

cat >> /tmp/p7-secrets.yaml <<EOF
jwt:
  secret: "${JWT_SECRET}"
postgresql:
  password: "${PG_PWD}"
redis:
  password: "${REDIS_PWD}"
EOF

echo "迁移完成，请查看 /tmp/p7-secrets.yaml 并合并到 values-prod.yaml"
