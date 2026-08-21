# Phase 8 - P1：多 Provider 抽象层 + 语义缓存 + 智能路由

- **日期**：2026-07-20
- **阶段**：Phase 8 / P1
- **前置**：
  - Phase 7 已完成（501 后端测试通过）
  - 前端集成已完成（543 测试通过）
  - 现有架构：5 类引擎抽象（image/tts/llm/video/character）+ EngineManager + ProviderFailover 熔断器 + ResultCacheService（精确 key）
  - 已接入 Provider：DeepSeek（LLM）、Pollinations（Image）、edge-tts（TTS）、ffmpeg（Video）
- **后续**：P2（AMD/Intel GPU）→ P3（LoRA 训练 UI）→ P4（K8s）→ P5（多区域）→ 生产部署

## 1. 目标

将现有"单 Provider per 引擎"架构升级为"多 Provider 注册表 + 智能路由 + 语义缓存"，性能对标并超过 ComfyUI / 即梦。

### 1.1 核心目标

1. **多 Provider 注册表**：14 个 Provider 统一注册，按引擎类型分组
2. **智能路由**：按订阅层级 + 用户偏好 + Provider 可用性动态选择
3. **语义缓存**：仅 LLM 引擎，bge-m3 + ChromaDB + 每用户独立（cosine ≥ 0.90）
4. **配额管理**：Free/Pro/Enterprise 分层限流
5. **Provider 健康检查**：定期 ping + 自动 fallback（复用现有 ProviderFailover）
6. **本地推理订阅鉴权**：JWT 验证订阅 + 硬件自适应 + 模型下载指引
7. **源码保护**：Cython 编译关键模块 + Electron asar 加密

### 1.2 性能对标目标

| 指标 | 当前 | P1 目标 | 即梦 | ComfyUI |
|---|---|---|---|---|
| LLM 首字延迟 | 2-5s（DeepSeek API） | 0.3-0.8s（自建 Qwen2.5）/ <50ms（语义缓存命中） | ~0.5s | N/A |
| LLM 重复 prompt | 重新调 API | <50ms（缓存命中） | ~0.5s | 有 cache |
| Image 首次延迟 | 10-30s（本地冷启） | 3-8s（Seedream API + 模型常驻） | ~2s | ~5s |
| Video 延迟 | 30s-2min（CPU ffmpeg） | 5-15s（Seedance/Kling API） | ~5s | N/A |
| 故障容忍 | 单点 | L1 故障自动 L3 fallback | 单点 | 本地 |

### 1.3 非目标

- 不实现 AMD/Intel GPU 支持（P2）
- 不实现 LoRA 训练 UI（P3）
- 不实现 K8s 部署（P4）
- 不实现多区域（P5）
- 不重构现有 EngineManager 的引擎类型枚举（保留 5 类）
- 不修改现有 ResultCacheService（精确 key 缓存继续保留，语义缓存是新增层）

## 2. 范围

### 2.1 商业化分层

| 用户层 | 云端推理 | 本地推理 | 模型下载 | 配额 |
|---|---|---|---|---|
| Free | 限流（DeepSeek + SDXL CPU） | ❌ | ❌ | 10 次/天 |
| Pro | 所有云端模型（共享 GPU 池） | ✅（按硬件自动推荐） | ✅（平台镜像） | 1000 次/月 |
| Enterprise | 专属 GPU + 优先队列 | ✅ + 多 GPU 并行 | ✅（高速镜像） | 不限 |

### 2.2 开源策略

- **源码仓库**：私有仓库（不公开到 GitHub）
- **客户端分发**：编译后分发（PyInstaller + Electron asar）
- **模型权重**：本地推理用户从 HuggingFace 官方/平台镜像下载，平台不分发
- **License**：专有许可（禁止复制/分发/修改源码）
- **本地推理 Key**：无需用户自备 API Key（平台仅验证订阅状态）

## 3. 总体架构

### 3.1 分层结构

```
┌──────────────────────────────────────────────────────────┐
│  API Layer (现有)                                         │
│  - /api/v1/chat, /api/v1/images, /api/v1/videos, ...    │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Router Layer (新增)                                      │
│  - ProviderRouter: 按订阅/偏好/可用性选择 Provider        │
│  - QuotaGuard: 配额检查 + 限流                           │
│  - SubscriptionGuard: 本地推理订阅验证                    │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Cache Layer (新增 + 现有)                                │
│  - SemanticCache (新): bge-m3 + ChromaDB (仅 LLM)        │
│  - ResultCacheService (现有): 精确 key (image/video/tts) │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Provider Registry (新增)                                 │
│  - IMAGE: seedream / flux / kolors / sdxl (4)            │
│  - VIDEO: seedance / kling / wan / hunyuan (4)           │
│  - LLM:   qwen / deepseek / glm / doubao (4)             │
│  - TTS:   volcano / cosyvoice / edge (3)                 │
└──────────────────────────────────────────────────────────┘
                          ↓
┌──────────────────────────────────────────────────────────┐
│  Provider Implementations (新增 11 + 现有 3)              │
│  - API Provider: Seedream/Seedance/Kling/Kolors/GLM/    │
│    豆包/火山TTS/DeepSeek (8)                              │
│  - Local Provider: FLUX/Wan2.1/Hunyuan/Qwen2.5/CosyVoice│
│    /SDXL/edge-tts (7)                                    │
└──────────────────────────────────────────────────────────┘
```

