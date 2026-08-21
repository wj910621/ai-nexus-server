# Phase 8 P2: AMD/Intel GPU 支持 设计文档

> **状态**：已批准
> **日期**：2026-07-20
> **作者**：ComicStudio AI 团队
> **依赖**：Phase 8 P1（多 Provider 抽象层 + 语义缓存 + 智能路由 + 配额管理 + 本地推理订阅鉴权）
> **后续**：Phase 8 P3（LoRA 训练 UI）→ P4（K8s 部署）

---

## 1. 背景与目标

### 1.1 背景

Phase 8 P1 已建立 14 Provider 注册表 + 智能路由 + 语义缓存 + 配额管理 + 本地推理订阅鉴权，但本地推理层仅支持 NVIDIA CUDA：

- `LocalRuntimeDetector` 只检测 `torch.cuda.is_available()`
- 5 个本地 Provider（FLUX/Wan/Hunyuan/QwenLocal/CosyVoice）硬编码 `"cuda"` 设备
- AMD ROCm 与 Intel XPU 用户无法使用本地推理，被迫走云端 API（增加成本、降低体验）

### 1.2 目标

在不破坏 P1 已有 14 Provider 注册表的前提下，让本地推理层自动适配 **NVIDIA CUDA / AMD ROCm / Intel XPU** 三大厂商，并暴露统一基准测试入口。

### 1.3 范围

**包含**：
- AMD ROCm 支持（PyTorch ROCm 构建，走 `torch.cuda` API）
- Intel XPU 支持（`torch.xpu` API + IPEX 可选）
- 混合 LLM 引擎策略：NVIDIA/AMD 用 vLLM，Intel/CPU 用 llama.cpp
- 全后端 + 基准测试（含吞吐/延迟/显存三项指标）
- 前端基准测试结果展示

**不包含**（YAGNI）：
- Apple Silicon MPS 支持（P5 或后续）
- NPU 支持（无市场需求）
- 多 GPU 并行推理（单 GPU 足够漫剧场景）
- 基准测试结果持久化到数据库（仅内存缓存）
- 基准测试定时自动执行（手动触发即可）
- DirectML / OneAPI 后端（仅 ROCm + XPU 已满足需求，DirectML/OneAPI 留待 P5）

### 1.4 关键约束

| 约束 | 说明 |
|---|---|
| 既有抽象不变 | `base.py` / `registry.py` / `router.py` / `quota_guard.py` / `subscription_guard.py` 的核心 API 不破坏 |
| 零回归 | P1 的 669 个测试必须全部通过 |
| 单一入口 | `DeviceManager` 是唯一设备入口，Provider 不直接调用 `torch.cuda.*` 或 `torch.xpu.*` |
| 失败安全 | DeviceManager 永不让应用启动失败，最差回退 CPU |
| 测试目标 | 总测试数 704+ 通过（669 既有 + 35 新增） |

### 1.5 关键技术现实

| 厂商 | 探测方式 | LLM 引擎 | diffusers | 备注 |
|---|---|---|---|---|
| NVIDIA | `torch.cuda.is_available()` + name 含 "NVIDIA" | vLLM | 完整支持 | 基线 |
| AMD | `torch.cuda.is_available()` + name 含 "AMD"/"Radeon"/"gfx" | vLLM ROCm | 大部分支持 | API 兼容 cuda |
| Intel | `torch.xpu.is_available()` + name 含 "Intel"/"Arc" | llama.cpp (Vulkan) | 部分支持 | IPEX 可选 |

---

## 2. 架构总览

### 2.1 三层架构

```
┌─────────────────────────────────────────────────────┐
│  Provider 层（5 个本地 Provider + 1 个新 Provider）  │
│  FluxProvider / WanProvider / HunyuanProvider /     │
│  QwenLocalProvider(vLLM) / CosyVoiceProvider        │
│  + LlamaCppProvider（Intel LLM fallback）           │
│  ↓ 每次构造/initialize 调用                          │
├─────────────────────────────────────────────────────┤
│  DeviceManager（单例，唯一设备入口）                 │
│  · detect_vendor()      → NVIDIA/AMD/Intel/None     │
│  · get_device_string()  → "cuda:0"/"xpu:0"/"cpu"    │
│  · get_torch_dtype()    → bfloat16/float16/float32  │
│  · recommend_llm_engine()→ "vllm"/"llama_cpp"       │
│  · benchmark()          → BenchmarkReport           │
├─────────────────────────────────────────────────────┤
│  Detector 层（无副作用，纯探测）                     │
│  GPUVendorDetector  +  CPUDetector  +  RAMDetector  │
└─────────────────────────────────────────────────────┘
```

### 2.2 关键设计决策

