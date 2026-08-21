# 剧本编排模块

> 本文档详细说明剧本模块的功能设计、数据结构、智能生成与编辑器实现。

---

## 一、模块概述

### 1.1 功能定位
剧本模块是漫剧创作的"导演"，负责将故事大纲转化为结构化的分镜剧本。支持AI智能生成与人工编辑相结合，产出可直接用于画面生成的剧本数据。

### 1.2 核心能力
| 能力 | 描述 | 技术方案 |
|------|------|----------|
| 智能剧本生成 | 根据大纲自动生成完整剧本 | LLM (DeepSeek/GPT) + 提示词工程 |
| 剧本编辑器 | 可视化剧本编辑 | 富文本编辑器 + 结构化数据 |
| 对话管理 | 角色对话与情绪标注 | 角色关联 + 情绪标签系统 |
| 剧情结构 | 三幕式/起承转合结构 | 剧情模板 + 节奏分析 |
| 剧本解析 | 自动提取分镜信息 | NLP + 规则匹配 |

---

## 二、数据模型

```python
# backend/app/models/script.py
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

class Script(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """剧本实体"""
    __tablename__ = "scripts"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False, index=True)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=False)
    title = Column(String(200), nullable=False, comment="剧本标题")
    description = Column(Text, comment="剧本简介")
    
    # 剧本结构
    structure = Column(String(50), default="three_act", 
                       comment="结构: three_act/four_act/hero_journey/free")
    genre = Column(String(50), comment="类型: romance/action/mystery/comedy/drama")
    target_audience = Column(String(50), comment="目标受众")
    
    # 剧本内容
    outline = Column(Text, comment="故事大纲")
    total_scenes = Column(Integer, default=0, comment="总场景数")
    total_duration = Column(Integer, default=0, comment="预计时长（秒）")
    
    # 状态
    status = Column(String(20), default="draft", 
                    comment="draft/generating/completed/published")
    
    # 元数据
    tags = Column(JSON, default=[])
    characters = Column(JSON, default=[], comment="涉及的角色ID列表")

class Scene(Base, UUIDMixin, TimestampMixin):
    """场景（剧本中的一个场景）"""
    __tablename__ = "script_scenes"
    
    script_id = Column(UUID, ForeignKey('scripts.id'), nullable=False, index=True)
    scene_number = Column(Integer, nullable=False, comment="场景序号")
    title = Column(String(200), comment="场景标题")
    
    # 场景信息
    location = Column(String(200), comment="地点")
    time_of_day = Column(String(50), comment="时间")
    description = Column(Text, comment="场景描述")
    
    # 情绪氛围
    mood = Column(String(50), comment="情绪氛围")
    intensity = Column(Integer, default=5, comment="紧张度 1-10")
    
    # 关联
    scene_bg_id = Column(UUID, ForeignKey('scenes.id'), nullable=True, 
                         comment="关联的背景场景ID")
    
    # 排序
    order_index = Column(Integer, default=0)

class Dialogue(Base, UUIDMixin, TimestampMixin):
    """对话（场景中的对话）"""
    __tablename__ = "dialogues"
    
    scene_id = Column(UUID, ForeignKey('script_scenes.id'), nullable=False, index=True)
    character_id = Column(UUID, ForeignKey('characters.id'), nullable=True, 
                          comment="说话角色，None表示旁白")
    character_name = Column(String(100), comment="角色名称（冗余）")
    
    # 对话内容
    content = Column(Text, nullable=False, comment="对话内容")
    emotion = Column(String(50), comment="情绪: happy/sad/angry/surprised/neutral")
    action = Column(Text, comment="动作描述")
    
    # 对话气泡配置
    bubble_type = Column(String(50), default="normal", 
                         comment="normal/shout/whisper/thought/narration")
    bubble_position = Column(String(50), default="right", 
                             comment="left/right/center")
    
    # 时长
    duration = Column(Float, default=2.0, comment="预计时长（秒）")
    
    order_index = Column(Integer, default=0)

class ScriptTemplate(Base, UUIDMixin, TimestampMixin):
    """剧本模板"""
    __tablename__ = "script_templates"
    
    name = Column(String(200), nullable=False)
    genre = Column(String(50), nullable=False)
    description = Column(Text)
    
    # 模板结构
    structure = Column(JSON, comment="剧本结构定义")
    prompt_template = Column(Text, comment="AI生成提示词模板")
    sample_outline = Column(Text, comment="示例大纲")
    
    is_premium = Column(Boolean, default=False)
    usage_count = Column(Integer, default=0)
```

