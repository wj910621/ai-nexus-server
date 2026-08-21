# 角色设计与管理模块

> 本文档详细说明角色模块的功能设计、类结构、接口定义与实现细节。

---

## 一、模块概述

### 1.1 功能定位
角色模块是漫剧创作的核心，负责角色的创建、管理、一致性控制。解决AI生成中"同一角色在不同画面中长相不一致"的行业痛点。

### 1.2 核心能力
| 能力 | 描述 | 技术方案 |
|------|------|----------|
| 角色创建 | 文本描述生成角色形象 | Stable Diffusion + 角色提示词模板 |
| 角色卡系统 | 保存角色特征、服装、表情 | 结构化角色数据 + 向量特征 |
| 一致性控制 | 跨帧保持角色特征一致 | IP-Adapter + LoRA + Reference |
| 多视角生成 | 生成角色不同角度 | Reference多视图 + ControlNet |
| 角色变体 | 生成角色不同表情/姿势 | 角色LoRA + 表情/姿势控制 |

---

## 二、数据模型

### 2.1 角色实体

```python
# backend/app/models/character.py
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

class Character(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """角色实体"""
    __tablename__ = "characters"
    
    # 基本信息
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False, index=True)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=True, index=True)
    name = Column(String(100), nullable=False, comment="角色名称")
    description = Column(Text, comment="角色描述")
    
    # 角色属性
    style = Column(String(50), default="anime", comment="画风: anime/realistic/cartoon")
    gender = Column(String(20), comment="性别")
    age = Column(String(50), comment="年龄段")
    hair_color = Column(String(50), comment="发色")
    eye_color = Column(String(50), comment="瞳色")
    skin_tone = Column(String(50), comment="肤色")
    body_type = Column(String(50), comment="体型")
    
    # 服装与配饰
    outfit = Column(JSON, default={}, comment="服装配置")
    accessories = Column(JSON, default=[], comment="配饰列表")
    
    # 角色特征向量（用于一致性检索）
    feature_vector = Column(Vector(512), comment="角色特征向量")
    
    # LoRA模型关联
    lora_model_path = Column(String(500), comment="角色专属LoRA模型路径")
    lora_training_status = Column(String(20), default="none", 
                                   comment="none/training/completed/failed")
    
    # 参考图像
    reference_images = Column(JSON, default=[], comment="参考图URL列表")
    main_image_url = Column(String(500), comment="主形象图URL")
    
    # 表情库
    expressions = Column(JSON, default={}, comment="表情库")
    
    # 元数据
    tags = Column(JSON, default=[], comment="标签")
    usage_count = Column(Integer, default=0, comment="使用次数")
    rating = Column(Float, default=0.0, comment="评分")
    
    # 关联关系
    variants = relationship("CharacterVariant", back_populates="character")
    
class CharacterVariant(Base, UUIDMixin, TimestampMixin):
    """角色变体（不同表情、姿势、服装）"""
    __tablename__ = "character_variants"
    
    character_id = Column(UUID, ForeignKey('characters.id'), nullable=False)
    variant_type = Column(String(50), comment="变体类型: expression/pose/outfit")
    variant_name = Column(String(100), comment="变体名称")
    image_url = Column(String(500), comment="变体图片URL")
    config = Column(JSON, default={}, comment="生成配置")
    
    character = relationship("Character", back_populates="variants")
```

### 2.2 角色卡数据结构

```typescript
// frontend/src/types/character.ts
export interface CharacterCard {
  id: string;
  name: string;
  description: string;
  
  // 外观特征
  appearance: {
    style: 'anime' | 'realistic' | 'cartoon' | 'chibi';
    gender: 'male' | 'female' | 'neutral';
    age: string;
    hairColor: string;
    eyeColor: string;
    skinTone: string;
    bodyType: string;
  };
  
  // 服装配置
  outfit: {
    main: string;        // 主服装
    accessories: string[]; // 配饰
    colorScheme: string[]; // 配色
  };
  
  // 性格特征（用于表情生成）
  personality: {
    traits: string[];     // 性格标签
    defaultExpression: string; // 默认表情
    emotionRange: string[];    // 情绪范围
  };
  
  // 参考图像
  references: {
    mainImage: string;      // 主形象
    sideView?: string;      // 侧视图
    backView?: string;      // 背视图
    expressions?: Record<string, string>; // 表情库
  };
  
  // LoRA模型信息
  loraModel?: {
    path: string;
    weight: number;  // LoRA权重
    trained: boolean;
  };
}
```

