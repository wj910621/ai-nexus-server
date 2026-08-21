# 技术栈选型

> 本文档详细说明漫剧生成软件各层级的选型理由、对比分析及版本要求。

---

## 一、技术栈总览

| 层级 | 技术 | 版本 | 选型理由 |
|------|------|------|----------|
| AI框架 | PyTorch | 2.1+ | 扩散模型生态最成熟，CUDA加速完善 |
| 后端框架 | FastAPI | 0.104+ | 高性能异步，自动API文档，类型安全 |
| 前端框架 | React | 18.2+ | 生态丰富，TypeScript支持完善 |
| 前端语言 | TypeScript | 5.3+ | 类型安全，大型项目可维护 |
| 桌面端 | Electron | 28+ | 跨平台，Web技术复用 |
| 构建工具 | Vite | 5+ | 极速HMR，现代化构建 |
| 状态管理 | Redux Toolkit | 2.0+ | 可预测状态，DevTools强大 |
| 数据请求 | TanStack Query | 5+ | 服务端状态管理，缓存智能 |
| 节点编辑器 | React Flow | 12+ | 成熟的节点式UI库 |
| 数据库 | PostgreSQL | 15+ | 功能丰富，JSON支持好 |
| 缓存 | Redis | 7+ | 高性能，数据结构丰富 |
| 对象存储 | MinIO / S3 | 最新 | 兼容S3协议，可私有部署 |
| 任务队列 | Celery | 5.3+ | Python生态成熟，功能完善 |
| 视频处理 | FFmpeg | 6+ | 业界标准，功能全面 |
| 容器化 | Docker | 24+ | 环境隔离，便于部署 |

---

## 二、AI框架选型：PyTorch

### 2.1 为什么选择PyTorch？

| 框架 | 优势 | 劣势 | 适用场景 |
|------|------|------|----------|
| **PyTorch** | 生态最丰富、动态图易调试、社区活跃 | 部署稍复杂 | 研究+生产 |
| TensorFlow | 部署成熟（TF Serving）、移动端支持好 | API复杂、调试难 | 生产部署 |
| JAX | 函数式编程、自动并行 | 生态小、学习曲线陡 | 研究前沿 |

**选择理由：**
1. **扩散模型生态**：Diffusers、Stable Diffusion、ControlNet等核心库均基于PyTorch
2. **模型兼容性**：HuggingFace生态原生支持，模型加载无缝
3. **调试友好**：动态计算图，便于算法迭代与问题排查
4. **GPU加速**：CUDA支持完善，配合TensorRT可极致优化

### 2.2 关键AI库依赖

```python
# backend/requirements.txt - AI相关依赖
torch>=2.1.0
torchvision>=0.16.0
torchaudio>=2.1.0

# 扩散模型生态
diffusers>=0.25.0
transformers>=4.36.0
accelerate>=0.25.0
safetensors>=0.4.0

# ControlNet与辅助模型
controlnet-aux>=0.0.7
mediapipe>=0.10.0

# 图像处理
Pillow>=10.0.0
opencv-python>=4.8.0
numpy>=1.24.0

# 模型加速
xformers>=0.0.23
tensorrt>=8.6.0  # 可选，生产环境加速

# TTS语音合成
edge-tts>=6.1.0
pyttsx3>=2.90

# 本地TTS模型（可选）
fairseq>=0.12.0
```

### 2.3 GPU推理优化策略

```python
# backend/app/engines/optimization.py - 推理优化
import torch
from diffusers import StableDiffusionPipeline, DPMSolverMultistepScheduler

class InferenceOptimizer:
    """推理优化器：降低显存占用，提升生成速度"""
    
    @staticmethod
    def optimize_pipeline(pipe: StableDiffusionPipeline) -> StableDiffusionPipeline:
        """优化SD Pipeline"""
        # 1. 使用半精度推理，显存减半
        pipe = pipe.to("cuda", torch.float16)
        
        # 2. 启用xformers内存高效注意力
        pipe.enable_xformers_memory_efficient_attention()
        
        # 3. 启用CPU offload，显存不足时卸载到CPU
        pipe.enable_model_cpu_offload()
        
        # 4. 使用DPM++求解器，步数减少50%
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config,
            use_karras_sigmas=True
        )
        
        return pipe
    
    @staticmethod
    def enable_attention_slicing(pipe):
        """注意力切片，降低显存峰值"""
        pipe.enable_attention_slicing(1)
    
    @staticmethod
    def enable_vae_slicing(pipe):
        """VAE切片，批量生成时节省显存"""
        pipe.enable_vae_slicing()
```

---

## 三、后端框架选型：FastAPI

### 3.1 框架对比

