# 渲染导出模块

> 本文档详细说明渲染与导出模块的功能设计、渲染管线与多格式导出能力。

---

## 一、模块概述

### 1.1 功能定位
渲染导出模块是漫剧创作的"最后一公里"，负责将分镜画面、配音、音效、字幕合成为最终的视频作品，支持多种格式和质量导出。

### 1.2 核心能力
| 能力 | 描述 | 技术方案 |
|------|------|----------|
| 批量渲染 | 并行渲染所有分镜画面 | Celery + GPU批量推理 |
| 视频合成 | 帧序列+音频合成视频 | FFmpeg |
| 字幕叠加 | 烧录字幕到视频 | FFmpeg subtitles滤镜 |
| 转场效果 | 场景间转场动画 | FFmpeg xfade滤镜 |
| 多格式导出 | MP4/WebM/GIF/图片序列 | FFmpeg编码器 |
| 质量控制 | 多分辨率/码率选择 | FFmpeg编码参数 |

---

## 二、渲染管线架构

```
分镜数据 → 画面生成 → 帧序列 → 视频合成 → 字幕叠加 → 转场效果 → 最终导出
              │           │          │          │          │
              ▼           ▼          ▼          ▼          ▼
         GPU并行      临时存储    音频混合    SRT字幕    xfade滤镜
         推理         帧图片      WAV/MP3    烧录       过渡动画
```

---

## 三、数据模型

```python
# backend/app/models/render.py
from sqlalchemy import Column, String, Text, JSON, ForeignKey, Integer, Float, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.models.base import Base, UUIDMixin, TimestampMixin

class RenderTask(Base, UUIDMixin, TimestampMixin):
    """渲染任务"""
    __tablename__ = "render_tasks"
    
    user_id = Column(UUID, ForeignKey('users.id'), nullable=False)
    project_id = Column(UUID, ForeignKey('projects.id'), nullable=False)
    script_id = Column(UUID, ForeignKey('scripts.id'), nullable=False)
    
    # 任务信息
    name = Column(String(200), comment="任务名称")
    status = Column(String(20), default='pending',
                    comment="pending/processing/completed/failed/cancelled")
    progress = Column(Integer, default=0, comment="进度 0-100")
    
    # 渲染配置
    config = Column(JSON, comment="渲染配置")
    """
    config示例:
    {
        "resolution": "1920x1080",  // 分辨率
        "fps": 24,                  // 帧率
        "format": "mp4",            // 输出格式
        "quality": "high",          // 质量: low/medium/high/ultra
        "bitrate": "8M",            // 码率
        "include_subtitle": true,   // 是否包含字幕
        "include_bgm": true,        // 是否包含背景音乐
        "transition": "fade",       // 转场效果
        "watermark": false          // 是否添加水印
    }
    """
    
    # 结果
    output_url = Column(String(500), nullable=True, comment="输出文件URL")
    output_size = Column(Integer, nullable=True, comment="文件大小（字节）")
    duration = Column(Float, nullable=True, comment="视频时长（秒）")
    frame_count = Column(Integer, nullable=True, comment="总帧数")
    
    # 统计
    started_at = Column(TIMESTAMP, nullable=True)
    completed_at = Column(TIMESTAMP, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # 成本
    credits_cost = Column(Integer, default=0, comment="消耗积分")

class RenderQueue(Base, UUIDMixin, TimestampMixin):
    """渲染队列"""
    __tablename__ = "render_queue"
    
    task_id = Column(UUID, ForeignKey('render_tasks.id'), nullable=False)
    frame_id = Column(UUID, ForeignKey('storyboard_frames.id'), nullable=False)
    
    # 帧渲染状态
    status = Column(String(20), default='pending',
                    comment="pending/rendering/completed/failed")
    output_path = Column(String(500), nullable=True)
    
    # 渲染参数
    prompt = Column(Text, comment="生成提示词")
    negative_prompt = Column(Text)
    generation_params = Column(JSON, comment="生成参数")
    
    order_index = Column(Integer)
```

---

## 四、渲染服务

