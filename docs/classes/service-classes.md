# 服务类说明

> 本文档汇总业务服务层的所有服务类定义与关键方法。

---

## 一、服务层架构

```
BaseService (抽象基类)
├── UserService          用户服务
├── ProjectService       项目服务
├── CharacterService     角色服务
├── SceneService         场景服务
├── ScriptService        剧本服务
├── StoryboardService    分镜服务
├── AudioService         音频服务
├── RenderService        渲染服务
├── ExportService        导出服务
├── BillingService       计费服务
├── CollabService        协作服务
└── AssetService         素材服务
```

---

## 二、BaseService 基类

```python
# backend/app/services/base_service.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List
from sqlalchemy.orm import Session

T = TypeVar('T')

class BaseService(ABC, Generic[T]):
    """业务服务基类"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def create(self, data: dict) -> T:
        """创建实体"""
        pass
    
    async def get_by_id(self, entity_id: str) -> Optional[T]:
        """根据ID获取"""
        pass
    
    async def update(self, entity_id: str, data: dict) -> Optional[T]:
        """更新实体"""
        pass
    
    async def delete(self, entity_id: str, soft: bool = True) -> bool:
        """删除实体（默认软删除）"""
        pass
    
    async def list(self, filters: dict = None, page: int = 1, 
                   size: int = 20) -> tuple[List[T], int]:
        """分页列表"""
        pass
```

---

## 三、核心服务类

### 3.1 UserService 用户服务

```python
class UserService(BaseService[User]):
    """用户服务"""
    
    async def register(self, username: str, email: str, password: str) -> User:
        """用户注册"""
    
    async def login(self, email: str, password: str) -> tuple[User, str]:
        """用户登录，返回(user, token)"""
    
    async def update_profile(self, user_id: str, data: dict) -> User:
        """更新资料"""
    
    async def change_password(self, user_id: str, old_pwd: str, new_pwd: str) -> bool:
        """修改密码"""
    
    async def verify_email(self, token: str) -> bool:
        """邮箱验证"""
    
    async def get_user_plan(self, user_id: str) -> dict:
        """获取用户订阅计划"""
```

### 3.2 CharacterService 角色服务

```python
class CharacterService(BaseService[Character]):
    """角色服务 - 详见角色模块文档"""
    
    async def create_character(self, user_id: str, character_data: dict) -> Character:
        """
        创建角色
        流程：校验积分 → 生成形象 → 提取特征 → 保存 → 扣费
        """
    
    async def generate_variant(self, character_id: str, 
                                variant_type: str, config: dict) -> CharacterVariant:
        """生成角色变体（表情/姿势/服装）"""
    
    async def train_character_lora(self, character_id: str, 
                                    training_images: list) -> str:
        """训练角色LoRA，返回任务ID"""
    
    async def find_similar(self, feature_vector: np.ndarray, 
                           threshold: float = 0.85) -> list:
        """查找相似角色"""
    
    def _build_character_prompt(self, data: dict) -> str:
        """构建角色生成提示词"""
```

### 3.3 SceneService 场景服务

```python
class SceneService(BaseService[Scene]):
    """场景服务 - 详见场景模块文档"""
    
    async def generate_scene(self, user_id: str, scene_data: dict) -> Scene:
        """生成场景"""
    
    async def generate_scene_variant(self, scene_id: str, 
                                      variant_config: dict) -> str:
        """生成场景变体（不同时间/天气）"""
    
    async def apply_template(self, user_id: str, template_id: str, 
                              customizations: dict) -> Scene:
        """应用场景模板"""
    
    def _build_scene_prompt(self, data: dict) -> str:
        """构建场景提示词"""
```

### 3.4 ScriptService 剧本服务

```python
class ScriptService(BaseService[Script]):
    """剧本服务 - 详见剧本模块文档"""
    
    async def generate_script(self, user_id: str, project_id: str, 
                               generation_config: dict) -> Script:
        """AI生成剧本"""
    
    async def update_scene(self, scene_id: str, updates: dict) -> Scene:
        """更新场景"""
    
    async def add_dialogue(self, scene_id: str, dialogue_data: dict) -> Dialogue:
        """添加对话"""
    
    async def parse_to_storyboard(self, script_id: str) -> list:
        """将剧本解析为分镜数据"""
    
    def _build_generation_prompt(self, config: dict) -> str:
        """构建LLM生成提示词"""
    
    def _parse_script_response(self, response: str) -> dict:
        """解析LLM响应"""
```

### 3.5 StoryboardService 分镜服务

```python
class StoryboardService(BaseService[StoryboardFrame]):
    """分镜服务 - 详见分镜模块文档"""
    
    async def auto_generate_storyboard(self, script_id: str, 
                                        options: dict = None) -> List[StoryboardFrame]:
        """自动生成分镜"""
    
    def _create_establishing_shot(self, scene: Scene, 
                                   frame_number: int) -> StoryboardFrame:
        """创建建立镜头"""
    
    def _create_dialogue_frame(self, scene: Scene, dialogue: Dialogue,
                                frame_number: int) -> StoryboardFrame:
        """创建对话分镜帧"""
    
    def _build_prompt(self, shot_type: str, camera_angle: str,
                      description: str, mood: str) -> str:
        """构建生成提示词"""
```

### 3.6 AudioService 音频服务