| 框架 | 性能 | 异步支持 | 类型安全 | 文档生成 | 学习曲线 |
|------|------|----------|----------|----------|----------|
| **FastAPI** | ⭐⭐⭐⭐⭐ | 原生async | Pydantic | 自动OpenAPI | 低 |
| Django | ⭐⭐⭐ | 部分支持 | DRF Serializer | 需插件 | 中 |
| Flask | ⭐⭐⭐ | 需扩展 | 无 | 需插件 | 低 |
| Tornado | ⭐⭐⭐⭐ | 原生async | 无 | 无 | 中 |

**选择理由：**
1. **性能卓越**：基于Starlette，性能媲美Node.js/Go
2. **异步原生**：AI推理IO密集，async/await提升吞吐量
3. **类型安全**：Pydantic模型校验，减少运行时错误
4. **自动文档**：OpenAPI/Swagger UI自动生成，降低维护成本
5. **WebSocket支持**：原生支持，便于实时通信

### 3.2 后端核心依赖

```python
# backend/requirements.txt - 后端框架依赖
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
python-multipart>=0.0.6

# 数据库ORM
sqlalchemy>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0  # PostgreSQL异步驱动

# Redis
redis[hiredis]>=5.0.0

# 任务队列
celery>=5.3.0
flower>=2.0.0  # Celery监控

# 认证授权
python-jose[cryptography]>=3.3.0  # JWT
passlib[bcrypt]>=1.7.4  # 密码哈希
python-multipart>=0.0.6

# 限流
fastapi-limiter>=0.1.5

# 对象存储
minio>=7.2.0
boto3>=1.34.0  # S3兼容

# 工具库
pydantic>=2.5.0
pydantic-settings>=2.1.0
loguru>=0.7.0  # 日志
httpx>=0.25.0  # 异步HTTP客户端
python-dotenv>=1.0.0
```

---

## 四、前端技术栈

### 4.1 核心框架

```json
// frontend/package.json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "react-router-dom": "^6.21.0",
    
    "@reduxjs/toolkit": "^2.0.0",
    "react-redux": "^9.0.0",
    
    "@tanstack/react-query": "^5.17.0",
    "axios": "^1.6.0",
    
    "reactflow": "^12.0.0",
    "@xyflow/react": "^12.0.0",
    
    "antd": "^5.12.0",
    "tailwindcss": "^3.4.0",
    
    "zustand": "^4.4.0",
    "immer": "^10.0.0",
    
    "socket.io-client": "^4.7.0",
    
    "fabric": "^5.3.0",
    "konva": "^9.3.0",
    "react-konva": "^18.2.0",
    
    "dayjs": "^1.11.0",
    "lodash-es": "^4.17.0"
  },
  "devDependencies": {
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "@vitejs/plugin-react": "^4.2.0",
    
    "eslint": "^8.56.0",
    "@typescript-eslint/eslint-plugin": "^6.15.0",
    "prettier": "^3.1.0",
    
    "vitest": "^1.1.0",
    "@testing-library/react": "^14.1.0",
    
    "@storybook/react": "^7.6.0"
  }
}
```

### 4.2 关键库选型理由

#### React Flow（节点编辑器）
```typescript
// 选择理由：ComfyUI式节点编辑的最佳选择
import ReactFlow, { 
  Background, 
  Controls, 
  MiniMap,
  Node, 
  Edge,
  ConnectionMode
} from 'reactflow';

// 自定义节点示例：图像生成节点
function ImageGenNode({ data }: { data: ImageGenNodeData }) {
  return (
    <div className="bg-white rounded-lg shadow-lg p-4 w-64">
      <div className="font-bold text-sm mb-2">图像生成</div>
      <select className="w-full border rounded px-2 py-1 mb-2">
        <option>Stable Diffusion XL</option>
        <option>SD 1.5</option>
      </select>
      <textarea 
        placeholder="输入提示词..."
        className="w-full border rounded px-2 py-1 text-sm"
      />
    </div>
  );
}
```

**选择理由：**
- 专为节点式UI设计，API完善
- 支持自定义节点、连线、端口
- 拖拽、缩放、选择等交互内置
- TypeScript支持优秀
- 社区活跃，文档完善

#### TanStack Query（数据请求）
```typescript
// 选择理由：服务端状态管理的最佳实践
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';

// 角色列表查询
function useCharacters(projectId: string) {
  return useQuery({
    queryKey: ['characters', projectId],
    queryFn: () => characterApi.list(projectId),
    staleTime: 5 * 60 * 1000,  // 5分钟内不重新请求
  });
}

// 角色创建
function useCreateCharacter() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: characterApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['characters'] });
    },
  });
}
```

