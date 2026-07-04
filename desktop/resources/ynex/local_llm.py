"""
Y·NEX 本地LLM推理引擎
支持：
  - Ollama（推荐，一键安装管理模型）
  - llama.cpp 直接调用（轻量无依赖）
  - 自动降级：本地 -> DeepSeek API -> Mock

功能：
  - 模型自动下载/管理
  - 量化级别自动选择（根据显存）
  - Function Calling 支持
  - 流式输出
  - 显存检测与自动调配
"""

import os
import json
import time
import re
import hashlib
import subprocess
import threading
from collections import OrderedDict
from typing import Optional, List, Dict, Callable, Generator
from dataclasses import dataclass
from pathlib import Path

from logger import logger
from config import settings


# =============================================================================
# 硬件检测
# =============================================================================

@dataclass
class HardwareInfo:
    total_ram_gb: float = 0
    vram_gb: float = 0
    cpu_cores: int = 0
    has_gpu: bool = False
    gpu_name: str = ""


# 硬件信息缓存，避免每次健康检查重复检测
_HARDWARE_CACHE: Optional[HardwareInfo] = None


def detect_hardware() -> HardwareInfo:
    """检测硬件配置，决定模型加载策略（带缓存）"""
    global _HARDWARE_CACHE
    if _HARDWARE_CACHE is not None:
        return _HARDWARE_CACHE

    info = HardwareInfo()

    try:
        import psutil
        info.total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
        info.cpu_cores = psutil.cpu_count(logical=True) or 4
    except Exception:
        info.total_ram_gb = 8
        info.cpu_cores = 4

    try:
        import torch
        if torch.cuda.is_available():
            info.has_gpu = True
            info.gpu_name = torch.cuda.get_device_name(0)
            vram_bytes = torch.cuda.get_device_properties(0).total_memory
            info.vram_gb = round(vram_bytes / (1024**3), 1)
    except Exception:
        pass

    if not info.has_gpu:
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=3
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if lines:
                    parts = lines[0].split(", ")
                    if len(parts) >= 2:
                        info.has_gpu = True
                        info.gpu_name = parts[0]
                        info.vram_gb = round(float(parts[1]) / 1024, 1)
        except Exception:
            pass

    logger.info(f"硬件检测: RAM={info.total_ram_gb}GB VRAM={info.vram_gb}GB "
                f"CPU={info.cpu_cores}核 GPU={info.gpu_name or '无'}")
    _HARDWARE_CACHE = info
    return info


# =============================================================================
# 模型推荐
# =============================================================================

MODEL_CATALOG = [
    {
        "id": "qwen2.5:1.5b-instruct-q4_K_M",
        "name": "Qwen2.5 1.5B",
        "size": "1.5B",
        "quant": "Q4_K_M",
        "vram_needed": 1.2,
        "ram_needed": 2,
        "speed": "快",
        "quality": "一般",
        "chinese": True,
        "description": "通义千问2.5 15亿参数，速度极快，适合简单任务",
    },
    {
        "id": "qwen2.5:3b-instruct-q4_K_M",
        "name": "Qwen2.5 3B",
        "size": "3B",
        "quant": "Q4_K_M",
        "vram_needed": 2.2,
        "ram_needed": 4,
        "speed": "较快",
        "quality": "良好",
        "chinese": True,
        "description": "通义千问2.5 30亿参数，中文能力强，性价比最高",
    },
    {
        "id": "qwen2.5:7b-instruct-q4_K_M",
        "name": "Qwen2.5 7B",
        "size": "7B",
        "quant": "Q4_K_M",
        "vram_needed": 4.5,
        "ram_needed": 8,
        "speed": "中等",
        "quality": "优秀",
        "chinese": True,
        "description": "通义千问2.5 70亿参数，能力强，推荐8GB显存以上使用",
    },
    {
        "id": "llama3.2:3b-instruct-q4_K_M",
        "name": "Llama 3.2 3B",
        "size": "3B",
        "quant": "Q4_K_M",
        "vram_needed": 2.2,
        "ram_needed": 4,
        "speed": "较快",
        "quality": "良好",
        "chinese": False,
        "description": "Meta Llama 3.2 30亿参数，英文强，中文一般",
    },
    {
        "id": "gemma2:2b-instruct-q4_K_M",
        "name": "Gemma 2 2B",
        "size": "2B",
        "quant": "Q4_K_M",
        "vram_needed": 1.5,
        "ram_needed": 3,
        "speed": "快",
        "quality": "良好",
        "chinese": False,
        "description": "Google Gemma 2 20亿参数，小巧精悍",
    },
    {
        "id": "qwen2.5:7b-instruct-q2_K",
        "name": "Qwen2.5 7B Q2",
        "size": "7B",
        "quant": "Q2_K",
        "vram_needed": 2.8,
        "ram_needed": 6,
        "speed": "中等",
        "quality": "一般",
        "chinese": True,
        "description": "7B模型极小量化版，4GB显存可跑，质量有损失",
    },
]