---

## 三、服务层设计

### 3.1 剧本服务

```python
# backend/app/services/script_service.py
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.script import Script, Scene, Dialogue
from app.core.exceptions import ScriptNotFoundError

class ScriptService:
    """剧本服务：管理剧本全生命周期"""
    
    def __init__(
        self,
        db: Session,
        llm_client: 'LLMClient'  # 大语言模型客户端
    ):
        self.db = db
        self.llm_client = llm_client
    
    async def generate_script(
        self,
        user_id: str,
        project_id: str,
        generation_config: dict
    ) -> Script:
        """
        AI智能生成剧本
        
        流程：
        1. 根据大纲生成剧本结构
        2. 逐场景生成详细内容
        3. 为每个场景生成对话
        4. 标注情绪与动作
        """
        # 1. 构建生成提示词
        prompt = self._build_generation_prompt(generation_config)
        
        # 2. 调用LLM生成剧本结构
        script_structure = await self.llm_client.generate(
            prompt=prompt,
            system_prompt=self._get_system_prompt(),
            temperature=0.7,
            max_tokens=4000
        )
        
        # 3. 解析LLM输出
        parsed = self._parse_script_response(script_structure)
        
        # 4. 创建剧本记录
        script = Script(
            user_id=user_id,
            project_id=project_id,
            title=parsed['title'],
            description=parsed['description'],
            structure=generation_config.get('structure', 'three_act'),
            genre=generation_config.get('genre', 'drama'),
            outline=generation_config.get('outline', ''),
            total_scenes=len(parsed['scenes']),
            status='completed',
            characters=parsed.get('characters', [])
        )
        self.db.add(script)
        self.db.flush()
        
        # 5. 创建场景与对话
        for idx, scene_data in enumerate(parsed['scenes']):
            scene = Scene(
                script_id=script.id,
                scene_number=idx + 1,
                title=scene_data.get('title', f'场景 {idx+1}'),
                location=scene_data.get('location', ''),
                time_of_day=scene_data.get('time_of_day', 'day'),
                description=scene_data.get('description', ''),
                mood=scene_data.get('mood', 'neutral'),
                intensity=scene_data.get('intensity', 5),
                order_index=idx
            )
            self.db.add(scene)
            self.db.flush()
            
            # 创建对话
            for didx, dialogue_data in enumerate(scene_data.get('dialogues', [])):
                dialogue = Dialogue(
                    scene_id=scene.id,
                    character_name=dialogue_data.get('character', '旁白'),
                    content=dialogue_data.get('content', ''),
                    emotion=dialogue_data.get('emotion', 'neutral'),
                    action=dialogue_data.get('action', ''),
                    bubble_type=dialogue_data.get('bubble_type', 'normal'),
                    duration=dialogue_data.get('duration', 2.0),
                    order_index=didx
                )
                self.db.add(dialogue)
        
        self.db.commit()
        self.db.refresh(script)
        
        return script
    
    def _build_generation_prompt(self, config: dict) -> str:
        """构建剧本生成提示词"""
        outline = config.get('outline', '')
        genre = config.get('genre', '日常')
        structure = config.get('structure', 'three_act')
        target_scenes = config.get('target_scenes', 10)
        characters = config.get('characters', [])
        
        prompt = f"""
请根据以下信息创作一个漫剧剧本：

【故事大纲】
{outline}

【类型】{genre}
【结构】{structure}
【目标场景数】{target_scenes}个场景

【主要角色】
{self._format_characters(characters)}

请按以下JSON格式输出剧本：
{{
    "title": "剧本标题",
    "description": "一句话简介",
    "characters": ["角色1", "角色2"],
    "scenes": [
        {{
            "title": "场景标题",
            "location": "地点",
            "time_of_day": "day/dusk/night",
            "description": "场景环境描述（用于画面生成）",
            "mood": "happy/sad/tense/mysterious",
            "intensity": 1-10,
            "dialogues": [
                {{
                    "character": "角色名",
                    "content": "对话内容",
                    "emotion": "happy/sad/angry/surprised/neutral",
                    "action": "动作描述（可选）",
                    "bubble_type": "normal/shout/whisper/thought",
                    "duration": 2.0
                }}
            ]
        }}
    ]
}}

要求：
1. 剧情紧凑，有起承转合
2. 对话自然，符合角色性格
3. 每个场景有明确的情绪氛围
4. 场景描述详细，便于AI生成画面
5. 对话包含情绪标注和动作描述
"""
        return prompt
    
    def _get_system_prompt(self) -> str:
        """系统提示词"""
        return (
            "你是一位专业的漫剧编剧，擅长创作引人入胜的故事。"
            "你的剧本结构清晰、对话生动、情绪丰富。"
            "请严格按照JSON格式输出，不要添加额外说明。"
        )
    
    def _format_characters(self, characters: list) -> str:
        """格式化角色信息"""
        if not characters:
            return "（待定，请自行创作角色）"
        
        lines = []
        for char in characters:
            lines.append(f"- {char.get('name', '未命名')}: {char.get('description', '')}")
        return '\n'.join(lines)
    
    def _parse_script_response(self, response: str) -> dict:
        """解析LLM生成的剧本"""
        import json
        import re
        
        # 尝试提取JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # 解析失败，返回默认结构
        return {
            'title': '未命名剧本',
            'description': '',
            'characters': [],
            'scenes': [{
                'title': '场景 1',
                'dialogues': [{
                    'character': '旁白',
                    'content': response[:200],
                    'emotion': 'neutral'
                }]
            }]
        }
    
    async def update_scene(
        self,
        scene_id: str,
        updates: dict
    ) -> Scene:
        """更新场景"""
        scene = self.db.query(Scene).filter_by(id=scene_id).first()
        if not scene:
            raise ValueError("场景不存在")
        
        for key, value in updates.items():
            if hasattr(scene, key):
                setattr(scene, key, value)
        
        self.db.commit()
        self.db.refresh(scene)
        return scene
    
    async def add_dialogue(
        self,
        scene_id: str,
        dialogue_data: dict
    ) -> Dialogue:
        """添加对话"""
        # 获取当前最大order_index
        max_order = self.db.query(Dialogue).filter_by(scene_id=scene_id).count()
        
        dialogue = Dialogue(
            scene_id=scene_id,
            order_index=max_order,
            **dialogue_data
        )
        self.db.add(dialogue)
        self.db.commit()
        self.db.refresh(dialogue)
        return dialogue
    
    async def parse_to_storyboard(self, script_id: str) -> list:
        """
        将剧本解析为分镜数据
        
        每个对话 + 场景描述 = 一个分镜
        """
        script = await self.get_script(script_id)
        scenes = self.db.query(Scene).filter_by(script_id=script_id)\
            .order_by(Scene.order_index).all()
        
        storyboard_data = []
        frame_idx = 0
        
        for scene in scenes:
            dialogues = self.db.query(Dialogue).filter_by(scene_id=scene.id)\
                .order_by(Dialogue.order_index).all()
            
            if not dialogues:
                # 无对话的场景，生成环境镜头
                storyboard_data.append({
                    'frame_index': frame_idx,
                    'scene_id': scene.id,
                    'shot_type': 'wide',  # 全景
                    'description': scene.description,
                    'dialogue': None,
                    'duration': 3.0
                })
                frame_idx += 1
            else:
                for dialogue in dialogues:
                    # 根据情绪推荐镜头类型
                    shot_type = self._recommend_shot_type(
                        dialogue.emotion, 
                        dialogue.bubble_type
                    )
                    
                    storyboard_data.append({
                        'frame_index': frame_idx,
                        'scene_id': scene.id,
                        'shot_type': shot_type,
                        'description': scene.description,
                        'dialogue': {
                            'character': dialogue.character_name,
                            'content': dialogue.content,
                            'emotion': dialogue.emotion,
                            'action': dialogue.action
                        },
                        'duration': dialogue.duration
                    })
                    frame_idx += 1
        
        return storyboard_data
    
    def _recommend_shot_type(
        self,
        emotion: str,
        bubble_type: str
    ) -> str:
        """根据情绪和气泡类型推荐镜头类型"""
        if bubble_type == 'shout':
            return 'close_up'  # 特写
        elif bubble_type == 'whisper':
            return 'medium_close'  # 中特写
        elif emotion in ['angry', 'surprised']:
            return 'close_up'  # 特写
        elif emotion in ['sad']:
            return 'medium'  # 中景
        else:
            return 'medium_wide'  # 中远景
```

