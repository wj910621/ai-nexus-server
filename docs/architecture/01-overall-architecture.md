# 整体架构设计

> 本文档详细描述漫剧生成软件（ComicStudio AI）的系统架构、分层设计、组件关系与数据流转。

---

## 一、架构概览

### 1.1 设计目标
- **可扩展性**：支持水平扩展，AI推理任务可分布式调度
- **高可用性**：核心服务无单点故障，支持故障自动转移
- **性能优先**：AI生成任务异步化，用户操作低延迟响应
- **开发友好**：前后端分离，模块解耦，支持团队并行开发
- **商业化就绪**：内置计费、限流、多租户支持

### 1.2 架构风格
采用**分层架构 + 微服务化**的混合模式：
- **分层架构**：清晰的职责划分（客户端→网关→业务→引擎→基础设施）
- **模块化服务**：业务服务按领域划分，可独立部署
- **事件驱动**：AI生成任务通过消息队列异步处理

---

## 二、系统分层架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           客户端层 (Client Layer)                         │
│                                                                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐         │
│  │  Desktop App    │  │    Web App      │  │  Mobile App     │         │
│  │  (Electron)     │  │  (React SPA)    │  │  (未来扩展)      │         │
│  │                 │  │                 │  │                 │         │
│  │ - 本地文件操作   │  │ - 浏览器访问    │  │ - 移动端预览    │         │
│  │ - 离线缓存      │  │ - 实时协作      │  │ - 通知推送      │         │
│  │ - 系统集成      │  │ - 云端同步      │  │                 │         │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘         │
└───────────┼────────────────────┼────────────────────┼──────────────────┘
            │                    │                    │
            └────────────────────┼────────────────────┘
                                 │ HTTPS / WSS
┌────────────────────────────────▼───────────────────────────────────────┐
│                         API网关层 (API Gateway)                         │
│                                                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ 认证授权  │ │ 限流熔断  │ │ 负载均衡  │ │ WebSocket│ │ API版本  │    │
│  │ JWT/OAuth│ │ RateLimit│ │ Nginx/   │ │ 实时通信  │ │ 管理路由  │    │
│  │          │ │          │ │ Traefik  │ │          │ │          │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────────────────┐
│                     业务服务层 (Business Services)                      │
│                                                                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │
│  │  用户服务    │ │  项目服务    │ │  素材服务    │ │  渲染服务    │     │
│  │ UserService │ │ProjectService│ │AssetService │ │RenderService│     │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │
│  │  角色服务    │ │  场景服务    │ │  剧本服务    │ │  分镜服务    │     │
│  │CharacterSvc │ │ SceneSvc    │ │ ScriptSvc   │ │StoryboardSvc│     │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │
│  │  配音服务    │ │  导出服务    │ │  计费服务    │ │  协作服务    │     │
│  │ AudioSvc    │ │ ExportSvc   │ │ BillingSvc  │ │ CollabSvc   │     │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘     │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────────────────┐
│                       AI引擎层 (AI Engine Layer)                       │
│                                                                        │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ 图像生成引擎  │ │ 角色一致性引擎│ │ 配音TTS引擎  │ │ 场景生成引擎  │ │
│  │ImageGenEngine│ │CharConsistEng│ │ TTSEngine    │ │SceneGenEngine│ │
│  │              │ │              │ │              │ │              │ │
│  │- SD/SDXL     │ │- IP-Adapter  │ │- Edge-TTS    │ │- 场景理解    │ │
│  │- ControlNet  │ │- LoRA        │ │- 本地模型    │ │- 透视控制    │ │
│  │- 图生图      │ │- Reference   │ │- 音色克隆    │ │- 光影生成    │ │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                   │
│  │ 分镜布局引擎  │ │ 视频合成引擎  │ │ 工作流编排引擎│                   │
│  │LayoutEngine  │ │VideoComposE  │ │WorkflowEngine│                   │
│  │              │ │              │ │              │                   │
│  │- 构图算法    │ │- FFmpeg      │ │- 节点调度    │                   │
│  │- 镜头语言    │ │- 帧合成      │ │- 依赖解析    │                   │
│  │- 视觉叙事    │ │- 特效处理    │ │- 模板系统    │                   │
│  └──────────────┘ └──────────────┘ └──────────────┘                   │
└────────────────────────────────┬───────────────────────────────────────┘
                                 │