---

## 三、服务层设计

### 3.1 角色服务类

```python
# backend/app/services/character_service.py
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.character import Character, CharacterVariant
from app.engines.image_gen_engine import ImageGenEngine
from app.engines.character_consistency_engine import CharacterConsistencyEngine
from app.core.exceptions import CharacterNotFoundError, InsufficientCreditsError

class CharacterService:
    """角色服务：管理角色全生命周期"""
    
    def __init__(
        self,
        db: Session,
        image_engine: ImageGenEngine,
        consistency_engine: CharacterConsistencyEngine,
        billing_service: 'BillingService'
    ):
        self.db = db
        self.image_engine = image_engine
        self.consistency_engine = consistency_engine
        self.billing_service = billing_service
    
    async def create_character(
        self,
        user_id: str,
        character_data: dict
    ) -> Character:
        """
        创建新角色
        
        流程：
        1. 校验用户积分
        2. 生成角色主形象
        3. 提取特征向量
        4. 保存角色信息
        5. 扣除积分
        """
        # 1. 检查积分
        if not await self.billing_service.check_credits(user_id, cost=10):
            raise InsufficientCreditsError()
        
        # 2. 构建角色提示词
        prompt = self._build_character_prompt(character_data)
        
        # 3. 生成主形象
        main_image = await self.image_engine.generate(
            prompt=prompt,
            negative_prompt="lowres, bad anatomy, bad hands, deformed",
            width=768,
            height=1024,
            steps=30,
            guidance_scale=7.5
        )
        
        # 4. 提取特征向量（用于一致性检索）
        feature_vector = await self.consistency_engine.extract_features(main_image)
        
        # 5. 上传图片到对象存储
        image_url = await self._upload_image(main_image)
        
        # 6. 创建角色记录
        character = Character(
            user_id=user_id,
            name=character_data['name'],
            description=character_data.get('description', ''),
            style=character_data.get('style', 'anime'),
            feature_vector=feature_vector,
            main_image_url=image_url,
            reference_images=[image_url],
            **{k: v for k, v in character_data.items() 
               if k in ['gender', 'age', 'hair_color', 'eye_color', 'skin_tone', 'body_type']}
        )
        self.db.add(character)
        self.db.commit()
        self.db.refresh(character)
        
        # 7. 扣除积分
        await self.billing_service.deduct_credits(user_id, 10, "create_character")
        
        return character
    
    async def generate_variant(
        self,
        character_id: str,
        variant_type: str,
        variant_config: dict
    ) -> CharacterVariant:
        """
        生成角色变体（不同表情/姿势/服装）
        
        Args:
            character_id: 角色ID
            variant_type: 变体类型 (expression/pose/outfit)
            variant_config: 变体配置
        """
        character = await self.get_character(character_id)
        if not character:
            raise CharacterNotFoundError(character_id)
        
        # 使用角色参考图 + LoRA保持一致性
        if character.lora_model_path:
            self.image_engine.load_lora(
                character.lora_model_path,
                weight=0.8
            )
        
        # 根据变体类型生成
        if variant_type == "expression":
            image = await self._generate_expression(character, variant_config)
        elif variant_type == "pose":
            image = await self._generate_pose(character, variant_config)
        elif variant_type == "outfit":
            image = await self._generate_outfit(character, variant_config)
        else:
            raise ValueError(f"不支持的变体类型: {variant_type}")
        
        # 保存变体
        variant = CharacterVariant(
            character_id=character_id,
            variant_type=variant_type,
            variant_name=variant_config.get('name', ''),
            image_url=await self._upload_image(image),
            config=variant_config
        )
        self.db.add(variant)
        self.db.commit()
        
        return variant
    
    async def train_character_lora(
        self,
        character_id: str,
        training_images: List[str]
    ) -> str:
        """
        训练角色专属LoRA模型
        
        Args:
            character_id: 角色ID
            training_images: 训练图片URL列表（至少5张）
        
        Returns:
            task_id: 训练任务ID
        """
        character = await self.get_character(character_id)
        if not character:
            raise CharacterNotFoundError(character_id)
        
        if len(training_images) < 5:
            raise ValueError("至少需要5张训练图片")
        
        # 更新训练状态
        character.lora_training_status = "training"
        self.db.commit()
        
        # 异步训练任务
        from app.tasks.training_tasks import train_lora
        task = train_lora.delay(
            character_id=character_id,
            image_urls=training_images,
            model_name=f"char_{character.name}_{character_id[:8]}"
        )
        
        return task.id
    
    async def get_character(self, character_id: str) -> Optional[Character]:
        """获取角色详情"""
        return self.db.query(Character).filter(
            Character.id == character_id,
            Character.is_deleted == False
        ).first()
    
    async def list_characters(
        self,
        user_id: str,
        page: int = 1,
        size: int = 20,
        filters: dict = None
    ) -> tuple[List[Character], int]:
        """获取角色列表"""
        query = self.db.query(Character).filter(
            Character.user_id == user_id,
            Character.is_deleted == False
        )
        
        if filters:
            if 'style' in filters:
                query = query.filter(Character.style == filters['style'])
            if 'tags' in filters:
                query = query.filter(Character.tags.contains(filters['tags']))
        
        total = query.count()
        characters = query.offset((page - 1) * size).limit(size).all()
        
        return characters, total
    
    def _build_character_prompt(self, data: dict) -> str:
        """构建角色生成提示词"""
        parts = []
        
        # 画风
        style_map = {
            'anime': 'anime style, detailed anime art',
            'realistic': 'realistic, photorealistic, high detail',
            'cartoon': 'cartoon style, flat shading',
            'chibi': 'chibi style, super deformed'
        }
        parts.append(style_map.get(data.get('style', 'anime'), ''))
        
        # 基本特征
        if data.get('gender'):
            parts.append(f"1{data['gender']}")
        if data.get('age'):
            parts.append(data['age'])
        if data.get('hair_color'):
            parts.append(f"{data['hair_color']} hair")
        if data.get('eye_color'):
            parts.append(f"{data['eye_color']} eyes")
        
        # 描述
        if data.get('description'):
            parts.append(data['description'])
        
        # 质量标签
        parts.extend([
            'masterpiece', 'best quality', 
            'detailed face', 'detailed eyes'
        ])
        
        return ', '.join(parts)
    
    async def _generate_expression(
        self,
        character: Character,
        config: dict
    ) -> bytes:
        """生成不同表情"""
        expressions = {
            'happy': 'smiling, happy expression',
            'sad': 'sad, crying expression',
            'angry': 'angry, furious expression',
            'surprised': 'surprised, shocked expression',
            'neutral': 'neutral expression'
        }
        
        expression_prompt = expressions.get(
            config.get('expression', 'neutral'), 
            'neutral expression'
        )
        
        # 使用Reference保持一致性
        return await self.consistency_engine.generate_with_reference(
            reference_image=character.main_image_url,
            prompt=f"{character.description}, {expression_prompt}",
            controlnet_type='reference',
            weight=0.8
        )
    
    async def _generate_pose(
        self,
        character: Character,
        config: dict
    ) -> bytes:
        """生成不同姿势"""
        # 使用OpenPose ControlNet控制姿势
        pose_map = {
            'standing': 'standing pose',
            'sitting': 'sitting pose',
            'running': 'running pose',
            'jumping': 'jumping pose'
        }
        
        return await self.consistency_engine.generate_with_reference(
            reference_image=character.main_image_url,
            prompt=f"{character.description}, {pose_map.get(config['pose'], '')}",
            controlnet_type='openpose',
            weight=0.6
        )
```