```python
# backend/app/services/render_service.py
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.render import RenderTask, RenderQueue
from app.models.storyboard import StoryboardFrame
from app.engines.video_engine import VideoComposer
from app.engines.audio_mixer import AudioMixer
from celery import Celery
import asyncio

class RenderService:
    """渲染服务：管理渲染任务全流程"""
    
    def __init__(self, db: Session):
        self.db = db
        self.video_composer = VideoComposer()
        self.audio_mixer = AudioMixer()
    
    async def create_render_task(
        self,
        user_id: str,
        project_id: str,
        script_id: str,
        config: dict
    ) -> RenderTask:
        """
        创建渲染任务
        
        流程：
        1. 计算所需积分
        2. 创建渲染任务
        3. 创建帧渲染队列
        4. 异步启动渲染
        """
        # 获取分镜帧数
        frames = self.db.query(StoryboardFrame).filter_by(script_id=script_id).all()
        
        # 计算积分消耗
        credits = self._calculate_credits(len(frames), config)
        
        # 创建渲染任务
        task = RenderTask(
            user_id=user_id,
            project_id=project_id,
            script_id=script_id,
            name=config.get('name', f'渲染任务 {len(frames)}帧'),
            status='pending',
            config=config,
            frame_count=len(frames),
            credits_cost=credits
        )
        self.db.add(task)
        self.db.flush()
        
        # 创建帧渲染队列
        for idx, frame in enumerate(frames):
            queue_item = RenderQueue(
                task_id=task.id,
                frame_id=frame.id,
                status='pending',
                prompt=frame.prompt,
                negative_prompt=frame.negative_prompt,
                generation_params={
                    'shot_type': frame.shot_type,
                    'camera_angle': frame.camera_angle,
                    'characters': frame.characters_in_frame
                },
                order_index=idx
            )
            self.db.add(queue_item)
        
        self.db.commit()
        
        # 异步启动渲染
        from app.tasks.render_tasks import render_comic
        render_comic.delay(str(task.id))
        
        return task
    
    def _calculate_credits(self, frame_count: int, config: dict) -> int:
        """计算渲染所需积分"""
        base_cost = 2  # 每帧基础2积分
        
        # 质量加成
        quality_multiplier = {
            'low': 1.0,
            'medium': 1.5,
            'high': 2.0,
            'ultra': 3.0
        }.get(config.get('quality', 'medium'), 1.5)
        
        # 分辨率加成
        resolution = config.get('resolution', '1920x1080')
        if '4K' in resolution or '3840' in resolution:
            res_multiplier = 2.0
        elif '2K' in resolution or '2560' in resolution:
            res_multiplier = 1.5
        else:
            res_multiplier = 1.0
        
        return int(frame_count * base_cost * quality_multiplier * res_multiplier)
```

---

## 五、视频合成引擎