┌────────────────────────────────▼───────────────────────────────────────┐
│                     基础设施层 (Infrastructure Layer)                   │
│                                                                        │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │PostgreSQL│ │  Redis   │ │ MinIO/S3 │ │ Celery   │ │ FFmpeg   │   │
│  │          │ │          │ │          │ │          │ │          │   │
│  │- 业务数据 │ │- 缓存    │ │- 素材存储 │ │- 任务队列 │ │- 视频处理 │   │
│  │- 用户数据 │ │- 会话    │ │- 生成结果 │ │- 异步任务 │ │- 转码    │   │
│  │- 项目数据 │ │- 消息队列│ │- 模型文件 │ │- 定时任务 │ │- 合成    │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心组件详解

### 3.1 客户端层

#### Desktop App (Electron)
```typescript
// desktop/main/main.ts - Electron主进程入口
import { app, BrowserWindow } from 'electron';
import path from 'path';

class MainWindow {
  private window: BrowserWindow | null = null;
  
  createWindow(): void {
    this.window = new BrowserWindow({
      width: 1440,
      height: 900,
      minWidth: 1024,
      minHeight: 768,
      webPreferences: {
        preload: path.join(__dirname, '../preload/index.js'),
        contextIsolation: true,
        nodeIntegration: false,
      },
    });
    
    // 开发环境加载本地开发服务器，生产环境加载打包文件
    if (process.env.NODE_ENV === 'development') {
      this.window.loadURL('http://localhost:5173');
    } else {
      this.window.loadFile(path.join(__dirname, '../renderer/index.html'));
    }
  }
}
```

**职责：**
- 提供原生桌面应用体验（Windows/macOS/Linux）
- 本地文件系统访问（素材导入、结果导出）
- 系统级集成（快捷键、通知、托盘）
- 离线缓存能力

#### Web App (React SPA)
```typescript
// frontend/src/App.tsx - React应用入口
import { BrowserRouter } from 'react-router-dom';
import { Provider } from 'react-redux';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import AppRoutes from './routes';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function App() {
  return (
    <Provider store={store}>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </Provider>
  );
}
```

**职责：**
- 浏览器端创作界面
- 实时协作编辑
- 云端项目管理
- 响应式布局适配

### 3.2 API网关层

```python
# backend/app/api/gateway.py - API网关配置
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_limiter import FastAPILimiter
import redis.asyncio as redis

class APIGateway:
    """API网关：统一入口，负责认证、限流、路由"""
    
    def __init__(self):
        self.app = FastAPI(title="ComicStudio API", version="1.0.0")
        self._setup_middleware()
        self._setup_routes()
    
    def _setup_middleware(self):
        """配置中间件"""
        # CORS跨域
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # 生产环境需配置具体域名
            allow_methods=["*"],
            allow_headers=["*"],
        )
        # JWT认证中间件
        self.app.middleware("http")(self._auth_middleware)
        # 请求日志中间件
        self.app.middleware("http")(self._logging_middleware)
    
    async def _auth_middleware(self, request: Request, call_next):
        """JWT认证中间件"""
        # 排除公开接口
        if request.url.path in ["/api/auth/login", "/api/auth/register", "/docs"]:
            return await call_next(request)
        
        token = request.headers.get("Authorization")
        if not token:
            return JSONResponse(status_code=401, content={"detail": "未授权"})
        
        # 验证token并注入用户信息
        user = await self._verify_token(token)
        request.state.user = user
        return await call_next(request)
```

**网关职责：**
- **认证授权**：JWT Token验证、OAuth2.0集成
- **限流熔断**：基于用户/IP/接口的多维度限流
- **负载均衡**：多实例服务的请求分发
- **WebSocket管理**：长连接管理与消息推送
- **API版本管理**：多版本API共存与路由

### 3.3 业务服务层

业务服务按**领域驱动设计（DDD）**划分，每个服务独立部署：

```python
# backend/app/services/base_service.py - 服务基类
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List
from sqlalchemy.orm import Session

T = TypeVar('T')

class BaseService(ABC, Generic[T]):
    """业务服务基类，提供CRUD和通用业务逻辑"""
    
    def __init__(self, db: Session):
        self.db = db
        self.repository = self._create_repository()
    
    @abstractmethod
    def _create_repository(self):
        """创建数据访问对象"""
        pass
    
    async def create(self, data: dict) -> T:
        """创建实体"""
        entity = self.repository.model(**data)
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity
    
    async def get_by_id(self, entity_id: int) -> Optional[T]:
        """根据ID获取实体"""
        return self.db.query(self.repository.model).filter(
            self.repository.model.id == entity_id
        ).first()
    
    async def update(self, entity_id: int, data: dict) -> Optional[T]:
        """更新实体"""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return None
        for key, value in data.items():
            setattr(entity, key, value)
        self.db.commit()
        self.db.refresh(entity)
        return entity
    
    async def delete(self, entity_id: int) -> bool:
        """删除实体"""
        entity = await self.get_by_id(entity_id)
        if not entity:
            return False
        self.db.delete(entity)
        self.db.commit()
        return True
```

