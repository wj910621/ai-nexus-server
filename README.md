# Y·NEX Story Studio（Y·NEX 漫剧工坊）

> **产品品牌：** Y·NEX Story Studio / Y·NEX 漫剧工坊  
> **定位：** AI驱动的漫剧创作一体化平台  
> **目标：** 打造"专业+易用"兼顾的商业化漫剧生成软件，类似ComfyUI的专业能力 + 即梦的易用体验

---

## 📖 文档导航

本Wiki文档分为以下几大板块，建议按顺序阅读：

### 🏗️ 架构设计 ([docs/architecture/](docs/architecture/))
- [整体架构设计](docs/architecture/01-overall-architecture.md) - 系统分层架构与组件关系
- [技术栈选型](docs/architecture/02-tech-stack.md) - 技术选型理由与对比分析
- [系统设计原则](docs/architecture/03-system-design.md) - 设计哲学与核心原则

### 🎨 核心功能模块 ([docs/modules/](docs/modules/))
- [角色设计与管理模块](docs/modules/character-module.md) - 角色创建、一致性控制、角色卡系统
- [场景构建模块](docs/modules/scene-module.md) - 场景生成、模板库、光影控制
- [剧本编排模块](docs/modules/script-module.md) - 智能剧本、分镜脚本、对话管理
- [分镜生成模块](docs/modules/storyboard-module.md) - 自动分镜、镜头语言、构图优化
- [配音音效模块](docs/modules/audio-module.md) - AI语音合成、音色定制、音效匹配
- [渲染导出模块](docs/modules/render-module.md) - 批量渲染、视频合成、多格式导出

### 🤖 AI引擎 ([docs/ai-engine/](docs/ai-engine/))
- [图像生成引擎](docs/ai-engine/image-generation.md) - 扩散模型集成与推理优化
- [角色一致性引擎](docs/ai-engine/character-consistency.md) - 跨帧角色特征锁定技术
- [工作流引擎](docs/ai-engine/workflow-engine.md) - 节点式工作流编排系统

### 🔌 API接口 ([docs/api/](docs/api/))
- [REST API文档](docs/api/rest-api.md) - HTTP接口规范与示例
- [WebSocket API文档](docs/api/websocket-api.md) - 实时通信接口规范

### 📚 关键类与函数 ([docs/classes/](docs/classes/))
- [核心数据类](docs/classes/core-classes.md) - 数据模型与实体定义
- [服务类](docs/classes/service-classes.md) - 业务服务层类说明
- [引擎类](docs/classes/engine-classes.md) - AI引擎层类说明

### 🚀 部署运维 ([docs/deployment/](docs/deployment/))
- [本地部署指南](docs/deployment/local-deployment.md) - 开发环境搭建
- [云端部署指南](docs/deployment/cloud-deployment.md) - 生产环境部署
- [开发指南](docs/deployment/dev-guide.md) - 开发规范与流程

### 💰 商业化 ([docs/business/](docs/business/))
- [商业化策略](docs/business/monetization.md) - 订阅模式、定价策略、生态建设

---

## 🎯 项目概述

### 产品定位
Y·NEX Story Studio 是一款面向漫剧创作者的 AI 一体化创作平台，解决三大核心痛点：
1. **创作门槛高** - 通过模板化创作+AI辅助，让小白用户10分钟生成漫剧
2. **角色一致性差** - 自研角色ID追踪技术，确保跨帧角色特征一致
3. **工具分散** - 从剧本到成片的一站式流程，无需多工具切换

### 核心能力
| 能力域 | 描述 | 技术壁垒 |
|--------|------|----------|
| 角色一致性 | 跨帧保持角色特征一致 | IP-Adapter + LoRA + Reference技术栈 |
| 剧情连贯性 | 理解上下文生成连贯画面 | 多模态LLM + 场景图理解 |
| 多模态融合 | 图文音视频联动生成 | 统一的多模态生成框架 |
| 工作流编排 | 节点式可视化创作 | 自研节点引擎 + 模板系统 |

### 目标用户
- **个人创作者（60%）**：漫画爱好者、自媒体作者、内容创业者
- **专业工作室（25%）**：漫画工作室、动画公司、MCN机构
- **企业客户（15%）**：品牌方、广告公司、教育机构

---

## 🏛️ 技术架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                          客户端层 (Client)                           │
│   Desktop (Electron)  │  Web (React SPA)  │  Mobile (未来扩展)       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                        API网关层 (Gateway)                          │
│        认证授权 / 限流 / 负载均衡 / WebSocket / 版本管理              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      业务服务层 (Business Services)                  │
│  用户服务 │ 项目服务 │ 素材服务 │ 渲染服务 │ 计费服务 │ 协作服务      │
│  角色服务 │ 场景服务 │ 剧本服务 │ 分镜服务 │ 配音服务 │ 导出服务      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                       AI引擎层 (AI Engine)                          │
│  图像生成引擎 │ 角色一致性引擎 │ 配音TTS引擎 │ 场景生成引擎           │
│  分镜布局引擎 │ 视频合成引擎   │ 工作流编排引擎                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────────────┐
│                      基础设施层 (Infrastructure)                     │
│  PostgreSQL │ Redis │ MinIO/S3 │ Celery │ FFmpeg │ 模型仓库          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 📁 项目目录结构