### 3.2 数据流（LLM 示例）

```
用户 LLM 请求 (user_id, messages, model_preference)
    ↓
[1] QuotaGuard.check(user_id, "llm") → 配额是否充足
    ↓ 充足
[2] SemanticCache.lookup(user_id, messages)
    ↓ 命中 (cosine ≥ 0.90, TTL 未过期)
[3a] 返回缓存结果（不扣 API 额度，记录 hit_count）
    ↓ 未命中
[3b] ProviderRouter.select("llm", user_subscription, user_preference)
    ↓
[4] 调用选中的 Provider.chat(messages)
    ↓ 失败
[5] ProviderFailover 记录失败 + fallback 到次级 Provider
    ↓ 成功
[6] SemanticCache.store(user_id, messages, response)
    ↓
[7] QuotaGuard.consume(user_id, "llm", token_count)
    ↓
[8] 返回结果
```

### 3.3 文件清单

**后端新增（21 个文件）**：

| 路径 | 用途 |
|---|---|
| `backend/app/engines/registry.py` | Provider 注册表（按引擎类型分组） |
| `backend/app/engines/router.py` | 智能路由器（订阅/偏好/可用性） |
| `backend/app/engines/quota_guard.py` | 配额管理 + 限流 |
| `backend/app/engines/subscription_guard.py` | 本地推理订阅验证 |
| `backend/app/core/semantic_cache.py` | 语义缓存核心（bge-m3 + ChromaDB） |
| `backend/app/core/embedding_service.py` | bge-m3 embedding 服务（懒加载 + 批量） |
| `backend/app/engines/image/seedream.py` | 即梦 Seedream Provider (Volcano API) |
| `backend/app/engines/image/flux.py` | FLUX.1-dev Provider (本地 diffusers) |
| `backend/app/engines/image/kolors.py` | 可图 Kolors Provider (快手 API) |
| `backend/app/engines/video/seedance.py` | 即梦 Seedance Provider (Volcano API) |
| `backend/app/engines/video/kling.py` | 可灵 Kling Provider (快手 API) |
| `backend/app/engines/video/wan.py` | Wan2.1 Provider (本地 diffusers) |
| `backend/app/engines/video/hunyuan.py` | 混元 Video Provider (本地 diffusers) |
| `backend/app/engines/llm/qwen_local.py` | Qwen2.5 本地 Provider (vLLM) |
| `backend/app/engines/llm/glm.py` | 智谱 GLM-4 Provider (API) |
| `backend/app/engines/llm/doubao.py` | 火山豆包 Provider (API) |
| `backend/app/engines/tts/volcano_tts.py` | 火山语音 Provider (API) |
| `backend/app/engines/tts/cosyvoice.py` | CosyVoice Provider (本地) |
| `backend/app/api/models.py` | 模型清单 API（含硬件自适应推荐） |
| `backend/app/models/local_model.py` | 本地模型元数据表（用户已下载模型） |
| `backend/alembic/versions/007_add_local_models_table.py` | 迁移：local_models 表 |

**后端修改（5 个文件）**：

| 路径 | 改动 |
|---|---|
| `backend/app/engines/manager.py` | 集成 ProviderRegistry + ProviderRouter；保留现有单 Provider 接口作为默认 |
| `backend/app/engines/base.py` | 新增 `capability` 属性 + `is_local` 属性 + `supported_models` 列表 |
| `backend/app/core/config.py` | 新增 14 个 Provider 配置项 + 语义缓存配置 + 订阅验证配置 |
| `backend/app/engines/llm/deepseek.py` | 在 chat() 中接入 SemanticCache（查询 → 未命中调 API → 存储） |
| `backend/app/api/routes.py` | 新增 `/api/v1/models/local/{hardware_profile}` 端点 |

**前端新增（2 个文件）**：

| 路径 | 用途 |
|---|---|
| `frontend/src/api/models.ts` | 模型清单 API 客户端 |
| `frontend/src/components/settings/ProviderSelector.tsx` | Provider 选择器组件（首启向导 + 设置页） |

**前端修改（2 个文件）**：

| 路径 | 改动 |
|---|---|
| `frontend/src/pages/FirstLaunchPage.tsx` | Step 3 改为调用 `/api/v1/models/local/{hardware_profile}` 获取推荐模型 |
| `frontend/src/pages/SettingsPage.tsx` | 新增 Provider 偏好设置 Tab |

**法律/许可（1 个文件）**：

| 路径 | 用途 |
|---|---|
| `LICENSE` | 专有许可（禁止复制/分发/修改） |

**测试新增（11 个文件）**：

| 路径 | 测试数 |
|---|---|
| `backend/tests/test_provider_registry.py` | 8 |
| `backend/tests/test_provider_router.py` | 10 |
| `backend/tests/test_quota_guard.py` | 6 |
| `backend/tests/test_subscription_guard.py` | 5 |
| `backend/tests/test_semantic_cache.py` | 10 |
| `backend/tests/test_embedding_service.py` | 5 |
| `backend/tests/test_seedream_provider.py` | 5 |
| `backend/tests/test_seedance_provider.py` | 5 |
| `backend/tests/test_kling_provider.py` | 5 |
| `backend/tests/test_local_model_api.py` | 6 |
| `frontend/tests/api/models.test.ts` | 5 |

