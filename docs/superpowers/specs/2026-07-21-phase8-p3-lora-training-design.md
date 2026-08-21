# Phase 8 P3: LoRA 训练 UI 设计规格

> 日期：2026-07-21
> 状态：设计完成，待用户审阅
> 前置：P1（本地推理）+ P2（AMD/Intel GPU 支持）已完成

## 1. 概述

### 1.1 目标

为漫剧创作平台新增 LoRA 训练能力，让用户上传角色图片即可训练专属 SDXL LoRA adapter，生成一致角色形象。

### 1.2 范围

- **训练目标**：仅图像模型（SDXL base 1.0），不支持 FLUX/LLM 训练
- **训练位置**：本地（peft+diffusers）+ 云端（Replicate API）
- **数据集**：支持两种来源——上传图片+自动 caption（BLIP-2）/ 上传文件夹（图片+同名 txt）
- **绑定对象**：以 Character 为核心，训练产物与角色绑定

### 1.3 用户故事

1. Pro 用户在角色详情页点"训练 LoRA"，进入分步向导
2. 上传 5-20 张角色图片，选择自动生成或手动填写 caption
3. 选择预设档位（快速/标准/高质量）和训练位置（本地/云端）
4. 提交训练，实时查看进度（WebSocket 推送）
5. 训练完成后，该角色后续生图自动加载 LoRA，角色形象一致

### 1.4 非目标（YAGNI）

- 不做 FLUX LoRA 训练（仅支持加载预训练 FLUX LoRA）
- 不做 LLM 风格 LoRA 训练
- 不做训练历史版本管理（只保留最新 LoRA）
- 不做 LoRA 权重调节 UI（推理时固定 weight=1.0）
- 不做多角色混合 LoRA
- 不做训练数据集标注协作

## 2. 整体架构与数据流

### 2.1 架构总览

```
┌─────────────────────────────────────────────────────┐
│ Frontend (React)                                    │
│  TrainingPage → DatasetUploader + CaptionEditor     │
│  + TrainConfigForm + TrainProgressPanel (WS)        │
└────────────────────┬────────────────────────────────┘
                     │ REST + WS
┌────────────────────▼────────────────────────────────┐
│ Backend API                                         │
│  POST /characters/{id}/train  (提交训练任务)        │
│  POST /datasets               (上传数据集)          │
│  GET  /characters/{id}/train/status (查状态)        │
│  WS   task:{task_id}           (进度推送)           │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────┐
│ LoraTrainingService (注册到 TaskService)            │
│  ┌─────────────────────────────────────┐            │
│  │ TrainingEngine (抽象基类)           │            │
│  │  ├─ LocalTrainingEngine (peft+diff) │            │
│  │  └─ ReplicateTrainingEngine (API)   │            │
│  └─────────────────────────────────────┘            │
│  + CaptionGenerator (BLIP-2 自动 caption)           │
└────────────────────┬────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
   本地 GPU                Replicate API
   peft+diffusers         POST /predictions
   保存 .safetensors       轮询 → 下载产物
        │                       │
        └───────────┬───────────┘
                    ▼
   uploads/lora_adapters/{character_id}/{date}/adapter.safetensors
                    │
                    ▼
   Character.lora_model_path = 上述路径
   Character.lora_training_status = "ready"
   ModelManager.load_lora() 推理时加载
```

### 2.2 数据流

1. 用户在角色详情页点"训练 LoRA" → 进入 `TrainingPage`
2. 上传 5-20 张图片 → `POST /datasets/{id}/images` 存到 `uploads/datasets/{dataset_id}/`
3. 选择 caption 方式：自动生成（`POST /datasets/{id}/auto-caption`）或手动填写
4. 选训练参数（预设档位/高级）+ 训练位置（本地/云端）
5. `POST /characters/{id}/train` → `LoraTrainingService.submit()`
6. `TaskService` 创建 `BackgroundTask(type="lora_train")` → 异步执行
7. 训练中通过 `task_service.update_progress()` 推送 WebSocket 频道 `task:{task_id}`
8. 训练完成 → 产物存 `uploads/lora_adapters/` → 更新 `Character.lora_model_path` + `lora_training_status="ready"`
9. 后续生图时 `ModelManager.load_lora()` 自动加载该角色的 LoRA