### 3.2 角色一致性引擎接口

```python
# backend/app/engines/character_consistency_engine.py
from abc import ABC, abstractmethod
import numpy as np

class CharacterConsistencyEngine:
    """
    角色一致性引擎
    
    技术栈：
    - IP-Adapter：图像提示，保持面部特征
    - LoRA：低秩适应，微调模型学习角色特征
    - Reference：参考图引导，保持整体风格
    """
    
    def __init__(self, image_engine):
        self.image_engine = image_engine
        self.ip_adapter = None
        self._loaded = False
    
    async def load_models(self):
        """加载一致性模型"""
        if not self._loaded:
            # 加载IP-Adapter
            self.image_engine.pipe.load_ip_adapter(
                "h94/IP-Adapter",
                subfolder="models",
                weight_name="ip-adapter-plus_sd15.safetensors"
            )
            self._loaded = True
    
    async def extract_features(self, image: bytes) -> np.ndarray:
        """
        从图像中提取角色特征向量
        
        使用CLIP图像编码器提取512维特征向量，
        用于后续的相似度检索和一致性控制。
        """
        from transformers import CLIPImageProcessor, CLIPVisionModel
        import torch
        from PIL import Image
        from io import BytesIO
        
        processor = CLIPImageProcessor.from_pretrained("openai/clip-vit-base-patch32")
        model = CLIPVisionModel.from_pretrained("openai/clip-vit-base-patch32")
        
        image_pil = Image.open(BytesIO(image))
        inputs = processor(images=image_pil, return_tensors="pt")
        
        with torch.no_grad():
            outputs = model(**inputs)
        
        # 平均池化得到512维向量
        features = outputs.last_hidden_state.mean(dim=1).squeeze().numpy()
        return features
    
    async def generate_with_reference(
        self,
        reference_image: str,
        prompt: str,
        controlnet_type: str = 'reference',
        weight: float = 0.8,
        **kwargs
    ) -> bytes:
        """
        使用参考图引导生成，保持角色一致性
        
        Args:
            reference_image: 参考图URL
            prompt: 生成提示词
            controlnet_type: 控制类型 (reference/ip_adapter/openpose)
            weight: 一致性权重 (0-1)，越高越像参考图
        """
        await self.load_models()
        
        # 下载参考图
        ref_image = await self._download_image(reference_image)
        
        if controlnet_type == 'ip_adapter':
            # IP-Adapter方式：面部特征一致性
            return await self.image_engine.generate(
                prompt=prompt,
                ip_adapter_image=ref_image,
                ip_adapter_weight=weight,
                **kwargs
            )
        elif controlnet_type == 'reference':
            # Reference方式：整体风格一致性
            return await self.image_engine.generate(
                prompt=prompt,
                reference_image=ref_image,
                reference_weight=weight,
                **kwargs
            )
        elif controlnet_type == 'openpose':
            # OpenPose方式：姿势控制
            from controlnet_aux import OpenposeDetector
            pose_detector = OpenposeDetector.from_pretrained("lllyasviel/ControlNet")
            pose_image = pose_detector(ref_image)
            
            return await self.image_engine.generate(
                prompt=prompt,
                controlnet_image=pose_image,
                controlnet_weight=weight,
                **kwargs
            )
    
    async def find_similar_characters(
        self,
        feature_vector: np.ndarray,
        threshold: float = 0.85
    ) -> list:
        """
        查找相似角色（用于去重和推荐）
        
        使用向量相似度检索，找到特征向量相近的角色。
        """
        from sqlalchemy import text
        
        # 使用PostgreSQL的pgvector进行向量检索
        query = text("""
            SELECT id, name, main_image_url,
                   1 - (feature_vector <=> :vector) as similarity
            FROM characters
            WHERE feature_vector IS NOT NULL
                AND is_deleted = false
                AND 1 - (feature_vector <=> :vector) > :threshold
            ORDER BY feature_vector <=> :vector
            LIMIT 10
        """)
        
        result = self.db.execute(query, {
            "vector": feature_vector.tolist(),
            "threshold": threshold
        })
        
        return result.fetchall()
```

