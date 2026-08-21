# 引擎类说明

> 本文档汇总AI引擎层的所有引擎类定义与关键方法。

---

## 一、引擎层架构

```
BaseEngine (抽象基类)
├── ImageGenEngine          图像生成引擎
├── CharacterConsistencyEngine  角色一致性引擎
├── SceneGenEngine          场景生成引擎
├── TTSEngine               语音合成引擎
│   ├── EdgeTTSEngine       Edge-TTS实现
│   └── VITSEngine          VITS本地实现
├── LayoutEngine            分镜布局引擎
├── VideoComposer           视频合成引擎
├── AudioMixer              音频混合引擎
├── WorkflowEngine          工作流引擎
└── LoRATrainer             LoRA训练器
```

---

## 二、BaseEngine 基类

```python
# backend/app/engines/base_engine.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import torch

class BaseEngine(ABC):
    """AI引擎基类"""
    
    def __init__(self, model_path: str = None, device: str = "cuda"):
        self.model_path = model_path
        self.device = device
        self.model = None
        self._loaded = False
    
    async def load_model(self) -> None:
        """加载模型"""
        if self._loaded:
            return
        self.model = await self._load_model_impl()
        if self.model:
            self.model.to(self.device)
        self._loaded = True
    
    @abstractmethod
    async def _load_model_impl(self):
        """子类实现具体加载逻辑"""
        pass
    
    @abstractmethod
    async def infer(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行推理"""
        pass
    
    async def unload_model(self) -> None:
        """卸载模型"""
        if self.model:
            del self.model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            self._loaded = False
```

---

## 三、图像生成引擎

### 3.1 ImageGenEngine

```python
# backend/app/engines/image_gen_engine.py - 详见AI引擎文档

class ImageGenEngine:
    """
    图像生成引擎
    
    核心能力：
    - text2img: 文生图
    - img2img: 图生图  
    - inpaint: 局部重绘
    - generate_with_controlnet: ControlNet引导
    - load_lora: LoRA模型加载
    """
    
    MODEL_CONFIGS = {
        'sd15': {'class': StableDiffusionPipeline, 'path': 'models/sd15'},
        'sdxl': {'class': StableDiffusionXLPipeline, 'path': 'models/sdxl'},
        'sdxl_lightning': {'class': StableDiffusionXLPipeline, 'path': 'models/sdxl_lightning'}
    }
    
    async def load_model(self, model_name: str = "sdxl", optimization: bool = True):
        """加载基础模型"""
    
    async def generate(self, prompt: str, negative_prompt: str = "",
                       width: int = 1024, height: int = 1024,
                       num_inference_steps: int = 30, guidance_scale: float = 7.5,
                       seed: int = None, batch_size: int = 1, **kwargs) -> bytes:
        """文生图"""
    
    async def img2img(self, init_image, prompt: str, strength: float = 0.6,
                      num_inference_steps: int = 30, **kwargs) -> bytes:
        """图生图"""
    
    async def inpaint(self, init_image, mask_image, prompt: str, **kwargs) -> bytes:
        """局部重绘"""
    
    async def generate_with_controlnet(self, prompt: str, controlnet_type: str,
                                       controlnet_image, controlnet_weight: float = 1.0,
                                       **kwargs) -> bytes:
        """ControlNet引导生成"""
    
    def load_lora(self, lora_path: str, weight: float = 0.8):
        """加载LoRA"""
    
    def unload_lora(self):
        """卸载LoRA"""
```

---

## 四、角色一致性引擎

### 4.1 CharacterConsistencyEngine

```python
# backend/app/engines/character_consistency_engine.py - 详见AI引擎文档

class CharacterConsistencyEngine:
    """
    角色一致性引擎
    
    技术栈：IP-Adapter + LoRA + Reference
    """
    
    async def initialize(self):
        """初始化（加载CLIP和IP-Adapter）"""
    
    async def extract_features(self, image: bytes) -> np.ndarray:
        """提取512维特征向量"""
    
    async def generate_consistent(self, character: dict, prompt: str,
                                   scene_context: dict = None,
                                   consistency_weight: float = 0.8) -> bytes:
        """生成保持角色一致性的画面"""
    
    async def generate_multi_character(self, characters: list,
                                        scene_prompt: str,
                                        layout: dict = None) -> bytes:
        """多角色场景生成"""
    
    def _enhance_prompt(self, prompt: str, character: dict,
                        scene_context: dict = None) -> str:
        """增强提示词"""
```

