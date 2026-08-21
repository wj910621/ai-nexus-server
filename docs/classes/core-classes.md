# 核心数据类

> 本文档汇总所有核心数据模型与实体类的定义。

---

## 一、用户与权限

### 1.1 User 用户实体

```python
# backend/app/models/user.py
class User(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """用户实体"""
    __tablename__ = "users"
    
    # 基本信息
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    password_hash = Column(String(200), nullable=False)
    avatar_url = Column(String(500))
    bio = Column(Text)
    
    # 账户状态
    status = Column(String(20), default='active')  # active/banned/inactive
    email_verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime)
    
    # 订阅信息
    plan = Column(String(20), default='free')  # free/pro/enterprise
    plan_expires_at = Column(DateTime)
    credits = Column(Integer, default=100)  # 积分余额
    
    # 偏好设置
    preferences = Column(JSON, default={
        'language': 'zh-CN',
        'theme': 'dark',
        'default_model': 'sdxl',
        'auto_save': True
    })
```

### 1.2 Project 项目实体

```python
# backend/app/models/project.py
class Project(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """项目实体"""
    __tablename__ = "projects"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text)
    genre = Column(String(50))  # romance/action/mystery/comedy/drama
    
    # 状态
    status = Column(String(20), default='active')  # active/archived/deleted
    
    # 配置
    config = Column(JSON, default={
        'resolution': '1920x1080',
        'fps': 24,
        'style': 'anime'
    })
    
    # 统计
    character_count = Column(Integer, default=0)
    scene_count = Column(Integer, default=0)
    frame_count = Column(Integer, default=0)
    
    # 协作
    is_shared = Column(Boolean, default=False)
    collaborators = Column(JSON, default=[])  # [{user_id, role}]
```

---

## 二、角色数据类

### 2.1 Character 角色实体

```python
# backend/app/models/character.py
class Character(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """角色实体 - 详见角色模块文档"""
    __tablename__ = "characters"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=True)
    name = Column(String(100), nullable=False)
    description = Column(Text)
    
    # 外观特征
    style = Column(String(50), default="anime")
    gender = Column(String(20))
    age = Column(String(50))
    hair_color = Column(String(50))
    eye_color = Column(String(50))
    skin_tone = Column(String(50))
    body_type = Column(String(50))
    
    # 特征向量（pgvector）
    feature_vector = Column(Vector(512))
    
    # LoRA模型
    lora_model_path = Column(String(500))
    lora_training_status = Column(String(20), default="none")
    
    # 图像
    main_image_url = Column(String(500))
    reference_images = Column(JSON, default=[])
    
    # 元数据
    tags = Column(JSON, default=[])
    usage_count = Column(Integer, default=0)
```

### 2.2 CharacterCard 角色卡（前端类型）

```typescript
// frontend/src/types/character.ts
export interface CharacterCard {
  id: string;
  name: string;
  description: string;
  
  appearance: {
    style: 'anime' | 'realistic' | 'cartoon' | 'chibi';
    gender: 'male' | 'female' | 'neutral';
    age: string;
    hairColor: string;
    eyeColor: string;
    skinTone: string;
    bodyType: string;
  };
  
  outfit: {
    main: string;
    accessories: string[];
    colorScheme: string[];
  };
  
  personality: {
    traits: string[];
    defaultExpression: string;
    emotionRange: string[];
  };
  
  references: {
    mainImage: string;
    sideView?: string;
    backView?: string;
    expressions?: Record<string, string>;
  };
  
  loraModel?: {
    path: string;
    weight: number;
    trained: boolean;
  };
}
```

---

## 三、剧本数据类

### 3.1 Script 剧本实体

```python
class Script(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """剧本实体 - 详见剧本模块文档"""
    __tablename__ = "scripts"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    
    structure = Column(String(50), default="three_act")
    genre = Column(String(50))
    outline = Column(Text)
    
    total_scenes = Column(Integer, default=0)
    total_duration = Column(Integer, default=0)
    status = Column(String(20), default="draft")
```

### 3.2 Scene 场景实体