---

## 四、前端组件

### 4.1 角色编辑器组件

```typescript
// frontend/src/features/character/CharacterEditor.tsx
import { useState } from 'react';
import { Card, Form, Input, Select, Button, Upload } from 'antd';
import { useCreateCharacter } from './hooks/useCharacters';

const { TextArea } = Input;

export function CharacterEditor() {
  const [form] = Form.useForm();
  const createCharacter = useCreateCharacter();
  
  const handleSubmit = async (values: any) => {
    await createCharacter.mutateAsync(values);
  };
  
  return (
    <Card title="创建角色" className="character-editor">
      <Form form={form} layout="vertical" onFinish={handleSubmit}>
        <Form.Item name="name" label="角色名称" rules={[{ required: true }]}>
          <Input placeholder="输入角色名称" />
        </Form.Item>
        
        <Form.Item name="description" label="角色描述" rules={[{ required: true }]}>
          <TextArea rows={4} placeholder="详细描述角色特征..." />
        </Form.Item>
        
        <Form.Item name="style" label="画风" initialValue="anime">
          <Select>
            <Select.Option value="anime">动漫</Select.Option>
            <Select.Option value="realistic">写实</Select.Option>
            <Select.Option value="cartoon">卡通</Select.Option>
            <Select.Option value="chibi">Q版</Select.Option>
          </Select>
        </Form.Item>
        
        <div className="grid grid-cols-2 gap-4">
          <Form.Item name="gender" label="性别">
            <Select>
              <Select.Option value="male">男</Select.Option>
              <Select.Option value="female">女</Select.Option>
            </Select>
          </Form.Item>
          
          <Form.Item name="age" label="年龄段">
            <Input placeholder="如：少年、青年" />
          </Form.Item>
          
          <Form.Item name="hair_color" label="发色">
            <Input placeholder="如：黑色、金色" />
          </Form.Item>
          
          <Form.Item name="eye_color" label="瞳色">
            <Input placeholder="如：蓝色、红色" />
          </Form.Item>
        </div>
        
        <Button type="primary" htmlType="submit" loading={createCharacter.isPending}>
          生成角色
        </Button>
      </Form>
    </Card>
  );
}
```