### 4.2 LoRATrainer

```python
# backend/app/engines/lora_trainer.py - 详见AI引擎文档

class LoRATrainer:
    """LoRA训练器"""
    
    async def train_character_lora(self, character_id: str, character_name: str,
                                    training_images: list, config: dict = None) -> dict:
        """训练角色LoRA"""
    
    def _default_config(self) -> dict:
        """默认训练配置"""
    
    async def _prepare_dataset(self, character_id: str, character_name: str,
                                image_urls: list) -> Path:
        """准备训练数据"""
    
    async def _auto_caption(self, dataset_dir: Path, character_name: str) -> list:
        """自动标注"""
    
    async def _execute_training(self, dataset_dir, captions, character_name, config) -> str:
        """执行训练"""
    
    async def _validate_lora(self, lora_path: str, character_name: str,
                              reference_image: str) -> float:
        """验证LoRA质量"""
```

---

## 五、场景生成引擎

### 5.1 SceneGenEngine

```python
# backend/app/engines/scene_gen_engine.py - 详见场景模块文档

class SceneGenEngine:
    """
    场景生成引擎
    
    特色：透视线控制、深度图引导
    """
    
    async def generate_with_perspective(self, prompt: str,
                                         perspective_type: str = 'one_point',
                                         perspective_image: bytes = None) -> bytes:
        """使用透视控制生成场景"""
    
    async def generate_with_depth(self, prompt: str,
                                   depth_map: bytes = None) -> bytes:
        """使用深度图引导生成"""
    
    async def _generate_perspective_lines(self, perspective_type: str) -> bytes:
        """生成透视线参考图"""
```

---

## 六、语音合成引擎

### 6.1 ITTSEngine 接口

```python
# backend/app/engines/tts_engine.py - 详见配音模块文档

class ITTSEngine(ABC):
    """TTS引擎抽象接口"""
    
    @abstractmethod
    async def synthesize(self, text: str, voice_id: str, rate: int = 0,
                         pitch: int = 0, volume: int = 100) -> bytes:
        """语音合成"""
    
    @abstractmethod
    async def get_voices(self, language: str = "zh-CN") -> list:
        """获取可用音色"""
```

### 6.2 EdgeTTSEngine

```python
class EdgeTTSEngine(ITTSEngine):
    """Edge-TTS引擎（免费）"""
    
    VOICE_MAP = {
        'female_gentle': 'zh-CN-XiaoxiaoNeural',
        'female_bright': 'zh-CN-XiaoyiNeural',
        'male_gentle': 'zh-CN-YunxiNeural',
        'male_deep': 'zh-CN-YunyangNeural',
    }
    
    async def synthesize(self, text: str, voice_id: str = "zh-CN-XiaoxiaoNeural",
                         rate: int = 0, pitch: int = 0, volume: int = 100) -> bytes:
        """合成语音"""
    
    async def synthesize_with_timestamps(self, text: str, voice_id: str,
                                          **kwargs) -> dict:
        """合成语音并返回时间戳（用于字幕）"""
```

---

## 七、视频合成引擎

### 7.1 VideoComposer

```python
# backend/app/engines/video_engine.py - 详见渲染模块文档

class VideoComposer:
    """视频合成引擎"""
    
    async def compose_video(self, frames: list, audio_tracks: list,
                             config: dict, output_path: str) -> dict:
        """合成最终视频"""
    
    async def _frames_to_video_with_transitions(self, frames: list, config: dict) -> str:
        """帧序列转视频（含转场）"""
    
    async def _mix_audio_tracks(self, tracks: list, frames: list) -> str:
        """混合音频"""
    
    async def _merge_audio_video(self, video_path: str, audio_path: str) -> str:
        """合并音视频"""
    
    async def _add_subtitle(self, video_path: str, subtitle_path: str) -> str:
        """添加字幕"""
    
    async def _add_watermark(self, video_path: str, text: str, position: str) -> str:
        """添加水印"""
    
    def _final_encode(self, input_path: str, output_path: str, config: dict):
        """最终编码"""
    
    async def export_gif(self, video_path: str, output_path: str,
                          fps: int = 15, width: int = 480) -> str:
        """导出GIF"""
```

### 7.2 AudioMixer

