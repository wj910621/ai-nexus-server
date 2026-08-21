# 系统设计原则

> 本文档阐述漫剧生成软件的设计哲学、核心原则与架构约束。

---

## 一、设计哲学

### 1.1 产品愿景
**"让每个人都能创作专业漫剧"** - 降低创作门槛，释放创意潜能。

### 1.2 核心设计理念
1. **专业与易用并存**：双模式设计（节点式 + 模板化），满足不同用户层级
2. **AI原生**：AI不是附加功能，而是核心创作方式
3. **商业化导向**：架构设计为SaaS订阅和按量付费预留扩展点
4. **生态开放**：插件机制和API开放，构建创作者生态

---

## 二、架构设计原则

### 2.1 分层职责清晰

**原则**：每层只负责自己的核心职责，不越层调用。

```
禁止的调用方向：
❌ 引擎层直接调用客户端
❌ 基础设施层直接调用业务服务
❌ 客户端直接操作数据库

允许的调用方向：
✅ 客户端 → API网关 → 业务服务 → AI引擎 → 基础设施
✅ 同层服务之间通过接口调用
```

### 2.2 模块高内聚低耦合

**原则**：每个模块独立完成一个业务领域，模块间通过定义良好的接口通信。

```python
# ✅ 正确：模块间通过接口通信
class CharacterService:
    def __init__(self, image_engine: IImageGenEngine):
        self.image_engine = image_engine  # 依赖抽象接口
    
    async def create_character(self, params):
        # 角色服务不关心图像引擎的具体实现
        image = await self.image_engine.generate(params)
        return Character(image=image)

# ❌ 错误：直接依赖具体实现
class CharacterService:
    def __init__(self):
        self.engine = StableDiffusionEngine()  # 硬编码依赖
```

### 2.3 依赖倒置原则（DIP）

**原则**：高层模块不依赖低层模块，二者都依赖抽象。

```python
# 抽象接口定义
from abc import ABC, abstractmethod

class IImageGenEngine(ABC):
    """图像生成引擎抽象接口"""
    
    @abstractmethod
    async def generate(self, prompt: str, params: dict) -> bytes:
        """生成图像"""
        pass
    
    @abstractmethod
    async def img2img(self, image: bytes, prompt: str, strength: float) -> bytes:
        """图生图"""
        pass

# 具体实现：Stable Diffusion
class SDEngine(IImageGenEngine):
    async def generate(self, prompt: str, params: dict) -> bytes:
        # SD实现
        pass

# 具体实现：DALL-E（未来扩展）
class DalleEngine(IImageGenEngine):
    async def generate(self, prompt: str, params: dict) -> bytes:
        # DALL-E实现
        pass

# 业务服务依赖抽象，可灵活替换实现
class CharacterService:
    def __init__(self, engine: IImageGenEngine):
        self.engine = engine  # 注入抽象接口
```

### 2.4 单一职责原则（SRP）

**原则**：每个类/模块只负责一个功能领域。

```python
# ✅ 正确：职责单一
class CharacterService:
    """只负责角色业务逻辑"""
    async def create_character(self): pass
    async def update_character(self): pass
    async def delete_character(self): pass

class CharacterRepository:
    """只负责角色数据持久化"""
    async def save(self, character): pass
    async def find_by_id(self, id): pass

class CharacterValidator:
    """只负责角色数据校验"""
    def validate(self, data): pass

# ❌ 错误：职责混乱
class CharacterManager:
    """同时处理业务、存储、校验"""
    async def create_character(self):
        self.validate()    # 不应该在这里
        self.save_to_db()  # 不应该在这里
        self.send_email()  # 不应该在这里
```

---

## 三、API设计原则

### 3.1 RESTful规范

```python
# 资源命名：使用名词复数
GET    /api/v1/characters          # 获取角色列表
POST   /api/v1/characters          # 创建角色
GET    /api/v1/characters/{id}     # 获取角色详情
PUT    /api/v1/characters/{id}     # 更新角色
DELETE /api/v1/characters/{id}     # 删除角色

# 嵌套资源
GET    /api/v1/projects/{id}/characters  # 获取项目下的角色

# 操作类接口使用动词
POST   /api/v1/characters/{id}/train-lora  # 训练LoRA
POST   /api/v1/render/start                 # 启动渲染
```