**测试目标**：543 → 618+（新增 75：后端 65 + 前端 5 + 集成测试 5，零回归）

> 注：单元测试 65 + 前端 5 = 70 个新增测试；集成测试 5 个计入回归。543 + 70 + 5 = 618

### 3.4 新增依赖

**后端**：
- `sentence-transformers`（bge-m3 embedding，已在 user_profile 技术栈中）
- `chromadb`（向量存储，已集成）
- `volcengine-python-sdk`（即梦 Seedream/Seedance/火山 TTS/豆包）
- `kling-sdk`（可灵视频，若官方有 SDK；否则用 httpx）
- `zhipuai`（智谱 GLM SDK）
- `vllm`（Qwen2.5 本地推理，仅云端服务器安装）
- `cython`（源码保护编译）

**前端**：无新增

## 4. Provider 注册表设计

### 4.1 接口定义

```python
# backend/app/engines/registry.py
from typing import Type
from app.engines.base import BaseEngine


class ProviderRegistry:
    """Provider 注册表 - 按引擎类型分组"""

    _registry: dict[str, dict[str, Type[BaseEngine]]] = {
        "image": {},
        "video": {},
        "llm": {},
        "tts": {},
    }

    @classmethod
    def register(
        cls,
        engine_type: str,
        provider_name: str,
        provider_class: Type[BaseEngine],
    ) -> None:
        """注册 Provider"""
        if engine_type not in cls._registry:
            raise ValueError(f"未知引擎类型: {engine_type}")
        cls._registry[engine_type][provider_name] = provider_class

    @classmethod
    def get(
        cls,
        engine_type: str,
        provider_name: str,
    ) -> Type[BaseEngine]:
        """获取 Provider 类"""
        providers = cls._registry.get(engine_type, {})
        if provider_name not in providers:
            raise KeyError(f"未注册的 Provider: {engine_type}/{provider_name}")
        return providers[provider_name]

    @classmethod
    def list_providers(cls, engine_type: str) -> list[str]:
        """列出某引擎类型的所有 Provider 名"""
        return list(cls._registry.get(engine_type, {}).keys())

    @classmethod
    def list_all(cls) -> dict[str, list[str]]:
        """列出所有注册的 Provider"""
        return {
            engine_type: list(providers.keys())
            for engine_type, providers in cls._registry.items()
        }
```

### 4.2 注册时机

在 `backend/app/engines/__init__.py` 中导入所有 Provider 模块时自动注册（每个 Provider 模块底部调用 `ProviderRegistry.register(...)`）。

### 4.3 Provider 元数据扩展

```python
# backend/app/engines/base.py 扩展
class BaseEngine(ABC):
    name: str = "base"
    display_name: str = "基础引擎"

    # P1 新增属性
    is_local: bool = False           # True=本地推理, False=云端 API
    requires_api_key: bool = True    # True=需要 API Key, False=本地无需
    subscription_required: str = "free"  # "free" / "pro" / "enterprise"
    capability: dict = {}            # 如 {"max_resolution": 1024, "supports_stream": True}
    supported_models: list[str] = []  # 支持的模型列表
    health_check_url: str = ""       # API 健康检查端点（本地为空）
```

## 5. 智能路由设计

### 5.1 接口定义

```python
# backend/app/engines/router.py
from dataclasses import dataclass
from typing import Optional
from app.engines.base import BaseEngine
from app.engines.provider_failover import ProviderFailover


@dataclass
class RouteContext:
    """路由上下文"""
    user_id: int
    subscription_tier: str       # "free" / "pro" / "enterprise"
    engine_type: str             # "image" / "video" / "llm" / "tts"
    user_preference: str = ""    # 用户在首启向导/设置中选择的 provider
    force_local: bool = False    # 本地推理模式下强制本地


class ProviderRouter:
    """智能路由器 - 按 4 维度选择 Provider"""

    # 默认优先级（按订阅层级）
    PRIORITY: dict[str, dict[str, list[str]]] = {
        "free": {
            "image": ["sdxl-cpu", "kolors"],
            "video": [],
            "llm": ["deepseek"],
            "tts": ["edge"],
        },
        "pro": {
            "image": ["seedream", "flux", "sdxl", "kolors"],
            "video": ["seedance", "kling", "wan", "hunyuan"],
            "llm": ["qwen-local", "deepseek", "glm", "doubao"],
            "tts": ["volcano", "cosyvoice", "edge"],
        },
        "enterprise": {
            "image": ["seedream", "flux", "sdxl", "kolors"],
            "video": ["seedance", "kling", "wan", "hunyuan"],
            "llm": ["qwen-local", "deepseek", "glm", "doubao"],
            "tts": ["volcano", "cosyvoice", "edge"],
        },
    }

    def __init__(self, failovers: dict[str, ProviderFailover]):
        self._failovers = failovers

    async def select(
        self,
        ctx: RouteContext,
        instantiated: dict[str, BaseEngine],
    ) -> Optional[BaseEngine]:
        """选择最优 Provider

        策略:
        1. 如果用户偏好存在且可用 → 用偏好
        2. 否则按订阅层级优先级列表遍历
        3. 检查熔断器状态（CLOSED/HALF_OPEN 优先）
        4. 检查 is_local 与 force_local 匹配
        5. 检查 subscription_required 是否满足
        6. 返回第一个可用的 Provider，None 表示无可用
        """
        candidates = self._get_candidates(ctx)
        for provider_name in candidates:
            provider = instantiated.get(provider_name)
            if provider is None:
                continue
            if not self._is_available(ctx.engine_type, provider_name):
                continue
            if not self._subscription_ok(provider, ctx.subscription_tier):
                continue
            if ctx.force_local and not provider.is_local:
                continue
            return provider
        return None

    def _get_candidates(self, ctx: RouteContext) -> list[str]:
        """获取候选 Provider 列表（用户偏好优先）"""
        tier_list = self.PRIORITY.get(ctx.subscription_tier, {}).get(ctx.engine_type, [])
        if ctx.user_preference and ctx.user_preference in tier_list:
            return [ctx.user_preference] + [p for p in tier_list if p != ctx.user_preference]
        return tier_list

    def _is_available(self, engine_type: str, provider_name: str) -> bool:
        """检查熔断器是否允许调用"""
        failover = self._failovers.get(f"{engine_type}:{provider_name}")
        if failover is None:
            return True
        return failover.can_call()

    def _subscription_ok(self, provider: BaseEngine, tier: str) -> bool:
        """检查用户订阅是否满足 Provider 要求"""
        required = provider.subscription_required
        tier_order = {"free": 0, "pro": 1, "enterprise": 2}
        return tier_order.get(tier, 0) >= tier_order.get(required, 0)
```

