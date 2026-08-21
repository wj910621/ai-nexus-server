# 图像生成引擎

> 本文档详细说明图像生成引擎的架构设计、模型集成、推理优化与接口定义。

---

## 一、引擎概述

### 1.1 功能定位
图像生成引擎是漫剧生成的核心AI能力，负责将文本描述转化为高质量的画面。基于Stable Diffusion生态，集成多种模型和ControlNet，支持文生图、图生图、局部重绘等能力。

### 1.2 支持的模型

| 模型 | 版本 | 适用场景 | 显存需求 |
|------|------|----------|----------|
| Stable Diffusion | 1.5 | 通用动漫风格 | 4GB+ |
| Stable Diffusion XL | 1.0 | 高质量通用 | 8GB+ |
| SDXL Lightning | - | 快速生成 | 8GB+ |
| Anything V5 | - | 二次元动漫 | 4GB+ |
| Flat-2D | - | 扁平卡通 | 4GB+ |
| Realistic Vision | - | 写实风格 | 4GB+ |

---

## 二、引擎架构

```python
# backend/app/engines/image_gen_engine.py
from typing import Optional, List, Union, Dict, Any
from pathlib import Path
import torch
from diffusers import (
    StableDiffusionPipeline,
    StableDiffusionXLPipeline,
    DPMSolverMultistepScheduler,
    EulerAncestralDiscreteScheduler,
    ControlNetModel,
    StableDiffusionControlNetPipeline
)
from PIL import Image
from io import BytesIO
import numpy as np

class ImageGenEngine:
    """
    图像生成引擎
    
    核心能力：
    - 文生图（text2img）：文本描述生成图像
    - 图生图（img2img）：基于参考图修改
    - 局部重绘（inpaint）：指定区域重绘
    - ControlNet引导：多种条件控制
    - LoRA加载：风格/角色微调模型
    """
    
    # 支持的模型配置
    MODEL_CONFIGS = {
        'sd15': {
            'class': StableDiffusionPipeline,
            'path': 'models/sd15',
            'resolution': (512, 512),
        },
        'sdxl': {
            'class': StableDiffusionXLPipeline,
            'path': 'models/sdxl',
            'resolution': (1024, 1024),
        },
        'sdxl_lightning': {
            'class': StableDiffusionXLPipeline,
            'path': 'models/sdxl_lightning',
            'resolution': (1024, 1024),
        }
    }
    
    def __init__(self, device: str = "cuda"):
        self.device = device
        self.pipe: Optional[StableDiffusionPipeline] = None
        self.current_model: Optional[str] = None
        self.controlnets: Dict[str, ControlNetModel] = {}
        self.loaded_loras: List[dict] = []
    
    async def load_model(
        self,
        model_name: str = "sdxl",
        optimization: bool = True
    ) -> None:
        """
        加载基础模型
        
        Args:
            model_name: 模型名称
            optimization: 是否启用优化（半精度、xformers等）
        """
        if self.current_model == model_name and self.pipe:
            return  # 已加载
        
        config = self.MODEL_CONFIGS.get(model_name)
        if not config:
            raise ValueError(f"不支持的模型: {model_name}")
        
        # 卸载当前模型
        if self.pipe:
            del self.pipe
            torch.cuda.empty_cache()
        
        # 加载新模型
        self.pipe = config['class'].from_pretrained(
            config['path'],
            torch_dtype=torch.float16 if optimization else torch.float32,
            safety_checker=None,  # 禁用安全检查器（自部署）
            requires_safety_checker=False
        )
        
        if optimization:
            self._apply_optimizations()
        
        self.current_model = model_name
    
    def _apply_optimizations(self):
        """应用推理优化"""
        # 1. 移到GPU
        self.pipe = self.pipe.to(self.device)
        
        # 2. 启用xformers内存高效注意力
        try:
            self.pipe.enable_xformers_memory_efficient_attention()
        except ImportError:
            pass  # xformers未安装，跳过
        
        # 3. 启用CPU offload（显存不足时）
        self.pipe.enable_model_cpu_offload()
        
        # 4. 使用DPM++求解器（快速且高质量）
        self.pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            self.pipe.scheduler.config,
            use_karras_sigmas=True,
            algorithm_type="dpmsolver++"
        )
        
        # 5. VAE切片（批量生成节省显存）
        self.pipe.enable_vae_slicing()
    
    async def generate(
        self,
        prompt: str,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        batch_size: int = 1,
        **kwargs
    ) -> bytes:
        """
        文生图：文本生成图像
        
        Args:
            prompt: 正向提示词
            negative_prompt: 负面提示词
            width: 图像宽度
            height: 图像高度
            num_inference_steps: 推理步数（20-50）
            guidance_scale: 引导强度（1-20）
            seed: 随机种子（None为随机）
            batch_size: 批量生成数量
        
        Returns:
            PNG格式图像字节
        """
        # 确保模型已加载
        if not self.pipe:
            await self.load_model("sdxl")
        
        # 设置随机种子
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        
        # 生成图像
        result = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            num_images_per_prompt=batch_size,
            generator=generator,
            **kwargs
        )
        
        # 转为PNG字节
        image = result.images[0]
        return self._image_to_bytes(image)
    
    async def img2img(
        self,
        init_image: Union[bytes, str, Image.Image],
        prompt: str,
        negative_prompt: str = "",
        strength: float = 0.6,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        seed: Optional[int] = None,
        **kwargs
    ) -> bytes:
        """
        图生图：基于参考图修改
        
        Args:
            init_image: 初始图像（字节/URL/PIL.Image）
            prompt: 修改提示词
            strength: 修改强度（0-1），越高越偏离原图
        """
        if not self.pipe:
            await self.load_model()
        
        # 加载初始图像
        image = await self._load_image(init_image)
        
        generator = None
        if seed is not None:
            generator = torch.Generator(device=self.device).manual_seed(seed)
        
        result = self.pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=image,
            strength=strength,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            generator=generator,
            **kwargs
        )
        
        return self._image_to_bytes(result.images[0])
    
    async def inpaint(
        self,
        init_image: Union[bytes, str],
        mask_image: Union[bytes, str],
        prompt: str,
        negative_prompt: str = "",
        strength: float = 1.0,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
    ) -> bytes:
        """
        局部重绘：指定区域重新生成
        
        Args:
            init_image: 原始图像
            mask_image: 蒙版图（白色区域为重绘区域）
            prompt: 重绘提示词
        """
        from diffusers import StableDiffusionInpaintPipeline
        
        # 加载inpaint专用pipeline
        inpaint_pipe = StableDiffusionInpaintPipeline.from_pretrained(
            "models/sd15-inpaint",
            torch_dtype=torch.float16
        ).to(self.device)
        
        image = await self._load_image(init_image)
        mask = await self._load_image(mask_image)
        
        result = inpaint_pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=image,
            mask_image=mask,
            strength=strength,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
        )
        
        return self._image_to_bytes(result.images[0])
    
    async def generate_with_controlnet(
        self,
        prompt: str,
        controlnet_type: str,
        controlnet_image: Union[bytes, str, Image.Image],
        controlnet_weight: float = 1.0,
        negative_prompt: str = "",
        width: int = 512,
        height: int = 512,
        num_inference_steps: int = 30,
        guidance_scale: float = 7.5,
        **kwargs
    ) -> bytes:
        """
        ControlNet引导生成
        
        Args:
            controlnet_type: 控制类型
                - canny: 边缘检测
                - depth: 深度图
                - openpose: 姿势检测
                - mlsd: 线段检测（建筑）
                - scribble: 涂鸦
                - reference: 参考图
            controlnet_image: 控制条件图像
            controlnet_weight: 控制权重（0-2）
        """
        # 加载ControlNet
        controlnet = await self._load_controlnet(controlnet_type)
        
        # 创建ControlNet pipeline
        pipe = StableDiffusionControlNetPipeline.from_pretrained(
            "models/sd15",
            controlnet=controlnet,
            torch_dtype=torch.float16,
            safety_checker=None
        ).to(self.device)
        
        # 加载控制图像
        control_image = await self._load_image(controlnet_image)
        
        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt,
            image=control_image,
            width=width,
            height=height,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            controlnet_conditioning_scale=controlnet_weight,
            **kwargs
        )
        
        return self._image_to_bytes(result.images[0])
    
    async def _load_controlnet(self, controlnet_type: str) -> ControlNetModel:
        """加载ControlNet模型"""
        if controlnet_type in self.controlnets:
            return self.controlnets[controlnet_type]
        
        # ControlNet模型路径映射
        controlnet_paths = {
            'canny': 'lllyasviel/control_v11p_sd15_canny',
            'depth': 'lllyasviel/control_v11f1p_sd15_depth',
            'openpose': 'lllyasviel/control_v11p_sd15_openpose',
            'mlsd': 'lllyasviel/control_v11p_sd15_mlsd',
            'scribble': 'lllyasviel/control_v11p_sd15_scribbles',
            'normal': 'lllyasviel/control_v11p_sd15_normalbae',
            'segmentation': 'lllyasviel/control_v11p_sd15_seg',
        }
        
        path = controlnet_paths.get(controlnet_type)
        if not path:
            raise ValueError(f"不支持的ControlNet类型: {controlnet_type}")
        
        controlnet = ControlNetModel.from_pretrained(
            path,
            torch_dtype=torch.float16
        )
        
        self.controlnets[controlnet_type] = controlnet
        return controlnet
    
    def load_lora(self, lora_path: str, weight: float = 0.8) -> None:
        """
        加载LoRA模型
        
        Args:
            lora_path: LoRA模型路径
            weight: LoRA权重（0-1）
        """
        self.pipe.load_lora_weights(lora_path)
        self.pipe.fuse_lora(lora_scale=weight)
        
        self.loaded_loras.append({
            'path': lora_path,
            'weight': weight
        })
    
    def unload_lora(self) -> None:
        """卸载LoRA模型"""
        if self.loaded_loras:
            self.pipe.unfuse_lora()
            self.pipe.unload_lora_weights()
            self.loaded_loras.clear()
    
    async def _load_image(self, image: Union[bytes, str, Image.Image]) -> Image.Image:
        """加载图像（支持多种输入格式）"""
        if isinstance(image, Image.Image):
            return image
        elif isinstance(image, bytes):
            return Image.open(BytesIO(image)).convert("RGB")
        elif isinstance(image, str):
            if image.startswith('http'):
                import httpx
                response = await httpx.AsyncClient().get(image)
                return Image.open(BytesIO(response.content)).convert("RGB")
            else:
                return Image.open(image).convert("RGB")
        else:
            raise ValueError(f"不支持的图像类型: {type(image)}")
    
    def _image_to_bytes(self, image: Image.Image, format: str = "PNG") -> bytes:
        """PIL图像转字节"""
        buffer = BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()
    
    def get_model_info(self) -> dict:
        """获取当前模型信息"""
        return {
            'current_model': self.current_model,
            'device': self.device,
            'loaded_loras': self.loaded_loras,
            'controlnets': list(self.controlnets.keys()),
            'gpu_memory_allocated': torch.cuda.memory_allocated() / 1024**3 if torch.cuda.is_available() else 0,
            'gpu_memory_reserved': torch.cuda.memory_reserved() / 1024**3 if torch.cuda.is_available() else 0,
        }
```