```
comic-studio-ai/
├── README.md                          # 项目总览（本文件）
├── docs/                              # 文档目录
│   ├── architecture/                  # 架构设计文档
│   ├── modules/                       # 核心模块文档
│   ├── ai-engine/                     # AI引擎文档
│   ├── api/                           # API文档
│   ├── classes/                       # 类与函数说明
│   ├── deployment/                    # 部署运维文档
│   └── business/                      # 商业化文档
├── backend/                           # 后端服务 (Python)
│   ├── app/                           # 应用主目录
│   │   ├── api/                       # API路由层
│   │   ├── services/                  # 业务服务层
│   │   ├── models/                    # 数据模型层
│   │   ├── engines/                   # AI引擎层
│   │   ├── workflows/                 # 工作流定义
│   │   ├── core/                      # 核心组件
│   │   └── utils/                     # 工具函数
│   ├── alembic/                       # 数据库迁移
│   ├── tests/                         # 测试代码
│   ├── requirements.txt               # Python依赖
│   └── main.py                        # 应用入口
├── frontend/                          # 前端应用 (React + TypeScript)
│   ├── src/
│   │   ├── components/                # 通用组件
│   │   ├── pages/                     # 页面组件
│   │   ├── features/                  # 功能模块
│   │   │   ├── character/             # 角色模块
│   │   │   ├── scene/                 # 场景模块
│   │   │   ├── script/                # 剧本模块
│   │   │   ├── storyboard/            # 分镜模块
│   │   │   ├── audio/                 # 配音模块
│   │   │   └── render/                # 渲染模块
│   │   ├── stores/                    # 状态管理
│   │   ├── services/                  # API调用
│   │   ├── hooks/                     # 自定义Hooks
│   │   ├── types/                     # TypeScript类型
│   │   └── utils/                     # 工具函数
│   ├── public/                        # 静态资源
│   ├── package.json                   # Node依赖
│   └── vite.config.ts                 # Vite配置
├── desktop/                           # Electron桌面端
│   ├── main/                          # 主进程
│   ├── preload/                       # 预加载脚本
│   └── electron-builder.json          # 打包配置
├── ai-models/                         # AI模型仓库
│   ├── checkpoints/                   # 基础模型
│   ├── lora/                          # LoRA模型
│   ├── controlnet/                    # ControlNet模型
│   └── embeddings/                    # 文本编码
├── docker/                            # Docker配置
│   ├── docker-compose.yml             # 开发环境
│   ├── docker-compose.prod.yml        # 生产环境
│   └── Dockerfile.*                   # 各服务Dockerfile
├── scripts/                           # 脚本工具
│   ├── setup.sh                       # 环境初始化
│   ├── download_models.py             # 模型下载
│   └── migrate.py                     # 数据库迁移
└── .github/                           # CI/CD配置
    └── workflows/                     # GitHub Actions
```

---

## 🚀 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- Docker 24+

### 一键启动（推荐）

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2. 启动开发环境 (Windows)
.\scripts\dev.ps1

# 或 (Linux/macOS)
./scripts/dev.sh
```

### 手动启动

```bash
# 1. 启动基础设施服务
cd docker
docker-compose up -d postgres redis minio

# 2. 启动后端
cd ../backend
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. 启动前端
cd ../frontend
npm install
npm run dev
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 前端 UI | http://localhost:5173 |
| 后端 API 文档 | http://localhost:8000/docs |
| MinIO 控制台 | http://localhost:9001 |

### 运行测试

```bash
# 后端测试
cd backend
python -m pytest tests/ -v
```

详细部署说明请参考 [本地部署指南](docs/deployment/local-deployment.md)。

---

## 📊 项目状态

| 模块 | 状态 | 说明 |
|------|------|------|
| 项目架构设计 | ✅ 完成 | 技术选型与架构设计已确定 |
| 核心模块设计 | ✅ 完成 | 6大核心模块功能规格完成 |
| AI引擎设计 | ✅ 完成 | 图像生成、一致性、工作流引擎设计完成 |
| API接口设计 | ✅ 完成 | REST + WebSocket接口规范完成 |
| 后端开发 | ✅ 基础完成 | FastAPI + SQLAlchemy + 9个API模块 + 17项测试通过 |
| 前端开发 | ✅ 基础完成 | React 18 + TypeScript + Vite + React Flow + TRAE风格UI |
| Docker 开发环境 | ✅ 完成 | docker-compose 编排 PostgreSQL/Redis/MinIO |
| 商业化方案 | ✅ 完成 | 订阅+按量+生态策略完成 |

---

## 📞 联系与反馈

- **项目仓库**：待创建
- **文档反馈**：请通过 Issue 提交
- **开发团队**：待组建

---

*本文档最后更新：2026-07-18*