#### Zustand（轻量状态管理）
```typescript
// 选择理由：简单场景的状态管理，避免Redux样板代码
import { create } from 'zustand';
import { immer } from 'zustand/middleware/immer';

interface EditorState {
  selectedNodeId: string | null;
  isPlaying: boolean;
  currentFrame: number;
  selectNode: (id: string | null) => void;
  play: () => void;
  pause: () => void;
  setFrame: (frame: number) => void;
}

export const useEditorStore = create<EditorState>()(
  immer((set) => ({
    selectedNodeId: null,
    isPlaying: false,
    currentFrame: 0,
    selectNode: (id) => set((state) => {
      state.selectedNodeId = id;
    }),
    play: () => set((state) => {
      state.isPlaying = true;
    }),
    pause: () => set((state) => {
      state.isPlaying = false;
    }),
    setFrame: (frame) => set((state) => {
      state.currentFrame = frame;
    }),
  }))
);
```

---

## 五、桌面端选型：Electron

### 5.1 为什么选择Electron？

| 方案 | 跨平台 | Web技术复用 | 性能 | 包体积 | 生态 |
|------|--------|-------------|------|--------|------|
| **Electron** | ✅ | ✅ 完全复用 | 中 | 大(~100MB) | ⭐⭐⭐⭐⭐ |
| Tauri | ✅ | ✅ | 高 | 小(~10MB) | ⭐⭐⭐ |
| Qt | ✅ | ❌ | 高 | 中 | ⭐⭐⭐⭐ |
| .NET MAUI | ✅ | ❌ | 高 | 中 | ⭐⭐ |

**选择理由：**
1. **Web技术复用**：与Web版前端代码100%复用，降低维护成本
2. **生态成熟**：VS Code、Figma、Discord等大型应用验证
3. **开发效率**：一套代码三端运行（Win/Mac/Linux）
4. **社区支持**：问题解决方案丰富，第三方库兼容性好

### 5.2 Electron架构

```typescript
// desktop/main/main.ts - 主进程
import { app, BrowserWindow, ipcMain } from 'electron';
import path from 'path';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 900,
    show: false,  // 防止白屏闪烁
    webPreferences: {
      preload: path.join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.once('ready-to-show', () => {
    mainWindow?.show();
  });

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }
}

// IPC通信处理
ipcMain.handle('dialog:openFile', async () => {
  const result = await dialog.showOpenDialog(mainWindow!, {
    properties: ['openFile'],
    filters: [{ name: 'Images', extensions: ['png', 'jpg', 'webp'] }],
  });
  return result;
});

app.whenReady().then(createWindow);
```

```typescript
// desktop/preload/index.ts - 预加载脚本（安全桥接）
import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
  openFile: () => ipcRenderer.invoke('dialog:openFile'),
  saveFile: (data: Buffer, filename: string) => 
    ipcRenderer.invoke('dialog:saveFile', data, filename),
  onMenuAction: (callback: (action: string) => void) =>
    ipcRenderer.on('menu-action', (_, action) => callback(action)),
});
```

---

## 六、数据存储选型

### 6.1 PostgreSQL

**选择理由：**
- **JSON支持**：存储灵活的配置数据（工作流定义、角色属性）
- **全文搜索**：内置中文全文搜索，支持素材检索
- **事务支持**：ACID事务，保证数据一致性
- **扩展性**：pgvector扩展支持向量检索（AI相似度搜索）

```sql
-- 数据库扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID主键
CREATE EXTENSION IF NOT EXISTS "pgvector";    -- 向量检索
CREATE EXTENSION IF NOT EXISTS "pg_trgm";     -- 模糊搜索

-- 角色表示例（含向量字段）
CREATE TABLE characters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id),
    name VARCHAR(100) NOT NULL,
    description TEXT,
    style VARCHAR(50),
    -- 角色特征向量，用于一致性检索
    feature_vector VECTOR(512),
    -- 角色配置（JSON）
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 向量索引，加速相似度检索
CREATE INDEX idx_characters_vector ON characters 
    USING ivfflat (feature_vector vector_cosine_ops);
```

### 6.2 Redis

**使用场景：**
- **缓存**：热点数据缓存（用户会话、项目配置）
- **消息队列**：Celery任务队列broker
- **实时通信**：WebSocket适配器（多实例广播）
- **限流**：API限流计数器