### 2.3 关键复用

| 现有组件 | 复用方式 |
|---|---|
| `TaskService` | `register_handler("lora_train", handler)` |
| `BackgroundTask` 表 | `task_type="lora_train"`, `payload` 存训练参数 |
| `WebSocketManager` | 频道 `task:{task_id}` 推送进度 |
| `DeviceManager` | 本地训练时获取 GPU/VRAM/设备字符串 |
| `ModelManager` | 训练后 `load_lora()` 加载到 pipeline |
| `FileStorage` | 数据集和产物存储 |
| `Character.lora_*` 字段 | 状态机 `none→drafting→training→ready/failed` |

## 3. 后端数据模型与存储

### 3.1 新增模型：`TrainingDataset`

```python
# backend/app/models/training_dataset.py
class TrainingDataset(Base):
    __tablename__ = "training_datasets"
    id            = Column(String(36), primary_key=True)  # ds_xxx
    character_id  = Column(String(36), ForeignKey("characters.id"))
    user_id       = Column(String(36), ForeignKey("users.id"))
    name          = Column(String(100))
    status        = Column(String(20), default="drafting")  # drafting/captioning/ready/training/used
    image_count   = Column(Integer, default=0)
    caption_mode  = Column(String(20), default="auto")      # auto/manual
    trigger_word  = Column(String(50), default="")          # 触发词，如 zkq_char
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, onupdate=datetime.utcnow)
    items         = relationship("DatasetItem", back_populates="dataset", cascade="all,delete-orphan")
```

### 3.2 新增模型：`DatasetItem`

```python
class DatasetItem(Base):
    __tablename__ = "dataset_items"
    id            = Column(String(36), primary_key=True)  # di_xxx
    dataset_id    = Column(String(36), ForeignKey("training_datasets.id"))
    image_path    = Column(String(500))   # uploads/datasets/{ds_id}/xxx.png
    caption       = Column(Text, default="")
    caption_source= Column(String(20))   # auto/manual/imported
    width         = Column(Integer)
    height        = Column(Integer)
    dataset       = relationship("TrainingDataset", back_populates="items")
```

### 3.3 复用 `BackgroundTask` 表

不新建训练任务表，直接复用：
- `task_type = "lora_train"`
- `payload = {"dataset_id": "ds_xxx", "character_id": "ch_xxx", "engine": "local"|"replicate", "trigger_word": "...", "params": {...}}`
- `result = {"adapter_path": "uploads/lora_adapters/...", "metrics": {"final_loss": 0.12, "steps": 1000, "train_time_sec": 1800}}`
- `progress` 0-100 + `message`

### 3.4 存储目录结构

```
uploads/
├── datasets/
│   └── {dataset_id}/
│       ├── img_001.png
│       ├── img_001.txt        # caption（与图片同名，用于文件夹上传模式）
│       └── ...
├── lora_adapters/
│   └── {character_id}/
│       └── {YYYYMMDD}/
│           ├── adapter.safetensors
│           └── training_config.json   # 训练参数快照
└── (既有 images/ audio/)
```

### 3.5 `Character` 字段语义

现有 `lora_training_status` 状态机扩展：
- `none`：从未训练
- `drafting`：用户正在准备数据集（数据集创建时设置，训练提交时改为 `training`）
- `training`：训练任务执行中
- `ready`：训练完成，LoRA 可用
- `failed`：训练失败
- `lora_model_path`：指向 `uploads/lora_adapters/.../adapter.safetensors`（仅 `ready` 状态时有值）

### 3.6 `bootstrap.py` 预创建目录

在现有 `images/` `audio/` 基础上新增 `datasets/` `lora_adapters/`。

