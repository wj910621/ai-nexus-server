# 分镜生成模块

> 本文档详细说明分镜模块的功能设计、镜头语言系统与自动分镜算法。

---

## 一、模块概述

### 1.1 功能定位
分镜模块将剧本转化为具体的画面构图方案，决定每个镜头的景别、角度、构图、角色站位等视觉要素，是连接剧本与画面生成的关键桥梁。

### 1.2 核心能力
| 能力 | 描述 | 技术方案 |
|------|------|----------|
| 自动分镜 | 根据剧本自动规划分镜 | LLM + 镜头语言规则引擎 |
| 镜头语言 | 景别/角度/运动方式 | 专业摄影知识库 |
| 构图优化 | AI推荐最佳构图 | 构图规则 + 美学评分 |
| 分镜时间轴 | 可视化时间轴管理 | 时间轴编辑器 |
| 手动调整 | 支持微调每个分镜 | 拖拽编辑 + 参数调整 |

---

## 二、镜头语言系统

### 2.1 景别定义

```python
# backend/app/engines/layout_engine.py

class ShotType:
    """镜头景别"""
    EXTREME_WIDE = 'extreme_wide'  # 大远景：交代环境
    WIDE = 'wide'                  # 远景：展示全貌
    MEDIUM_WIDE = 'medium_wide'    # 中远景：人物+环境
    MEDIUM = 'medium'              # 中景：人物上半身
    MEDIUM_CLOSE = 'medium_close'  # 中特写：胸部以上
    CLOSE_UP = 'close_up'          # 特写：面部
    EXTREME_CLOSE = 'extreme_close' # 大特写：眼睛/细节
    
    # 景别对应的生成提示词
    PROMPTS = {
        'extreme_wide': 'extreme wide shot, establishing shot, vast landscape, tiny figures',
        'wide': 'wide shot, full body, environment visible',
        'medium_wide': 'medium wide shot, cowboy shot, from knees up',
        'medium': 'medium shot, waist up, conversation distance',
        'medium_close': 'medium close up, chest up',
        'close_up': 'close up shot, face focus, head and shoulders',
        'extreme_close': 'extreme close up, eye detail, macro shot'
    }

class CameraAngle:
    """摄像机角度"""
    EYE_LEVEL = 'eye_level'    # 平视
    HIGH_ANGLE = 'high_angle'  # 俯拍
    LOW_ANGLE = 'low_angle'    # 仰拍
    BIRDS_EYE = 'birds_eye'    # 鸟瞰
    WORMS_EYE = 'worms_eye'    # 虫眼
    DUTCH = 'dutch'            # 倾斜
    
    PROMPTS = {
        'eye_level': 'eye level shot',
        'high_angle': 'high angle shot, looking down',
        'low_angle': 'low angle shot, looking up, imposing',
        'birds_eye': "bird's eye view, top-down",
        'worms_eye': "worm's eye view, from below",
        'dutch': 'dutch angle, tilted, dramatic'
    }

class Composition:
    """构图方式"""
    RULE_OF_THIRDS = 'rule_of_thirds'    # 三分法
    CENTER = 'center'                      # 居中
    SYMMETRY = 'symmetry'                  # 对称
    LEADING_LINES = 'leading_lines'        # 引导线
    FRAME_WITHIN = 'frame_within'          # 框中框
    GOLDEN_RATIO = 'golden_ratio'          # 黄金比例
    
    PROMPTS = {
        'rule_of_thirds': 'rule of thirds composition',
        'center': 'centered composition',
        'symmetry': 'symmetrical composition',
        'leading_lines': 'leading lines composition',
        'frame_within': 'frame within frame composition',
        'golden_ratio': 'golden ratio composition'
    }
```

### 2.2 自动分镜规则