1. **DeviceManager 单例**：唯一设备入口，所有 Provider 通过它获取设备字符串与厂商信息
2. **混合 LLM 引擎**：NVIDIA/AMD 用 vLLM（已有 QwenLocalProvider），Intel/CPU 用 llama.cpp（新增 LlamaCppProvider）
3. **三层降级**：本地推理 → 同厂商其他 Provider → 云端 API → 明确错误
4. **基准测试缓存**：首次调用触发，结果缓存在 DeviceManager 单例，TTL 1 小时
5. **复用 P1 熔断器**：仅扩展 `failure_reason` 字段，差异化冷却时间

### 2.3 与 P1 已有抽象的关系

- **不修改**：`base.py`（仅加 `_init_error` 字段）、`registry.py`、`quota_guard.py`、`subscription_guard.py`、`manager.py` 路由核心逻辑
- **新增**：`device_manager.py`、`gpu_vendor_detector.py`、`benchmark_suite.py`、`llm/llama_cpp.py`
- **修改**：`local_runtime.py`（委托给 DeviceManager）、5 个本地 Provider（替换 device 获取方式）、`engines/__init__.py`（注册 llama_cpp）、`config.py`（新增基准测试开关）、`router.py`（加 failure_reason）、`manager.py`（加 LLM 引擎过滤）

---

## 3. 模块详情

### 3.1 `backend/app/core/gpu_vendor_detector.py`（新建，~120 行）

**职责**：纯探测，无副作用。返回厂商信息。

```python
class GPUVendor(str, enum.Enum):
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    NONE = "none"

@dataclass
class GPUInfo:
    vendor: GPUVendor
    device_name: str          # "NVIDIA GeForce RTX 4090" / "AMD Radeon RX 7900 XTX" / "Intel Arc A770"
    vram_gb: float
    device_index: int = 0
    backend: str = ""         # "cuda" (NVIDIA) / "cuda" (AMD ROCm) / "xpu" (Intel)

class GPUVendorDetector:
    def detect(self) -> Optional[GPUInfo]:
        """探测顺序：NVIDIA CUDA → AMD ROCm (仍走 cuda API) → Intel XPU"""
        # 1. torch.cuda.is_available() → 取 name 判断 vendor
        # 2. torch.xpu.is_available() → Intel
        # 3. 都没有 → None
```

**厂商识别规则**（关键）：
- `name.startswith("NVIDIA")` → NVIDIA
- `name.startswith("AMD")` 或 `"Radeon"` in name 或 name 以 `gfx` 开头（ROCm GPU）→ AMD
- `name.startswith("Intel")` 或 `"Arc"` in name → Intel（XPU 路径）
- 其他 → 未知，回退 CPU

### 3.2 `backend/app/core/device_manager.py`（新建，~180 行）

**职责**：单例。封装设备选择、dtype 选择、LLM 引擎推荐、基准测试入口。

```python
class DeviceManager:
    _instance = None  # 单例

    def __init__(self):
        self._gpu_info: Optional[GPUInfo] = None
        self._runtime_info: RuntimeInfo = None
        self._benchmark: Optional[BenchmarkReport] = None
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> "DeviceManager": ...

    async def initialize(self) -> None:
        """初始化：探测 GPU + CPU/RAM，结果缓存"""

    def detect_vendor(self) -> GPUVendor: ...

    def get_device_string(self, engine_type: str = "image") -> str:
        """返回 Provider 应使用的 device 字符串
        - NVIDIA: "cuda:0"
        - AMD (ROCm): "cuda:0"  ← API 兼容
        - Intel: "xpu:0"
        - 无 GPU: "cpu"
        """

    def get_torch_dtype(self, engine_type: str = "image") -> Any:
        """返回推荐的 torch dtype
        - NVIDIA/AMD (>=16GB): bfloat16
        - NVIDIA/AMD (<16GB): float16
        - Intel: float16  (bfloat16 支持不完整)
        - CPU: float32
        """

    def recommend_llm_engine(self) -> str:
        """LLM 引擎推荐
        - NVIDIA/AMD: "vllm"
        - Intel: "llama_cpp"  (vLLM 对 Intel 支持差)
        - CPU: "llama_cpp"
        """

    def get_gpu_info(self) -> Optional[GPUInfo]: ...
    def get_runtime_info(self) -> RuntimeInfo: ...

    async def benchmark(self, force: bool = False) -> "BenchmarkReport":
        """运行基准测试（首次调用或 force=True 时执行，结果缓存）"""
```

### 3.3 `backend/app/core/benchmark_suite.py`（新建，~150 行）

**职责**：标准化基准测试，输出可比较的吞吐/延迟/显存数据。