## 4. 训练引擎抽象与实现

### 4.1 `TrainingEngine` 抽象基类

```python
# backend/app/engines/training/base.py
class TrainingEngine(ABC):
    @abstractmethod
    async def train(
        self,
        dataset_path: str,           # uploads/datasets/{ds_id}/
        output_dir: str,             # uploads/lora_adapters/{ch_id}/{date}/
        params: TrainingParams,
        progress_callback: Callable[[int, str], Awaitable[None]],
    ) -> TrainingResult:
        """执行训练，返回产物路径与指标"""

    @abstractmethod
    def check_available(self) -> tuple[bool, str]:
        """检查引擎是否可用（本地查 GPU/依赖，云端查 API key）"""
```

### 4.2 `TrainingParams`（统一参数 schema）

```python
@dataclass
class TrainingParams:
    base_model: str = "stabilityai/sdxl-base-1.0"
    resolution: int = 1024
    rank: int = 32                  # LoRA rank
    learning_rate: float = 1e-4
    batch_size: int = 1
    max_train_steps: int = 1000     # 替代 epoch，更精确
    gradient_accumulation: int = 4
    lr_scheduler: str = "cosine"
    seed: int = 42
    trigger_word: str = ""
    preset: str = "standard"        # quick/standard/high_quality
```

预设档位映射：
- `quick`: max_train_steps=500
- `standard`: max_train_steps=1000
- `high_quality`: max_train_steps=2000

### 4.3 `LocalTrainingEngine`

```python
# backend/app/engines/training/local.py
class LocalTrainingEngine(TrainingEngine):
    def check_available(self) -> tuple[bool, str]:
        dm = DeviceManager.get_instance()
        gpu = dm.get_gpu_info()
        if gpu.vram_gb < 8:
            return False, f"VRAM 不足: {gpu.vram_gb}GB < 8GB (SDXL LoRA 最低要求)"
        if not _check_peft_installed():
            return False, "peft 未安装，请安装 peft>=0.10.0"
        return True, "ok"

    async def train(self, dataset_path, output_dir, params, progress_callback):
        # 1. 加载 SDXL base pipeline (通过 ModelManager 复用缓存)
        # 2. 构造 dataset (datasets.load_dataset 图片+caption)
        # 3. 配置 peft LoraConfig (rank=params.rank)
        # 4. diffusers 训练循环（参考 train_dreambooth_lora_sdxl.py 核心逻辑）
        # 5. 每 50 步调用 progress_callback(step/total*100, f"训练中 {step}/{total}")
        # 6. 保存 adapter.safetensors 到 output_dir
        # 7. 返回 TrainingResult(adapter_path, metrics={loss, step, time})
```

### 4.4 `ReplicateTrainingEngine`

```python
# backend/app/engines/training/replicate.py
class ReplicateTrainingEngine(TrainingEngine):
    def check_available(self) -> tuple[bool, str]:
        if not settings.replicate_api_token:
            return False, "Replicate API token 未配置"
        return True, "ok"

    async def train(self, dataset_path, output_dir, params, progress_callback):
        # 1. 上传数据集图片到 Replicate (或用 data URL)
        # 2. POST /v1/predictions (model: 托管在 Replicate 的 SDXL LoRA 训练模型)
        # 3. 轮询 prediction.status every 5s，30 分钟超时
        # 4. 每次轮询调用 progress_callback (Replicate 返回 progress 0-1)
        # 5. 完成后下载 output adapter.safetensors 到 output_dir
        # 6. 返回 TrainingResult
```

### 4.5 `TrainingEngineProvider`（路由选择）

```python
# backend/app/engines/training/__init__.py
class TrainingEngineProvider:
    @staticmethod
    def select(location: str) -> TrainingEngine:
        if location == "local":
            return LocalTrainingEngine()
        elif location == "replicate":
            return ReplicateTrainingEngine()
        raise ValueError(f"Unknown training location: {location}")

    @staticmethod
    def auto_select() -> tuple[str, TrainingEngine]:
        """自动选择：优先本地（VRAM≥8GB），否则云端"""
        local = LocalTrainingEngine()
        ok, _ = local.check_available()
        if ok:
            return "local", local
        return "replicate", ReplicateTrainingEngine()
```