```python
class StoryboardRules:
    """分镜规则引擎"""
    
    @staticmethod
    def recommend_shot_type(
        emotion: str,
        bubble_type: str,
        dialogue_content: str,
        scene_intensity: int
    ) -> str:
        """
        根据对话情绪推荐镜头景别
        
        规则：
        - 喊叫/愤怒/惊讶 → 特写（强调情绪）
        - 低语/思考 → 中特写（营造亲密感）
        - 旁白/环境描述 → 远景（交代环境）
        - 日常对话 → 中景（自然距离）
        - 高紧张度 → 倾斜角度（增加压迫感）
        """
        if bubble_type == 'shout':
            return ShotType.CLOSE_UP
        elif bubble_type == 'whisper':
            return ShotType.MEDIUM_CLOSE
        elif bubble_type == 'thought':
            return ShotType.MEDIUM_CLOSE
        elif bubble_type == 'narration':
            return ShotType.WIDE
        
        if emotion in ['angry', 'surprised', 'fearful']:
            return ShotType.CLOSE_UP
        elif emotion in ['sad', 'contemplative']:
            return ShotType.MEDIUM_CLOSE
        elif emotion in ['happy', 'neutral']:
            return ShotType.MEDIUM
        
        return ShotType.MEDIUM
    
    @staticmethod
    def recommend_camera_angle(
        shot_type: str,
        character_role: str,
        scene_mood: str
    ) -> str:
        """
        推荐摄像机角度
        
        规则：
        - 权威角色/反派 → 仰拍（增加压迫感）
        - 弱势角色 → 俯拍（增加脆弱感）
        - 正面对抗 → 平视（公平感）
        - 混乱/紧张 → 倾斜（不安感）
        """
        if character_role in ['villain', 'authority', 'boss']:
            return CameraAngle.LOW_ANGLE
        elif character_role in ['victim', 'child', 'weak']:
            return CameraAngle.HIGH_ANGLE
        elif scene_mood in ['chaotic', 'tense', 'unstable']:
            return CameraAngle.DUTCH
        else:
            return CameraAngle.EYE_LEVEL
    
    @staticmethod
    def recommend_composition(
        shot_type: str,
        num_characters: int,
        scene_description: str
    ) -> str:
        """推荐构图方式"""
        if num_characters == 1:
            if shot_type in [ShotType.CLOSE_UP, ShotType.EXTREME_CLOSE]:
                return Composition.CENTER
            else:
                return Composition.RULE_OF_THIRDS
        elif num_characters == 2:
            return Composition.SYMMETRY  # 对话场景对称构图
        else:
            return Composition.RULE_OF_THIRDS
```

---

## 三、数据模型

```python
# backend/app/models/storyboard.py
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin

class StoryboardFrame(Base, UUIDMixin, TimestampMixin):
    """分镜帧"""
    __tablename__ = "storyboard_frames"
    
    script_id = Column(UUID, ForeignKey('scripts.id'), nullable=False, index=True)
    scene_id = Column(UUID, ForeignKey('script_scenes.id'), nullable=True)
    
    # 帧序号
    frame_number = Column(Integer, nullable=False, comment="帧序号")
    
    # 镜头信息
    shot_type = Column(String(50), comment="景别")
    camera_angle = Column(String(50), comment="摄像机角度")
    composition = Column(String(50), comment="构图")
    camera_movement = Column(String(50), comment="镜头运动: static/pan/zoom/tracking")
    
    # 画面内容
    description = Column(Text, comment="画面描述（用于AI生成）")
    prompt = Column(Text, comment="完整生成提示词")
    negative_prompt = Column(Text, comment="负面提示词")
    
    # 角色信息
    characters_in_frame = Column(JSON, default=[], 
                                  comment="画面中的角色配置")
    # 示例: [{"id": "xxx", "position": "left", "expression": "happy", "action": "standing"}]
    
    # 对话
    dialogue_id = Column(UUID, ForeignKey('dialogues.id'), nullable=True)
    
    # 持续时间
    duration = Column(Float, default=2.0, comment="持续时间（秒）")
    
    # 转场
    transition = Column(String(50), default='cut', 
                        comment="转场: cut/fade/dissolve/wipe")
    transition_duration = Column(Float, default=0.5)
    
    # 生成的图像
    generated_image_url = Column(String(500), nullable=True)
    generation_status = Column(String(20), default='pending',
                               comment="pending/generating/completed/failed")
    
    # 顺序
    order_index = Column(Integer, default=0)
```

---

## 四、分镜服务

