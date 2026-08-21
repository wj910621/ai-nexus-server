# backend/app/engines/workflow/nodes/generation_nodes.py
"""生成节点 - 调用 Phase 2 的 5 个 AI 引擎"""
import time
from typing import Any

from app.engines.base import GenerationResult
from app.engines.manager import engine_manager
from app.engines.workflow.node_base import (
    BaseNode,
    NodeCategory,
    NodeDefinition,
    ParameterDefinition,
    PortDefinition,
)


class TextToImageNode(BaseNode):
    """文生图节点 - 调用图像生成引擎"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_to_image",
            name="文生图",
            category=NodeCategory.GENERATION,
            description="根据文本提示词生成图像",
            icon="image",
            inputs=[
                PortDefinition(name="prompt", type="text", required=True, description="正向提示词"),
                PortDefinition(name="negative_prompt", type="text", required=False, description="负向提示词"),
            ],
            outputs=[PortDefinition(name="image", type="image", description="生成的图像 URL")],
            parameters=[
                ParameterDefinition(name="width", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="height", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="model", type="select", default="flux",
                                    options=["flux", "turbo", "flux-realism", "flux-anime", "flux-3d"]),
                ParameterDefinition(name="seed", type="int", default=-1, description="-1 表示随机"),
            ],
            is_async=True,
            estimated_time=5.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            prompt = inputs.get("prompt") or self.params.get("prompt", "")
            if not prompt:
                raise ValueError("缺少 prompt 输入")

            negative_prompt = inputs.get("negative_prompt") or self.params.get("negative_prompt", "")
            seed = self.params.get("seed", -1)
            if seed == -1:
                seed = None

            engine = engine_manager.get_image_engine()
            if engine is None:
                raise RuntimeError("图像引擎未初始化")

            result: GenerationResult = await engine.text2img(
                prompt=prompt,
                negative_prompt=negative_prompt,
                width=self.params.get("width", 1024),
                height=self.params.get("height", 1024),
                seed=seed,
                model=self.params.get("model", "flux"),
            )

            if not result.success:
                raise RuntimeError(result.error or "图像生成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"image": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class TTSNode(BaseNode):
    """语音合成节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="tts",
            name="语音合成",
            category=NodeCategory.GENERATION,
            description="文本转语音",
            icon="audio",
            inputs=[PortDefinition(name="text", type="text", required=True, description="要合成的文本")],
            outputs=[PortDefinition(name="audio", type="audio", description="生成的音频 URL")],
            parameters=[
                ParameterDefinition(name="voice", type="select", default="zh-CN-XiaoxiaoNeural",
                                    options=["zh-CN-XiaoxiaoNeural", "zh-CN-YunxiNeural",
                                             "zh-CN-YunyangNeural", "zh-CN-XiaoyiNeural",
                                             "en-US-JennyNeural", "en-US-GuyNeural"]),
                ParameterDefinition(name="rate", type="int", default=0, min=-100, max=100),
                ParameterDefinition(name="pitch", type="int", default=0, min=-100, max=100),
            ],
            is_async=True,
            estimated_time=2.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            text = inputs.get("text") or self.params.get("text", "")
            if not text:
                raise ValueError("缺少 text 输入")

            engine = engine_manager.get_tts_engine()
            if engine is None:
                raise RuntimeError("TTS 引擎未初始化")

            result = await engine.synthesize(
                text=text,
                voice=self.params.get("voice", "zh-CN-XiaoxiaoNeural"),
                rate=self.params.get("rate", 0),
                pitch=self.params.get("pitch", 0),
            )

            if not result.success:
                raise RuntimeError(result.error or "语音合成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"audio": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class LLMChatNode(BaseNode):
    """LLM 对话节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="llm_chat",
            name="LLM 对话",
            category=NodeCategory.GENERATION,
            description="调用大语言模型对话",
            icon="chat",
            inputs=[
                PortDefinition(name="user_message", type="text", required=True, description="用户消息"),
                PortDefinition(name="system_prompt", type="text", required=False, description="系统提示词"),
            ],
            outputs=[PortDefinition(name="response", type="text", description="LLM 响应")],
            parameters=[
                ParameterDefinition(name="model", type="select", default="deepseek-chat",
                                    options=["deepseek-chat", "deepseek-reasoner"]),
                ParameterDefinition(name="temperature", type="float", default=0.7, min=0, max=2),
                ParameterDefinition(name="max_tokens", type="int", default=2000, min=1, max=8192),
            ],
            is_async=True,
            estimated_time=3.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            user_message = inputs.get("user_message") or self.params.get("user_message", "")
            if not user_message:
                raise ValueError("缺少 user_message 输入")

            messages = []
            system_prompt = inputs.get("system_prompt") or self.params.get("system_prompt")
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": user_message})

            engine = engine_manager.get_llm_engine()
            if engine is None:
                raise RuntimeError("LLM 引擎未初始化")

            result = await engine.chat(
                messages=messages,
                model=self.params.get("model", "deepseek-chat"),
                temperature=self.params.get("temperature", 0.7),
                max_tokens=self.params.get("max_tokens", 2000),
            )

            if not result.success:
                raise RuntimeError(result.error or "LLM 调用失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"response": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class VideoComposeNode(BaseNode):
    """视频合成节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="video_compose",
            name="视频合成",
            category=NodeCategory.COMPOSITE,
            description="将图像帧列表合成为视频",
            icon="video",
            inputs=[
                PortDefinition(name="frames", type="image_array", required=True, description="图像帧 URL 列表"),
                PortDefinition(name="audio", type="audio", required=False, description="音频 URL"),
            ],
            outputs=[PortDefinition(name="video", type="video", description="合成的视频路径")],
            parameters=[
                ParameterDefinition(name="fps", type="int", default=24, min=1, max=60),
                ParameterDefinition(name="width", type="int", default=1920, min=64, max=4096),
                ParameterDefinition(name="height", type="int", default=1080, min=64, max=4096),
                ParameterDefinition(name="transition", type="select", default="none",
                                    options=["none", "fade"]),
            ],
            is_async=True,
            estimated_time=10.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            frames = inputs.get("frames") or self.params.get("frames", [])
            if not frames:
                raise ValueError("缺少 frames 输入")

            if isinstance(frames, str):
                frames = [frames]

            audio = inputs.get("audio") or self.params.get("audio")

            engine = engine_manager.get_video_engine()
            if engine is None:
                raise RuntimeError("视频引擎未初始化")

            width = self.params.get("width", 1920)
            height = self.params.get("height", 1080)

            result = await engine.compose(
                frames=frames,
                audio=audio,
                fps=self.params.get("fps", 24),
                resolution=(width, height),
            )

            if not result.success:
                raise RuntimeError(result.error or "视频合成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"video": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise


class CharacterGenNode(BaseNode):
    """角色一致性生成节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="character_gen",
            name="角色生成",
            category=NodeCategory.GENERATION,
            description="基于参考图生成保持一致性的角色图像",
            icon="character",
            inputs=[
                PortDefinition(name="prompt", type="text", required=True, description="画面描述"),
                PortDefinition(name="reference_image", type="image", required=True, description="参考图 URL 或 base64"),
            ],
            outputs=[PortDefinition(name="image", type="image", description="生成的角色图像 URL")],
            parameters=[
                ParameterDefinition(name="consistency_weight", type="float", default=0.8, min=0, max=1),
                ParameterDefinition(name="character_description", type="text", default=""),
                ParameterDefinition(name="mood", type="select", default="",
                                    options=["", "happy", "sad", "angry", "surprised"]),
                ParameterDefinition(name="width", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="height", type="int", default=1024, min=64, max=2048),
                ParameterDefinition(name="seed", type="int", default=-1),
            ],
            is_async=True,
            estimated_time=6.0,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        try:
            prompt = inputs.get("prompt") or self.params.get("prompt", "")
            reference_image = inputs.get("reference_image") or self.params.get("reference_image")

            if not prompt:
                raise ValueError("缺少 prompt 输入")
            if not reference_image:
                raise ValueError("缺少 reference_image 输入")

            # 如果是 URL，下载为 bytes；如果是 base64，解码
            image_bytes = await self._load_image_bytes(reference_image)

            seed = self.params.get("seed", -1)
            if seed == -1:
                seed = None

            engine = engine_manager.get_character_engine()
            if engine is None:
                raise RuntimeError("角色一致性引擎未初始化")

            result = await engine.generate_consistent(
                prompt=prompt,
                reference_image=image_bytes,
                consistency_weight=self.params.get("consistency_weight", 0.8),
                character_description=self.params.get("character_description") or None,
                mood=self.params.get("mood") or None,
                width=self.params.get("width", 1024),
                height=self.params.get("height", 1024),
                seed=seed,
            )

            if not result.success:
                raise RuntimeError(result.error or "角色生成失败")

            self.status = "completed"
            self.completed_at = time.time()
            self.result = {"image": result.data}
            return self.result
        except Exception as e:
            self.status = "failed"
            self.completed_at = time.time()
            self.error = str(e)
            raise

    async def _load_image_bytes(self, image_ref: str) -> bytes:
        """加载图像为 bytes"""
        if image_ref.startswith("data:image"):
            # data URL: data:image/png;base64,xxxx
            import base64
            _, b64data = image_ref.split(",", 1)
            return base64.b64decode(b64data)
        elif image_ref.startswith("http"):
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(image_ref)
                resp.raise_for_status()
                return resp.content
        else:
            # 假设是 base64 或本地路径
            import base64
            try:
                return base64.b64decode(image_ref)
            except Exception:
                from pathlib import Path
                return Path(image_ref).read_bytes()