```python
# backend/app/core/redis.py - Redis配置
import redis.asyncio as redis
from redis.connection import ConnectionPool

class RedisManager:
    """Redis连接管理器"""
    
    def __init__(self, url: str = "redis://localhost:6379"):
        self.pool = ConnectionPool.from_url(url, max_connections=50)
        self._client = None
    
    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(connection_pool=self.pool)
        return self._client
    
    async def cache_json(self, key: str, value: dict, ttl: int = 3600):
        """缓存JSON数据"""
        import json
        await self.client.setex(key, ttl, json.dumps(value))
    
    async def get_cached_json(self, key: str) -> dict | None:
        """获取缓存的JSON数据"""
        import json
        data = await self.client.get(key)
        return json.loads(data) if data else None
```

### 6.3 MinIO / S3

```python
# backend/app/core/storage.py - 对象存储
from minio import Minio
from minio.error import S3Error
from io import BytesIO

class StorageManager:
    """对象存储管理器，兼容S3协议"""
    
    def __init__(self, endpoint: str, access_key: str, secret_key: str):
        self.client = Minio(
            endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=False  # 生产环境设为True
        )
        self._ensure_buckets()
    
    def _ensure_buckets(self):
        """确保必要的bucket存在"""
        buckets = ['assets', 'generated', 'models', 'exports']
        for bucket in buckets:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
    
    async def upload_image(self, bucket: str, object_name: str, 
                           image_data: bytes, content_type: str = "image/png") -> str:
        """上传图片"""
        self.client.put_object(
            bucket, object_name, BytesIO(image_data),
            length=len(image_data), content_type=content_type
        )
        return f"{bucket}/{object_name}"
    
    async def get_presigned_url(self, bucket: str, object_name: str, 
                                 expires: int = 3600) -> str:
        """获取预签名URL，用于临时访问"""
        from datetime import timedelta
        return self.client.presigned_get_object(
            bucket, object_name, expires=timedelta(seconds=expires)
        )
```

---

## 七、视频处理：FFmpeg

```python
# backend/app/engines/video_engine.py - 视频合成引擎
import ffmpeg
from pathlib import Path

class VideoComposer:
    """视频合成引擎，基于FFmpeg"""
    
    @staticmethod
    def frames_to_video(frames_dir: str, output_path: str, 
                        fps: int = 24, resolution: str = "1920x1080"):
        """帧序列转视频"""
        (
            ffmpeg
            .input(Path(frames_dir) / '%04d.png', framerate=fps)
            .output(
                output_path,
                vcodec='libx264',
                pix_fmt='yuv420p',
                s=resolution,
                crf=18,  # 高质量
                preset='medium'
            )
            .overwrite_output()
            .run()
        )
    
    @staticmethod
    def merge_audio_video(video_path: str, audio_path: str, 
                          output_path: str):
        """合并音视频"""
        video = ffmpeg.input(video_path)
        audio = ffmpeg.input(audio_path)
        (
            ffmpeg
            .concat(video, audio, v=1, a=1)
            .output(output_path)
            .overwrite_output()
            .run()
        )
    
    @staticmethod
    def add_subtitle(video_path: str, subtitle_path: str, 
                     output_path: str):
        """添加字幕"""
        (
            ffmpeg
            .input(video_path)
            .output(output_path, vf=f"subtitles={subtitle_path}")
            .overwrite_output()
            .run()
        )
```

---

## 八、容器化部署：Docker

### 8.1 Dockerfile示例

```dockerfile
# backend/Dockerfile - 后端服务
FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```dockerfile
# backend/Dockerfile.gpu - GPU版本
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

RUN apt-get update && apt-get install -y python3.11 python3-pip \
    ffmpeg libgl1-mesa-glx libglib2.0-0

WORKDIR /app
COPY requirements.gpu.txt .
RUN pip install --no-cache-dir -r requirements.gpu.txt

COPY . .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 8.2 开发环境编排

```yaml
# docker/docker-compose.yml
version: '3.8'

services:
  backend:
    build: ../backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/comic_studio
      - REDIS_URL=redis://redis:6379
      - MINIO_ENDPOINT=minio:9000
    depends_on:
      - postgres
      - redis
      - minio
    volumes:
      - ../backend:/app
      - ../ai-models:/models
  
  frontend:
    image: node:18-alpine
    working_dir: /app
    command: sh -c "npm install && npm run dev -- --host"
    ports:
      - "5173:5173"
    volumes:
      - ../frontend:/app
  
  celery_worker:
    build: ../backend
    command: celery -A app.celery worker --loglevel=info --concurrency=4
    environment:
      - DATABASE_URL=postgresql://user:pass@postgres:5432/comic_studio
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
      - postgres
  
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: comic_studio
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
  
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
  
  minio:
    image: minio/minio:latest
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
    ports:
      - "9000:9000"
      - "9001:9001"
    volumes:
      - minio_data:/data

volumes:
  postgres_data:
  minio_data:
```

---

*本文档最后更新：2026-07-18*