```python
@dataclass
class BenchmarkMetric:
    name: str               # "image_t2i_throughput" / "llm_tokens_per_sec" / ...
    value: float
    unit: str               # "img/s" / "tokens/s" / "ms" / "GB"
    details: dict = field(default_factory=dict)

@dataclass
class BenchmarkReport:
    vendor: GPUVendor
    device_name: str
    metrics: list[BenchmarkMetric]
    timestamp: str
    duration_sec: float

class BenchmarkSuite:
    async def run_full(self) -> BenchmarkReport:
        """完整基准测试套件
        - LLM: 100-token 生成，测 tokens/s
        - Image: 512x512 4-step，测 img/s
        - Video: 2s 8fps，测 frame/s
        - VRAM 峰值占用（torch.cuda/xpu.memory_allocated）
        """

    async def run_llm(self) -> BenchmarkMetric: ...
    async def run_image(self) -> BenchmarkMetric: ...
    async def run_vram_peak(self) -> BenchmarkMetric: ...
```

### 3.4 `backend/app/engines/llm/llama_cpp.py`（新建，~150 行）

**职责**：Intel XPU / CPU 用的 LLM Provider，基于 `llama-cpp-python`。

```python
class LlamaCppProvider(LLMProvider):
    name = "llama_cpp"
    display_name = "Llama.cpp (Intel/CPU)"
    is_local = True
    supported_models = ["Qwen/Qwen2.5-7B-Instruct-GGUF", "Qwen/Qwen2.5-14B-Instruct-GGUF"]

    def __init__(self, model_path=None, n_gpu_layers=-1, n_ctx=8192):
        self.device_string = DeviceManager.get_instance().get_device_string("llm")
        # Intel XPU 走 llama.cpp 的 Vulkan 后端，n_gpu_layers=-1 全卸载
        # CPU 时 n_gpu_layers=0

    async def initialize(self): ...  # 加载 GGUF 模型
    async def chat(...) -> GenerationResult: ...
    async def chat_stream(...) -> AsyncGenerator[str, None]: ...
```

### 3.5 修改：`backend/app/core/local_runtime.py`

- `LocalRuntimeDetector.detect()` 内部委托给 `DeviceManager`：GPU 信息从 `DeviceManager.get_gpu_info()` 获取
- 对外 API 完全兼容（`RuntimeInfo` 数据结构不变），P1 已有调用方零改动
- 新增 `detect_vendor()` 透传方法

### 3.6 修改：5 个本地 Provider

每个 Provider 改动**仅 1-2 行**（device 获取方式）：

```python
# 修改前（flux.py / wan.py / hunyuan.py / cosyvoice.py）
from app.core.config import settings
self.device = device or settings.device

# 修改后
from app.core.device_manager import DeviceManager
self.device = device or DeviceManager.get_instance().get_device_string("image")
self.dtype = DeviceManager.get_instance().get_torch_dtype("image")
```

`qwen_local.py` 特殊处理：
```python
# 增加 LLM 引擎选择
self.engine_hint = DeviceManager.get_instance().recommend_llm_engine()
if self.engine_hint == "llama_cpp" and not _VLLM_AVAILABLE:
    # Intel 或 CPU 环境，由 LlamaCppProvider 接管，此 Provider 健康检查返回 False
    self._available = False
```

### 3.7 修改：`backend/app/engines/__init__.py`

注册新 Provider：
```python
try:
    from app.engines.llm.llama_cpp import LlamaCppProvider
    provider_registry.register("llm", "llama_cpp", LlamaCppProvider)
except Exception:
    pass
```

### 3.8 修改：`backend/app/core/config.py`

新增字段：
```python
benchmark_enabled: bool = True           # 是否启用基准测试
benchmark_cache_ttl: int = 3600          # 基准结果缓存时长（秒）
llama_cpp_model_path: str = ""            # GGUF 模型路径
llama_cpp_n_gpu_layers: int = -1          # GPU 层数（-1=全部）
```

### 3.9 修改：`backend/app/engines/router.py`

扩展熔断器状态：
```python
@dataclass
class CircuitBreakerState:
    failure_count: int
    last_failure_time: float
    cooldown_seconds: int
    failure_reason: str = ""  # 新增: "oom" / "unsupported" / "dependency" / "timeout" / "unknown"
```

**冷却时间按原因差异化**：
- `oom` → 5min（短期，可能下次内存够）
- `unsupported` → 永久（需重启应用）
- `dependency` → 永久（需安装依赖）
- `timeout` → 1min（短期，可能是临时负载）
- `unknown` → 30s（保守）

### 3.10 修改：`backend/app/engines/base.py`

新增字段：
```python
class BaseEngine(ABC):
    _initialized: bool = False
    _init_error: Optional[str] = None  # 新增: 初始化失败原因
```

`EngineManager._instantiate_all_providers()` 调用后检查 `_init_error`，若非空则向路由器注册"不可用"标记。

### 3.11 修改：`backend/app/engines/manager.py`

新增 LLM 引擎适配过滤逻辑：

