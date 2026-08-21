# 配音音效模块

> 本文档详细说明配音与音效模块的功能设计、TTS引擎集成与音效匹配算法。

---

## 一、模块概述

### 1.1 功能定位
配音音效模块负责将对话文本转化为语音，并为画面匹配合适的背景音乐和音效，实现漫剧的"声画合一"。

### 1.2 核心能力
| 能力 | 描述 | 技术方案 |
|------|------|----------|
| AI语音合成 | 文本转语音，支持多音色 | Edge-TTS（免费）+ VITS（本地） |
| 角色音色定制 | 为每个角色设定独特音色 | 音色库 + 语音克隆 |
| 音效匹配 | 根据场景自动推荐音效 | 场景标签 + 音效库检索 |
| 背景音乐 | 智能匹配BGM | 情绪分析 + 音乐推荐 |
| 字幕生成 | 自动生成时间轴字幕 | TTS时间戳 + SRT格式 |

---

## 二、数据模型

```python
# backend/app/models/audio.py
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin, SoftDeleteMixin

class VoiceProfile(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音色配置"""
    __tablename__ = "voice_profiles"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    character_id = Column(UUID, ForeignKey('characters.id'), nullable=True)
    
    name = Column(String(100), nullable=False, comment="音色名称")
    
    # TTS配置
    engine = Column(String(50), default="edge_tts", 
                    comment="edge_tts/vits/azure/coqui")
    voice_id = Column(String(100), comment="音色ID")
    language = Column(String(10), default="zh-CN", comment="语言")
    
    # 语音参数
    rate = Column(Integer, default=0, comment="语速 -100到100")
    pitch = Column(Integer, default=0, comment="音高 -100到100")
    volume = Column(Integer, default=100, comment="音量 0到100")
    
    # 音色特征
    gender = Column(String(20), comment="male/female")
    age_group = Column(String(20), comment="child/young/adult/elder")
    tone = Column(String(50), comment="音色特征: gentle/deep/bright/sharp")
    
    # 克隆模型（如果是克隆音色）
    clone_model_path = Column(String(500), nullable=True)
    
    is_default = Column(Boolean, default=False)

class AudioTrack(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin):
    """音频轨道"""
    __tablename__ = "audio_tracks"
    
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=False)
    
    track_type = Column(String(50), nullable=False, 
                        comment="voice/bgm/sfx/ambient")
    name = Column(String(200), comment="轨道名称")
    
    # 音频文件
    audio_url = Column(String(500), comment="音频文件URL")
    duration = Column(Float, comment="时长（秒）")
    
    # 时间轴
    start_time = Column(Float, default=0, comment="开始时间")
    end_time = Column(Float, comment="结束时间")
    
    # 关联
    frame_id = Column(UUID, ForeignKey('storyboard_frames.id'), nullable=True)
    dialogue_id = Column(UUID, ForeignKey('dialogues.id'), nullable=True)
    character_id = Column(UUID, ForeignKey('characters.id'), nullable=True)
    voice_profile_id = Column(UUID, ForeignKey('voice_profiles.id'), nullable=True)
    
    # 音量与效果
    volume = Column(Float, default=1.0, comment="音量 0-1")
    fade_in = Column(Float, default=0, comment="淡入时长")
    fade_out = Column(Float, default=0, comment="淡出时长")
    
    # 配置
    config = Column(JSON, default={})
    
    order_index = Column(Integer, default=0)

class SoundEffect(Base, UUIDMixin, TimestampMixin):
    """音效库"""
    __tablename__ = "sound_effects"
    
    name = Column(String(200), nullable=False)
    category = Column(String(50), comment="door/footstep/explosion/rain/wind/etc")
    description = Column(Text)
    
    # 音频文件
    audio_url = Column(String(500), nullable=False)
    duration = Column(Float)
    
    # 标签（用于智能匹配）
    tags = Column(JSON, default=[])
    mood = Column(String(50), comment="情绪标签")
    
    # 商业信息
    is_premium = Column(Boolean, default=False)
    is_original = Column(Boolean, default=True, comment="是否原创（无版权风险）")
    author = Column(String(100))

class BackgroundMusic(Base, UUIDMixin, TimestampMixin):
    """背景音乐库"""
    __tablename__ = "background_music"
    
    title = Column(String(200), nullable=False)
    artist = Column(String(100))
    genre = Column(String(50), comment="pop/classical/electronic/ambient")
    mood = Column(String(50), comment="happy/sad/tense/epic/calm")
    tempo = Column(Integer, comment="BPM")
    
    audio_url = Column(String(500), nullable=False)
    duration = Column(Float)
    
    # 标签
    tags = Column(JSON, default=[])
    suitable_scenes = Column(JSON, default=[], comment="适用场景标签")
    
    is_premium = Column(Boolean, default=False)
    license_type = Column(String(50), default="royalty_free")
```