```python
class AudioService(BaseService[AudioTrack]):
    """音频服务 - 详见配音模块文档"""
    
    async def synthesize_voiceover(self, project_id: str, dialogue_id: str,
                                    voice_profile_id: str) -> AudioTrack:
        """生成配音"""
    
    async def batch_synthesize(self, project_id: str, 
                                frame_ids: list) -> List[AudioTrack]:
        """批量生成配音"""
    
    async def match_sound_effects(self, frame_id: str, 
                                   scene_description: str) -> List[str]:
        """智能匹配音效"""
    
    def _generate_srt(self, word_boundaries: list) -> str:
        """生成SRT字幕"""
    
    def _extract_audio_keywords(self, description: str) -> list:
        """提取音频关键词"""
```

### 3.7 RenderService 渲染服务

```python
class RenderService(BaseService[RenderTask]):
    """渲染服务 - 详见渲染模块文档"""
    
    async def create_render_task(self, user_id: str, project_id: str,
                                  script_id: str, config: dict) -> RenderTask:
        """创建渲染任务"""
    
    async def get_render_progress(self, task_id: str) -> dict:
        """获取渲染进度"""
    
    async def cancel_render(self, task_id: str) -> bool:
        """取消渲染"""
    
    def _calculate_credits(self, frame_count: int, config: dict) -> int:
        """计算渲染积分"""
```

### 3.8 BillingService 计费服务

```python
class BillingService:
    """计费服务"""
    
    # 积分消耗规则
    CREDIT_COSTS = {
        'create_character': 10,
        'generate_scene': 5,
        'generate_script': 8,
        'generate_frame': 2,
        'render_video': 3,  # 每帧
        'train_lora': 50,
        'tts_synthesize': 1,
    }
    
    async def check_credits(self, user_id: str, cost: int) -> bool:
        """检查积分是否充足"""
    
    async def deduct_credits(self, user_id: str, amount: int, 
                              reason: str, related_id: str = None) -> bool:
        """扣除积分"""
    
    async def recharge(self, user_id: str, amount: int, 
                        payment_method: str) -> dict:
        """充值积分"""
    
    async def get_usage_stats(self, user_id: str, 
                               start_date: str, end_date: str) -> dict:
        """获取用量统计"""
    
    async def subscribe(self, user_id: str, plan: str, 
                         payment_method: str) -> Subscription:
        """订阅计划"""
```

### 3.9 CollabService 协作服务

```python
class CollabService:
    """实时协作服务"""
    
    async def join_session(self, project_id: str, user_id: str) -> str:
        """加入协作会话"""
    
    async def leave_session(self, project_id: str, user_id: str):
        """离开协作会话"""
    
    async def broadcast_change(self, project_id: str, change: dict):
        """广播内容变更"""
    
    async def sync_cursor(self, project_id: str, user_id: str, position: dict):
        """同步光标位置"""
    
    async def resolve_conflict(self, changes: list) -> dict:
        """解决编辑冲突（OT算法）"""
    
    async def get_active_users(self, project_id: str) -> list:
        """获取在线协作用户"""
```

### 3.10 AssetService 素材服务

```python
class AssetService:
    """素材资源管理服务"""
    
    async def upload(self, user_id: str, file: bytes, 
                     file_type: str, metadata: dict = None) -> Asset:
        """上传素材"""
    
    async def search(self, query: str, filters: dict = None, 
                     page: int = 1, size: int = 20) -> tuple[list, int]:
        """搜索素材"""
    
    async def categorize(self, asset_id: str, category: str):
        """素材分类"""
    
    async def get_user_assets(self, user_id: str, asset_type: str = None) -> list:
        """获取用户素材"""
    
    async def delete_asset(self, asset_id: str, user_id: str) -> bool:
        """删除素材"""
```

---

## 四、服务依赖关系

```python
# backend/app/core/dependencies.py
from app.services import *

def get_character_service(db: Session = Depends(get_db)):
    """获取角色服务（依赖注入）"""
    image_engine = ImageGenEngine()
    consistency_engine = CharacterConsistencyEngine(image_engine)
    billing_service = BillingService(db)
    return CharacterService(db, image_engine, consistency_engine, billing_service)

def get_script_service(db: Session = Depends(get_db)):
    """获取剧本服务"""
    llm_client = LLMClient()
    return ScriptService(db, llm_client)

def get_render_service(db: Session = Depends(get_db)):
    """获取渲染服务"""
    return RenderService(db)
```

---

## 五、服务调用示例

```python
# 完整的漫剧生成流程
async def generate_comic_full_flow(user_id: str, outline: str):
    """完整漫剧生成流程"""
    
    # 1. 创建项目
    project_service = ProjectService(db)
    project = await project_service.create({
        'user_id': user_id,
        'name': '新漫剧项目'
    })
    
    # 2. 生成剧本
    script_service = ScriptService(db, llm_client)
    script = await script_service.generate_script(
        user_id=user_id,
        project_id=project.id,
        generation_config={'outline': outline, 'target_scenes': 10}
    )
    
    # 3. 自动分镜
    storyboard_service = StoryboardService(db)
    frames = await storyboard_service.auto_generate_storyboard(script.id)
    
    # 4. 批量生成配音
    audio_service = AudioService(db)
    voiceover_tracks = await audio_service.batch_synthesize(
        project.id, [f.id for f in frames]
    )
    
    # 5. 创建渲染任务
    render_service = RenderService(db)
    render_task = await render_service.create_render_task(
        user_id=user_id,
        project_id=project.id,
        script_id=script.id,
        config={
            'resolution': '1920x1080',
            'fps': 24,
            'format': 'mp4',
            'quality': 'high'
        }
    )
    
    return {
        'project_id': project.id,
        'script_id': script.id,
        'frame_count': len(frames),
        'render_task_id': render_task.id
    }
```

---

*本文档最后更新：2026-07-18*
