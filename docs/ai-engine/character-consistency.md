# 角色一致性引擎

> 本文档详细说明角色一致性引擎的技术方案，这是漫剧生成软件的核心技术壁垒。

---

## 一、技术概述

### 1.1 行业痛点
AI生成漫画时，同一个角色在不同画面中会出现"换脸"问题——长相、发型、服装不一致，导致故事无法连贯。这是阻碍AI漫剧落地的最大技术挑战。

### 1.2 技术方案矩阵

| 技术 | 原理 | 一致性 | 灵活性 | 训练成本 | 推理速度 |
|------|------|--------|--------|----------|----------|
| **IP-Adapter** | 图像提示，面部特征迁移 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 无需训练 | 快 |
| **LoRA微调** | 低秩适应，学习角色特征 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | 需训练(15-30min) | 快 |
| **Reference** | 参考图引导生成 | ⭐⭐⭐ | ⭐⭐⭐⭐ | 无需训练 | 中 |
| **Textual Inversion** | 文本反转学习 | ⭐⭐⭐ | ⭐⭐ | 需训练(10min) | 快 |
| **FaceID** | 面部ID保持 | ⭐⭐⭐⭐⭐ | ⭐⭐ | 无需训练 | 中 |

### 1.3 我们的方案：多技术融合
采用 **IP-Adapter + LoRA + Reference** 的组合方案：
1. **IP-Adapter**：实时面部特征一致性（无需训练）
2. **LoRA**：角色专属模型，深度学习角色特征
3. **Reference**：整体风格引导，保持画风一致

---

## 二、引擎架构