```python
# backend/app/services/storyboard_service.py
from typing import List
from sqlalchemy.orm import Session
from app.models.storyboard import StoryboardFrame
from app.models.script import Scene, Dialogue
from app.engines.layout_engine import (
    ShotType, CameraAngle, Composition, StoryboardRules
)

class StoryboardService:
    """分镜服务"""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def auto_generate_storyboard(
        self,
        script_id: str,
        options: dict = None
    ) -> List[StoryboardFrame]:
        """
        自动生成分镜
        
        流程：
        1. 获取剧本所有场景与对话
        2. 为每段对话规划镜头
        3. 添加环境镜头（场景切换时）
        4. 应用镜头语言规则
        5. 生成画面提示词
        """
        options = options or {}
        
        # 获取场景列表
        scenes = self.db.query(Scene).filter_by(script_id=script_id)\
            .order_by(Scene.order_index).all()
        
        frames = []
        frame_number = 0
        
        for scene_idx, scene in enumerate(scenes):
            # 场景开头添加建立镜头（远景交代环境）
            if scene_idx == 0 or self._is_location_change(scenes, scene_idx):
                frames.append(self._create_establishing_shot(
                    scene, frame_number
                ))
                frame_number += 1
            
            # 获取该场景的所有对话
            dialogues = self.db.query(Dialogue).filter_by(scene_id=scene.id)\
                .order_by(Dialogue.order_index).all()
            
            if not dialogues:
                # 无对话的场景，生成一个环境镜头
                frames.append(self._create_environment_shot(
                    scene, frame_number
                ))
                frame_number += 1
            else:
                # 为每个对话生成分镜
                for dialogue in dialogues:
                    frame = self._create_dialogue_frame(
                        scene, dialogue, frame_number
                    )
                    frames.append(frame)
                    frame_number += 1
        
        # 批量保存
        self.db.add_all(frames)
        self.db.commit()
        
        return frames
    
    def _create_establishing_shot(
        self,
        scene: Scene,
        frame_number: int
    ) -> StoryboardFrame:
        """创建建立镜头（场景开头远景）"""
        return StoryboardFrame(
            script_id=scene.script_id,
            scene_id=scene.id,
            frame_number=frame_number,
            shot_type=ShotType.WIDE,
            camera_angle=CameraAngle.EYE_LEVEL,
            composition=Composition.RULE_OF_THIRDS,
            camera_movement='static',
            description=f"建立镜头：{scene.location}，{scene.description}",
            prompt=self._build_prompt(
                ShotType.WIDE,
                CameraAngle.EYE_LEVEL,
                scene.description,
                scene.mood
            ),
            duration=3.0,
            transition='fade' if frame_number > 0 else 'cut',
            order_index=frame_number
        )
    
    def _create_dialogue_frame(
        self,
        scene: Scene,
        dialogue: Dialogue,
        frame_number: int
    ) -> StoryboardFrame:
        """创建对话分镜帧"""
        # 推荐镜头参数
        shot_type = StoryboardRules.recommend_shot_type(
            emotion=dialogue.emotion,
            bubble_type=dialogue.bubble_type,
            dialogue_content=dialogue.content,
            scene_intensity=scene.intensity
        )
        
        camera_angle = StoryboardRules.recommend_camera_angle(
            shot_type=shot_type,
            character_role=dialogue.character_name,  # 简化处理
            scene_mood=scene.mood
        )
        
        composition = StoryboardRules.recommend_composition(
            shot_type=shot_type,
            num_characters=1,
            scene_description=scene.description
        )
        
        # 构建画面描述
        description = self._build_frame_description(
            scene, dialogue, shot_type
        )
        
        # 构建AI生成提示词
        prompt = self._build_prompt(
            shot_type, camera_angle, description, scene.mood
        )
        
        return StoryboardFrame(
            script_id=scene.script_id,
            scene_id=scene.id,
            frame_number=frame_number,
            shot_type=shot_type,
            camera_angle=camera_angle,
            composition=composition,
            camera_movement='static',
            description=description,
            prompt=prompt,
            dialogue_id=dialogue.id,
            characters_in_frame=[{
                'name': dialogue.character_name,
                'expression': dialogue.emotion,
                'action': dialogue.action
            }],
            duration=dialogue.duration,
            transition='cut',
            order_index=frame_number
        )
    
    def _build_frame_description(
        self,
        scene: Scene,
        dialogue: Dialogue,
        shot_type: str
    ) -> str:
        """构建画面描述"""
        parts = []
        
        # 场景环境
        parts.append(f"地点：{scene.location}")
        parts.append(f"时间：{scene.time_of_day}")
        
        # 角色动作
        if dialogue.action:
            parts.append(f"{dialogue.character_name}{dialogue.action}")
        
        # 角色表情
        if dialogue.emotion:
            parts.append(f"表情：{dialogue.emotion}")
        
        # 场景氛围
        if scene.mood:
            parts.append(f"氛围：{scene.mood}")
        
        return '；'.join(parts)
    
    def _build_prompt(
        self,
        shot_type: str,
        camera_angle: str,
        description: str,
        mood: str
    ) -> str:
        """构建AI图像生成提示词"""
        parts = []
        
        # 镜头景别
        parts.append(ShotType.PROMPTS.get(shot_type, ''))
        
        # 摄像机角度
        parts.append(CameraAngle.PROMPTS.get(camera_angle, ''))
        
        # 画面描述
        parts.append(description)
        
        # 氛围
        mood_map = {
            'happy': 'bright, cheerful, warm colors',
            'sad': 'melancholic, desaturated, soft light',
            'tense': 'dramatic lighting, high contrast',
            'mysterious': 'dark, mysterious, low key lighting',
            'romantic': 'soft, romantic, warm glow'
        }
        parts.append(mood_map.get(mood, ''))
        
        # 质量标签
        parts.extend(['masterpiece', 'best quality', 'detailed'])
        
        return ', '.join(filter(None, parts))
    
    def _is_location_change(self, scenes: list, idx: int) -> bool:
        """判断是否场景切换"""
        if idx == 0:
            return True
        return scenes[idx].location != scenes[idx-1].location
```