```python
class Scene(Base, UUIDMixin, TimestampMixin):
    """场景实体"""
    __tablename__ = "script_scenes"
    
    script_id = Column(UUID, ForeignKey('scripts.id'), nullable=False)
    scene_number = Column(Integer, nullable=False)
    title = Column(String(200))
    location = Column(String(200))
    time_of_day = Column(String(50))
    description = Column(Text)
    mood = Column(String(50))
    intensity = Column(Integer, default=5)
    scene_bg_id = Column(UUID, ForeignKey('scenes.id'), nullable=True)
    order_index = Column(Integer, default=0)
```

### 3.3 Dialogue 对话实体

```python
class Dialogue(Base, UUIDMixin, TimestampMixin):
    """对话实体"""
    __tablename__ = "dialogues"
    
    scene_id = Column(UUID, ForeignKey('script_scenes.id'), nullable=False)
    character_id = Column(UUID, ForeignKey('characters.id'), nullable=True)
    character_name = Column(String(100))
    
    content = Column(Text, nullable=False)
    emotion = Column(String(50))  # happy/sad/angry/surprised/neutral
    action = Column(Text)
    
    bubble_type = Column(String(50), default="normal")
    bubble_position = Column(String(50), default="right")
    duration = Column(Float, default=2.0)
    order_index = Column(Integer, default=0)
```

---

## 四、分镜数据类

### 4.1 StoryboardFrame 分镜帧

```python
class StoryboardFrame(Base, UUIDMixin, TimestampMixin):
    """分镜帧 - 详见分镜模块文档"""
    __tablename__ = "storyboard_frames"
    
    script_id = Column(UUID, ForeignKey('scripts.id'), nullable=False)
    scene_id = Column(UUID, ForeignKey('script_scenes.id'), nullable=True)
    frame_number = Column(Integer, nullable=False)
    
    # 镜头信息
    shot_type = Column(String(50))  # extreme_wide/wide/medium/close_up
    camera_angle = Column(String(50))  # eye_level/high_angle/low_angle
    composition = Column(String(50))  # rule_of_thirds/center/symmetry
    camera_movement = Column(String(50))  # static/pan/zoom/tracking
    
    # 内容
    description = Column(Text)
    prompt = Column(Text)
    negative_prompt = Column(Text)
    
    # 角色配置
    characters_in_frame = Column(JSON, default=[])
    
    # 时间
    duration = Column(Float, default=2.0)
    transition = Column(String(50), default='cut')
    transition_duration = Column(Float, default=0.5)
    
    # 生成结果
    generated_image_url = Column(String(500), nullable=True)
    generation_status = Column(String(20), default='pending')
```

---

## 五、音频数据类

### 5.1 VoiceProfile 音色配置

```python
class VoiceProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音色配置 - 详见配音模块文档"""
    __tablename__ = "voice_profiles"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    character_id = Column(UUID, ForeignKey('characters.id'), nullable=True)
    
    name = Column(String(100), nullable=False)
    engine = Column(String(50), default="edge_tts")
    voice_id = Column(String(100))
    language = Column(String(10), default="zh-CN")
    
    rate = Column(Integer, default=0)
    pitch = Column(Integer, default=0)
    volume = Column(Integer, default=100)
    
    gender = Column(String(20))
    age_group = Column(String(20))
    tone = Column(String(50))
```

### 5.2 AudioTrack 音频轨道

```python
class AudioTrack(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音频轨道"""
    __tablename__ = "audio_tracks"
    
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=False)
    track_type = Column(String(50), nullable=False)  # voice/bgm/sfx/ambient
    name = Column(String(200))
    
    audio_url = Column(String(500))
    duration = Column(Float)
    
    start_time = Column(Float, default=0)
    end_time = Column(Float)
    
    frame_id = Column(UUID, ForeignKey('storyboard_frames.id'), nullable=True)
    dialogue_id = Column(UUID, ForeignKey('dialogues.id'), nullable=True)
    voice_profile_id = Column(UUID, ForeignKey('voice_profiles.id'), nullable=True)
    
    volume = Column(Float, default=1.0)
    fade_in = Column(Float, default=0)
    fade_out = Column(Float, default=0)
```

---

## 六、渲染数据类

### 6.1 RenderTask 渲染任务