### 3.2 统一响应格式

```python
# backend/app/core/response.py
from pydantic import BaseModel
from typing import Generic, TypeVar, Optional, Any

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    """统一API响应格式"""
    code: int = 0           # 0表示成功，非0表示错误
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

# 使用示例
@router.get("/characters", response_model=PaginatedResponse[Character])
async def list_characters(page: int = 1, size: int = 20):
    characters = await character_service.list(page, size)
    return PaginatedResponse(
        data=characters,
        total=len(characters),
        page=page,
        page_size=size
    )
```

### 3.3 错误处理规范

```python
# backend/app/core/exceptions.py
from fastapi import HTTPException

class BusinessException(Exception):
    """业务异常基类"""
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message

class CharacterNotFoundError(BusinessException):
    def __init__(self, character_id: str):
        super().__init__(code=40401, message=f"角色不存在: {character_id}")

class InsufficientCreditsError(BusinessException):
    def __init__(self):
        super().__init__(code=40201, message="积分不足，请充值")

class RenderFailedError(BusinessException):
    def __init__(self, reason: str):
        super().__init__(code=50001, message=f"渲染失败: {reason}")

# 全局异常处理
@app.exception_handler(BusinessException)
async def business_exception_handler(request, exc: BusinessException):
    return ApiResponse(
        code=exc.code,
        message=exc.message,
        timestamp=int(time.time())
    )
```

---

## 四、数据设计原则

### 4.1 数据模型规范

```python
# backend/app/models/base.py
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
import uuid

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    """时间戳混入，所有表都包含创建/更新时间"""
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, 
                        onupdate=datetime.utcnow, nullable=False)

class UUIDMixin:
    """UUID主键混入"""
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

class SoftDeleteMixin:
    """软删除混入"""
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
```

### 4.2 软删除设计

```python
# 所有业务数据采用软删除，保证数据可恢复
class Character(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "characters"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    name = Column(String(100), nullable=False)
    # ...

# 查询时自动过滤已删除数据
class CharacterRepository:
    def __init__(self, db: Session):
        self.db = db
    
    async def find_active(self, character_id: str) -> Character | None:
        return self.db.query(Character).filter(
            Character.id == character_id,
            Character.is_deleted == False  # 只查未删除
        ).first()
```

---

## 五、安全设计原则

### 5.1 认证与授权

```python
# 三层安全模型：认证 → 授权 → 限流

# 1. 认证：验证用户身份
async def authenticate(token: str) -> User:
    """JWT认证"""
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    user = await user_service.get_by_id(payload["user_id"])
    if not user:
        raise AuthenticationError("用户不存在")
    return user

# 2. 授权：验证用户权限
def require_permission(permission: str):
    """权限装饰器"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            user = kwargs.get("current_user")
            if not user.has_permission(permission):
                raise AuthorizationError(f"无权限: {permission}")
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# 3. 限流：防止滥用
@router.post("/characters", dependencies=[
    Depends(RateLimiter(times=10, hours=1))  # 每小时10次
])
async def create_character():
    pass
```

### 5.2 输入校验

```python
from pydantic import BaseModel, validator, Field

class CreateCharacterRequest(BaseModel):
    """创建角色请求，严格校验输入"""
    name: str = Field(..., min_length=1, max_length=100, description="角色名称")
    description: str = Field(..., max_length=2000, description="角色描述")
    style: str = Field(..., regex="^(realistic|anime|cartoon|chibi)$")
    
    @validator('name')
    def validate_name(cls, v):
        # 防止XSS
        import re
        if re.search(r'[<>"\']', v):
            raise ValueError('名称包含非法字符')
        return v.strip()
```

---

## 六、性能设计原则

### 6.1 异步优先

```python
# ✅ 正确：异步IO，高并发
async def generate_frames(frames: list[Frame]):
    tasks = [generate_frame(frame) for frame in frames]
    return await asyncio.gather(*tasks)  # 并行生成

# ❌ 错误：同步阻塞
def generate_frames(frames: list[Frame]):
    results = []
    for frame in frames:
        results.append(generate_frame(frame))  # 串行，慢
    return results
```

### 6.2 缓存策略