### 5.2 Fallback 策略

当主 Provider 调用失败时：
1. `ProviderFailover.record_failure()` 记录失败
2. 重新调用 `ProviderRouter.select()` 获取次级 Provider
3. 若所有 Provider 都失败 → 返回错误（含所有 Provider 的失败原因）

## 6. 语义缓存设计

### 6.1 接口定义

```python
# backend/app/core/semantic_cache.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CacheEntry:
    """缓存条目"""
    query: str
    response: str
    embedding: list[float]
    created_at: datetime
    hit_count: int = 0


class SemanticCache:
    """语义缓存 - 基于 embedding 相似度

    仅适用于 LLM 引擎。每用户独立缓存（user_id 过滤）。
    """

    def __init__(
        self,
        embedding_service: "EmbeddingService",
        collection_name: str = "llm_semantic_cache",
        similarity_threshold: float = 0.90,
        ttl_seconds: int = 1800,
        max_entries_per_user: int = 1000,
    ):
        self._embedding = embedding_service
        self._collection_name = collection_name
        self._threshold = similarity_threshold
        self._ttl = ttl_seconds
        self._max_entries = max_entries_per_user
        self._chroma_client = None

    async def initialize(self) -> None:
        """初始化 ChromaDB 客户端 + collection"""
        import chromadb
        self._chroma_client = chromadb.PersistentClient(path="data/chroma_semantic")
        self._collection = self._chroma_client.get_or_create_collection(
            name=self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    async def lookup(
        self,
        user_id: int,
        query: str,
        system_prompt_hash: str = "",
        model: str = "",
    ) -> Optional[CacheEntry]:
        """查询缓存

        流程:
        1. 生成 query embedding
        2. ChromaDB where 过滤: user_id + system_prompt_hash + model + TTL
        3. cosine 相似度 ≥ threshold → 命中
        4. 命中则 hit_count++ 并返回
        """
        ...

    async def store(
        self,
        user_id: int,
        query: str,
        response: str,
        system_prompt_hash: str = "",
        model: str = "",
    ) -> None:
        """存储缓存

        流程:
        1. 生成 query embedding
        2. 检查用户缓存条目数（超过 max_entries 则删除最旧的）
        3. 写入 ChromaDB（id=user_id:hash, metadata=user_id/system_prompt_hash/model/created_at）
        """
        ...

    async def invalidate_user(self, user_id: int) -> None:
        """清空指定用户的所有缓存"""
        ...

    async def stats(self, user_id: int) -> dict:
        """返回用户缓存统计（条目数/命中率/节省 API 调用次数）"""
        ...
```

### 6.2 关键设计

1. **仅 LLM 启用**：Image/Video/TTS 不适合语义缓存（用户期望独特结果），继续用现有 ResultCacheService 精确 key
2. **每用户独立**：ChromaDB `where={"user_id": user_id}` 过滤，避免用户间泄露
3. **system_prompt 隔离**：不同 system_prompt（如不同角色设定）的缓存隔离
4. **model 隔离**：不同 LLM 模型（Qwen vs DeepSeek）的缓存隔离
5. **TTL 30min**：LLM 结果可能随时间变化，沿用现有 ResultCacheService 的 LLM_TTL
6. **FIFO 淘汰**：每用户超过 1000 条时删除最旧的（按 created_at 排序）
7. **禁用场景**：流式响应（stream=True）不缓存（结果不完整）；max_tokens < 100 不缓存（太短）

### 6.3 ChromaDB 数据结构

```python
# Collection: llm_semantic_cache
# documents: 原始 query（messages JSON）
# embeddings: bge-m3 1024 维向量
# metadatas:
{
    "user_id": 123,
    "system_prompt_hash": "sha256...",
    "model": "qwen2.5-14b",
    "created_at": 1784529963,
    "hit_count": 5,
}
# ids: f"{user_id}:{sha256(query)[:16]}"
```

