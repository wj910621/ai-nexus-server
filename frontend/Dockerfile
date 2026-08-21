# =============================================================================
# 前端 Nginx 镜像 (多阶段构建)
# Phase 8 P4 K8s 容器化
# =============================================================================
# 构建命令：docker build -t frontend:latest .
# 运行命令：docker run -p 8080:8080 frontend:latest
# =============================================================================

# -----------------------------------------------------------------------------
# 阶段 1：builder - 编译前端静态资源
# -----------------------------------------------------------------------------
FROM node:20-alpine AS builder

ARG VITE_BASE_PATH=/story/
ARG VITE_ROUTER_BASE=/story
ARG VITE_API_BASE_URL=/story-api
ARG VITE_WS_BASE_URL=/story-ws
# 商业化开关（构建期注入）。默认关闭；经有权审批后方可在生产构建中置为 true。
ARG VITE_COMMERCIAL_OPERATIONS_ENABLED=false
ENV VITE_BASE_PATH=${VITE_BASE_PATH} \
    VITE_ROUTER_BASE=${VITE_ROUTER_BASE} \
    VITE_API_BASE_URL=${VITE_API_BASE_URL} \
    VITE_WS_BASE_URL=${VITE_WS_BASE_URL} \
    VITE_COMMERCIAL_OPERATIONS_ENABLED=${VITE_COMMERCIAL_OPERATIONS_ENABLED}

# 设置工作目录
WORKDIR /build

# 复制依赖清单文件（优先复制以利用 Docker 缓存）
# package-lock.json 确保 npm ci 严格还原依赖版本
COPY package.json package-lock.json ./

# 使用 npm ci 进行严格的依赖安装
# ci 命令比 install 更快、更可靠，适用于 CI/CD 与容器构建
RUN npm ci

# 复制源代码
COPY . .

# 执行生产构建，产物输出到 dist/ 目录
RUN npm run build

# -----------------------------------------------------------------------------
# 阶段 2：runtime - Nginx 静态资源服务
# -----------------------------------------------------------------------------
# Phase 8 P7 安全加固：使用 nginx-unprivileged 镜像，默认以非 root（UID 101）运行
# 该镜像默认监听 8080 端口（非特权端口），无需 root 即可绑定
FROM nginxinc/nginx-unprivileged:alpine AS runtime

# 维护者信息
LABEL maintainer="漫剧软件项目组" \
      description="前端 Nginx 静态资源服务 (非 root 运行)" \
      stage="phase8-p7-security"

# 从 builder 阶段复制编译产物到 Nginx 默认静态资源目录
# nginx-unprivileged 的静态资源目录仍为 /usr/share/nginx/html，UID 101 可读
COPY --from=builder /build/dist /usr/share/nginx/html

# 复制自定义 Nginx 配置（含 API 反向代理与 WebSocket 转发）
COPY nginx.conf /etc/nginx/conf.d/default.conf

# 暴露 HTTP 端口（nginx-unprivileged 默认监听 8080）
EXPOSE 8080

# 健康检查：使用 wget --spider 检测 Nginx 根路径响应
# 间隔 30s，超时 5s，启动等待 5s，重试 3 次
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --spider --quiet http://localhost:8080/ || exit 1

# Nginx 默认 CMD 已配置为启动 nginx -g 'daemon off;'
# 无需显式 CMD