```python
# 多级缓存：内存 → Redis → 数据库
class CharacterService:
    @lru_cache(maxsize=100)  # 内存缓存
    async def get_character(self, character_id: str) -> Character:
        # 内存未命中，查Redis
        cached = await redis.get(f"char:{character_id}")
        if cached:
            return Character(**json.loads(cached))
        
        # Redis未命中，查数据库
        character = await self.repo.find_by_id(character_id)
        if character:
            # 写入Redis缓存，1小时过期
            await redis.setex(
                f"char:{character_id}", 
                3600, 
                character.json()
            )
        return character
```

### 6.3 数据库优化

```python
# 批量操作代替循环
async def batch_create_characters(characters: list[dict]):
    # ✅ 批量插入，1次IO
    await db.execute(
        insert(Character),
        characters
    )
    
    # ❌ 循环插入，N次IO
    # for char in characters:
    #     db.add(Character(**char))
```

---

## 七、可观测性设计

### 7.1 日志规范

```python
from loguru import logger

# 结构化日志，便于检索分析
logger.configure(
    handlers=[{
        "sink": "logs/app.log",
        "format": "{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}",
        "rotation": "100 MB",
        "retention": "30 days",
        "compression": "zip",
    }]
)

# 关键操作记录日志
class CharacterService:
    async def create_character(self, user_id: str, data: dict):
        logger.info(
            "创建角色",
            user_id=user_id,
            character_name=data.get("name"),
            extra={"action": "create_character"}
        )
        try:
            character = await self.repo.create(data)
            logger.info(f"角色创建成功: {character.id}")
            return character
        except Exception as e:
            logger.exception(f"角色创建失败: {e}")
            raise
```

### 7.2 监控指标

```python
from prometheus_client import Counter, Histogram, Gauge

# 定义监控指标
api_requests = Counter(
    'comic_studio_api_requests_total',
    'API请求总数',
    ['method', 'endpoint', 'status']
)

api_latency = Histogram(
    'comic_studio_api_latency_seconds',
    'API响应时间',
    ['endpoint']
)

active_generations = Gauge(
    'comic_studio_active_generations',
    '当前活跃的生成任务数'
)

# 中间件自动记录
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    
    api_requests.labels(
        method=request.method,
        endpoint=request.url.path,
        status=response.status_code
    ).inc()
    
    api_latency.labels(
        endpoint=request.url.path
    ).observe(time.time() - start_time)
    
    return response
```

---

## 八、扩展性设计

### 8.1 插件机制

```python
# 插件系统设计，支持第三方扩展
from typing import Protocol

class IPlugin(Protocol):
    """插件接口"""
    name: str
    version: str
    
    def initialize(self, context: PluginContext) -> None: ...
    def get_nodes(self) -> list[NodeDefinition]: ...
    def cleanup(self) -> None: ...

class PluginManager:
    """插件管理器"""
    
    def __init__(self):
        self.plugins: dict[str, IPlugin] = {}
    
    def load_plugin(self, plugin_path: str):
        """动态加载插件"""
        import importlib
        module = importlib.import_module(plugin_path)
        plugin = module.Plugin()
        plugin.initialize(self.context)
        self.plugins[plugin.name] = plugin
    
    def get_all_nodes(self) -> list[NodeDefinition]:
        """获取所有插件提供的节点"""
        nodes = []
        for plugin in self.plugins.values():
            nodes.extend(plugin.get_nodes())
        return nodes
```

### 8.2 策略模式

```python
# 生成策略可灵活替换
class GenerationStrategy(ABC):
    @abstractmethod
    async def generate(self, params: dict) -> bytes: pass

class FastStrategy(GenerationStrategy):
    """快速生成：低分辨率，少步数"""
    async def generate(self, params: dict) -> bytes:
        params['steps'] = 20
        params['resolution'] = '512x512'
        return await engine.generate(params)

class QualityStrategy(GenerationStrategy):
    """高质量生成：高分辨率，多步数"""
    async def generate(self, params: dict) -> bytes:
        params['steps'] = 50
        params['resolution'] = '1024x1024'
        return await engine.generate(params)

# 根据用户等级选择策略
def get_strategy(user: User) -> GenerationStrategy:
    if user.is_premium:
        return QualityStrategy()
    return FastStrategy()
```

---

*本文档最后更新：2026-07-18*
