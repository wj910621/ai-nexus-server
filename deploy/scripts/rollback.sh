#!/bin/bash
# rollback.sh - Phase 8 P4 Helm Rollback 脚本
#
# 用法：
#   ./rollback.sh prod              # 回滚到上一个 release
#   ./rollback.sh prod 5            # 回滚到指定 revision 5
#   ./rollback.sh prod --list       # 列出所有 revision
set -e

ENV=${1:-dev}
REVISION=${2:-}
NAMESPACE="comic-${ENV}"
RELEASE_NAME="comic-platform"

if [ "$REVISION" = "--list" ]; then
  echo "📜 ${RELEASE_NAME} 的 Helm history (namespace: ${NAMESPACE})"
  helm history "${RELEASE_NAME}" -n "${NAMESPACE}"
  exit 0
fi

echo "⏪ 回滚 ${RELEASE_NAME} (namespace: ${NAMESPACE})"

if [ -n "$REVISION" ]; then
  echo "   目标 revision: ${REVISION}"
  helm rollback "${RELEASE_NAME}" "${REVISION}" -n "${NAMESPACE}" --wait
else
  echo "   回滚到上一个 revision"
  helm rollback "${RELEASE_NAME}" -n "${NAMESPACE}" --wait
fi

echo "✅ 回滚完成"
echo ""
echo "当前状态："
helm status "${RELEASE_NAME}" -n "${NAMESPACE}"