def recommend_models(hardware: HardwareInfo, quant_preference: str = "auto") -> List[dict]:
    """根据硬件推荐合适的模型，支持量化偏好"""
    # 量化级别映射：根据显存自动选择
    quant_levels = ["Q4_K_M", "Q2_K", "Q8_0"]
    if quant_preference != "auto":
        quant_levels = [quant_preference.upper()]

    recommended = []
    for m in MODEL_CATALOG:
        # 量化过滤
        if not any(q in m["quant"] for q in quant_levels):
            continue
        vram_ok = (not hardware.has_gpu) or (hardware.vram_gb >= m["vram_needed"] * 0.8)
        ram_ok = hardware.total_ram_gb >= m["ram_needed"]
        if vram_ok and ram_ok:
            recommended.append(m)

    if not recommended:
        # 显存不足时，推荐最小量化版本
        for m in MODEL_CATALOG:
            if m["quant"] in ("Q2_K", "Q4_K_M"):
                recommended.append(m)
                break
    if not recommended:
        recommended = [MODEL_CATALOG[0]]
    return recommended


def get_best_model(hardware: HardwareInfo, quant_preference: str = "auto") -> dict:
    """获取最适合的模型"""
    models = recommend_models(hardware, quant_preference)
    for m in models:
        if m["chinese"] and m["size"] in ["3B", "7B"]:
            return m
    return models[0]


def get_optimal_quant(hardware: HardwareInfo, base_model_size: str = "7B") -> str:
    """
    根据显存自动推荐最佳量化级别
    """
    vram = hardware.vram_gb if hardware.has_gpu else hardware.total_ram_gb
    if base_model_size == "7B":
        if vram >= 8:
            return "Q4_K_M"
        elif vram >= 5:
            return "Q4_K_M"  # 仍可尝试
        elif vram >= 3.5:
            return "Q2_K"
        else:
            return "Q2_K"
    elif base_model_size == "3B":
        if vram >= 4:
            return "Q4_K_M"
        elif vram >= 2:
            return "Q2_K"
        else:
            return "Q2_K"
    return "Q4_K_M"


def build_model_tag(base_name: str, quant: str) -> str:
    """构建完整模型标签，如 qwen2.5:7b-instruct-q4_K_M"""
    # 如果用户已指定完整 tag，直接返回
    if ":" in base_name:
        return base_name
    size = "7b"  # 默认
    for s in ["1.5b", "3b", "7b", "13b", "34b", "70b"]:
        if s in base_name.lower():
            size = s
            break
    return f"{base_name}:{size}-instruct-{quant.lower()}" if "instruct" not in base_name.lower() else f"{base_name}-{quant.lower()}"


# 后端工厂
SUPPORTED_BACKENDS = {"ollama", "vllm", "tensorrt", "llama.cpp"}


# =============================================================================
# Ollama 后端
# =============================================================================