```python
class RenderTask(Base, UUIDMixin, TimestampMixin):
    """渲染任务 - 详见渲染模块文档"""
    __tablename__ = "render_tasks"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=False)
    script_id = Column(UUID, ForeignKey('scripts.id'), nullable=False)
    
    name = Column(String(200))
    status = Column(String(20), default='pending')
    progress = Column(Integer, default=0)
    
    config = Column(JSON)  # 渲染配置
    output_url = Column(String(500), nullable=True)
    output_size = Column(Integer, nullable=True)
    duration = Column(Float, nullable=True)
    frame_count = Column(Integer, nullable=True)
    
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    credits_cost = Column(Integer, default=0)
```

---

## 七、工作流数据类

### 7.1 Workflow 工作流

```python
class Workflow(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """工作流定义"""
    __tablename__ = "workflows"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=True)
    
    name = Column(String(200), nullable=False)
    description = Column(Text)
    
    # 工作流数据（节点与连线）
    nodes = Column(JSON, nullable=False)  # 节点列表
    edges = Column(JSON, nullable=False)  # 连线列表
    
    # 元数据
    category = Column(String(50), default='custom')
    is_template = Column(Boolean, default=False)
    is_public = Column(Boolean, default=False)
    
    # 版本
    version = Column(Integer, default=1)
    parent_version_id = Column(UUID, nullable=True)
```

### 7.2 WorkflowExecution 工作流执行记录

```python
class WorkflowExecution(Base, UUIDMixin, TimestampMixin):
    """工作流执行记录"""
    __tablename__ = "workflow_executions"
    
    workflow_id = Column(UUID, ForeignKey('workflows.id'), nullable=False)
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    
    status = Column(String(20), default='running')  # running/completed/failed
    inputs = Column(JSON)  # 输入参数
    results = Column(JSON)  # 执行结果
    errors = Column(JSON)  # 错误信息
    
    started_at = Column(DateTime)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Float, nullable=True)
    
    # 节点执行详情
    node_executions = Column(JSON, default=[])  # 每个节点的执行记录
```

---

## 八、计费数据类

### 8.1 Subscription 订阅

```python
class Subscription(Base, UUIDMixin, TimestampMixin):
    """订阅记录"""
    __tablename__ = "subscriptions"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    plan = Column(String(20), nullable=False)  # free/pro/enterprise
    status = Column(String(20), default='active')  # active/cancelled/expired
    
    # 时间
    started_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    cancelled_at = Column(DateTime, nullable=True)
    
    # 付费信息
    amount = Column(Integer)  # 金额（分）
    payment_method = Column(String(50))
    payment_id = Column(String(200))  # 第三方支付ID
    
    # 自动续费
    auto_renew = Column(Boolean, default=False)
```

### 8.2 CreditTransaction 积分交易

```python
class CreditTransaction(Base, UUIDMixin, TimestampMixin):
    """积分交易记录"""
    __tablename__ = "credit_transactions"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    
    # 交易类型
    type = Column(String(20), nullable=False)  # recharge/deduct/bonus/refund
    amount = Column(Integer, nullable=False)  # 正数为充值，负数为扣除
    balance_after = Column(Integer, nullable=False)  # 交易后余额
    
    # 原因
    reason = Column(String(50))  # create_character/render/lora_train/recharge
    description = Column(String(200))
    
    # 关联
    related_id = Column(UUID, nullable=True)  # 关联的资源ID
    related_type = Column(String(50))  # character/render_task/...
```

---

## 九、通用基类

### 9.1 基类定义

```python
# backend/app/models/base.py
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """ORM基类"""
    pass

class UUIDMixin:
    """UUID主键混入"""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class TimestampMixin:
    """时间戳混入"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, 
                        onupdate=datetime.utcnow, nullable=False)

class SoftDeleteMixin:
    """软删除混入"""
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
```

### 9.2 统一响应类

```python
# backend/app/core/response.py
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    """统一API响应"""
    code: int = 0
    message: str = "success"
    data: Optional[T] = None
    timestamp: int = 0

class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应"""
    code: int = 0
    message: str = "success"
    data: list[T] = []
    total: int = 0
    page: int = 1
    page_size: int = 20
    timestamp: int = 0
```

---

*本文档最后更新：2026-07-18*