## 7. Embedding 服务设计

```python
# backend/app/core/embedding_service.py
class EmbeddingService:
    """bge-m3 Embedding 服务

    懒加载模型（首次调用时加载），支持批量编码。
    模型大小 ~2.3GB，首次启动时从 HuggingFace 下载。
    """

    MODEL_NAME = "BAAI/bge-m3"
    EMBEDDING_DIM = 1024
    MAX_SEQ_LENGTH = 8192

    def __init__(self, model_cache_dir: str = "data/models/bge-m3"):
        self._model_cache_dir = model_cache_dir
        self._model = None

    async def initialize(self) -> None:
        """懒加载模型"""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self.MODEL_NAME,
                cache_folder=self._model_cache_dir,
            )

    async def encode(self, text: str) -> list[float]:
        """编码单个文本 → 1024 维向量"""
        await self.initialize()
        return self._model.encode(text, normalize_embeddings=True).tolist()

    async def encode_batch(self, texts: list[str]) -> list[list[float]]:
        """批量编码"""
        await self.initialize()
        return self._model.encode(
            texts,
            batch_size=32,
            normalize_embeddings=True,
        ).tolist()
```

**关键设计**：
1. 懒加载（避免阻塞启动）
2. 持久化缓存到 `data/models/bge-m3/`
3. `normalize_embeddings=True`（cosine = 内积，更快）
4. CPU 推理 ~20ms/请求，无需 GPU

## 8. Provider 实现细节

### 8.1 即梦 Seedream（Image API）

```python
# backend/app/engines/image/seedream.py
class SeedreamProvider(ImageGenProvider):
    """即梦 Seedream 图像生成 Provider (Volcano API)"""

    name = "seedream"
    display_name = "即梦 Seedream 4.0"
    is_local = False
    requires_api_key = True
    subscription_required = "pro"
    supported_models = ["seedream-4.0"]
    health_check_url = "https://visual.volcengineapi.com/health"

    API_BASE = "https://visual.volcengineapi.com/v1/images/generate"
    REQUEST_TYPE = "lcm"

    def __init__(self, api_key: str, api_secret: str, region: str = "cn-north-1"):
        self._api_key = api_key
        self._api_secret = api_secret
        self._region = region

    async def text2img(self, prompt, negative_prompt="", width=1024, height=1024, seed=None, **kwargs):
        # 1. Volcano V4 签名
        # 2. POST 到 API_BASE
        # 3. 轮询任务状态（Seedream 是异步任务）
        # 4. 下载结果图片
        # 5. 返回 GenerationResult(data=bytes, content_type="image/png", metadata={...})
        ...
```

### 8.2 即梦 Seedance（Video API）

```python
# backend/app/engines/video/seedance.py
class SeedanceProvider(VideoGenProvider):
    """即梦 Seedance 视频生成 Provider (Volcano API)"""

    name = "seedance"
    display_name = "即梦 Seedance 1.0 Pro"
    is_local = False
    requires_api_key = True
    subscription_required = "pro"
    supported_models = ["seedance-1.0-pro", "seedance-1.0-lite"]
    capability = {
        "max_duration": 10,
        "supports_img2video": True,
        "supports_text2video": True,
        "resolutions": ["720p", "1080p"],
    }

    async def text2video(self, prompt, duration=5, **kwargs):
        # 1. 提交任务到 Volcano API
        # 2. WebSocket 推送进度（复用 Task 3 的 WS publish）
        # 3. 任务完成后下载视频
        ...
```

### 8.3 可灵 Kling（Video API）

```python
# backend/app/engines/video/kling.py
class KlingProvider(VideoGenProvider):
    """可灵 Kling 视频生成 Provider (快手 API)"""

    name = "kling"
    display_name = "可灵 Kling 1.6"
    is_local = False
    requires_api_key = True
    subscription_required = "pro"
    supported_models = ["kling-1.6-pro", "kling-1.6-standard"]
    capability = {
        "max_duration": 10,
        "supports_img2video": True,
        "supports_text2video": True,
        "resolutions": ["720p", "1080p"],
    }
```

### 8.4 FLUX（Image 本地）

```python
# backend/app/engines/image/flux.py
class FluxProvider(ImageGenProvider):
    """FLUX.1-dev 图像生成 Provider (本地 diffusers)"""

    name = "flux"
    display_name = "FLUX.1-dev"
    is_local = True
    requires_api_key = False
    subscription_required = "pro"
    supported_models = ["flux-dev-fp16", "flux-dev-q4"]
    capability = {
        "max_resolution": 2048,
        "requires_vram_gb": 12,
    }

    def __init__(self, model_path: str = "data/models/flux-dev"):
        self._model_path = model_path
        self._pipeline = None  # 懒加载

    async def initialize(self):
        # 懒加载 FLUX pipeline (diffusers.FluxPipeline)
        # 4bit 量化版本支持 12GB 显存
        ...

    async def text2img(self, prompt, **kwargs):
        # 调用 self._pipeline(prompt, ...)
        # 返回 PIL Image → bytes
        ...
```

### 8.5 Qwen2.5 本地（LLM vLLM）

