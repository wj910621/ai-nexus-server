# 场景构建模块

> 本文档详细说明场景模块的功能设计、类结构与实现细节。

---

## 一、模块概述

### 1.1 功能定位
场景模块负责漫剧背景画面的生成与管理，包括场景描述生成、场景模板库、透视/光影控制等。为角色提供沉浸式的活动环境。

### 1.2 核心能力
| 能力 | 描述 | 技术方案 |
|------|------|----------|
| 场景生成 | 文本描述生成场景画面 | Stable Diffusion + 场景提示词 |
| 场景模板 | 预设场景库（校园/都市/奇幻） | 模板系统 + 参数化生成 |
| 透视控制 | 一点/两点/三点透视 | ControlNet + 透视线检测 |
| 光影控制 | 时间/天气/光源控制 | 提示词工程 + 光照模型 |
| 场景变体 | 同一场景不同时间/天气 | img2img + 风格迁移 |

---

## 二、数据模型

```python
# backend/app/models/scene.py
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

class Scene(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """场景实体"""
    __tablename__ = "scenes"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False, index=True)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=True)
    name = Column(String(100), nullable=False, comment="场景名称")
    description = Column(Text, comment="场景描述")
    
    # 场景类型
    category = Column(String(50), comment="分类: indoor/outdoor/fantasy/sci-fi")
    subcategory = Column(String(50), comment="子分类: classroom/street/forest")
    
    # 画面参数
    perspective = Column(String(50), default="one_point", 
                         comment="透视: one_point/two_point/three_point/aerial")
    time_of_day = Column(String(50), default="day", 
                         comment="时间: dawn/morning/noon/afternoon/dusk/night")
    weather = Column(String(50), default="clear", 
                     comment="天气: clear/cloudy/rain/snow/fog/storm")
    season = Column(String(50), default="spring", 
                    comment="季节: spring/summer/autumn/winter")
    
    # 光照配置
    lighting = Column(JSON, default={}, comment="光照配置")
    
    # 生成参数
    style = Column(String(50), default="anime")
    color_palette = Column(JSON, default=[], comment="配色方案")
    mood = Column(String(50), comment="氛围: bright/dark/mysterious/warm")
    
    # 图像
    main_image_url = Column(String(500), comment="主场景图")
    variants = Column(JSON, default=[], comment="变体图URL列表")
    
    # 元数据
    tags = Column(JSON, default=[])
    usage_count = Column(Integer, default=0)
    is_template = Column(Boolean, default=False, comment="是否为模板")

class SceneTemplate(Base, UUIDMixin, TimestampMixin):
    """场景模板（预设场景库）"""
    __tablename__ = "scene_templates"
    
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False)
    description = Column(Text)
    preview_url = Column(String(500), comment="预览图")
    
    # 模板参数
    default_params = Column(JSON, comment="默认生成参数")
    prompt_template = Column(Text, comment="提示词模板")
    negative_prompt = Column(Text, comment="负面提示词")
    
    # ControlNet配置
    controlnet_config = Column(JSON, comment="ControlNet配置")
    
    # 商业信息
    is_premium = Column(Boolean, default=False, comment="是否付费模板")
    price = Column(Integer, default=0, comment="价格（积分）")
```

---

## 三、服务层设计

