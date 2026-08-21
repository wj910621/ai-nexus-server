#!/bin/bash
# install.sh - 安装 Prometheus + Grafana + Loki 监控栈
set -e
MONITORING_NS=${1:-monitoring}

echo "📦 添加 Helm 仓库"
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

echo "🚀 安装 kube-prometheus-stack"
helm upgrade --install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace "${MONITORING_NS}" \
  --create-namespace \
  -f "$(dirname "$0")/kube-prometheus-stack-values.yaml" \
  --atomic --timeout 10m

echo "🚀 安装 loki-stack"
helm upgrade --install loki-stack grafana/loki-stack \
  --namespace "${MONITORING_NS}" \
  -f "$(dirname "$0")/loki-stack-values.yaml" \
  --atomic --timeout 10m

echo "✅ 监控栈安装完成"
echo ""
echo "访问 Grafana："
echo "  kubectl -n ${MONITORING_NS} port-forward svc/kube-prometheus-stack-grafana 3000:80"
echo "  默认账号: admin / admin"
echo ""
echo "访问 Prometheus："
echo "  kubectl -n ${MONITORING_NS} port-forward svc/kube-prometheus-stack-prometheus 9090:9090"
