# Phase 8 P6 - 监控可观测性设计

## 概述

基于 P4 K8s 容器化基础，建立完整的监控可观测性体系，覆盖：
- **Metrics（指标）**: Prometheus 采集 + Grafana 可视化
- **Logs（日志）**: Loki + Promtail 聚合 K8s Pod 日志
- **Alerts（报警）**: Alertmanager + 飞书 webhook 通知

## 目标

1. 零成本：全开源方案（kube-prometheus-stack + Loki stack）
2. 业务可观测：API 延迟、Celery 队列、Provider 调用、DB/Redis 健康
3. 基础设施可观测：CPU/内存/磁盘/Pod 状态
4. 报警可执行：飞书机器人实时通知

## 架构

```
┌─────────────────────────────────────────────────────┐
│  K8s Cluster (comic-prod namespace)                 │
│                                                      │
│  ┌─────────────┐    metrics    ┌──────────────┐     │
│  │ backend-web │──────────────▶│ Prometheus   │     │
│  │ backend-worker│              │ (kube-prom   │     │
│  │ frontend    │              │  -stack)     │     │
│  └─────────────┘              └──────┬───────┘     │
│         │                             │              │
│         │ logs                        │ query        │
│         ▼                             ▼              │
│  ┌─────────────┐              ┌──────────────┐     │
│  │  Promtail   │──────────────│    Loki      │     │
│  │ (DaemonSet) │   push logs  │              │     │
│  └─────────────┘              └──────┬───────┘     │
│                                       │              │
│                              ┌────────▼───────┐     │
│                              │    Grafana     │     │
│                              │  (dashboards)  │     │
│                              └────────┬───────┘     │
│                                       │              │
│                              ┌────────▼───────┐     │
│                              │ Alertmanager   │     │
│                              │  → 飞书 webhook │     │
│                              └────────────────┘     │
└─────────────────────────────────────────────────────┘
```

## 范围

### 1. Prometheus ServiceMonitor
- `backend-web` ServiceMonitor：抓取 `/metrics` 端点（已暴露）
- `backend-worker` ServiceMonitor：抓取 worker metrics
- 抓取间隔 30s，超时 10s

### 2. Grafana Dashboards（ConfigMap 形式）
- **API 概览**: QPS、延迟 P50/P95/P99、错误率、状态码分布
- **Celery Worker**: 队列长度、活跃 worker、任务时长、失败率
- **基础设施**: Pod CPU/内存、节点资源、PVC 使用率
- **数据库**: 连接数、查询时长、慢查询

### 3. Alertmanager 报警规则
- **Critical**（立即通知）:
  - PodCrashLooping: Pod 重启次数 > 5 在 15min
  - DBConnectionFailure: /ready 返回 503 持续 2min
  - DiskUsageHigh: PVC 使用率 > 90%
- **Warning**（5min 内恢复则不通知）:
  - HighCPUUsage: CPU > 80% 持续 5min
  - HighMemoryUsage: 内存 > 85% 持续 5min
  - CeleryQueueBacklog: 队列长度 > 100 持续 5min
  - HTTP5xxErrorRate: 5xx 错误率 > 5% 持续 5min

### 4. Loki 日志聚合
- Promtail DaemonSet：收集所有 pod 日志
- 日志保留 30 天
- Loki PVC: 50Gi

### 5. Alertmanager 飞书通知
- 复用现有 `alerting_webhook_url` 配置
- 报警分组：critical 单独发，warning 汇总发
- 静默窗口：维护期间可静默

## 文件清单

```
deploy/
├── helm/
│   └── comic-platform/
│       └── templates/
│           ├── servicemonitor-web.yaml         # 新增
│           ├── servicemonitor-worker.yaml      # 新增
│           ├── grafana-dashboard-configmap.yaml # 新增
│           ├── prometheus-rules.yaml            # 新增
│           └── alertmanager-config.yaml         # 新增
└── monitoring/
    ├── kube-prometheus-stack-values.yaml        # 新增
    ├── loki-stack-values.yaml                   # 新增
    ├── dashboards/
    │   ├── api-overview.json                    # 新增
    │   ├── celery-worker.json                   # 新增
    │   └── infrastructure.json                  # 新增
    └── install.sh                               # 新增
backend/
└── app/
    └── core/
        └── metrics.py                           # 已有，补充 LLM token 指标
```

## 兼容性

- P4 Helm Chart 添加 `monitoring.enabled` 开关（默认 false），开启时才渲染 ServiceMonitor
- 现有 metrics.py 不破坏，只增量添加新指标
- 报警规则独立 ConfigMap，不修改 kube-prometheus-stack 默认值

## 不在范围

- 分布式追踪（Jaeger/Tempo）- 留到 Phase 9
- APM（应用性能监控）- 留到 Phase 9
- 自定义日志分析 - 用 Loki 查询即可