```python
# backend/app/engines/llm/qwen_local.py
class QwenLocalProvider(LLMProvider):
    """Qwen2.5 本地 LLM Provider (vLLM)"""

    name = "qwen-local"
    display_name = "Qwen2.5-14B (本地 vLLM)"
    is_local = True
    requires_api_key = False
    subscription_required = "pro"
    supported_models = ["qwen2.5-14b-instruct-q4", "qwen2.5-14b-instruct-fp16"]
    capability = {
        "supports_stream": True,
        "max_context": 32768,
    }

    def __init__(self, model_path: str = "data/models/qwen2.5-14b"):
        self._model_path = model_path
        self._llm = None  # vLLM 引擎懒加载

    async def initialize(self):
        # from vllm import AsyncLLMEngine
        ...
```

### 8.6 其他 API Provider（GLM/豆包/火山 TTS/Kolors）

模式类似 Seedream：API Key + httpx 请求 + 结果解析。具体签名/响应格式见各 Provider 实现文件。

### 8.7 Wan2.1 / Hunyuan / CosyVoice（本地）

模式类似 FLUX：懒加载 diffusers/AudioLDM 模型 + 本地推理。

## 9. 配额管理设计

```python
# backend/app/engines/quota_guard.py
class QuotaGuard:
    """配额管理 + 限流

    按订阅层级 + 引擎类型限制调用次数。
    数据存储在 Redis（生产）或内存（开发）。
    """

    LIMITS: dict[str, dict[str, dict[str, int]]] = {
        "free": {
            "image": {"daily": 5, "monthly": 100},
            "video": {"daily": 0, "monthly": 0},
            "llm": {"daily": 10, "monthly": 200},
            "tts": {"daily": 10, "monthly": 200},
        },
        "pro": {
            "image": {"daily": 50, "monthly": 1000},
            "video": {"daily": 10, "monthly": 200},
            "llm": {"daily": 100, "monthly": 2000},
            "tts": {"daily": 100, "monthly": 2000},
        },
        "enterprise": {
            "image": {"daily": -1, "monthly": -1},  # -1 = 不限
            "video": {"daily": -1, "monthly": -1},
            "llm": {"daily": -1, "monthly": -1},
            "tts": {"daily": -1, "monthly": -1},
        },
    }

    async def check(self, user_id, engine_type, subscription_tier) -> bool:
        """检查配额是否充足"""
        ...

    async def consume(self, user_id, engine_type, amount: int = 1) -> None:
        """消耗配额"""
        ...

    async def get_info(self, user_id, engine_type) -> "QuotaInfo":
        """获取配额信息（Dashboard 展示）"""
        ...
```

**关键设计**：
1. 语义缓存命中不扣额度
2. 本地推理不扣额度（`is_local=True`）
3. Redis 存储：`quota:user:{user_id}:{engine_type}:{date}`，TTL 24h
4. 内存降级：Redis 不可用时降级到内存 dict
5. Enterprise 不限：daily/monthly = -1

## 10. 本地推理订阅鉴权

### 10.1 接口

```python
# backend/app/engines/subscription_guard.py
class SubscriptionGuard:
    """本地推理订阅验证"""

    OFFLINE_GRACE_DAYS = 7

    async def verify(self, user_id: int, jwt_token: str) -> dict:
        """验证订阅状态

        返回:
        {
            "allowed": bool,
            "tier": "pro" | "enterprise" | "free",
            "expires_at": datetime,
            "last_verified": datetime,
            "offline_remaining_days": int,
        }
        """
        ...

    async def get_hardware_profile(self) -> str:
        """检测硬件并返回 profile（low/mid/high/cpu）"""
        ...

    async def get_recommended_models(self, hardware_profile: str) -> dict:
        """获取硬件适配的推荐模型清单"""
        ...

    async def record_model_download(self, user_id: int, model_name: str) -> None:
        """记录用户已下载的模型"""
        ...
```

### 10.2 硬件自适应推荐

```python
HARDWARE_PROFILES = {
    "low": {  # 4-8GB VRAM
        "image": ["sdxl-base-q4", "sdxl-refiner-q4"],
        "video": [],
        "llm": ["qwen2.5-7b-instruct-q4"],
        "tts": ["edge-tts"],
        "requires_subscription": "pro",
    },
    "mid": {  # 12-16GB VRAM
        "image": ["flux-dev-q4", "sdxl-base"],
        "video": ["wan2.1-1.3b"],
        "llm": ["qwen2.5-14b-instruct-q4"],
        "tts": ["cosyvoice-300m", "edge-tts"],
        "requires_subscription": "pro",
    },
    "high": {  # 24GB+ VRAM
        "image": ["flux-dev-fp16", "sdxl-base"],
        "video": ["wan2.1-14b", "hunyuan-video"],
        "llm": ["qwen2.5-14b-instruct-fp16"],
        "tts": ["cosyvoice-300m", "edge-tts"],
        "requires_subscription": "pro",
    },
    "cpu": {  # 仅 CPU
        "image": ["sdxl-base-cpu-q4"],
        "video": [],
        "llm": ["qwen2.5-7b-instruct-q4-cpu"],
        "tts": ["edge-tts"],
        "requires_subscription": "free",
    },
}
```

### 10.3 离线宽限

- 用户首次必须联网验证订阅
- 验证成功后，本地保存 `last_verified` 时间戳 + JWT
- 之后每次启动本地推理检查 `now - last_verified < OFFLINE_GRACE_DAYS`
- 超过宽限期 → 本地推理禁用，提示用户重新联网验证