---

## 四、前端剧本编辑器

```typescript
// frontend/src/features/script/ScriptEditor.tsx
import { useState } from 'react';
import { Card, Input, Button, List, Tag, Space } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';
import { useScript, useUpdateScene, useAddDialogue } from './hooks/useScripts';

const { TextArea } = Input;

const EMOTION_COLORS: Record<string, string> = {
  happy: 'green',
  sad: 'blue',
  angry: 'red',
  surprised: 'orange',
  neutral: 'default',
};

export function ScriptEditor({ scriptId }: { scriptId: string }) {
  const { data: script, isLoading } = useScript(scriptId);
  const updateScene = useUpdateScene();
  const addDialogue = useAddDialogue();
  
  if (isLoading) return <div>加载中...</div>;
  
  return (
    <div className="script-editor">
      {/* 剧本头部信息 */}
      <Card className="mb-4">
        <h2>{script.title}</h2>
        <p className="text-gray-500">{script.description}</p>
        <Space>
          <Tag color="blue">{script.genre}</Tag>
          <Tag>{script.total_scenes} 场景</Tag>
        </Space>
      </Card>
      
      {/* 场景列表 */}
      {script.scenes.map((scene, index) => (
        <Card
          key={scene.id}
          title={`场景 ${index + 1}: ${scene.title}`}
          className="mb-4"
        >
          {/* 场景信息 */}
          <div className="mb-4">
            <Space>
              <Tag>{scene.location}</Tag>
              <Tag>{scene.time_of_day}</Tag>
              <Tag color={scene.mood === 'happy' ? 'green' : 'orange'}>
                {scene.mood}
              </Tag>
            </Space>
          </div>
          
          {/* 场景描述 */}
          <TextArea
            value={scene.description}
            onChange={(e) => updateScene.mutate({
              sceneId: scene.id,
              updates: { description: e.target.value }
            })}
            autoSize={{ minRows: 2 }}
            className="mb-4"
          />
          
          {/* 对话列表 */}
          <List
            dataSource={scene.dialogues}
            renderItem={(dialogue, didx) => (
              <List.Item>
                <div className="flex items-start gap-3 w-full">
                  <div className="flex-shrink-0">
                    <Tag color={EMOTION_COLORS[dialogue.emotion]}>
                      {dialogue.character_name}
                    </Tag>
                  </div>
                  <div className="flex-1">
                    <div className="mb-1">{dialogue.content}</div>
                    {dialogue.action && (
                      <div className="text-xs text-gray-400 italic">
                        ({dialogue.action})
                      </div>
                    )}
                  </div>
                </div>
              </List.Item>
            )}
          />
          
          {/* 添加对话 */}
          <Button
            icon={<PlusOutlined />}
            onClick={() => addDialogue.mutate({
              sceneId: scene.id,
              dialogueData: {
                character_name: '新角色',
                content: '输入对话内容...',
                emotion: 'neutral'
              }
            })}
          >
            添加对话
          </Button>
        </Card>
      ))}
    </div>
  );
}
```

---

## 五、API接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/scripts | 创建剧本 |
| POST | /api/v1/scripts/generate | AI生成剧本 |
| GET | /api/v1/scripts/{id} | 获取剧本详情 |
| PUT | /api/v1/scripts/{id} | 更新剧本 |
| GET | /api/v1/scripts/{id}/scenes | 获取场景列表 |
| PUT | /api/v1/scenes/{id} | 更新场景 |
| POST | /api/v1/scenes/{id}/dialogues | 添加对话 |
| PUT | /api/v1/dialogues/{id} | 更新对话 |
| DELETE | /api/v1/dialogues/{id} | 删除对话 |
| GET | /api/v1/scripts/{id}/storyboard | 解析为分镜数据 |

---

*本文档最后更新：2026-07-18*