```python
async def get_engine_routed(self, engine_type, user_id, subscription_tier,
                            user_preference="", force_local=False):
    candidates = ProviderRouter.select(...)

    # 新增: LLM 引擎适配过滤
    if engine_type == "llm":
        llm_engine_hint = DeviceManager.get_instance().recommend_llm_engine()
        if llm_engine_hint == "llama_cpp":
            candidates = [c for c in candidates if c.name != "qwen_local"]
        elif llm_engine_hint == "vllm":
            candidates = [c for c in candidates if c.name != "llama_cpp"]

    return candidates[0] if candidates else None
```

### 3.12 修改：`backend/app/api/admin.py`

新增端点：
```python
@router.post("/admin/benchmark")
async def run_benchmark(force: bool = False, user: User = Depends(require_admin)):
    report = await DeviceManager.get_instance().benchmark(force=force)
    return report.to_dict()
```

---

## 4. 数据流与运行时行为

### 4.1 启动时数据流

```
Application startup
  │
  ▼
DeviceManager.get_instance().initialize()
  │
  ├─► GPUVendorDetector.detect()
  │     ├─ torch.cuda.is_available() → True?
  │     │   ├─ torch.cuda.get_device_name(0)
  │     │   │   ├─ contains "NVIDIA"  → vendor=NVIDIA, backend="cuda"
  │     │   │   ├─ contains "AMD"/"Radeon"/"gfx" → vendor=AMD, backend="cuda" (ROCm)
  │     │   │   └─ else → 未知，vendor=NONE
  │     │   └─ torch.xpu.is_available() → True?
  │     │       └─ vendor=INTEL, backend="xpu"
  │     └─ 都无 → vendor=NONE, device="cpu"
  │
  ├─► RAM 检测（psutil.virtual_memory()）
  │
  └─► 缓存 GPUInfo + RuntimeInfo（单例，后续复用）
```

**关键点**：
- `DeviceManager.initialize()` 只在应用启动时调用一次
- 探测失败不抛异常，回退 CPU 模式，仅记录 warning
- 缓存后所有 Provider 共享同一份 GPUInfo，避免重复探测

### 4.2 Provider 实例化数据流

```
EngineManager._instantiate_all_providers()  (P1 已有)
  │
  ├─► FluxProvider()
  │     └─► DeviceManager.get_instance().get_device_string("image")
  │           └─ 返回缓存值（无重复探测）：NVIDIA→"cuda:0", Intel→"xpu:0", CPU→"cpu"
  │
  ├─► QwenLocalProvider()
  │     └─► DeviceManager.get_instance().recommend_llm_engine()
  │         ├─ NVIDIA/AMD → "vllm" → QwenLocalProvider 正常初始化
  │         └─ Intel/CPU  → "llama_cpp" → QwenLocalProvider._available=False
  │
  └─► LlamaCppProvider()  (新增)
        └─► DeviceManager.get_instance().get_device_string("llm")
            ├─ Intel → "xpu:0"（Vulkan 后端，n_gpu_layers=-1）
            └─ CPU   → "cpu"（n_gpu_layers=0）
```

### 4.3 路由时数据流

P1 的 `ProviderRouter.select()` 在 P2 中**不修改**，但 `EngineManager.get_engine_routed()` 在选 LLM 时增加设备适配逻辑：

```
GET /llm/chat (Pro 用户, force_local=True)
  │
  ▼
EngineManager.get_engine_routed("llm", user, tier, pref, force_local=True)
  │
  ├─► ProviderRouter.select() → 返回候选 Provider 列表
  │     例如 ["qwen_local", "llama_cpp", "deepseek"]
  │
  ├─► 引擎适配过滤（新增逻辑）:
  │     llm_engine_hint = DeviceManager.recommend_llm_engine()
  │     if llm_engine_hint == "llama_cpp":
  │         candidates = [c for c in candidates if c.name != "qwen_local"]
  │     elif llm_engine_hint == "vllm":
  │         candidates = [c for c in candidates if c.name != "llama_cpp"]
  │
  └─► 返回首个可用 Provider
```

**为什么不在 Router 里过滤？** 保持 P1 Router 的纯策略性（基于订阅/配额/偏好），设备适配是运行时上下文，由 EngineManager 处理。

### 4.4 基准测试数据流

```
POST /admin/benchmark  (Enterprise 管理员)
  │
  ▼
DeviceManager.get_instance().benchmark(force=True)
  │
  ├─► BenchmarkSuite.run_full()
  │     ├─► run_llm(): 短 prompt 生成 100 tokens × 3 次，取中位数 tokens/s
  │     │     ├─► NVIDIA/AMD: QwenLocalProvider.chat()
  │     │     └─► Intel/CPU:  LlamaCppProvider.chat()
  │     ├─► run_image(): 512x512 4-step 生成 × 3 次，取中位数 img/s
  │     │     └─► FluxProvider.text2img()
  │     └─► run_vram_peak(): 记录推理过程 torch.cuda/xpu.memory_allocated 峰值
  │
  └─► 返回 BenchmarkReport（缓存 1 小时）
        ├─ 写入 metrics: [tokens/s, img/s, vram_peak_gb, ...]
        └─ 前端 SettingsPage 展示对比图表
```