---

## 三、推理优化策略

### 3.1 显存优化

```python
class MemoryOptimizer:
    """显存优化器"""
    
    @staticmethod
    def enable_all(pipe):
        """启用所有显存优化"""
        # 1. 半精度推理
        pipe = pipe.to(torch.float16)
        
        # 2. xformers注意力
        try:
            pipe.enable_xformers_memory_efficient_attention()
        except:
            pipe.enable_attention_slicing()
        
        # 3. CPU offload
        pipe.enable_model_cpu_offload()
        
        # 4. VAE切片
        pipe.enable_vae_slicing()
        
        # 5. VAE tile（大图生成）
        try:
            pipe.enable_vae_tiling()
        except:
            pass  # 旧版本不支持
        
        return pipe
```

### 3.2 速度优化

```python
class SpeedOptimizer:
    """推理速度优化"""
    
    # 快速生成配置
    FAST_CONFIG = {
        'steps': 15,           # 减少步数
        'guidance_scale': 5.0, # 降低引导强度
        'scheduler': 'DPM++ 2M Karras',
    }
    
    # 质量生成配置
    QUALITY_CONFIG = {
        'steps': 40,
        'guidance_scale': 8.0,
        'scheduler': 'DPM++ 3M Karras',
    }
    
    @staticmethod
    def use_fast_scheduler(pipe):
        """使用快速调度器"""
        from diffusers import DPMSolverMultistepScheduler
        
        pipe.scheduler = DPMSolverMultistepScheduler.from_config(
            pipe.scheduler.config,
            algorithm_type="dpmsolver++",
            solver_order=2,
            use_karras_sigmas=True,
        )
        return pipe
```