```python
# backend/app/engines/character_consistency_engine.py
from typing import Optional, List, Union
import torch
import numpy as np
from PIL import Image
from io import BytesIO
from transformers import CLIPImageProcessor, CLIPVisionModel

class CharacterConsistencyEngine:
    """
    角色一致性引擎
    
    融合三种技术实现跨帧角色一致性：
    1. IP-Adapter：图像提示，面部特征迁移
    2. LoRA：角色专属微调模型
    3. Reference：参考图风格引导
    """
    
    def __init__(self, image_engine):
        self.image_engine = image_engine
        
        # CLIP模型（特征提取）
        self.clip_processor = None
        self.clip_model = None
        
        # IP-Adapter状态
        self.ip_adapter_loaded = False
        
        # 角色LoRA缓存
        self.lora_cache: dict = {}  # {character_id: lora_path}
    
    async def initialize(self):
        """初始化引擎"""
        # 加载CLIP模型
        self.clip_processor = CLIPImageProcessor.from_pretrained(
            "openai/clip-vit-base-patch32"
        )
        self.clip_model = CLIPVisionModel.from_pretrained(
            "openai/clip-vit-base-patch32"
        ).to(self.image_engine.device)
        
        # 加载IP-Adapter
        await self._load_ip_adapter()
    
    async def _load_ip_adapter(self):
        """加载IP-Adapter模型"""
        if self.ip_adapter_loaded:
            return
        
        self.image_engine.pipe.load_ip_adapter(
            "h94/IP-Adapter",
            subfolder="models",
            weight_name="ip-adapter-plus_sd15.safetensors"
        )
        self.ip_adapter_loaded = True
    
    async def extract_features(self, image: bytes) -> np.ndarray:
        """
        提取角色特征向量
        
        使用CLIP图像编码器提取512维特征向量，
        用于：
        - 角色相似度检索
        - 去重检测
        - 角色推荐
        
        Args:
            image: 角色图像字节
        
        Returns:
            512维特征向量
        """
        image_pil = Image.open(BytesIO(image)).convert("RGB")
        
        inputs = self.clip_processor(images=image_pil, return_tensors="pt")
        inputs = {k: v.to(self.image_engine.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.clip_model(**inputs)
        
        # 平均池化得到512维向量
        features = outputs.last_hidden_state.mean(dim=1).squeeze()
        return features.cpu().numpy()
    
    async def generate_consistent(
        self,
        character: dict,
        prompt: str,
        scene_context: Optional[dict] = None,
        consistency_weight: float = 0.8
    ) -> bytes:
        """
        生成保持角色一致性的画面
        
        三层一致性保障：
        1. 如果角色有LoRA → 使用LoRA（最强一致性）
        2. 同时启用IP-Adapter → 面部特征引导
        3. 参考图作为Reference → 整体风格引导
        
        Args:
            character: 角色信息
                {
                    'id': str,
                    'reference_image': bytes/str,  # 参考图
                    'lora_path': str/None,         # LoRA模型路径
                    'description': str,            # 角色描述
                }
            prompt: 画面提示词
            scene_context: 场景上下文（可选）
            consistency_weight: 一致性权重 (0-1)
        
        Returns:
            生成的图像字节
        """
        # 1. 加载角色LoRA（如果存在）
        if character.get('lora_path'):
            await self._load_character_lora(
                character['id'],
                character['lora_path'],
                weight=consistency_weight
            )
        
        # 2. 准备IP-Adapter参考图
        ref_image = None
        if character.get('reference_image'):
            ref_image = await self.image_engine._load_image(
                character['reference_image']
            )
        
        # 3. 构建增强提示词
        enhanced_prompt = self._enhance_prompt(
            prompt, character, scene_context
        )
        
        # 4. 生成图像（启用IP-Adapter）
        kwargs = {}
        if ref_image and self.ip_adapter_loaded:
            kwargs['ip_adapter_image'] = ref_image
            kwargs['ip_adapter_weight'] = consistency_weight
        
        image = await self.image_engine.generate(
            prompt=enhanced_prompt,
            **kwargs
        )
        
        # 5. 卸载LoRA
        if character.get('lora_path'):
            self.image_engine.unload_lora()
        
        return image
    
    async def generate_multi_character(
        self,
        characters: List[dict],
        scene_prompt: str,
        layout: Optional[dict] = None
    ) -> bytes:
        """
        多角色场景生成
        
        保持多个角色一致性的策略：
        1. 使用Regional Prompter进行区域控制
        2. 每个角色使用独立LoRA
        3. IP-Adapter分别引导
        
        Args:
            characters: 角色列表
                [{
                    'id': str,
                    'reference_image': bytes,
                    'lora_path': str,
                    'position': 'left'/'right'/'center',
                    'description': str
                }]
            scene_prompt: 场景提示词
            layout: 布局配置
        """
        if len(characters) > 4:
            raise ValueError("单帧最多支持4个角色")
        
        # 构建区域提示词
        regional_prompts = self._build_regional_prompts(
            characters, scene_prompt, layout
        )
        
        # 加载所有角色LoRA（需要支持多LoRA叠加）
        lora_weights = []
        for char in characters:
            if char.get('lora_path'):
                self.image_engine.load_lora(
                    char['lora_path'],
                    weight=0.6  # 多角色时降低权重避免冲突
                )
                lora_weights.append(char['lora_path'])
        
        # 使用Regional Prompter生成
        # 需要安装 regional-prompter 扩展
        image = await self.image_engine.generate(
            prompt=regional_prompts['main'],
            **regional_prompts['regions']
        )
        
        # 清理LoRA
        for _ in lora_weights:
            self.image_engine.unload_lora()
        
        return image
    
    def _build_regional_prompts(
        self,
        characters: List[dict],
        scene_prompt: str,
        layout: Optional[dict]
    ) -> dict:
        """构建区域提示词"""
        # 主提示词（场景）
        main_prompt = scene_prompt
        
        # 区域提示词（每个角色）
        regions = {}
        for i, char in enumerate(characters):
            position = char.get('position', 'center')
            regions[f'region_{i+1}'] = {
                'prompt': char.get('description', ''),
                'position': position,
                'weight': 0.7
            }
        
        return {
            'main': main_prompt,
            'regions': regions
        }
    
    async def _load_character_lora(
        self,
        character_id: str,
        lora_path: str,
        weight: float = 0.8
    ):
        """加载角色LoRA模型"""
        # 检查缓存
        if character_id in self.lora_cache:
            if self.lora_cache[character_id] == lora_path:
                # 已加载相同LoRA
                return
        
        # 卸载之前的LoRA
        self.image_engine.unload_lora()
        
        # 加载新LoRA
        self.image_engine.load_lora(lora_path, weight=weight)
        self.lora_cache[character_id] = lora_path
    
    def _enhance_prompt(
        self,
        prompt: str,
        character: dict,
        scene_context: Optional[dict] = None
    ) -> str:
        """增强提示词，加入角色描述"""
        parts = [prompt]
        
        # 添加角色描述
        if character.get('description'):
            parts.append(character['description'])
        
        # 添加角色特征标签
        if character.get('tags'):
            parts.extend(character['tags'])
        
        # 场景上下文
        if scene_context:
            if scene_context.get('mood'):
                mood_map = {
                    'happy': 'smiling, happy',
                    'sad': 'sad expression',
                    'angry': 'angry expression',
                    'surprised': 'surprised expression'
                }
                parts.append(mood_map.get(scene_context['mood'], ''))
        
        # 质量标签
        parts.extend(['masterpiece', 'best quality', 'detailed face'])
        
        return ', '.join(filter(None, parts))
```

