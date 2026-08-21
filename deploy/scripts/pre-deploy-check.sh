#!/usr/bin/env bash
# Fail-closed production infrastructure preflight.
set -uo pipefail

NAMESPACE="${1:-comic-production}"
RELEASE_NAME="${2:-comic-platform}"
DOMAIN="${3:-story.ynexai.cn}"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
IMAGE_TAG="${IMAGE_TAG:-}"
CHART_DIR="$(cd "$(dirname "$0")/../helm/comic-platform" && pwd)"
VALUES_FILE="${CHART_DIR}/values-prod.yaml"
SECRET_NAME="${RELEASE_NAME}"
PASS_COUNT=0
FAIL_COUNT=0

pass() {
  printf '[PASS] %s\n' "$1"
  PASS_COUNT=$((PASS_COUNT + 1))
}

fail() {
  printf '[FAIL] %s\n' "$1"
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

require_command() {
  if command -v "$1" >/dev/null 2>&1; then
    pass "$1 is available"
  else
    fail "$1 is unavailable"
  fi
}

check_secret_key() {
  local key="$1"
  local value
  value="$(kubectl get secret "${SECRET_NAME}" -n "${NAMESPACE}" \
    -o "jsonpath={.data.${key}}" 2>/dev/null || true)"
  if [ -n "${value}" ]; then
    pass "Secret contains ${key}"
  else
    fail "Secret ${SECRET_NAME} is missing ${key}"
  fi
}

printf 'Production preflight: namespace=%s release=%s domain=%s\n' \
  "${NAMESPACE}" "${RELEASE_NAME}" "${DOMAIN}"

require_command kubectl
require_command helm
require_command docker

if ! command -v kubectl >/dev/null 2>&1 || ! command -v helm >/dev/null 2>&1; then
  printf '[SUMMARY] pass=%d fail=%d\n' "${PASS_COUNT}" "${FAIL_COUNT}"
  exit 1
fi

if kubectl cluster-info >/dev/null 2>&1; then
  pass "Kubernetes API is reachable"
else
  fail "Kubernetes API is unreachable"
fi

if [ "$(kubectl get namespace "${NAMESPACE}" -o jsonpath='{.status.phase}' 2>/dev/null || true)" = "Active" ]; then
  pass "Production namespace is active"
else
  fail "Production namespace is missing or inactive"
fi

if kubectl get secret "${SECRET_NAME}" -n "${NAMESPACE}" >/dev/null 2>&1; then
  pass "Production application Secret exists"
  REQUIRED_KEYS=(
    APP_SECRET_KEY
    JWT_SECRET_KEY
    DATABASE_URL
    REDIS_URL
    RATE_LIMIT_REDIS_URL
    CELERY_BROKER_URL
    CELERY_RESULT_BACKEND
    JARVIS_GATEWAY_SERVICE_TOKEN
    YNEX_SSO_SECRET
    YNEX_BILLING_SERVICE_TOKEN
    ALERTING_WEBHOOK_URL
  )
  for key in "${REQUIRED_KEYS[@]}"; do
    check_secret_key "${key}"
  done
else
  fail "Production application Secret does not exist"
fi

if [ -z "${IMAGE_REGISTRY}" ] || [[ "${IMAGE_REGISTRY}" != */ ]]; then
  fail "IMAGE_REGISTRY must be a non-empty repository prefix ending in /"
fi
if [[ ! "${IMAGE_TAG}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]] \
  && [[ ! "${IMAGE_TAG}" =~ ^sha-[0-9a-f]{7,64}$ ]]; then
  fail "IMAGE_TAG must be an immutable semantic-version or sha-* tag"
fi

if command -v docker >/dev/null 2>&1 && [ -n "${IMAGE_REGISTRY}" ] && [ -n "${IMAGE_TAG}" ]; then
  for repository in comic-backend-web comic-backend-worker comic-frontend; do
    image="${IMAGE_REGISTRY}${repository}:${IMAGE_TAG}"
    if docker manifest inspect "${image}" >/dev/null 2>&1; then
      pass "Published image exists: ${image}"
    else
      fail "Published image is inaccessible: ${image}"
    fi
  done
fi

if helm template "${RELEASE_NAME}" "${CHART_DIR}" \
  -f "${VALUES_FILE}" \
  --set-string "global.imageRegistry=${IMAGE_REGISTRY}" \
  --set-string "global.imageTag=${IMAGE_TAG}" \
  --set-string "ingress.host=${DOMAIN}" \
  | kubectl apply --dry-run=server -f - >/dev/null 2>&1; then
  pass "Production manifests pass Kubernetes server-side dry-run"
else
  fail "Production manifests failed Kubernetes server-side dry-run"
fi

if kubectl get crd prometheusrules.monitoring.coreos.com >/dev/null 2>&1 \
  && kubectl get crd servicemonitors.monitoring.coreos.com >/dev/null 2>&1 \
  && kubectl get crd alertmanagerconfigs.monitoring.coreos.com >/dev/null 2>&1; then
  pass "Prometheus Operator CRDs are installed"
else
  fail "Required Prometheus Operator CRDs are missing"
fi

if [ "$(kubectl get secret comic-tls -n "${NAMESPACE}" -o jsonpath='{.type}' 2>/dev/null || true)" = "kubernetes.io/tls" ]; then
  pass "Production TLS Secret exists"
else
  fail "Production TLS Secret comic-tls is missing or invalid"
fi

if command -v getent >/dev/null 2>&1 && getent ahosts "${DOMAIN}" >/dev/null 2>&1; then
  pass "Production domain resolves"
else
  fail "Production domain does not resolve"
fi

printf '[SUMMARY] pass=%d fail=%d\n' "${PASS_COUNT}" "${FAIL_COUNT}"
if [ "${FAIL_COUNT}" -ne 0 ]; then
  exit 1
fi