**12个核心业务服务：**

| 服务 | 职责 | 关键方法 |
|------|------|----------|
| UserService | 用户注册、登录、权限管理 | register(), login(), update_profile() |
| ProjectService | 项目CRUD、版本管理 | create_project(), fork(), export_project() |
| AssetService | 素材上传、分类、检索 | upload(), search(), categorize() |
| RenderService | 渲染任务调度与管理 | submit_render(), get_status(), cancel() |
| CharacterService | 角色创建、管理、一致性 | create_character(), train_lora(), get_variants() |
| SceneService | 场景生成、模板管理 | generate_scene(), apply_template() |
| ScriptService | 剧本编辑、智能生成 | generate_script(), parse_script() |
| StoryboardService | 分镜生成、布局优化 | auto_storyboard(), adjust_layout() |
| AudioService | 配音合成、音效匹配 | synthesize_voice(), match_sfx() |
| ExportService | 多格式导出、打包 | export_video(), export_package() |
| BillingService | 计费、订阅、用量统计 | charge(), subscribe(), get_usage() |
| CollabService | 实时协作、冲突解决 | join_session(), sync_changes() |

### 3.4 AI引擎层

AI引擎层是系统的**核心竞争力**，封装了所有AI模型的调用逻辑：

```python
# backend/app/engines/base_engine.py - 引擎基类
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import torch
from pathlib import Path

class BaseEngine(ABC):
    """AI引擎基类，统一模型加载与推理接口"""
    
    def __init__(self, model_path: str, device: str = "cuda"):
        self.model_path = Path(model_path)
        self.device = device
        self.model = None
        self._loaded = False
    
    async def load_model(self) -> None:
        """加载模型到内存/GPU"""
        if self._loaded:
            return
        self.model = await self._load_model_impl()
        self.model.to(self.device)
        self._loaded = True
    
    @abstractmethod
    async def _load_model_impl(self):
        """子类实现具体的模型加载逻辑"""
        pass
    
    @abstractmethod
    async def infer(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行推理"""
        pass
    
    async def unload_model(self) -> None:
        """卸载模型释放显存"""
        if self.model:
            del self.model
            torch.cuda.empty_cache()
            self._loaded = False
```

**7大AI引擎：**

| 引擎 | 基础模型 | 核心能力 |
|------|---------|----------|
| ImageGenEngine | Stable Diffusion XL | 文生图、图生图、局部重绘 |
| CharConsistEngine | IP-Adapter + LoRA | 角色特征锁定、多视角生成 |
| TTSEngine | Edge-TTS / VITS | 语音合成、音色克隆 |
| SceneGenEngine | SD + ControlNet | 场景生成、透视控制 |
| LayoutEngine | 自研规则引擎 | 分镜构图、镜头语言 |
| VideoComposEngine | FFmpeg + AnimateDiff | 视频合成、过渡动画 |
| WorkflowEngine | 自研DAG引擎 | 节点编排、依赖调度 |

### 3.5 基础设施层

```yaml
# docker/docker-compose.yml - 基础设施服务编排
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: comic_studio
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
  
  redis:
    image: redis:7-alpine
    command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
  
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: ${MINIO_USER}
      MINIO_ROOT_PASSWORD: ${MINIO_PASSWORD}
    volumes:
      - minio_data:/data
    ports:
      - "9000:9000"
      - "9001:9001"
  
  celery_worker:
    build:
      context: ../backend
      dockerfile: Dockerfile.worker
    command: celery -A app.celery worker --loglevel=info --concurrency=4
    depends_on:
      - redis
      - postgres

volumes:
  postgres_data:
  minio_data:
```

---

## 四、数据流转架构

### 4.1 漫剧生成核心流程

```
用户输入剧本
     │
     ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  剧本解析    │ ──▶ │  分镜规划    │ ──▶ │  角色匹配    │
│ ScriptParser│     │StoryboardPln│     │ CharMatcher │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  视频合成    │ ◀── │  画面渲染    │ ◀── │  画面生成    │
│VideoComposE │     │ RenderEngine│     │ ImageGenEng │
└─────────────┘     └─────────────┘     └─────────────┘
     │                                         ▲
     ▼                                         │
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  最终导出    │ ◀── │  音效合成    │ ◀── │  配音生成    │
│ ExportSvc   │     │ AudioMixer  │     │ TTSEngine   │
└─────────────┘     └─────────────┘     └─────────────┘
```

### 4.2 异步任务处理流程