---

## 三、LoRA训练流程

```python
# backend/app/engines/lora_trainer.py
from typing import Optional, List
import torch
from pathlib import Path
import json

class LoRATrainer:
    """
    LoRA训练器
    
    为每个角色训练专属LoRA模型，实现深度一致性。
    
    训练流程：
    1. 数据准备：收集角色图片（至少5张）
    2. 数据标注：自动生成图片描述
    3. 训练配置：设置LoRA参数
    4. 训练执行：低秩适应训练
    5. 模型验证：生成测试图片验证一致性
    """
    
    def __init__(self, output_dir: str = "ai-models/lora"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    async def train_character_lora(
        self,
        character_id: str,
        character_name: str,
        training_images: List[str],
        config: Optional[dict] = None
    ) -> dict:
        """
        训练角色LoRA
        
        Args:
            character_id: 角色ID
            character_name: 角色名称
            training_images: 训练图片URL列表
            config: 训练配置
        
        Returns:
            {
                'lora_path': str,      # LoRA模型路径
                'training_loss': float, # 最终训练损失
                'epochs': int,          # 训练轮数
                'quality_score': float  # 质量评分
            }
        """
        config = config or self._default_config()
        
        # 1. 准备训练数据
        dataset_dir = await self._prepare_dataset(
            character_id, character_name, training_images
        )
        
        # 2. 自动标注
        captions = await self._auto_caption(dataset_dir, character_name)
        
        # 3. 执行训练
        lora_path = await self._execute_training(
            dataset_dir=dataset_dir,
            captions=captions,
            character_name=character_name,
            config=config
        )
        
        # 4. 验证质量
        quality_score = await self._validate_lora(
            lora_path, character_name, training_images[0]
        )
        
        return {
            'lora_path': lora_path,
            'training_loss': 0.05,  # 示例值
            'epochs': config['epochs'],
            'quality_score': quality_score
        }
    
    def _default_config(self) -> dict:
        """默认训练配置"""
        return {
            'epochs': 10,
            'learning_rate': 1e-4,
            'batch_size': 2,
            'lora_rank': 32,          # LoRA秩
            'lora_alpha': 32,         # LoRA alpha
            'resolution': 512,
            'network_train_unet_only': True,
            'gradient_accumulation_steps': 4,
        }
    
    async def _prepare_dataset(
        self,
        character_id: str,
        character_name: str,
        image_urls: List[str]
    ) -> Path:
        """准备训练数据集"""
        dataset_dir = self.output_dir / character_id / "dataset"
        dataset_dir.mkdir(parents=True, exist_ok=True)
        
        # 下载训练图片
        import httpx
        for i, url in enumerate(image_urls):
            response = await httpx.AsyncClient().get(url)
            image_path = dataset_dir / f"image_{i:03d}.png"
            image_path.write_bytes(response.content)
        
        return dataset_dir
    
    async def _auto_caption(
        self,
        dataset_dir: Path,
        character_name: str
    ) -> List[str]:
        """
        自动为训练图片生成描述标注
        
        使用BLIP或WD14进行图片打标
        """
        # 使用WD14打标器（更准确）
        from onnxruntime import InferenceSession
        
        captions = []
        for image_path in sorted(dataset_dir.glob("*.png")):
            # 实际实现使用WD14模型生成标签
            # 这里简化处理
            caption = f"a photo of {character_name}, 1girl, solo"
            captions.append(caption)
            
            # 保存标注文件
            caption_path = image_path.with_suffix('.txt')
            caption_path.write_text(caption)
        
        return captions
    
    async def _execute_training(
        self,
        dataset_dir: Path,
        captions: List[str],
        character_name: str,
        config: dict
    ) -> str:
        """
        执行LoRA训练
        
        调用kohya-ss训练脚本
        """
        output_name = f"char_{character_name.lower().replace(' ', '_')}"
        output_path = self.output_dir / f"{output_name}.safetensors"
        
        # 构建训练命令
        cmd = f"""
        accelerate launch --num_cpu_threads_per_process=4 train_network.py \
            --pretrained_model_name_or_path=models/sd15 \
            --train_data_dir={dataset_dir} \
            --output_dir={self.output_dir} \
            --output_name={output_name} \
            --resolution={config['resolution']} \
            --train_batch_size={config['batch_size']} \
            --max_train_epochs={config['epochs']} \
            --learning_rate={config['learning_rate']} \
            --network_module=networks.lora \
            --network_dim={config['lora_rank']} \
            --network_alpha={config['lora_alpha']} \
            --gradient_accumulation_steps={config['gradient_accumulation_steps']} \
            --save_every_n_epochs=5 \
            --mixed_precision=fp16 \
            --save_precision=fp16
        """
        
        # 执行训练
        import subprocess
        subprocess.run(cmd, shell=True, check=True)
        
        return str(output_path)
    
    async def _validate_lora(
        self,
        lora_path: str,
        character_name: str,
        reference_image: str
    ) -> float:
        """
        验证LoRA质量
        
        生成测试图片，与参考图计算相似度
        """
        # 加载LoRA生成测试图
        from app.engines.image_gen_engine import ImageGenEngine
        engine = ImageGenEngine()
        engine.load_lora(lora_path, weight=0.8)
        
        test_image = await engine.generate(
            prompt=f"a photo of {character_name}, portrait",
            seed=42
        )
        
        # 计算与参考图的相似度
        ref_features = await self.extract_features(
            await self._download_image(reference_image)
        )
        test_features = await self.extract_features(test_image)
        
        # 余弦相似度
        similarity = np.dot(ref_features, test_features) / (
            np.linalg.norm(ref_features) * np.linalg.norm(test_features)
        )
        
        engine.unload_lora()
        
        return float(similarity)
```