**缓存策略**：
- 首次 benchmark 调用触发，结果缓存在 DeviceManager 单例
- TTL 由 `settings.benchmark_cache_ttl` 控制（默认 1 小时）
- `force=True` 跳过缓存重新测试

### 4.5 并发与线程安全

- `DeviceManager` 是单例，`initialize()` 使用 `asyncio.Lock` 防止并发重复探测
- `benchmark()` 同样加锁，防止并发执行造成显存冲突
- 5 个本地 Provider 共享同一份 GPUInfo，但各自维护独立的模型实例与显存
- 基准测试运行时**独占** DeviceManager.benchmark 锁，避免与正常推理混淆

### 4.6 兼容性矩阵

| 厂商 | backend | FLUX | Wan | Hunyuan | QwenLocal(vLLM) | LlamaCpp | CosyVoice |
|---|---|---|---|---|---|---|---|
| NVIDIA | cuda | ✅ bf16 | ✅ bf16 | ✅ bf16 | ✅ | ✗（不注册） | ✅ |
| AMD | cuda(ROCm) | ✅ fp16 | ✅ fp16 | ✅ fp16 | ⚠️ 实验性 | ✗（不注册） | ⚠️ |
| Intel | xpu | ✅ fp16 | ⚠️ 部分 | ⚠️ 部分 | ✗ | ✅ | ⚠️ |
| CPU | cpu | ✗（太慢） | ✗ | ✗ | ✗ | ✅ | ⚠️ |

⚠️ = 厂商支持但效果不佳，Provider 仍会注册，由用户在 ProviderSelector 中手动选择

---

## 5. 错误处理与降级策略

### 5.1 三层降级链

```
Tier 1: 本地推理（首选）
  │ 失败（OOM/不支持/未安装）
  ▼
Tier 2: 同厂商其他 Provider
  │ 无可用
  ▼
Tier 3: 云端 API（兜底）
  │ 全失败
  ▼
Tier 4: 返回明确错误
```

**示例**：
- AMD GPU 跑 Wan 视频生成 OOM → 切 Hunyuan（同厂商） → 切 Kling（云端）
- Intel XPU 跑 LLM → `qwen_local` 不可用 → 切 `llama_cpp` → 切 DeepSeek API

### 5.2 错误分类与处理矩阵

| 错误类型 | 检测方式 | 处理 |
|---|---|---|
| **OOM**（显存不足） | `torch.cuda.OutOfMemoryError` / `RuntimeError: ...out of memory` | 捕获 → 标记 Provider 短时不可用（5min）→ 路由器熔断 → 切下一候选 |
| **厂商不支持** | Provider `initialize()` 返回 `success=False` | 标记 Provider 长期不可用 → 路由器跳过 |
| **依赖缺失** | `ImportError` / `ModuleNotFoundError` | Provider 注册时跳过，日志 warning |
| **模型未下载** | `FileNotFoundError` / `OSError` | 返回错误，前端触发模型下载向导 |
| **运行时崩溃** | 任意未捕获 `Exception` | 捕获 → 记录 traceback → 路由器熔断 → 切下一候选 |
| **超时** | `asyncio.TimeoutError` | 30s 超时 → 标记 Provider 不可用（1min）→ 切下一候选 |

### 5.3 Provider.initialize() 错误传播

**统一约定**：`initialize()` 不抛异常，所有错误通过返回值或状态字段传播。

```python
class BaseEngine:
    _initialized: bool = False
    _init_error: Optional[str] = None  # 初始化失败原因

    async def initialize(self) -> None:
        """子类实现时必须捕获所有异常并设置 _init_error"""
        ...
```

`EngineManager._instantiate_all_providers()` 调用后检查 `_init_error`，若非空则向路由器注册"不可用"标记。

### 5.4 DeviceManager 探测失败的降级

```python
async def initialize(self) -> None:
    try:
        self._gpu_info = GPUVendorDetector().detect()
    except Exception as exc:
        logger.warning(f"GPU detection failed: {exc}, fallback to CPU")
        self._gpu_info = None  # CPU 模式

    # RAM 检测从不失败（psutil 必装）
    self._runtime_info = RuntimeInfo(
        device_type=DeviceType.GPU if self._gpu_info else DeviceType.CPU,
        vram_gb=self._gpu_info.vram_gb if self._gpu_info else 0.0,
        ram_gb=psutil.virtual_memory().total / (1024**3),
        gpu_name=self._gpu_info.device_name if self._gpu_info else "",
    )
```

**关键**：DeviceManager 永远不会让应用启动失败，最差回退到 CPU 模式。