### 4.2 角色卡片组件

```typescript
// frontend/src/features/character/CharacterCard.tsx
import { Card, Tag, Rate } from 'antd';
import { Character } from '@/types/character';

interface CharacterCardProps {
  character: Character;
  onClick?: (character: Character) => void;
}

export function CharacterCard({ character, onClick }: CharacterCardProps) {
  return (
    <Card
      hoverable
      className="character-card cursor-pointer"
      cover={<img src={character.main_image_url} alt={character.name} />}
      onClick={() => onClick?.(character)}
    >
      <Card.Meta
        title={character.name}
        description={
          <div className="space-y-2">
            <div>
              <Tag color="blue">{character.style}</Tag>
              {character.tags?.map(tag => (
                <Tag key={tag}>{tag}</Tag>
              ))}
            </div>
            <div className="flex items-center justify-between">
              <Rate disabled defaultValue={character.rating} allowHalf size="small" />
              <span className="text-xs text-gray-500">
                使用 {character.usage_count} 次
              </span>
            </div>
          </div>
        }
      />
    </Card>
  );
}
```

---

## 五、API接口

### 5.1 REST API

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/characters | 创建角色 |
| GET | /api/v1/characters | 获取角色列表 |
| GET | /api/v1/characters/{id} | 获取角色详情 |
| PUT | /api/v1/characters/{id} | 更新角色 |
| DELETE | /api/v1/characters/{id} | 删除角色 |
| POST | /api/v1/characters/{id}/variants | 生成角色变体 |
| POST | /api/v1/characters/{id}/train-lora | 训练LoRA |
| GET | /api/v1/characters/{id}/variants | 获取变体列表 |

### 5.2 接口示例

```python
# backend/app/api/character_routes.py
from fastapi import APIRouter, Depends, UploadFile, File
from app.services.character_service import CharacterService
from app.api.deps import get_current_user, get_db

router = APIRouter(prefix="/api/v1/characters", tags=["characters"])

@router.post("/", response_model=ApiResponse[Character])
async def create_character(
    request: CreateCharacterRequest,
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    service = CharacterService(db)
    character = await service.create_character(
        user_id=current_user.id,
        character_data=request.dict()
    )
    return ApiResponse(data=character)

@router.post("/{character_id}/train-lora")
async def train_lora(
    character_id: str,
    files: List[UploadFile] = File(...),
    current_user = Depends(get_current_user),
    db = Depends(get_db)
):
    """上传训练图片并启动LoRA训练"""
    service = CharacterService(db)
    
    # 上传图片
    image_urls = []
    for file in files:
        url = await upload_to_storage(file)
        image_urls.append(url)
    
    # 启动训练任务
    task_id = await service.train_character_lora(character_id, image_urls)
    
    return ApiResponse(data={"task_id": task_id, "status": "training"})
```

---

*本文档最后更新：2026-07-18*