## 5. Caption 自动生成

### 5.1 `CaptionGenerator`

```python
# backend/app/engines/training/caption.py
class CaptionGenerator:
    def __init__(self, model: str = "Salesforce/blip-image-captioning-large"):
        self._processor = None
        self._model = None
        self._model_name = model

    async def generate(self, image_path: str, trigger_word: str = "") -> str:
        """
        用 BLIP-2 生成图片描述，自动追加 trigger_word。
        例: "a woman with red hair in a blue dress, <trigger_word> character"
        """
        # 懒加载 BLIP 模型（首次调用，通过 ModelManager 缓存）
        # 返回 caption 字符串
```

### 5.2 trigger_word 机制

用户为角色设定一个触发词（如 `zkq_char`），每张图 caption 末尾自动追加 `，<trigger_word> character`。训练后生图时在 prompt 中包含 trigger_word 即可激活角色 LoRA。

### 5.3 文件夹上传模式

上传文件夹时，解析同名 `.txt` 文件作为 caption（`caption_source="imported"`），不调用 BLIP-2。

## 6. API 端点设计

### 6.1 数据集端点

| 方法 | 路径 | 功能 | 鉴权 |
|---|---|---|---|
| POST | `/datasets` | 创建数据集（绑定 character_id） | 用户 |
| POST | `/datasets/{id}/images` | 上传图片到数据集（multipart） | 用户 |
| POST | `/datasets/{id}/images/{item_id}/caption` | 手动设置/修改单张 caption | 用户 |
| POST | `/datasets/{id}/auto-caption` | 批量自动生成 caption | 用户 |
| GET | `/datasets/{id}` | 获取数据集详情（含 items） | 用户 |
| DELETE | `/datasets/{id}/images/{item_id}` | 删除单张图片 | 用户 |
| GET | `/characters/{id}/datasets` | 获取角色的数据集列表 | 用户 |

### 6.2 训练端点

`POST /characters/{id}/train` 请求体：
```json
{
  "dataset_id": "ds_xxx",
  "location": "local" | "replicate",
  "trigger_word": "zkq_char",
  "preset": "quick" | "standard" | "high_quality",
  "advanced": {
    "rank": 32,
    "learning_rate": 0.0001,
    "max_train_steps": 1000
  }
}
```

返回：
```json
{
  "task_id": "task_xxx",
  "character_id": "ch_xxx",
  "status": "pending"
}
```

`GET /characters/{id}/train/status` 返回：
```json
{
  "status": "training",
  "progress": 45,
  "message": "训练中 450/1000",
  "task_id": "task_xxx"
}
```

### 6.3 训练任务 handler 注册

```python
# backend/app/services/lora_training_service.py
class LoraTrainingService:
    def __init__(self):
        task_service.register_handler("lora_train", self._handle_train_task)

    async def _handle_train_task(self, task: BackgroundTask, db: Session):
        payload = task.payload
        engine = TrainingEngineProvider.select(payload["location"])
        params = self._build_params(payload)
        # Character.lora_training_status = "training"
        result = await engine.train(
            dataset_path=...,
            output_dir=...,
            params=params,
            progress_callback=lambda p, m: task_service.update_progress(db, task.id, p, m)
        )
        # Character.lora_model_path = result.adapter_path
        # Character.lora_training_status = "ready"
```

## 7. 前端 UI 设计

### 7.1 路由

```tsx
<Route path="/characters/:id/train" element={<TrainingPage />} />
```

从角色详情页 "训练 LoRA" 按钮跳转。

### 7.2 `TrainingPage` 布局（Ant Design Steps 分步向导）