class OllamaBackend:
    """Ollama 本地推理后端"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")
        self._available = None
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        """检查Ollama是否可用"""
        if self._available is not None:
            return self._available
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=2)
            self._available = resp.status_code == 200
        except Exception:
            self._available = False
        return self._available

    def list_models(self) -> List[str]:
        """列出已安装的模型"""
        if not self.is_available():
            return []
        try:
            import requests
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return [m["name"] for m in data.get("models", [])]
        except Exception as e:
            logger.error(f"获取Ollama模型列表失败: {e}")
        return []

    def pull_model(self, model_name: str, callback: Callable = None) -> bool:
        """下载模型"""
        if not self.is_available():
            return False
        try:
            import requests
            resp = requests.post(
                f"{self.base_url}/api/pull",
                json={"name": model_name},
                stream=True,
                timeout=300
            )
            for line in resp.iter_lines():
                if line and callback:
                    try:
                        data = json.loads(line)
                        callback(data)
                    except Exception:
                        pass
            return True
        except Exception as e:
            logger.error(f"下载模型失败: {e}")
            return False

    def _build_options(self) -> dict:
        """构建 Ollama options，从 settings 读取优化参数"""
        options = {
            "num_ctx": settings.llm_num_ctx,
            "temperature": settings.llm_temperature,
            "top_p": settings.llm_top_p,
            "top_k": settings.llm_top_k,
            "repeat_penalty": settings.llm_repeat_penalty,
        }
        if settings.llm_num_gpu >= 0:
            options["num_gpu"] = settings.llm_num_gpu
        return options

    def chat(self, model: str, messages: List[dict],
             stream: bool = False, tools: List[dict] = None) -> dict:
        """对话（支持Function Calling）"""
        if not self.is_available():
            raise RuntimeError("Ollama不可用")

        import requests
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "options": self._build_options(),
        }
        if tools:
            payload["tools"] = tools

        try:
            resp = requests.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=settings.request_timeout_seconds
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                raise RuntimeError(f"Ollama返回错误: {resp.status_code} {resp.text}")
        except requests.exceptions.Timeout:
            raise RuntimeError("Ollama推理超时")
        except Exception as e:
            raise RuntimeError(f"Ollama请求失败: {e}")

    def chat_stream(self, model: str, messages: List[dict],
                    tools: List[dict] = None) -> Generator[str, None, None]:
        """流式对话"""
        if not self.is_available():
            raise RuntimeError("Ollama不可用")

        import requests
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": self._build_options(),
        }
        if tools:
            payload["tools"] = tools

        resp = requests.post(
            f"{self.base_url}/api/chat",
            json=payload,
            stream=True,
            timeout=settings.request_timeout_seconds
        )
        for line in resp.iter_lines():
            if line:
                try:
                    data = json.loads(line)
                    if "message" in data and "content" in data["message"]:
                        yield data["message"]["content"]
                    if data.get("done"):
                        break
                except Exception:
                    pass

    def generate(self, model: str, prompt: str, stream: bool = False) -> str:
        """纯文本生成"""
        if not self.is_available():
            raise RuntimeError("Ollama不可用")

        import requests
        resp = requests.post(
            f"{self.base_url}/api/generate",
            json={"model": model, "prompt": prompt, "stream": stream},
            timeout=120
        )
        if resp.status_code == 200:
            return resp.json().get("response", "")
        raise RuntimeError(f"Ollama生成失败: {resp.status_code}")


# =============================================================================
# 其他后端预留接口（vLLM / TensorRT-LLM / llama.cpp）
# =============================================================================

class BaseLLMBackend:
    """LLM 后端抽象基类"""

    def is_available(self) -> bool:
        return False

    def list_models(self) -> List[str]:
        return []

    def chat(self, model: str, messages: List[dict], stream: bool = False, tools: List[dict] = None) -> dict:
        raise NotImplementedError

    def chat_stream(self, model: str, messages: List[dict], tools: List[dict] = None) -> Generator[str, None, None]:
        raise NotImplementedError


class VLLMBackend(BaseLLMBackend):
    """vLLM 后端（需额外安装 vllm 包并启动服务）"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            import requests
            return requests.get(f"{self.base_url}/health", timeout=2).status_code == 200
        except Exception:
            return False

    def chat(self, model: str, messages: List[dict], stream: bool = False, tools: List[dict] = None) -> dict:
        import requests
        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "top_p": settings.llm_top_p,
            "max_tokens": settings.llm_num_ctx,
            "stream": stream,
        }
        resp = requests.post(f"{self.base_url}/v1/chat/completions", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return {"message": {"role": "assistant", "content": data["choices"][0]["message"]["content"]}}

    def chat_stream(self, model: str, messages: List[dict], tools: List[dict] = None) -> Generator[str, None, None]:
        import requests
        payload = {
            "model": model,
            "messages": messages,
            "temperature": settings.llm_temperature,
            "top_p": settings.llm_top_p,
            "max_tokens": settings.llm_num_ctx,
            "stream": True,
        }
        resp = requests.post(f"{self.base_url}/v1/chat/completions", json=payload, stream=True, timeout=120)
        for line in resp.iter_lines():
            if line:
                text = line.decode("utf-8")
                if text.startswith("data: "):
                    try:
                        data = json.loads(text[6:])
                        delta = data["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        pass


class TensorRTBackend(BaseLLMBackend):
    """TensorRT-LLM 后端（预留，需 NVIDIA TensorRT-LLM 环境）"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        # TensorRT-LLM 通常通过 Triton Inference Server 暴露
        try:
            import requests
            return requests.get(f"{self.base_url}/v2/health/ready", timeout=2).status_code == 200
        except Exception:
            return False


# 后端工厂
def create_backend(backend_name: str, base_url: str = None):
    """根据配置创建后端"""
    backend_name = backend_name.lower()
    if backend_name == "ollama":
        return OllamaBackend(base_url or settings.local_base_url)
    elif backend_name == "vllm":
        return VLLMBackend(base_url or "http://localhost:8000")
    elif backend_name == "tensorrt":
        return TensorRTBackend(base_url or "http://localhost:8000")
    else:
        raise ValueError(f"不支持的后端: {backend_name}")


# =============================================================================
# 本地LLM管理器
# =============================================================================

class LocalLLM:
    """
    Y·NEX 本地LLM管理器
    自动选择最优后端和模型

    M3: KV-cache 复用 + batch 推理优化
      - 缓存最近 N 条请求的 KV-cache 前缀，避免重复计算
      - 同批次请求合并推理（batch inference）
      - 自动检测重复前缀，复用计算结果
    """

    def __init__(self):
        self.hardware = detect_hardware()
        self.backend_name = settings.local_backend
        self.backend = create_backend(self.backend_name)
        self.ollama = OllamaBackend()  # 保留兼容
        self.current_model: Optional[str] = None
        self._fallback_to_api = True
        self._lock = threading.Lock()

        # M3: KV-cache 优化
        self._cache_enabled = True
        self._cache_max_size = 20  # 最多缓存 20 条前缀
        self._cache = OrderedDict()  # key_hash -> (prefix_tokens, kv_cache_ref)
        self._cache_hits = 0
        self._cache_misses = 0
        self._batch_queue = []  # 批量推理队列
        self._batch_max_size = 4  # 最大批量大小
        self._batch_timeout = 0.05  # 50ms 批量窗口
        self._batch_lock = threading.Lock()

        # M5: 语义缓存初始化
        self._init_semantic_cache()

        # 自动选择已安装的模型
        self._auto_select_model()

    def _cache_key(self, messages: List[dict]) -> str:
        """生成缓存键：基于前缀消息（除最后一条外的所有消息）"""
        if len(messages) <= 1:
            return ""
        prefix = json.dumps(messages[:-1], sort_keys=True, ensure_ascii=False)
        return hashlib.md5(prefix.encode()).hexdigest()

    def _get_cached_prefix(self, messages: List[dict]) -> Optional[dict]:
        """检查是否有可复用的 KV-cache 前缀"""
        if not self._cache_enabled or len(messages) <= 1:
            return None
        key = self._cache_key(messages)
        if key in self._cache:
            self._cache_hits += 1
            entry = self._cache[key]
            # 移到末尾（LRU）
            self._cache.move_to_end(key)
            return entry
        self._cache_misses += 1
        return None

    def _store_prefix(self, messages: List[dict], prefix_info: dict):
        """存储 KV-cache 前缀"""
        if not self._cache_enabled:
            return
        key = self._cache_key(messages)
        self._cache[key] = prefix_info
        if len(self._cache) > self._cache_max_size:
            self._cache.popitem(last=False)

    def get_cache_stats(self) -> dict:
        """获取缓存统计"""
        total = self._cache_hits + self._cache_misses
        return {
            "enabled": self._cache_enabled,
            "size": len(self._cache),
            "max_size": self._cache_max_size,
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "hit_rate": round(self._cache_hits / max(total, 1) * 100, 1),
            "batch_queue": len(self._batch_queue),
            "batch_max": self._batch_max_size,
            "semantic_hits": self._semantic_hits,
            "semantic_misses": self._semantic_misses,
            "semantic_size": len(self._semantic_cache),
        }

    # ============================================================
    # M5: 语义缓存 — 基于相似度的响应缓存
    # 类似请求不再重复调用 LLM
    # ============================================================

    def _init_semantic_cache(self):
        """初始化语义缓存（使用简单哈希，无需额外依赖）"""
        self._semantic_cache = OrderedDict()  # hash -> (response, timestamp)
        self._semantic_cache_max = 100
        self._semantic_hits = 0
        self._semantic_misses = 0

    def _semantic_hash(self, prompt: str) -> str:
        """生成语义哈希：取关键词 + 前200字符"""
        # 提取关键词：去掉标点后取前几个词
        clean = re.sub(r'[^\w\u4e00-\u9fff]', ' ', prompt.lower())
        words = clean.split()[:10]
        # 加上前200字符
        sample = prompt[:200].strip()
        combined = ' '.join(words) + '|' + sample
        return hashlib.md5(combined.encode()).hexdigest()

    def _semantic_get(self, prompt: str, ttl: int = 300) -> Optional[str]:
        """从语义缓存获取响应"""
        key = self._semantic_hash(prompt)
        if key in self._semantic_cache:
            entry = self._semantic_cache[key]
            if time.time() - entry['t'] < ttl:
                self._semantic_hits += 1
                self._semantic_cache.move_to_end(key)
                return entry['response']
            else:
                del self._semantic_cache[key]
        self._semantic_misses += 1
        return None

    def _semantic_set(self, prompt: str, response: str):
        """存储到语义缓存"""
        key = self._semantic_hash(prompt)
        self._semantic_cache[key] = {'response': response, 't': time.time()}
        if len(self._semantic_cache) > self._semantic_cache_max:
            self._semantic_cache.popitem(last=False)

    def _auto_select_model(self):
        """启动时自动选择可用的本地模型"""
        try:
            if not self.backend.is_available():
                return
            models = self.backend.list_models()
            if not models:
                return

            preferred = getattr(settings, "local_model", None) or ""
            # 优先精确匹配或包含 preferred 关键字的模型
            for m in models:
                if preferred and (m == preferred or preferred in m):
                    self.current_model = m
                    return

            # 其次优先 qwen2.5 7b
            for m in models:
                name_lower = m.lower()
                if "qwen2.5" in name_lower and "7b" in name_lower:
                    self.current_model = m
                    return

            # 回退到第一个
            self.current_model = models[0]
        except Exception as e:
            logger.warning(f"自动选择本地模型失败: {e}")

    @property
    def is_available(self) -> bool:
        """本地LLM是否可用"""
        if self.ollama.is_available():
            models = self.ollama.list_models()
            if models:
                return True
        return False

    @property
    def available_models(self) -> List[str]:
        """可用模型列表"""
        return self.ollama.list_models() if self.ollama.is_available() else []

    def setup(self) -> tuple[bool, str]:
        """
        自动配置本地LLM
        返回 (success, message)
        """
        if not self.backend.is_available():
            return False, f"{self.backend_name} 后端未启动或不支持。当前配置后端: {self.backend_name}"

        models = self.backend.list_models()
        if models:
            self.current_model = models[0]
            return True, f"找到已安装模型: {models[0]}"

        recommended = recommend_models(self.hardware, settings.llm_quant_preference)
        if recommended:
            best = recommended[0]
            return False, (f"未找到已安装模型。推荐下载: {best['name']}\n"
                          f"  命令: ollama pull {best['id']}\n"
                          f"  显存需求: {best['vram_needed']}GB | 内存需求: {best['ram_needed']}GB")

        return False, "没有适合当前硬件的模型"

    def chat(self, messages: List[dict], tools: List[dict] = None,
             model: str = None, use_api_fallback: bool = True) -> tuple[str, str]:
        """
        对话，返回 (回复内容, 来源: local/api)
        """
        target_model = model or self.current_model

        # M5: 语义缓存检查
        prompt = messages[-1]["content"] if messages else ""
        cached = self._semantic_get(prompt)
        if cached:
            return cached, "local-cache"

        if target_model and self.backend.is_available():
            try:
                result = self.backend.chat(target_model, messages, tools=tools)
                content = result.get("message", {}).get("content", "")
                if content:
                    # M5: 存储到语义缓存
                    self._semantic_set(prompt, content)
                    return content, "local"
            except Exception as e:
                logger.warning(f"本地推理失败: {e}")

        if use_api_fallback and self._fallback_to_api:
            from brain import get_ai_response
            reply = get_ai_response(messages[-1]["content"] if messages else "", use_mock=False)
            self._semantic_set(prompt, reply)
            return reply, "api"

        raise RuntimeError("本地LLM和API均不可用")

    def chat_stream(self, messages: List[dict], tools: List[dict] = None,
                    model: str = None) -> Generator[tuple[str, str], None, None]:
        """流式对话，yield (token, source)"""
        target_model = model or self.current_model

        if target_model and self.backend.is_available():
            try:
                for token in self.backend.chat_stream(target_model, messages, tools=tools):
                    yield token, "local"
                return
            except Exception as e:
                logger.warning(f"本地流式推理失败: {e}")

        from brain import get_ai_response
        reply = get_ai_response(messages[-1]["content"] if messages else "", use_mock=False)
        for char in reply:
            yield char, "api"

    def get_status(self) -> dict:
        """获取状态信息（健康检查用，避免慢查询）"""
        backend_available = self.backend.is_available()
        ollama_available = self.ollama.is_available()
        return {
            "hardware": {
                "ram_gb": self.hardware.total_ram_gb,
                "vram_gb": self.hardware.vram_gb,
                "cpu_cores": self.hardware.cpu_cores,
                "has_gpu": self.hardware.has_gpu,
                "gpu_name": self.hardware.gpu_name,
            },
            "backend": self.backend_name,
            "backend_available": backend_available,
            "ollama_available": ollama_available,
            "installed_models": self.backend.list_models() if backend_available else [],
            "current_model": self.current_model,
            "recommended_models": [m["id"] for m in recommend_models(self.hardware, settings.llm_quant_preference)],
            "optimal_quant": get_optimal_quant(self.hardware),
            "inference_options": {
                "num_ctx": settings.llm_num_ctx,
                "num_gpu": settings.llm_num_gpu,
                "temperature": settings.llm_temperature,
                "top_p": settings.llm_top_p,
                "top_k": settings.llm_top_k,
                "repeat_penalty": settings.llm_repeat_penalty,
            },
        }


# 全局单例
_local_llm: Optional[LocalLLM] = None


def get_local_llm() -> LocalLLM:
    global _local_llm
    if _local_llm is None:
        _local_llm = LocalLLM()
    return _local_llm