### 5.5 基准测试失败处理

```python
async def run_full(self) -> BenchmarkReport:
    metrics = []
    for runner in [self.run_llm, self.run_image, self.run_vram_peak]:
        try:
            metric = await asyncio.wait_for(runner(), timeout=120)
            metrics.append(metric)
        except asyncio.TimeoutError:
            metrics.append(BenchmarkMetric(
                name=runner.__name__, value=0, unit="",
                details={"error": "timeout after 120s"}
            ))
        except Exception as exc:
            metrics.append(BenchmarkMetric(
                name=runner.__name__, value=0, unit="",
                details={"error": f"{type(exc).__name__}: {exc}"}
            ))
    return BenchmarkReport(...)
```

**关键**：单项目失败不阻断整体报告，便于用户诊断哪个引擎有问题。

### 5.6 前端错误展示

| 场景 | 前端行为 |
|---|---|
| GPU 未检测到 | FirstLaunchPage Step 2 显示"未检测到 GPU，将使用 CPU 模式（性能较低）" |
| AMD GPU 但 ROCm 未安装 | 显示警告 + 链接到模型下载页（提供 ROCm PyTorch 安装指引） |
| Intel XPU 但 IPEX 未安装 | 同上，链接到 IPEX 安装指引 |
| 基准测试某项失败 | SettingsPage 基准测试卡片显示"⚠️ 该项失败：{error}" |
| Provider 熔断 | ProviderSelector 中该 Provider 灰显 + tooltip 显示熔断原因与剩余冷却时间 |

### 5.7 日志规范

所有 P2 相关日志统一前缀 `[P2]`：

```python
logger.warning("[P2] GPU detection failed: ...")
logger.info("[P2] Device initialized: vendor=AMD, device=cuda:0, dtype=float16")
logger.error("[P2] FLUX initialize failed (OOM), circuit breaker activated for 5min")
```

便于运维通过日志前缀快速定位 P2 相关问题。

---

## 6. 测试策略

### 6.1 测试分层

```
单元测试 (70%)
  ├─ GPUVendorDetector
  ├─ DeviceManager
  ├─ BenchmarkSuite
  ├─ LlamaCppProvider
  └─ 5 个本地 Provider 的设备适配改造
集成测试 (20%)
  ├─ DeviceManager + EngineManager 联动
  ├─ LLM 引擎路由切换（NVIDIA→vLLM, Intel→llama_cpp）
  └─ 基准测试端到端
端到端测试 (10%)
  ├─ 模拟 AMD 环境，FLUX 推理全流程
  └─ 模拟 Intel 环境，LLM 推理全流程
```

### 6.2 GPUVendorDetector 单元测试

**关键测试用例**（Mock `torch.cuda` / `torch.xpu`）：

```python
@pytest.mark.parametrize("device_name,expected_vendor", [
    ("NVIDIA GeForce RTX 4090", GPUVendor.NVIDIA),
    ("NVIDIA GeForce RTX 3060", GPUVendor.NVIDIA),
    ("AMD Radeon RX 7900 XTX", GPUVendor.AMD),
    ("AMD Radeon PRO W7900", GPUVendor.AMD),
    ("gfx1100", GPUVendor.AMD),  # ROCm GPU 命名
    ("Intel Arc A770", GPUVendor.INTEL),
    ("Intel(R) Arc(TM) A750", GPUVendor.INTEL),
])
def test_vendor_identification_by_name(device_name, expected_vendor):
    """测试厂商识别规则"""
    ...

def test_nvidia_cuda_available(): ...
def test_amd_rocm_available(): ...
def test_intel_xpu_available(): ...
def test_no_gpu_fallback(): ...
def test_detection_exception_swallowed(): ...
```

### 6.3 DeviceManager 单元测试

```python
@pytest.mark.parametrize("vendor,expected_device,expected_dtype_str", [
    (GPUVendor.NVIDIA, "cuda:0", "bfloat16"),
    (GPUVendor.AMD, "cuda:0", "float16"),
    (GPUVendor.INTEL, "xpu:0", "float16"),
    (GPUVendor.NONE, "cpu", "float32"),
])
def test_device_string_by_vendor(vendor, expected_device, expected_dtype_str): ...

def test_dtype_depends_on_vram(): ...
def test_recommend_llm_engine_nvidia(): ...
def test_recommend_llm_engine_intel(): ...
def test_recommend_llm_engine_cpu(): ...
def test_singleton_pattern(): ...
async def test_initialize_idempotent(): ...
async def test_initialize_lock(): ...
```

### 6.4 BenchmarkSuite 单元测试

```python
async def test_run_full_returns_report(): ...
async def test_metric_failure_isolated(): ...
async def test_timeout_protection(): ...
async def test_benchmark_caching(): ...
```

### 6.5 LlamaCppProvider 单元测试