```python
# backend/app/services/scene_service.py
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.scene import Scene, SceneTemplate
from app.engines.image_gen_engine import ImageGenEngine
from app.engines.scene_gen_engine import SceneGenEngine

class SceneService:
    """场景服务：管理场景生成与模板"""
    
    # 场景提示词映射
    SCENE_PROMPTS = {
        'classroom': 'classroom, school, desks, chalkboard, windows, school supplies',
        'street': 'city street, buildings, road, sidewalk, traffic lights, shops',
        'forest': 'forest, trees, foliage, path, sunlight through trees, nature',
        'bedroom': 'bedroom, bed, furniture, window, cozy interior, warm lighting',
        'kitchen': 'kitchen, appliances, counter, cabinets, modern interior',
        'castle': 'castle, medieval architecture, stone walls, towers, grand hall',
        'space_station': 'space station interior, sci-fi, futuristic, screens, metal walls',
        'Japanese_street': 'Japanese street, traditional buildings, cherry blossoms, lanterns'
    }
    
    # 透视提示词
    PERSPECTIVE_PROMPTS = {
        'one_point': 'one point perspective, vanishing point centered',
        'two_point': 'two point perspective, dynamic angle',
        'three_point': 'three point perspective, dramatic view',
        'aerial': 'aerial view, bird\'s eye view, top-down perspective'
    }
    
    # 时间/光照提示词
    TIME_PROMPTS = {
        'dawn': 'dawn, early morning light, soft pink and orange sky',
        'morning': 'morning, bright sunlight, clear sky',
        'noon': 'noon, overhead sun, bright lighting',
        'afternoon': 'afternoon, warm golden light',
        'dusk': 'dusk, sunset, orange and purple sky',
        'night': 'night, dark sky, moonlight, artificial lights'
    }
    
    # 天气提示词
    WEATHER_PROMPTS = {
        'clear': 'clear sky, sunny',
        'cloudy': 'cloudy sky, overcast',
        'rain': 'rainy, wet surfaces, reflections, rain drops',
        'snow': 'snowing, snow covered ground, winter scene',
        'fog': 'foggy, misty atmosphere, low visibility',
        'storm': 'stormy, dramatic clouds, lightning'
    }
    
    def __init__(
        self,
        db: Session,
        image_engine: ImageGenEngine,
        scene_engine: SceneGenEngine
    ):
        self.db = db
        self.image_engine = image_engine
        self.scene_engine = scene_engine
    
    async def generate_scene(
        self,
        user_id: str,
        scene_data: dict
    ) -> Scene:
        """
        生成场景
        
        流程：
        1. 构建场景提示词
        2. 应用透视/光照/天气控制
        3. 调用图像生成引擎
        4. 保存场景
        """
        # 构建提示词
        prompt = self._build_scene_prompt(scene_data)
        negative_prompt = self._build_negative_prompt(scene_data)
        
        # 生成场景图
        image = await self.image_engine.generate(
            prompt=prompt,
            negative_prompt=negative_prompt,
            width=1024,
            height=576,  # 16:9宽屏
            steps=30,
            guidance_scale=7.0
        )
        
        # 上传图片
        image_url = await self._upload_image(image)
        
        # 创建场景记录
        scene = Scene(
            user_id=user_id,
            name=scene_data['name'],
            description=scene_data.get('description', ''),
            category=scene_data.get('category', 'outdoor'),
            subcategory=scene_data.get('subcategory'),
            perspective=scene_data.get('perspective', 'one_point'),
            time_of_day=scene_data.get('time_of_day', 'day'),
            weather=scene_data.get('weather', 'clear'),
            season=scene_data.get('season', 'spring'),
            style=scene_data.get('style', 'anime'),
            mood=scene_data.get('mood'),
            main_image_url=image_url,
            lighting=scene_data.get('lighting', {}),
            color_palette=scene_data.get('color_palette', []),
            tags=scene_data.get('tags', [])
        )
        self.db.add(scene)
        self.db.commit()
        self.db.refresh(scene)
        
        return scene
    
    async def generate_scene_variant(
        self,
        scene_id: str,
        variant_config: dict
    ) -> str:
        """
        生成场景变体（不同时间/天气/季节）
        
        使用img2img保持场景结构，只改变光影氛围
        """
        scene = await self.get_scene(scene_id)
        
        # 构建新的提示词（改变时间/天气）
        new_config = {
            'time_of_day': variant_config.get('time_of_day', scene.time_of_day),
            'weather': variant_config.get('weather', scene.weather),
            'season': variant_config.get('season', scene.season)
        }
        
        variant_prompt = self._build_variant_prompt(new_config)
        
        # 使用img2img，低重绘幅度保持结构
        image = await self.image_engine.img2img(
            init_image=scene.main_image_url,
            prompt=variant_prompt,
            strength=0.5,  # 较低强度，保持场景结构
            guidance_scale=7.0
        )
        
        # 上传并保存变体
        variant_url = await self._upload_image(image)
        scene.variants.append(variant_url)
        self.db.commit()
        
        return variant_url
    
    async def apply_template(
        self,
        user_id: str,
        template_id: str,
        customizations: dict
    ) -> Scene:
        """应用场景模板"""
        template = self.db.query(SceneTemplate).filter_by(id=template_id).first()
        if not template:
            raise ValueError("模板不存在")
        
        # 合并默认参数和自定义参数
        params = {**template.default_params, **customizations}
        
        # 构建提示词
        prompt = template.prompt_template.format(**params)
        
        # 生成场景
        image = await self.image_engine.generate(
            prompt=prompt,
            negative_prompt=template.negative_prompt,
            controlnet_config=template.controlnet_config,
            **params.get('gen_params', {})
        )
        
        image_url = await self._upload_image(image)
        
        scene = Scene(
            user_id=user_id,
            name=customizations.get('name', template.name),
            description=template.description,
            main_image_url=image_url,
            **{k: v for k, v in params.items() 
               if hasattr(Scene, k)}
        )
        self.db.add(scene)
        self.db.commit()
        
        return scene
    
    def _build_scene_prompt(self, data: dict) -> str:
        """构建场景提示词"""
        parts = []
        
        # 场景主体
        subcategory = data.get('subcategory', 'street')
        if subcategory in self.SCENE_PROMPTS:
            parts.append(self.SCENE_PROMPTS[subcategory])
        elif data.get('description'):
            parts.append(data['description'])
        
        # 透视
        perspective = data.get('perspective', 'one_point')
        parts.append(self.PERSPECTIVE_PROMPTS.get(perspective, ''))
        
        # 时间
        time_of_day = data.get('time_of_day', 'day')
        parts.append(self.TIME_PROMPTS.get(time_of_day, ''))
        
        # 天气
        weather = data.get('weather', 'clear')
        parts.append(self.WEATHER_PROMPTS.get(weather, ''))
        
        # 季节
        season = data.get('season', 'spring')
        season_prompts = {
            'spring': 'spring, fresh green leaves, blooming flowers',
            'summer': 'summer, lush green, bright sunlight',
            'autumn': 'autumn, falling leaves, warm colors',
            'winter': 'winter, bare trees, cold atmosphere'
        }
        parts.append(season_prompts.get(season, ''))
        
        # 氛围
        mood = data.get('mood')
        if mood:
            mood_prompts = {
                'bright': 'bright, cheerful atmosphere',
                'dark': 'dark, moody atmosphere',
                'mysterious': 'mysterious, enigmatic atmosphere',
                'warm': 'warm, cozy atmosphere'
            }
            parts.append(mood_prompts.get(mood, ''))
        
        # 画风
        style = data.get('style', 'anime')
        parts.append(f'{style} style, detailed background')
        
        # 质量标签
        parts.extend(['masterpiece', 'best quality', 'detailed scenery'])
        
        return ', '.join(filter(None, parts))
    
    def _build_negative_prompt(self, data: dict) -> str:
        """构建负面提示词"""
        return (
            'lowres, bad anatomy, bad hands, text, error, '
            'missing fingers, extra digit, fewer digits, '
            'cropped, worst quality, low quality, '
            'normal quality, jpeg artifacts, signature, watermark'
        )
```