```
┌─────────────────────────────────────────────────────┐
│  训练角色 LoRA - {character.name}                    │
├─────────────────────────────────────────────────────┤
│  ① 数据集  →  ② Caption  →  ③ 参数  →  ④ 训练      │
├─────────────────────────────────────────────────────┤
│  [当前步骤内容区]                                   │
├─────────────────────────────────────────────────────┤
│  [上一步]                          [下一步/开始训练]│
└─────────────────────────────────────────────────────┘
```

### 7.3 步骤组件

**Step 1: `DatasetUploader`**
- 拖拽上传 5-20 张图片（JPG/PNG，≤10MB/张）
- 缩略图网格预览，可删除单张
- 显示图片数/最小 5 张提示
- 支持"上传文件夹"模式（解析同名 .txt caption）

**Step 2: `CaptionEditor`**
- 两种模式切换：自动生成 / 手动编辑
- 自动模式：点"生成 Caption" → 调 `/auto-caption` → 显示进度
- 手动模式：每张图下方文本框，逐张编辑
- trigger_word 输入框（必填，2-20 字符，英文/拼音）
- 图片+caption 对照预览

**Step 3: `TrainConfigForm`**
- 预设档位卡片选择：
  - 快速（500步，~15分钟，适合测试）
  - 标准（1000步，~30分钟，推荐）
  - 高质量（2000步，~60分钟，最终成品）
- 训练位置选择：
  - 本地训练（显示 GPU 信息，VRAM<8GB 禁用并提示）
  - 云端训练（显示 Replicate 计费预估）
- 高级参数折叠面板：rank、learning_rate、batch_size（仅 Pro 可见）

**Step 4: `TrainProgressPanel`**
- WebSocket 订阅 `task:{task_id}`
- 进度条 + 当前步骤文案（"加载模型 30%"、"训练中 450/1000"、"保存 LoRA"）
- 实时 loss 曲线图（本地训练时）
- 训练日志滚动显示
- 完成后：下载 LoRA 按钮 + "用此角色生图"跳转按钮
- 失败时：错误详情 + 重试按钮

### 7.4 `CharacterCard` 增强

角色卡片显示 LoRA 状态徽章：
- 无 LoRA：灰色"未训练"
- 训练中：蓝色动画"训练中"（点击跳转进度页）
- 就绪：绿色"已训练"
- 失败：红色"训练失败"

### 7.5 权限控制

- Free 用户：不可训练（按钮禁用，提示升级 Pro）
- Pro 用户：本地训练无限次，云端训练每月赠送 10 次
- Enterprise：无限制

## 8. 依赖与计费

### 8.1 新增依赖

```python
# backend/requirements.txt 追加
peft>=0.10.0          # LoRA 训练核心
datasets>=2.18.0      # 训练数据集加载
replicate>=0.25.0     # Replicate API SDK (云端训练)
# diffusers/transformers/torch 已有
# BLIP-2 (自动 caption) 已包含在 transformers 中
```

注意：`peft`/`datasets`/`replicate` 为可选导入（try/except），训练不可用时优雅降级。

### 8.2 配置项

```python
# backend/app/core/config.py 新增
replicate_api_token: str = ""          # Replicate API token
replicate_train_model: str = ""        # Replicate 上托管的训练模型 ID
lora_train_local_enabled: bool = True  # 是否启用本地训练
lora_train_cloud_enabled: bool = True  # 是否启用云端训练
blip_model_name: str = "Salesforce/blip-image-captioning-large"
```

### 8.3 计费策略

| 用户类型 | 本地训练 | 云端训练 |
|---|---|---|
| Free | 禁用 | 禁用 |
| Pro | 无限次 | 每月 10 次免费，超出 ¥5/次 |
| Enterprise | 无限次 | 无限次 |

云端训练通过 `CreditTransaction(reason="lora_train")` 扣费，与现有计费系统对齐。

## 9. 测试策略

### 9.1 后端测试（TDD）