---

## 四、模型管理

```python
# backend/app/core/model_manager.py
from pathlib import Path
from typing import Dict, List
import json

class ModelManager:
    """模型管理器：管理所有AI模型的下载、加载、切换"""
    
    def __init__(self, models_dir: str = "ai-models"):
        self.models_dir = Path(models_dir)
        self.registry: Dict[str, dict] = {}
        self._load_registry()
    
    def _load_registry(self):
        """加载模型注册表"""
        registry_path = self.models_dir / "registry.json"
        if registry_path.exists():
            with open(registry_path) as f:
                self.registry = json.load(f)
    
    def list_models(self, model_type: str = None) -> List[dict]:
        """列出所有可用模型"""
        models = []
        for name, info in self.registry.items():
            if model_type and info['type'] != model_type:
                continue
            models.append({'name': name, **info})
        return models
    
    def get_model_path(self, model_name: str) -> str:
        """获取模型路径"""
        info = self.registry.get(model_name)
        if not info:
            raise ValueError(f"模型不存在: {model_name}")
        
        path = self.models_dir / info['path']
        if not path.exists():
            raise FileNotFoundError(f"模型文件不存在: {path}")
        
        return str(path)
```

---

## 五、API封装

```python
# backend/app/api/image_gen_routes.py
from fastapi import APIRouter, UploadFile, File, Form
from app.engines.image_gen_engine import ImageGenEngine

router = APIRouter(prefix="/api/v1/image-gen", tags=["image-generation"])
engine = ImageGenEngine()

@router.post("/text2img")
async def text_to_image(
    prompt: str = Form(...),
    negative_prompt: str = Form(""),
    width: int = Form(1024),
    height: int = Form(1024),
    steps: int = Form(30),
    guidance_scale: float = Form(7.5),
    seed: int = Form(None)
):
    """文生图"""
    image = await engine.generate(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=steps,
        guidance_scale=guidance_scale,
        seed=seed
    )
    return StreamingResponse(BytesIO(image), media_type="image/png")

@router.post("/img2img")
async def image_to_image(
    init_image: UploadFile = File(...),
    prompt: str = Form(...),
    strength: float = Form(0.6),
):
    """图生图"""
    image_bytes = await init_image.read()
    result = await engine.img2img(
        init_image=image_bytes,
        prompt=prompt,
        strength=strength
    )
    return StreamingResponse(BytesIO(result), media_type="image/png")
```

---

*本文档最后更新：2026-07-18*