```python
# backend/app/engines/video_engine.py
import ffmpeg
from pathlib import Path
from typing import List, Optional
import tempfile
import os

class VideoComposer:
    """视频合成引擎"""
    
    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
    
    async def compose_video(
        self,
        frames: List[dict],
        audio_tracks: List[dict],
        config: dict,
        output_path: str
    ) -> dict:
        """
        合成最终视频
        
        Args:
            frames: 帧数据列表
                [{
                    'image_path': str,
                    'duration': float,
                    'transition': str,  # cut/fade/dissolve
                    'transition_duration': float
                }]
            audio_tracks: 音频轨道
                [{
                    'audio_path': str,
                    'start_time': float,
                    'volume': float,
                    'type': 'voice'/'bgm'/'sfx'
                }]
            config: 渲染配置
            output_path: 输出路径
        
        Returns:
            {
                'output_path': str,
                'duration': float,
                'file_size': int
            }
        """
        # 1. 帧序列转视频（含转场）
        video_path = await self._frames_to_video_with_transitions(
            frames, config
        )
        
        # 2. 混合音频
        audio_path = await self._mix_audio_tracks(audio_tracks, frames)
        
        # 3. 合并音视频
        merged_path = await self._merge_audio_video(video_path, audio_path)
        
        # 4. 添加字幕（如果需要）
        if config.get('include_subtitle'):
            subtitle_path = config.get('subtitle_path')
            if subtitle_path:
                merged_path = await self._add_subtitle(merged_path, subtitle_path)
        
        # 5. 添加水印（如果需要）
        if config.get('watermark'):
            merged_path = await self._add_watermark(
                merged_path, 
                config['watermark_text'],
                config.get('watermark_position', 'bottom-right')
            )
        
        # 6. 最终编码
        self._final_encode(merged_path, output_path, config)
        
        # 获取视频信息
        duration = self._get_duration(output_path)
        file_size = os.path.getsize(output_path)
        
        return {
            'output_path': output_path,
            'duration': duration,
            'file_size': file_size
        }
    
    async def _frames_to_video_with_transitions(
        self,
        frames: List[dict],
        config: dict
    ) -> str:
        """帧序列转视频（含转场效果）"""
        fps = config.get('fps', 24)
        resolution = config.get('resolution', '1920x1080')
        
        # 为每帧创建视频片段
        clip_paths = []
        for i, frame in enumerate(frames):
            clip_path = os.path.join(self.temp_dir, f"clip_{i:04d}.mp4")
            duration = frame['duration']
            
            # 单帧转视频片段
            (
                ffmpeg
                .input(frame['image_path'], loop=1, t=duration, framerate=fps)
                .output(
                    clip_path,
                    vcodec='libx264',
                    pix_fmt='yuv420p',
                    s=resolution,
                    r=fps
                )
                .overwrite_output()
                .run()
            )
            clip_paths.append(clip_path)
        
        # 使用xfade滤镜添加转场
        if len(clip_paths) == 1:
            return clip_paths[0]
        
        # 构建转场链
        inputs = []
        for path in clip_paths:
            inputs.append(ffmpeg.input(path))
        
        # 第一个转场
        transition_type = config.get('transition', 'fade')
        transition_duration = 0.5
        
        merged = ffmpeg.filter(
            [inputs[0], inputs[1]],
            'xfade',
            transition=transition_type,
            duration=transition_duration,
            offset=frames[0]['duration'] - transition_duration
        )
        
        # 后续转场
        offset = frames[0]['duration'] + frames[1]['duration'] - 2 * transition_duration
        for i in range(2, len(inputs)):
            merged = ffmpeg.filter(
                [merged, inputs[i]],
                'xfade',
                transition=transition_type,
                duration=transition_duration,
                offset=offset
            )
            offset += frames[i]['duration'] - transition_duration
        
        output_path = os.path.join(self.temp_dir, 'video_no_audio.mp4')
        (
            merged
            .output(output_path, vcodec='libx264', pix_fmt='yuv420p')
            .overwrite_output()
            .run()
        )
        
        return output_path
    
    async def _mix_audio_tracks(
        self,
        tracks: List[dict],
        frames: List[dict]
    ) -> str:
        """混合所有音频轨道"""
        if not tracks:
            # 无音频，生成静音
            total_duration = sum(f['duration'] for f in frames)
            silent_path = os.path.join(self.temp_dir, 'silent.wav')
            (
                ffmpeg
                .input('anullsrc=channel_layout=stereo:sample_rate=44100',
                       f='lavfi', t=total_duration)
                .output(silent_path)
                .overwrite_output()
                .run()
            )
            return silent_path
        
        # 混合音频
        from pydub import AudioSegment
        from io import BytesIO
        
        total_duration = sum(f['duration'] for f in frames) * 1000  # 毫秒
        mixed = AudioSegment.silent(duration=total_duration)
        
        for track in tracks:
            audio = AudioSegment.from_file(track['audio_path'])
            
            # 调整音量
            volume = track.get('volume', 1.0)
            if track['type'] == 'bgm':
                audio = audio - 10  # BGM降低10dB
            elif track['type'] == 'sfx':
                audio = audio - 5   # 音效降低5dB
            
            # 叠加到指定位置
            start_ms = int(track.get('start_time', 0) * 1000)
            mixed = mixed.overlay(audio, position=start_ms)
        
        output_path = os.path.join(self.temp_dir, 'mixed_audio.wav')
        mixed.export(output_path, format='wav')
        return output_path
    
    async def _merge_audio_video(
        self,
        video_path: str,
        audio_path: str
    ) -> str:
        """合并音视频"""
        output_path = os.path.join(self.temp_dir, 'merged.mp4')
        
        video = ffmpeg.input(video_path)
        audio = ffmpeg.input(audio_path)
        
        (
            ffmpeg
            .output(video.video, audio.audio, output_path,
                    vcodec='copy', acodec='aac', shortest=True)
            .overwrite_output()
            .run()
        )
        
        return output_path
    
    async def _add_subtitle(
        self,
        video_path: str,
        subtitle_path: str
    ) -> str:
        """添加字幕"""
        output_path = os.path.join(self.temp_dir, 'with_subtitle.mp4')
        
        (
            ffmpeg
            .input(video_path)
            .output(output_path,
                    vf=f"subtitles={subtitle_path}:force_style='FontName=Noto Sans CJK SC,FontSize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'",
                    vcodec='libx264',
                    acodec='copy')
            .overwrite_output()
            .run()
        )
        
        return output_path
    
    async def _add_watermark(
        self,
        video_path: str,
        text: str,
        position: str = 'bottom-right'
    ) -> str:
        """添加文字水印"""
        output_path = os.path.join(self.temp_dir, 'watermarked.mp4')
        
        # 位置映射
        positions = {
            'top-left': 'x=10:y=10',
            'top-right': 'x=w-tw-10:y=10',
            'bottom-left': 'x=10:y=h-th-10',
            'bottom-right': 'x=w-tw-10:y=h-th-10'
        }
        pos = positions.get(position, positions['bottom-right'])
        
        (
            ffmpeg
            .input(video_path)
            .output(output_path,
                    vf=f"drawtext=text='{text}':{pos}:fontcolor=white@0.5:fontsize=20",
                    vcodec='libx264',
                    acodec='copy')
            .overwrite_output()
            .run()
        )
        
        return output_path
    
    def _final_encode(
        self,
        input_path: str,
        output_path: str,
        config: dict
    ):
        """最终编码，应用质量设置"""
        quality = config.get('quality', 'medium')
        
        # 质量预设
        presets = {
            'low': {'crf': 28, 'preset': 'fast'},
            'medium': {'crf': 23, 'preset': 'medium'},
            'high': {'crf': 18, 'preset': 'slow'},
            'ultra': {'crf': 15, 'preset': 'veryslow'}
        }
        preset = presets.get(quality, presets['medium'])
        
        (
            ffmpeg
            .input(input_path)
            .output(output_path,
                    vcodec='libx264',
                    acodec='aac',
                    crf=preset['crf'],
                    preset=preset['preset'],
                    pix_fmt='yuv420p',
                    movflags='faststart')
            .overwrite_output()
            .run()
        )
    
    def _get_duration(self, video_path: str) -> float:
        """获取视频时长"""
        probe = ffmpeg.probe(video_path)
        return float(probe['format']['duration'])
    
    async def export_gif(
        self,
        video_path: str,
        output_path: str,
        fps: int = 15,
        width: int = 480
    ) -> str:
        """导出GIF"""
        (
            ffmpeg
            .input(video_path)
            .output(output_path,
                    vf=f'fps={fps},scale={width}:-1:flags=lanczos',
                    loop=0)
            .overwrite_output()
            .run()
        )
        return output_path
    
    async def export_frames(
        self,
        video_path: str,
        output_dir: str,
        format: str = 'png'
    ) -> List[str]:
        """导出帧序列"""
        (
            ffmpeg
            .input(video_path)
            .output(os.path.join(output_dir, f'frame_%04d.{format}'))
            .overwrite_output()
            .run()
        )
        
        # 返回帧文件列表
        frames = sorted(Path(output_dir).glob(f'frame_*.{format}'))
        return [str(f) for f in frames]
```