---

## 三、TTS引擎

```python
# backend/app/engines/tts_engine.py
from abc import ABC, abstractmethod
from typing import Optional
import edge_tts
import asyncio

class ITTSEngine(ABC):
    """TTS引擎抽象接口"""
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        rate: int = 0,
        pitch: int = 0,
        volume: int = 100
    ) -> bytes:
        """语音合成"""
        pass
    
    @abstractmethod
    async def get_voices(self, language: str = "zh-CN") -> list:
        """获取可用音色列表"""
        pass

class EdgeTTSEngine(ITTSEngine):
    """Edge-TTS引擎（免费，质量较好）"""
    
    # 推荐音色映射
    VOICE_MAP = {
        'female_gentle': 'zh-CN-XiaoxiaoNeural',
        'female_bright': 'zh-CN-XiaoyiNeural',
        'female_mature': 'zh-CN-XiaomoNeural',
        'male_gentle': 'zh-CN-YunxiNeural',
        'male_deep': 'zh-CN-YunyangNeural',
        'male_young': 'zh-CN-YunjianNeural',
        'child': 'zh-CN-XiaoyiNeural',
        'elder': 'zh-CN-XiaomoNeural',
    }
    
    async def synthesize(
        self,
        text: str,
        voice_id: str = "zh-CN-XiaoxiaoNeural",
        rate: int = 0,
        pitch: int = 0,
        volume: int = 100
    ) -> bytes:
        """使用Edge-TTS合成语音"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            rate=f"{'+' if rate >= 0 else ''}{rate}%",
            pitch=f"{'+' if pitch >= 0 else ''}{pitch}Hz",
            volume=f"{volume}%"
        )
        
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        return audio_data
    
    async def synthesize_with_timestamps(
        self,
        text: str,
        voice_id: str,
        **kwargs
    ) -> dict:
        """合成语音并返回时间戳（用于字幕生成）"""
        communicate = edge_tts.Communicate(
            text=text,
            voice=voice_id,
            **kwargs
        )
        
        audio_data = b""
        word_boundaries = []
        
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
            elif chunk["type"] == "WordBoundary":
                word_boundaries.append({
                    'text': chunk["text"],
                    'offset': chunk["offset"] / 10000,  # 转为秒
                    'duration': chunk["duration"] / 10000
                })
        
        return {
            'audio': audio_data,
            'word_boundaries': word_boundaries,
            'duration': word_boundaries[-1]['offset'] + word_boundaries[-1]['duration']
                if word_boundaries else 0
        }
    
    async def get_voices(self, language: str = "zh-CN") -> list:
        """获取可用音色"""
        voices = await edge_tts.list_voices()
        return [v for v in voices if v['Locale'].startswith(language)]

class VITSEngine(ITTSEngine):
    """VITS本地TTS引擎（支持音色克隆）"""
    
    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None
    
    async def load_model(self):
        """加载VITS模型"""
        # 实际实现需要根据VITS版本调整
        pass
    
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        **kwargs
    ) -> bytes:
        """使用VITS合成语音"""
        # 加载模型
        if not self._model:
            await self.load_model()
        
        # 推理
        # 实际实现略
        pass
    
    async def clone_voice(
        self,
        reference_audio: bytes,
        transcript: str
    ) -> str:
        """
        音色克隆
        
        Args:
            reference_audio: 参考音频
            transcript: 参考音频的文字内容
        
        Returns:
            voice_id: 克隆的音色ID
        """
        # 使用VITS的few-shot克隆能力
        pass

class TTSEngineFactory:
    """TTS引擎工厂"""
    
    @staticmethod
    def create(engine_type: str, **kwargs) -> ITTSEngine:
        if engine_type == "edge_tts":
            return EdgeTTSEngine()
        elif engine_type == "vits":
            return VITSEngine(**kwargs)
        else:
            raise ValueError(f"不支持的TTS引擎: {engine_type}")
```