```python
# backend/app/workflows/comic_generation.py - 漫剧生成工作流
from celery import Celery, chain, group
from app.tasks.image_tasks import generate_frame
from app.tasks.audio_tasks import generate_voiceover
from app.tasks.video_tasks import compose_video

app = Celery('comic_studio', broker='redis://localhost:6379')

@app.task
def generate_comic(project_id: str, script_data: dict):
    """漫剧生成主任务"""
    
    # 1. 解析剧本，生成画面任务列表
    frames = parse_script_to_frames(script_data)
    
    # 2. 并行生成所有画面
    frame_tasks = group(
        generate_frame.s(frame) for frame in frames
    )
    
    # 3. 并行生成配音
    voice_tasks = group(
        generate_voiceover.s(frame) for frame in frames
    )
    
    # 4. 所有任务完成后合成视频
    workflow = chain(
        group(frame_tasks, voice_tasks),
        compose_video.s(project_id)
    )
    
    return workflow.apply_async()
```

### 4.3 实时协作数据流

```
用户A编辑 ──▶ WebSocket ──▶ 协作服务 ──▶ 广播变更 ──▶ 用户B更新
     │                          │
     │                          ▼
     │                    操作日志记录
     │                    冲突检测与解决
     │                          │
     └────── 同步确认 ◀─────────┘
```

---

## 五、关键技术决策

### 5.1 为什么选择前后端分离 + Electron？

| 方案 | 优势 | 劣势 | 选择理由 |
|------|------|------|----------|
| 纯桌面应用 | 性能好，离线可用 | 无法SaaS化，迭代慢 | ❌ 不符合商业化目标 |
| 纯Web应用 | 易分发，SaaS原生 | 无法本地AI推理，文件操作受限 | ❌ 无法满足AI算力需求 |
| **前后端分离+Electron** | **兼顾两者优势** | 架构稍复杂 | ✅ 最佳方案 |

### 5.2 为什么选择Python作为AI引擎？

- **生态优势**：PyTorch、Transformers、Diffusers等核心库均Python原生
- **模型兼容**：Stable Diffusion、ControlNet等模型均Python实现
- **开发效率**：AI算法迭代快，Python开发效率最高
- **社区支持**：AI社区以Python为主，问题解决资源丰富

### 5.3 为什么选择React而非Vue？

- **生态丰富**：React Flow（节点编辑器）、React Three.js（3D渲染）等关键库成熟
- **TypeScript支持**：类型系统完善，大型项目可维护性强
- **人才储备**：社区庞大，便于团队组建
- **性能优化**：Fiber架构 + 并发渲染，适合复杂交互场景

---

## 六、架构质量属性

### 6.1 性能指标

| 场景 | 指标 | 优化策略 |
|------|------|----------|
| 单帧图像生成 | < 5秒 (512x512) | TensorRT加速 + 批量推理 |
| 角色LoRA训练 | < 30分钟 | 低秩适应 + 早停策略 |
| 视频合成(30帧) | < 60秒 | GPU并行 + 流水线处理 |
| API响应时间 | < 200ms (P99) | Redis缓存 + 数据库索引 |
| 页面首屏加载 | < 2秒 | 代码分割 + CDN加速 |

### 6.2 可用性指标

| 指标 | 目标 | 保障措施 |
|------|------|----------|
| 系统可用性 | 99.9% | 多实例部署 + 自动故障转移 |
| 数据持久性 | 99.999% | PostgreSQL主从复制 + 定时备份 |
| 任务可靠性 | 99.5% | Celery重试机制 + 死信队列 |

### 6.3 安全性设计

- **认证授权**：JWT + RBAC权限模型
- **数据加密**：传输层TLS 1.3，存储层AES-256
- **输入校验**：Pydantic模型校验 + SQL注入防护
- **文件安全**：上传文件类型白名单 + 病毒扫描
- **API安全**：限流 + 防重放攻击 + 签名验证

---

## 七、架构演进路线

### Phase 1：MVP（单体架构）
- 单体后端 + 本地AI推理
- 核心功能：角色生成 + 分镜生成 + 基础导出
- 目标：验证产品可行性

### Phase 2：商业化（模块化）
- 服务模块化拆分
- 引入消息队列异步处理
- 上线SaaS版本
- 目标：支撑付费用户

### Phase 3：规模化（微服务）
- 完全微服务化
- AI推理服务独立扩缩容
- 多区域部署
- 目标：支撑大规模用户

### Phase 4：生态化（平台化）
- 开放API与插件SDK
- 素材市场上线
- 企业版私有化部署
- 目标：构建创作生态

---

*本文档最后更新：2026-07-18*