---

## 五、前端分镜时间轴

```typescript
// frontend/src/features/storyboard/StoryboardTimeline.tsx
import { useRef, useState } from 'react';
import { Card, Tag, Tooltip } from 'antd';
import { 
  PlayCircleOutlined, 
  PauseCircleOutlined 
} from '@ant-design/icons';

const SHOT_TYPE_LABELS: Record<string, string> = {
  extreme_wide: '大远景',
  wide: '远景',
  medium_wide: '中远景',
  medium: '中景',
  medium_close: '中特写',
  close_up: '特写',
  extreme_close: '大特写'
};

export function StoryboardTimeline({ frames }: { frames: Frame[] }) {
  const [selectedFrame, setSelectedFrame] = useState<string | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // 总时长
  const totalDuration = frames.reduce((sum, f) => sum + f.duration, 0);
  
  return (
    <Card 
      title="分镜时间轴"
      extra={
        <button onClick={() => setIsPlaying(!isPlaying)}>
          {isPlaying ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
          {isPlaying ? '暂停' : '播放'}
        </button>
      }
    >
      {/* 时间标尺 */}
      <div className="time-ruler mb-2">
        {Array.from({ length: Math.ceil(totalDuration / 5) }).map((_, i) => (
          <div key={i} className="time-mark">
            {i * 5}s
          </div>
        ))}
      </div>
      
      {/* 分镜帧列表 */}
      <div 
        ref={scrollRef}
        className="frames-container flex gap-2 overflow-x-auto pb-4"
      >
        {frames.map((frame) => (
          <div
            key={frame.id}
            className={`frame-card flex-shrink-0 border rounded cursor-pointer transition-all ${
              selectedFrame === frame.id 
                ? 'border-blue-500 shadow-lg' 
                : 'border-gray-300'
            }`}
            style={{ width: `${frame.duration * 40}px` }}
            onClick={() => setSelectedFrame(frame.id)}
          >
            {/* 帧预览图 */}
            <div className="frame-preview aspect-video bg-gray-100">
              {frame.generated_image_url ? (
                <img 
                  src={frame.generated_image_url} 
                  alt={`Frame ${frame.frame_number}`}
                  className="w-full h-full object-cover"
                />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-400">
                  未生成
                </div>
              )}
            </div>
            
            {/* 帧信息 */}
            <div className="p-2">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold">
                  #{frame.frame_number}
                </span>
                <Tag color="blue" className="text-xs">
                  {SHOT_TYPE_LABELS[frame.shot_type] || frame.shot_type}
                </Tag>
              </div>
              <div className="text-xs text-gray-500 truncate">
                {frame.duration}s
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {/* 选中帧的详情 */}
      {selectedFrame && (
        <FrameDetail frame={frames.find(f => f.id === selectedFrame)!} />
      )}
    </Card>
  );
}
```

---

## 六、API接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/scripts/{id}/storyboard | 自动生成分镜 |
| GET | /api/v1/scripts/{id}/storyboard | 获取分镜列表 |
| PUT | /api/v1/storyboard/frames/{id} | 更新分镜帧 |
| POST | /api/v1/storyboard/frames/{id}/regenerate | 重新生成画面 |
| GET | /api/v1/storyboard/frames/{id}/prompt | 获取生成提示词 |

---

*本文档最后更新：2026-07-18*