---

## 四、配音服务

```python
# backend/app/services/audio_service.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.audio import VoiceProfile, AudioTrack
from app.engines.tts_engine import TTSEngineFactory, ITTSEngine
import struct

class AudioService:
    """音频服务：管理配音与音效"""
    
    def __init__(self, db: Session):
        self.db = db
        self.tts_engine: ITTSEngine = TTSEngineFactory.create("edge_tts")
    
    async def synthesize_voiceover(
        self,
        project_id: str,
        dialogue_id: str,
        voice_profile_id: str
    ) -> AudioTrack:
        """
        为对话生成配音
        
        流程：
        1. 获取对话内容与音色配置
        2. 调用TTS合成语音
        3. 上传音频文件
        4. 创建音频轨道
        5. 生成字幕数据
        """
        from app.models.script import Dialogue
        
        # 获取对话
        dialogue = self.db.query(Dialogue).filter_by(id=dialogue_id).first()
        if not dialogue:
            raise ValueError("对话不存在")
        
        # 获取音色配置
        voice_profile = self.db.query(VoiceProfile).filter_by(
            id=voice_profile_id
        ).first()
        if not voice_profile:
            raise ValueError("音色配置不存在")
        
        # 合成语音（带时间戳）
        result = await self.tts_engine.synthesize_with_timestamps(
            text=dialogue.content,
            voice_id=voice_profile.voice_id,
            rate=voice_profile.rate,
            pitch=voice_profile.pitch,
            volume=voice_profile.volume
        )
        
        # 上传音频
        audio_url = await self._upload_audio(result['audio'])
        
        # 生成SRT字幕
        subtitle = self._generate_srt(result['word_boundaries'])
        
        # 创建音频轨道
        track = AudioTrack(
            project_id=project_id,
            track_type='voice',
            name=f"{dialogue.character_name}的配音",
            audio_url=audio_url,
            duration=result['duration'],
            dialogue_id=dialogue_id,
            character_id=voice_profile.character_id,
            voice_profile_id=voice_profile_id,
            config={'subtitle': subtitle}
        )
        self.db.add(track)
        self.db.commit()
        self.db.refresh(track)
        
        return track
    
    async def batch_synthesize(
        self,
        project_id: str,
        frame_ids: List[str]
    ) -> List[AudioTrack]:
        """批量生成配音"""
        tracks = []
        
        for frame_id in frame_ids:
            # 获取该帧的对话
            from app.models.storyboard import StoryboardFrame
            frame = self.db.query(StoryboardFrame).filter_by(id=frame_id).first()
            
            if frame and frame.dialogue_id:
                # 查找角色对应的音色
                dialogue = self.db.query(Dialogue).filter_by(
                    id=frame.dialogue_id
                ).first()
                
                voice_profile = self.db.query(VoiceProfile).filter_by(
                    character_id=dialogue.character_id if hasattr(dialogue, 'character_id') else None
                ).first()
                
                if voice_profile:
                    track = await self.synthesize_voiceover(
                        project_id, frame.dialogue_id, voice_profile.id
                    )
                    tracks.append(track)
        
        return tracks
    
    def _generate_srt(self, word_boundaries: list) -> str:
        """生成SRT格式字幕"""
        srt_lines = []
        
        for i, wb in enumerate(word_boundaries):
            start_time = self._format_srt_time(wb['offset'])
            end_time = self._format_srt_time(wb['offset'] + wb['duration'])
            
            srt_lines.append(f"{i+1}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(wb['text'])
            srt_lines.append("")
        
        return '\n'.join(srt_lines)
    
    def _format_srt_time(self, seconds: float) -> str:
        """格式化SRT时间"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    
    async def match_sound_effects(
        self,
        frame_id: str,
        scene_description: str
    ) -> List[str]:
        """
        智能匹配音效
        
        根据场景描述推荐合适的音效
        """
        from app.models.audio import SoundEffect
        
        # 分析场景，提取关键词
        keywords = self._extract_audio_keywords(scene_description)
        
        # 检索匹配的音效
        matched = self.db.query(SoundEffect).filter(
            SoundEffect.tags.op('&&')(keywords)
        ).limit(5).all()
        
        return [sfx.audio_url for sfx in matched]
    
    def _extract_audio_keywords(self, description: str) -> list:
        """从场景描述中提取音频关键词"""
        audio_keywords = {
            'door': ['门', '开门', '关门', '敲门'],
            'footstep': ['走路', '奔跑', '脚步'],
            'rain': ['下雨', '雨', '暴雨'],
            'wind': ['风', '刮风'],
            'explosion': ['爆炸', '轰隆'],
            'car': ['车', '汽车', '引擎'],
            'bird': ['鸟', '鸟鸣'],
            'ocean': ['海', '海浪', '海风'],
            'fire': ['火', '燃烧'],
            'thunder': ['雷', '雷声'],
        }
        
        keywords = []
        for key, words in audio_keywords.items():
            if any(word in description for word in words):
                keywords.append(key)
        
        return keywords
```