```python
async def test_initialize_cpu_mode(): ...
async def test_initialize_intel_xpu_mode(): ...
async def test_chat_returns_generation_result(): ...
async def test_chat_stream_yields_tokens(): ...
async def test_initialize_failure_sets_error(): ...
def test_module_registration(): ...
```

### 6.6 已有 Provider 改造的回归测试

5 个 Provider 各 1 个测试，验证通过 DeviceManager 获取设备：

```python
async def test_flux_uses_device_manager(): ...
async def test_flux_intel_xpu(): ...
# 同样模式写 wan/hunyuan/cosyvoice/qwen_local
```

### 6.7 集成测试

```python
async def test_engine_manager_filters_by_vendor(): ...
async def test_engine_manager_nvidia_prefers_vllm(): ...
async def test_fallback_to_cloud_on_local_failure(): ...
async def test_benchmark_endpoint_e2e(): ...
```

### 6.8 端到端测试（Mock 环境）

```python
async def test_amd_flux_full_pipeline(): ...
async def test_intel_llm_full_pipeline(): ...
```

### 6.9 测试目标与覆盖率

- **后端测试新增目标**：+35 个测试（约 +600 行）
- **既有测试零回归**：P1 的 669 个测试必须全部通过
- **总测试数目标**：669 + 35 = **704+ 通过**
- **覆盖率目标**：新增模块行覆盖率 ≥ 85%

### 6.10 测试基础设施

- 复用 P1 已建立的 `conftest.py` 与 mock 模式
- 新增 `tests/fixtures/device_mocks.py`：封装 torch.cuda / torch.xpu 的厂商 mock 工具
- 新增 `tests/fixtures/benchmark_mocks.py`：基准测试 mock 数据

---

## 7. 文件结构

### 7.1 新建文件（11 个核心 + 9 个测试 = 20 个）

| # | 文件 | 行数估计 | 职责 |
|---|---|---|---|
| 1 | `backend/app/core/gpu_vendor_detector.py` | ~120 | NVIDIA/AMD/Intel 厂商识别 |
| 2 | `backend/app/core/device_manager.py` | ~180 | 设备/dtype/引擎推荐单例 |
| 3 | `backend/app/core/benchmark_suite.py` | ~150 | LLM/Image/VRAM 基准测试 |
| 4 | `backend/app/engines/llm/llama_cpp.py` | ~150 | Intel XPU/CPU LLM Provider |
| 5 | `backend/tests/unit/test_gpu_vendor_detector.py` | ~200 | 厂商识别 8 个用例 |
| 6 | `backend/tests/unit/test_device_manager.py` | ~250 | DeviceManager 10 个用例 |
| 7 | `backend/tests/unit/test_benchmark_suite.py` | ~150 | 基准测试 4 个用例 |
| 8 | `backend/tests/unit/test_llama_cpp_provider.py` | ~180 | LlamaCpp 6 个用例 |
| 9 | `backend/tests/integration/test_device_manager_integration.py` | ~120 | 集成 4 个用例 |
| 10 | `backend/tests/fixtures/device_mocks.py` | ~120 | torch mock 工具 |
| 11 | `backend/tests/fixtures/benchmark_mocks.py` | ~80 | 基准 mock |
| 12 | `backend/tests/integration/test_flux_device_adaptation.py` | ~80 | FLUX 改造回归 |
| 13 | `backend/tests/integration/test_wan_device_adaptation.py` | ~80 | Wan 改造回归 |
| 14 | `backend/tests/integration/test_hunyuan_device_adaptation.py` | ~80 | Hunyuan 改造回归 |
| 15 | `backend/tests/integration/test_cosyvoice_device_adaptation.py` | ~80 | CosyVoice 改造回归 |
| 16 | `backend/tests/integration/test_qwen_local_device_adaptation.py` | ~80 | QwenLocal 改造回归 |
| 17 | `backend/tests/e2e/test_amd_environment.py` | ~100 | AMD E2E |
| 18 | `backend/tests/e2e/test_intel_environment.py` | ~100 | Intel E2E |
| 19 | `frontend/src/api/benchmark.ts` | ~50 | 基准测试 API |
| 20 | `frontend/src/components/settings/BenchmarkCard.tsx` | ~120 | 基准结果展示 |

### 7.2 修改文件（13 个）