| 测试文件 | 覆盖内容 |
|---|---|
| `test_caption_generator.py` | BLIP-2 mock 测试 caption 生成 |
| `test_training_engine_local.py` | LocalTrainingEngine（mock peft/diffusers） |
| `test_training_engine_replicate.py` | ReplicateTrainingEngine（mock replicate SDK） |
| `test_training_engine_provider.py` | 引擎选择与可用性检测 |
| `test_lora_training_service.py` | Service 集成（TaskService 注册 handler） |
| `test_datasets_api.py` | 数据集 CRUD 端点 |
| `test_train_api.py` | 训练提交/状态查询端点 |
| `test_training_dataset_model.py` | 数据模型 CRUD |

### 9.2 前端测试

| 测试文件 | 覆盖内容 |
|---|---|
| `TrainingPage.test.tsx` | 分步向导流程 |
| `DatasetUploader.test.tsx` | 上传交互 |
| `TrainProgressPanel.test.tsx` | WebSocket 进度 |

### 9.3 验收标准

- 后端 800+ 测试通过（P2 基线 731 + P3 新增 ~80）
- 前端 55+ 测试通过（P2 基线 47 + P3 新增 ~8）
- TypeScript 检查通过
- 前端 + Desktop 构建成功
- 实际本地训练一次（mock GPU 验证流程完整性）

## 10. 关键风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| peft/diffusers 训练 API 变动 | 训练失败 | 锁定版本 + 训练参数快照 |
| 本地训练 OOM | 任务失败 | 训练前 check VRAM，batch_size=1 默认 |
| Replicate API 超时 | 云端训练卡住 | 30 分钟超时 + 轮询间隔递增 |
| BLIP-2 模型下载慢 | 首次自动 caption 慢 | ModelManager 预下载 + 进度提示 |
| 数据集图片质量差 | 训练效果差 | 上传时提示推荐分辨率/数量 |

## 11. 文件清单（预估）

### 11.1 新建后端文件

```
backend/app/models/training_dataset.py
backend/app/schemas/training_dataset.py
backend/app/schemas/training.py
backend/app/api/datasets.py
backend/app/api/training.py
backend/app/services/lora_training_service.py
backend/app/engines/training/__init__.py
backend/app/engines/training/base.py
backend/app/engines/training/local.py
backend/app/engines/training/replicate.py
backend/app/engines/training/caption.py
backend/tests/test_caption_generator.py
backend/tests/test_training_engine_local.py
backend/tests/test_training_engine_replicate.py
backend/tests/test_training_engine_provider.py
backend/tests/test_lora_training_service.py
backend/tests/test_datasets_api.py
backend/tests/test_train_api.py
backend/tests/test_training_dataset_model.py
```

### 11.2 修改后端文件

```
backend/app/models/__init__.py          # 导出新模型
backend/app/core/config.py              # 新增配置项
backend/app/core/bootstrap.py           # 预创建目录
backend/app/api/__init__.py             # 注册新路由
backend/app/main.py                     # 挂载新路由
backend/requirements.txt                # 新增依赖
backend/app/services/task_service.py    # 启动时注册 lora_train handler
```

### 11.3 新建前端文件

```
frontend/src/api/training.ts
frontend/src/api/datasets.ts
frontend/src/pages/TrainingPage.tsx
frontend/src/components/training/DatasetUploader.tsx
frontend/src/components/training/CaptionEditor.tsx
frontend/src/components/training/TrainConfigForm.tsx
frontend/src/components/training/TrainProgressPanel.tsx
frontend/src/components/characters/LoraStatusBadge.tsx
frontend/src/types/training.ts
frontend/src/types/dataset.ts
frontend/src/pages/TrainingPage.test.tsx
frontend/src/components/training/DatasetUploader.test.tsx
frontend/src/components/training/TrainProgressPanel.test.tsx
```

### 11.4 修改前端文件

```
frontend/src/routes/index.tsx           # 新增路由
frontend/src/pages/CharacterDetailPage.tsx  # 添加"训练 LoRA"按钮 + 状态徽章
frontend/src/types/character.ts         # 确认 lora 字段类型
```