---

## 五、音频混合引擎

```python
# backend/app/engines/audio_mixer.py
from pydub import AudioSegment
from io import BytesIO
from typing import List

class AudioMixer:
    """音频混合引擎"""
    
    @staticmethod
    def mix_tracks(
        tracks: List[dict],
        output_format: str = "wav"
    ) -> bytes:
        """
        混合多个音频轨道
        
        Args:
            tracks: [{
                'audio_data': bytes,
                'start_time': float,
                'volume': float,
                'fade_in': float,
                'fade_out': float
            }]
        """
        # 计算总时长
        max_duration = max(
            t['start_time'] + len(AudioSegment.from_file(BytesIO(t['audio_data']))) / 1000
            for t in tracks
        )
        
        # 创建空的基础轨道
        mixed = AudioSegment.silent(duration=int(max_duration * 1000))
        
        for track in tracks:
            audio = AudioSegment.from_file(BytesIO(track['audio_data']))
            
            # 调整音量
            volume = track.get('volume', 1.0)
            audio = audio + (20 * (volume - 1))  # dB调整
            
            # 淡入淡出
            if track.get('fade_in', 0) > 0:
                fade_in_ms = int(track['fade_in'] * 1000)
                audio = audio.fade_in(fade_in_ms)
            
            if track.get('fade_out', 0) > 0:
                fade_out_ms = int(track['fade_out'] * 1000)
                audio = audio.fade_out(fade_out_ms)
            
            # 叠加到指定位置
            start_ms = int(track['start_time'] * 1000)
            mixed = mixed.overlay(audio, position=start_ms)
        
        # 导出
        output = BytesIO()
        mixed.export(output, format=output_format)
        return output.getvalue()
    
    @staticmethod
    def add_background_music(
        voice_audio: bytes,
        bgm_audio: bytes,
        bgm_volume: float = 0.3
    ) -> bytes:
        """添加背景音乐"""
        voice = AudioSegment.from_file(BytesIO(voice_audio))
        bgm = AudioSegment.from_file(BytesIO(bgm_audio))
        
        # 调整BGM音量
        bgm = bgm - int((1 - bgm_volume) * 20)  # 降低BGM音量
        
        # 循环BGM以匹配语音长度
        if len(bgm) < len(voice):
            loops = (len(voice) // len(bgm)) + 1
            bgm = bgm * loops
        
        # 裁剪BGM到相同长度
        bgm = bgm[:len(voice)]
        
        # 混合
        mixed = voice.overlay(bgm)
        
        output = BytesIO()
        mixed.export(output, format="wav")
        return output.getvalue()
```

---

## 六、API接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/audio/voiceover | 生成配音 |
| POST | /api/v1/audio/batch-voiceover | 批量生成配音 |
| GET | /api/v1/voice-profiles | 获取音色列表 |
| POST | /api/v1/voice-profiles | 创建音色 |
| POST | /api/v1/audio/match-sfx | 智能匹配音效 |
| POST | /api/v1/audio/mix | 混合音频轨道 |
| GET | /api/v1/sound-effects | 获取音效库 |
| GET | /api/v1/background-music | 获取背景音乐库 |

---

*本文档最后更新：2026-07-18*