---

## 四、场景生成引擎

```python
# backend/app/engines/scene_gen_engine.py
from typing import Optional
import numpy as np

class SceneGenEngine:
    """
    场景生成引擎
    
    特色功能：
    - 透视线检测与控制
    - 深度图引导
    - 语义分割引导
    """
    
    def __init__(self, image_engine):
        self.image_engine = image_engine
    
    async def generate_with_perspective(
        self,
        prompt: str,
        perspective_type: str = 'one_point',
        perspective_image: Optional[bytes] = None
    ) -> bytes:
        """
        使用透视控制生成场景
        
        Args:
            prompt: 场景提示词
            perspective_type: 透视类型
            perspective_image: 透视线参考图（可选）
        """
        if perspective_image:
            # 使用提供的透视线图
            control_image = perspective_image
        else:
            # 自动生成透视线
            control_image = await self._generate_perspective_lines(perspective_type)
        
        # 使用ControlNet的MLSD（线段检测）模型
        return await self.image_engine.generate_with_controlnet(
            prompt=prompt,
            controlnet_type='mlsd',
            controlnet_image=control_image,
            controlnet_weight=0.8
        )
    
    async def generate_with_depth(
        self,
        prompt: str,
        depth_map: Optional[bytes] = None
    ) -> bytes:
        """使用深度图引导生成"""
        if not depth_map:
            # 生成默认深度图
            depth_map = await self._generate_depth_map(prompt)
        
        return await self.image_engine.generate_with_controlnet(
            prompt=prompt,
            controlnet_type='depth',
            controlnet_image=depth_map,
            controlnet_weight=0.6
        )
    
    async def _generate_perspective_lines(
        self,
        perspective_type: str
    ) -> bytes:
        """生成透视线参考图"""
        import cv2
        import numpy as np
        
        width, height = 1024, 576
        img = np.ones((height, width, 3), dtype=np.uint8) * 255
        
        if perspective_type == 'one_point':
            # 一点透视：所有线汇聚到中心
            vanish_x, vanish_y = width // 2, height // 2
            # 绘制汇聚线
            for i in range(0, width, 80):
                cv2.line(img, (i, 0), (vanish_x, vanish_y), (0, 0, 0), 1)
                cv2.line(img, (i, height), (vanish_x, vanish_y), (0, 0, 0), 1)
            for i in range(0, height, 80):
                cv2.line(img, (0, i), (vanish_x, vanish_y), (0, 0, 0), 1)
                cv2.line(img, (width, i), (vanish_x, vanish_y), (0, 0, 0), 1)
        
        elif perspective_type == 'two_point':
            # 两点透视：两个消失点
            vp1_x, vp2_x = 0, width
            vp_y = height // 2
            for i in range(0, height, 60):
                cv2.line(img, (0, i), (vp1_x, vp_y), (0, 0, 0), 1)
                cv2.line(img, (width, i), (vp2_x, vp_y), (0, 0, 0), 1)
        
        return cv2.imencode('.png', img)[1].tobytes()
```