```python
# backend/app/engines/audio_mixer.py - 详见配音模块文档

class AudioMixer:
    """音频混合引擎"""
    
    @staticmethod
    def mix_tracks(tracks: list, output_format: str = "wav") -> bytes:
        """混合多个音频轨道"""
    
    @staticmethod
    def add_background_music(voice_audio: bytes, bgm_audio: bytes,
                              bgm_volume: float = 0.3) -> bytes:
        """添加背景音乐"""
```

---

## 八、工作流引擎

### 8.1 WorkflowEngine

```python
# backend/app/engines/workflow/workflow_engine.py - 详见工作流引擎文档

class WorkflowEngine:
    """工作流执行引擎"""
    
    async def execute_workflow(self, workflow_data: dict,
                                inputs: dict = None) -> dict:
        """执行工作流"""
    
    def register_node(self, node_type: str, node_class: type):
        """注册节点类型"""
    
    def _parse_workflow(self, workflow_data: dict) -> WorkflowGraph:
        """解析工作流"""
    
    def _topological_sort(self, graph: WorkflowGraph) -> list:
        """拓扑排序，返回执行层级"""
    
    async def _execute_node(self, graph, node_id, execution, external_inputs):
        """执行单个节点"""
```

### 8.2 BaseNode 节点基类

```python
# backend/app/engines/workflow/node_base.py - 详见工作流引擎文档

class BaseNode(ABC):
    """节点基类"""
    
    @abstractmethod
    async def execute(self, inputs: dict) -> dict:
        """执行节点逻辑"""
    
    @classmethod
    @abstractmethod
    def get_definition(cls) -> NodeDefinition:
        """获取节点定义"""
```

### 8.3 内置节点

| 节点类 | 类型 | 功能 |
|--------|------|------|
| TextToImageNode | text_to_image | 文生图 |
| CharacterGenNode | character_gen | 角色生成（带一致性） |
| ImageToImageNode | img2img | 图生图 |
| TextConcatNode | text_concat | 文本拼接 |
| ImagePreviewNode | image_preview | 图像预览 |
| VideoOutputNode | video_output | 视频输出 |

---

## 九、优化器类

### 9.1 InferenceOptimizer 推理优化器

```python
# backend/app/engines/optimization.py - 详见AI引擎文档

class InferenceOptimizer:
    """推理优化器"""
    
    @staticmethod
    def optimize_pipeline(pipe: StableDiffusionPipeline) -> StableDiffusionPipeline:
        """优化SD Pipeline（半精度+xformers+offload+DPM++）"""
    
    @staticmethod
    def enable_attention_slicing(pipe):
        """注意力切片"""
    
    @staticmethod
    def enable_vae_slicing(pipe):
        """VAE切片"""
```

### 9.2 ConsistencyEvaluator 一致性评估器

```python
# backend/app/engines/consistency_evaluator.py - 详见AI引擎文档

class ConsistencyEvaluator:
    """角色一致性评估器"""
    
    @staticmethod
    def evaluate(reference_image: bytes, generated_image: bytes,
                 clip_model=None) -> dict:
        """评估一致性，返回总体/面部/风格/特征相似度"""
```

---

## 十、模型管理类

### 10.1 ModelManager 模型管理器

```python
# backend/app/core/model_manager.py - 详见AI引擎文档

class ModelManager:
    """模型管理器"""
    
    def list_models(self, model_type: str = None) -> list:
        """列出所有可用模型"""
    
    def get_model_path(self, model_name: str) -> str:
        """获取模型路径"""
```

### 10.2 StorageManager 存储管理器

```python
# backend/app/core/storage.py

class StorageManager:
    """对象存储管理器"""
    
    async def upload_image(self, bucket: str, object_name: str,
                            image_data: bytes, content_type: str = "image/png") -> str:
        """上传图片"""
    
    async def get_presigned_url(self, bucket: str, object_name: str,
                                 expires: int = 3600) -> str:
        """获取预签名URL"""
```

### 10.3 RedisManager Redis管理器

```python
# backend/app/core/redis.py

class RedisManager:
    """Redis连接管理器"""
    
    async def cache_json(self, key: str, value: dict, ttl: int = 3600):
        """缓存JSON数据"""
    
    async def get_cached_json(self, key: str) -> dict | None:
        """获取缓存的JSON数据"""
```

---

*本文档最后更新：2026-07-18*