### 10.4 模型下载机制

**API 端点**：`GET /api/v1/models/local/{hardware_profile}`

**响应**：
```json
{
  "hardware_profile": "mid",
  "models": {
    "image": [
      {
        "name": "flux-dev-q4",
        "size_gb": 6.5,
        "download_url": "https://hf-mirror.com/black-forest-labs/FLUX.1-dev",
        "md5": "...",
        "destination": "data/models/flux-dev/"
      }
    ],
    "video": [],
    "llm": [...],
    "tts": [...]
  }
}
```

**下载流程**：
1. 客户端调用 API 获取模型清单
2. 用户选择下载（前端展示大小、用途）
3. 客户端用 Electron `download` API 下载（断点续传）
4. 下载进度通过 WebSocket 推送（复用 Task 3）
5. 下载完成校验 MD5
6. 调用 `SubscriptionGuard.record_model_download` 记录

## 11. 健康检查与 Fallback

### 11.1 健康检查

- **API Provider**：定期（5min）调用 `health_check_url`，更新熔断器状态
- **本地 Provider**：检查模型文件是否存在 + GPU 可用性

### 11.2 Fallback 流程

```
Provider 调用失败
    ↓
[1] ProviderFailover.record_failure()
    ↓
[2] 失败次数 ≥ threshold (5) → 熔断器 OPEN
    ↓
[3] 重新调用 ProviderRouter.select() 获取次级 Provider
    ↓ 有次级
[4] 调用次级 Provider（递归，最多 3 层）
    ↓ 无次级
[5] 返回错误（含所有 Provider 失败原因）
```

## 12. 源码保护方案

### 12.1 Python 后端（Cython 编译）

**关键模块编译为 .so/.pyd**：
- `app/engines/router.py`
- `app/engines/quota_guard.py`
- `app/engines/subscription_guard.py`
- `app/core/semantic_cache.py`
- `app/core/embedding_service.py`
- `app/engines/llm/qwen_local.py`
- 所有 API Provider 实现

**编译流程**：
```bash
# setup_compile.py
from Cython.Build import cythonize
cythonize(["app/engines/router.py", ...], language_level=3)
# 生成 .so/.pyd，删除 .py 源码
```

**PyInstaller 打包**：编译后的 .so/.pyd + 其他 .py 一起打包为可执行文件

### 12.2 Electron 客户端（asar 加密）

```yaml
# electron-builder.yml
asar: true
asarUnpack:
  - "**/*.node"
  - "**/*.dll"
```

启用 asar 后，源码打包为 `app.asar` 文件。可配合 `bytenode` 编译主进程 JS 为字节码。

### 12.3 License 文件

```
ComicStudio AI 专有许可

版权所有 (c) 2026 [作者名]

未经授权，严禁：
1. 复制、修改、合并本软件源码
2. 将本软件源码上传至任何公开仓库（包括 GitHub）
3. 分发本软件的源码或编译产物
4. 逆向工程、反编译本软件

授权使用：
1. 最终用户可下载并使用本软件的编译产物
2. 商业使用需购买订阅（Free/Pro/Enterprise）
3. 本地推理功能仅限已订阅用户使用

联系方式：[邮箱]
```

## 13. 配置项

### 13.1 新增配置（config.py）

```python
# === Provider 配置 ===
# Image Providers
seedream_api_key: str = ""
seedream_api_secret: str = ""
seedream_region: str = "cn-north-1"

flux_model_path: str = "data/models/flux-dev"

kolors_api_key: str = ""
kolors_api_base: str = "https://api.kuaishou.com"

sdxl_model_path: str = "data/models/sdxl-base"

# Video Providers
seedance_api_key: str = ""
seedance_api_secret: str = ""

kling_api_key: str = ""
kling_api_secret: str = ""

wan_model_path: str = "data/models/wan2.1"
hunyuan_model_path: str = "data/models/hunyuan-video"

# LLM Providers
qwen_model_path: str = "data/models/qwen2.5-14b"
qwen_vllm_port: int = 8001

glm_api_key: str = ""
glm_api_base: str = "https://open.bigmodel.cn/api/paas/v4"

doubao_api_key: str = ""
doubao_api_base: str = "https://ark.cn-beijing.volces.com/api/v3"

# TTS Providers
volcano_tts_app_id: str = ""
volcano_tts_access_token: str = ""

cosyvoice_model_path: str = "data/models/cosyvoice-300m"

# === 语义缓存配置 ===
semantic_cache_enabled: bool = True
semantic_cache_threshold: float = 0.90
semantic_cache_ttl_seconds: int = 1800
semantic_cache_max_entries_per_user: int = 1000
semantic_cache_chroma_path: str = "data/chroma_semantic"

# === Embedding 配置 ===
embedding_model_name: str = "BAAI/bge-m3"
embedding_model_cache_dir: str = "data/models/bge-m3"
embedding_batch_size: int = 32

# === 本地推理订阅验证 ===
local_inference_offline_grace_days: int = 7
local_inference_require_subscription: bool = True

# === 配额管理 ===
quota_redis_url: str = ""
quota_enabled: bool = True

# === 源码保护 ===
source_protection_enabled: bool = False
```