---

## 五、前端组件

```typescript
// frontend/src/features/scene/SceneGenerator.tsx
import { Card, Form, Input, Select, Button, Radio } from 'antd';
import { useGenerateScene } from './hooks/useScenes';

export function SceneGenerator() {
  const [form] = Form.useForm();
  const generateScene = useGenerateScene();
  
  return (
    <Card title="场景生成">
      <Form form={form} layout="vertical">
        <Form.Item name="name" label="场景名称" rules={[{ required: true }]}>
          <Input placeholder="如：放学后的教室" />
        </Form.Item>
        
        <Form.Item name="subcategory" label="场景类型">
          <Select>
            <Select.Option value="classroom">教室</Select.Option>
            <Select.Option value="street">街道</Select.Option>
            <Select.Option value="forest">森林</Select.Option>
            <Select.Option value="bedroom">卧室</Select.Option>
            <Select.Option value="castle">城堡</Select.Option>
          </Select>
        </Form.Item>
        
        <Form.Item name="perspective" label="透视">
          <Radio.Group>
            <Radio.Button value="one_point">一点透视</Radio.Button>
            <Radio.Button value="two_point">两点透视</Radio.Button>
            <Radio.Button value="three_point">三点透视</Radio.Button>
            <Radio.Button value="aerial">鸟瞰</Radio.Button>
          </Radio.Group>
        </Form.Item>
        
        <Form.Item name="time_of_day" label="时间">
          <Radio.Group>
            <Radio.Button value="dawn">黎明</Radio.Button>
            <Radio.Button value="morning">上午</Radio.Button>
            <Radio.Button value="noon">正午</Radio.Button>
            <Radio.Button value="dusk">黄昏</Radio.Button>
            <Radio.Button value="night">夜晚</Radio.Button>
          </Radio.Group>
        </Form.Item>
        
        <Form.Item name="weather" label="天气">
          <Radio.Group>
            <Radio.Button value="clear">晴</Radio.Button>
            <Radio.Button value="cloudy">阴</Radio.Button>
            <Radio.Button value="rain">雨</Radio.Button>
            <Radio.Button value="snow">雪</Radio.Button>
            <Radio.Button value="fog">雾</Radio.Button>
          </Radio.Group>
        </Form.Item>
        
        <Button 
          type="primary" 
          onClick={() => generateScene.mutateAsync(form.getFieldsValue())}
          loading={generateScene.isPending}
        >
          生成场景
        </Button>
      </Form>
    </Card>
  );
}
```

---

## 六、API接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/scenes | 生成场景 |
| GET | /api/v1/scenes | 获取场景列表 |
| GET | /api/v1/scenes/{id} | 获取场景详情 |
| POST | /api/v1/scenes/{id}/variant | 生成场景变体 |
| GET | /api/v1/scenes/templates | 获取场景模板列表 |
| POST | /api/v1/scenes/apply-template/{id} | 应用场景模板 |

---

*本文档最后更新：2026-07-18*