| # | 文件 | 改动量 | 内容 |
|---|---|---|---|
| 1 | `backend/app/core/local_runtime.py` | ~30 行 | 委托给 DeviceManager |
| 2 | `backend/app/core/config.py` | ~6 行 | +4 字段 |
| 3 | `backend/app/engines/__init__.py` | ~5 行 | 注册 LlamaCpp |
| 4 | `backend/app/engines/manager.py` | ~25 行 | +LLM 引擎适配过滤 |
| 5 | `backend/app/engines/router.py` | ~10 行 | +failure_reason |
| 6 | `backend/app/engines/base.py` | ~3 行 | +_init_error 字段 |
| 7 | `backend/app/engines/llm/qwen_local.py` | ~15 行 | +engine_hint |
| 8 | `backend/app/engines/image/flux.py` | ~5 行 | DeviceManager 接入 |
| 9 | `backend/app/engines/video/wan.py` | ~5 行 | DeviceManager 接入 |
| 10 | `backend/app/engines/video/hunyuan.py` | ~5 行 | DeviceManager 接入 |
| 11 | `backend/app/engines/tts/cosyvoice.py` | ~5 行 | DeviceManager 接入 |
| 12 | `backend/app/api/admin.py` | ~30 行 | +POST /admin/benchmark |
| 13 | `frontend/src/pages/SettingsPage.tsx` | ~20 行 | +基准测试 Tab |

---

## 8. 实施任务清单（预估 18 个 Task）

| Task | 名称 | 类型 | 关键依赖 |
|---|---|---|---|
| 1 | GPUVendorDetector | 新建+测试 | 无 |
| 2 | DeviceManager 单例 | 新建+测试 | Task 1 |
| 3 | LocalRuntimeDetector 委托 | 修改+回归 | Task 2 |
| 4 | config.py 扩展 | 修改 | 无 |
| 5 | BaseEngine 加 _init_error | 修改+回归 | 无 |
| 6 | Router 加 failure_reason | 修改+回归 | Task 5 |
| 7 | FLUX Provider 接入 DeviceManager | 修改+回归 | Task 2 |
| 8 | Wan Provider 接入 | 修改+回归 | Task 2 |
| 9 | Hunyuan Provider 接入 | 修改+回归 | Task 2 |
| 10 | CosyVoice Provider 接入 | 修改+回归 | Task 2 |
| 11 | QwenLocal Provider 引擎适配 | 修改+回归 | Task 2 |
| 12 | LlamaCppProvider | 新建+测试 | Task 2 |
| 13 | BenchmarkSuite | 新建+测试 | Task 2 |
| 14 | EngineManager LLM 引擎过滤 | 修改+集成测试 | Task 11, 12 |
| 15 | POST /admin/benchmark 端点 | 修改+集成测试 | Task 13 |
| 16 | 前端 BenchmarkCard + SettingsPage | 新建+修改 | Task 15 |
| 17 | E2E 测试（AMD/Intel 模拟环境） | 新建 | All |
| 18 | 全量回归测试 | 验证 | All |

---

## 9. 风险与缓解

| 风险 | 缓解措施 |
|---|---|
| ROCm 下 diffusers 某些 op 不支持 | Provider 返回 `success=False`，路由切云端 API |
| Intel IPEX 安装复杂 | LlamaCppProvider 用 llama-cpp-python 的 Vulkan 后端，不依赖 IPEX |
| llama-cpp-python 在 Windows 编译困难 | 提供 wheel 安装指引 + 可选回退到 CPU 模式 |
| 基准测试耗时过长 | 单项 120s 超时 + 整体缓存 1 小时 |
| 测试无法真实跑 GPU | 全部 mock torch.cuda/xpu，仅验证逻辑分支 |
| 5 个 Provider 改造引发回归 | 每个 Provider 单独写适配回归测试 |

---

## 10. 验收标准

- ✅ 20 个新建文件全部创建并通过单元测试（4 核心 + 14 测试 + 2 前端）
- ✅ 13 个修改文件改动通过回归测试
- ✅ 既有 669 测试零回归
- ✅ 新增 35+ 测试全部通过
- ✅ 总测试数 **704+** 通过
- ✅ AMD 模拟环境下 FLUX 推理成功
- ✅ Intel 模拟环境下 LLM 推理（llama_cpp）成功
- ✅ NVIDIA 环境行为与 P1 完全一致（向后兼容）
- ✅ `POST /admin/benchmark` 端到端可用
- ✅ 前端 SettingsPage 可查看基准测试结果

---

## 11. 不在 P2 范围内（YAGNI）

- ❌ Apple Silicon MPS 支持（P5 或后续）
- ❌ NPU 支持（无市场需求）
- ❌ 多 GPU 并行推理（单 GPU 足够漫剧场景）
- ❌ 基准测试结果持久化到数据库（仅内存缓存即可）
- ❌ 基准测试定时自动执行（手动触发即可）
- ❌ DirectML / OneAPI 后端（仅 ROCm + XPU 已满足需求，DirectML/OneAPI 留待 P5）

---

## 12. 后续阶段

- **P3**：LoRA 训练 UI（基于 P2 的 DeviceManager 选择训练设备）
- **P4**：K8s 部署（基于 P2 的厂商探测实现多节点异构 GPU 调度）
- **P5**：多区域部署 + Apple Silicon + DirectML/OneAPI

---

**Spec 结束**