---

## 四、一致性评分系统

```python
# backend/app/engines/consistency_evaluator.py
import numpy as np
from typing import List

class ConsistencyEvaluator:
    """
    角色一致性评估器
    
    评估生成的角色与参考角色的一致性程度
    """
    
    @staticmethod
    def evaluate(
        reference_image: bytes,
        generated_image: bytes,
        clip_model=None
    ) -> dict:
        """
        评估一致性
        
        Returns:
            {
                'overall_score': float,    # 总体一致性 0-1
                'face_similarity': float,  # 面部相似度
                'style_similarity': float, # 风格相似度
                'feature_similarity': float # 特征相似度
            }
        """
        # 提取特征
        ref_features = extract_features(reference_image, clip_model)
        gen_features = extract_features(generated_image, clip_model)
        
        # 计算各维度相似度
        face_sim = ConsistencyEvaluator._face_similarity(
            reference_image, generated_image
        )
        
        feature_sim = ConsistencyEvaluator._cosine_similarity(
            ref_features, gen_features
        )
        
        style_sim = ConsistencyEvaluator._style_similarity(
            reference_image, generated_image
        )
        
        # 加权综合评分
        overall = 0.4 * face_sim + 0.4 * feature_sim + 0.2 * style_sim
        
        return {
            'overall_score': overall,
            'face_similarity': face_sim,
            'style_similarity': style_sim,
            'feature_similarity': feature_sim
        }
    
    @staticmethod
    def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
        """余弦相似度"""
        return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    
    @staticmethod
    def _face_similarity(img1: bytes, img2: bytes) -> float:
        """面部相似度（使用FaceNet）"""
        # 实际实现使用face_recognition或DeepFace
        # 简化返回示例值
        return 0.85
    
    @staticmethod
    def _style_similarity(img1: bytes, img2: bytes) -> float:
        """风格相似度（使用Gram矩阵）"""
        # 实际实现计算Gram矩阵距离
        return 0.90
```

---

## 五、最佳实践配置

### 5.1 不同场景的推荐配置

```python
# 场景配置推荐
SCENE_CONFIGS = {
    'portrait': {
        # 角色特写：强调面部一致性
        'ip_adapter_weight': 0.9,
        'lora_weight': 0.8,
        'controlnet': 'reference',
        'controlnet_weight': 0.7,
    },
    'full_body': {
        # 全身镜头：平衡面部与身体
        'ip_adapter_weight': 0.7,
        'lora_weight': 0.9,
        'controlnet': 'openpose',
        'controlnet_weight': 0.5,
    },
    'multi_character': {
        # 多人场景：降低单角色权重
        'ip_adapter_weight': 0.5,
        'lora_weight': 0.6,
        'use_regional_prompter': True,
    },
    'action': {
        # 动作场景：强调姿势控制
        'ip_adapter_weight': 0.6,
        'lora_weight': 0.7,
        'controlnet': 'openpose',
        'controlnet_weight': 0.8,
    }
}
```

---

*本文档最后更新：2026-07-18*