### 13.2 环境变量（.env 示例）

```env
# Image Providers
SEEDREAM_API_KEY=your_seedream_key
SEEDREAM_API_SECRET=your_seedream_secret
KOLORS_API_KEY=your_kolors_key

# Video Providers
SEEDANCE_API_KEY=your_seedance_key
KLING_API_KEY=your_kling_key

# LLM Providers
GLM_API_KEY=your_glm_key
DOUBAO_API_KEY=your_doubao_key

# TTS Providers
VOLCANO_TTS_APP_ID=your_volcano_app_id
VOLCANO_TTS_ACCESS_TOKEN=your_volcano_token

# 语义缓存
SEMANTIC_CACHE_ENABLED=true
```

## 14. API 端点新增

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/v1/models` | 列出所有可用 Provider + 模型（按引擎类型分组） |
| GET | `/api/v1/models/local/{hardware_profile}` | 获取硬件适配的本地模型推荐清单 |
| POST | `/api/v1/models/local/{model_name}/download` | 记录模型下载（触发 WS 进度推送） |
| GET | `/api/v1/providers/health` | 获取所有 Provider 健康状态 |
| GET | `/api/v1/quota/me` | 获取当前用户配额信息 |
| POST | `/api/v1/cache/invalidate` | 清空当前用户的语义缓存 |

## 15. 测试策略

### 15.1 单元测试

- **Provider 注册表**：8 个测试（注册/获取/列出/重复注册/未知类型/未知 Provider）
- **Provider 路由器**：10 个测试（订阅层级/用户偏好/熔断器/fallback/force_local）
- **配额管理**：6 个测试（check/consume/超额/Enterprise 不限/本地不扣/缓存命中不扣）
- **订阅验证**：5 个测试（验证成功/订阅过期/离线宽限/硬件检测/记录下载）
- **语义缓存**：10 个测试（命中/未命中/TTL 过期/system_prompt 隔离/model 隔离/FIFO 淘汰/清空/统计/批量/禁用场景）
- **Embedding 服务**：5 个测试（懒加载/单次编码/批量编码/健康检查/异常）
- **Seedream Provider**：5 个测试（初始化/text2img/健康检查/签名/错误处理）
- **Seedance Provider**：5 个测试（初始化/text2video/健康检查/进度推送/错误处理）
- **Kling Provider**：5 个测试（同 Seedance）
- **本地模型 API**：6 个测试（hardware_profile 检测/模型清单/记录下载/订阅验证/未知 profile/订阅不足）

### 15.2 集成测试

- **LLM 完整流程**：用户请求 → 语义缓存查询 → 路由选择 → Provider 调用 → 缓存存储 → 配额消耗
- **Fallback 流程**：主 Provider 失败 → 自动切换次级 → 最终返回结果
- **本地推理流程**：订阅验证 → 硬件检测 → 模型下载 → 本地 Provider 调用

### 15.3 前端测试

- **models API 客户端**：5 个测试（获取列表/获取本地推荐/记录下载/错误处理/类型）

### 15.4 回归测试

- 全量后端测试：543 → 618+ passed
- 全量前端测试：548+ passed
- TypeScript 类型检查：0 errors
- 前端构建成功
- Desktop 构建成功

## 16. 风险与缓解

| 风险 | 影响 | 缓解 |
|---|---|---|
| bge-m3 模型大（2.3GB） | 首次启动慢 | 懒加载 + 后台下载 + 进度提示 |
| ChromaDB 并发性能 | 高并发时查询慢 | HNSW 索引 + 批量查询 + 连接池 |
| Volcano API 签名复杂 | 集成难度大 | 用官方 SDK + 详细日志 + mock 测试 |
| vLLM 仅支持 Linux | Windows 服务器无法自建 Qwen | 云端服务器用 Linux + Docker；Windows 仅作开发 |
| Provider API 变更 | 接口失效 | 健康检查 + 熔断器 + fallback |
| 源码保护不彻底 | Cython 仍可反编译 | 关键算法用 C 扩展 + License 法律保护 |

## 17. 验收标准

- [ ] 14 个 Provider 全部注册并可实例化
- [ ] 智能路由按订阅层级正确选择 Provider
- [ ] 语义缓存命中率 ≥ 30%（重复 prompt 场景）
- [ ] 语义缓存查询延迟 < 50ms
- [ ] 配额管理正确限流（Free/Pro/Enterprise）
- [ ] 本地推理订阅验证生效
- [ ] 硬件自适应推荐正确（4 个 profile）
- [ ] 健康检查 + fallback 自动切换
- [ ] 后端测试 618+ passed
- [ ] 前端测试 548+ passed
- [ ] TypeScript 0 errors
- [ ] 前端 + Desktop 构建成功
- [ ] LICENSE 文件已创建

## 18. 后续阶段衔接

P1 完成后：
- **P2（AMD/Intel GPU）**：扩展 `LocalRuntimeDetector` 支持 DirectML/OpenVINO，新增 `is_local=True` 的 AMD/Intel Provider
- **P3（LoRA 训练 UI）**：基于 P1 的本地推理基础设施，新增训练 pipeline + 前端训练配置 UI
- **P4（K8s）**：基于 P1 的多 Provider 架构，部署到 K8s 集群
- **P5（多区域）**：基于 P4 的 K8s，扩展到多区域