---

## 六、异步渲染任务

```python
# backend/app/tasks/render_tasks.py
from celery import Celery, group, chain
from celery_progress.backend import ProgressRecorder
from app.services.render_service import RenderService
from app.engines.image_gen_engine import ImageGenEngine
from app.engines.character_consistency_engine import CharacterConsistencyEngine
import os

app = Celery('comic_studio', broker='redis://localhost:6379')

@app.task(bind=True)
def render_comic(self, task_id: str):
    """漫剧渲染主任务"""
    progress_recorder = ProgressRecorder(self)
    
    # 1. 获取渲染任务
    db = get_db_session()
    task = db.query(RenderTask).filter_by(id=task_id).first()
    task.status = 'processing'
    task.started_at = datetime.utcnow()
    db.commit()
    
    try:
        # 2. 获取帧渲染队列
        queue = db.query(RenderQueue).filter_by(task_id=task_id)\
            .order_by(RenderQueue.order_index).all()
        
        total_frames = len(queue)
        
        # 3. 并行渲染所有帧
        frame_paths = []
        for i, item in enumerate(queue):
            progress_recorder.set_progress(
                i, total_frames,
                description=f'渲染第 {i+1}/{total_frames} 帧'
            )
            
            # 渲染单帧
            frame_path = render_single_frame.delay(
                str(item.id), 
                task.config
            ).get()
            
            frame_paths.append({
                'image_path': frame_path,
                'duration': get_frame_duration(item.frame_id, db),
                'transition': 'fade',
                'transition_duration': 0.5
            })
            
            # 更新进度
            item.status = 'completed'
            item.output_path = frame_path
            db.commit()
        
        # 4. 获取音频轨道
        audio_tracks = get_audio_tracks(task.project_id, db)
        
        # 5. 合成视频
        progress_recorder.set_progress(
            total_frames, total_frames,
            description='正在合成视频...'
        )
        
        output_path = os.path.join(
            OUTPUT_DIR, f'render_{task_id}.mp4'
        )
        
        composer = VideoComposer()
        result = await composer.compose_video(
            frames=frame_paths,
            audio_tracks=audio_tracks,
            config=task.config,
            output_path=output_path
        )
        
        # 6. 更新任务状态
        task.status = 'completed'
        task.output_url = upload_to_storage(output_path)
        task.output_size = result['file_size']
        task.duration = result['duration']
        task.completed_at = datetime.utcnow()
        db.commit()
        
        return {'output_url': task.output_url}
        
    except Exception as e:
        task.status = 'failed'
        task.error_message = str(e)
        db.commit()
        raise

@app.task
def render_single_frame(queue_id: str, config: dict) -> str:
    """渲染单个帧"""
    db = get_db_session()
    
    queue_item = db.query(RenderQueue).filter_by(id=queue_id).first()
    queue_item.status = 'rendering'
    db.commit()
    
    try:
        # 初始化引擎
        image_engine = ImageGenEngine()
        consistency_engine = CharacterConsistencyEngine(image_engine)
        
        # 如果有角色，加载角色LoRA
        characters = queue_item.generation_params.get('characters', [])
        for char in characters:
            if char.get('lora_path'):
                image_engine.load_lora(char['lora_path'], weight=0.8)
        
        # 生成画面
        image_data = await image_engine.generate(
            prompt=queue_item.prompt,
            negative_prompt=queue_item.negative_prompt,
            width=1920,
            height=1080,
            steps=30,
            guidance_scale=7.5
        )
        
        # 保存图片
        frame_path = os.path.join(TEMP_DIR, f'frame_{queue_id}.png')
        with open(frame_path, 'wb') as f:
            f.write(image_data)
        
        return frame_path
        
    except Exception as e:
        queue_item.status = 'failed'
        db.commit()
        raise
```

---

## 七、导出格式支持

| 格式 | 用途 | 参数 |
|------|------|------|
| MP4 (H.264) | 通用视频，兼容性最好 | crf=18-28, preset=medium |
| MP4 (H.265) | 高压缩比，4K推荐 | crf=20-25, preset=slow |
| WebM (VP9) | 网页嵌入，开源友好 | crf=30-40, deadline=good |
| GIF | 短循环动画，社交分享 | fps=15, width=480 |
| PNG序列 | 后期编辑，无损 | format=png |
| WebP序列 | 网页动画，小体积 | quality=80 |

---

## 八、API接口

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/v1/render/tasks | 创建渲染任务 |
| GET | /api/v1/render/tasks/{id} | 获取渲染状态 |
| GET | /api/v1/render/tasks/{id}/progress | 获取渲染进度 |
| POST | /api/v1/render/tasks/{id}/cancel | 取消渲染任务 |
| GET | /api/v1/render/tasks/{id}/download | 下载渲染结果 |
| POST | /api/v1/render/tasks/{id}/export-gif | 导出GIF |

---

*本文档最后更新：2026-07-18*
