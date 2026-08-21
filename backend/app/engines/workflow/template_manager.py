# backend/app/engines/workflow/template_manager.py
"""工作流模板系统"""
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class WorkflowTemplate:
    """工作流模板"""
    template_id: str
    name: str
    description: str
    category: str = "general"
    is_premium: bool = False
    workflow_data: dict = field(default_factory=lambda: {"nodes": [], "edges": []})
    tags: list[str] = field(default_factory=list)
    icon: str = ""

    def to_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "is_premium": self.is_premium,
            "workflow_data": self.workflow_data,
            "tags": self.tags,
            "icon": self.icon,
        }


# 内置模板
BUILTIN_TEMPLATES: list[WorkflowTemplate] = [
    WorkflowTemplate(
        template_id="basic_text_to_image",
        name="基础文生图",
        description="单个提示词生成图像",
        category="basic",
        icon="image",
        tags=["图像", "入门"],
        workflow_data={
            "nodes": [
                {"id": "input", "type": "text_input", "params": {"value": "a cute cat"}},
                {"id": "gen", "type": "text_to_image", "params": {"width": 1024, "height": 1024, "model": "flux"}},
                {"id": "preview", "type": "image_preview", "params": {}},
            ],
            "edges": [
                {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"},
                {"from": "gen", "to": "preview", "from_port": "image", "to_port": "image"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="llm_prompt_enhance",
        name="LLM 提示词增强",
        description="LLM 增强提示词后生成图像",
        category="advanced",
        icon="workflow",
        tags=["LLM", "图像", "进阶"],
        workflow_data={
            "nodes": [
                {"id": "input", "type": "text_input", "params": {"value": "a girl"}},
                {"id": "llm", "type": "llm_chat", "params": {
                    "model": "deepseek-chat",
                    "max_tokens": 500,
                }},
                {"id": "gen", "type": "text_to_image", "params": {"model": "flux"}},
                {"id": "preview", "type": "image_preview", "params": {}},
            ],
            "edges": [
                {"from": "input", "to": "llm", "from_port": "text", "to_port": "user_message"},
                {"from": "llm", "to": "gen", "from_port": "response", "to_port": "prompt"},
                {"from": "gen", "to": "preview", "from_port": "image", "to_port": "image"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="tts_pipeline",
        name="文本转语音",
        description="文本输入生成语音",
        category="basic",
        icon="audio",
        tags=["TTS", "音频"],
        workflow_data={
            "nodes": [
                {"id": "input", "type": "text_input", "params": {"value": "你好，世界"}},
                {"id": "tts", "type": "tts", "params": {"voice": "zh-CN-XiaoxiaoNeural"}},
            ],
            "edges": [
                {"from": "input", "to": "tts", "from_port": "text", "to_port": "text"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="character_consistency_demo",
        name="角色一致性生成",
        description="基于参考图生成一致角色",
        category="advanced",
        is_premium=True,
        icon="character",
        tags=["角色", "一致性", "进阶"],
        workflow_data={
            "nodes": [
                {"id": "prompt_input", "type": "text_input", "params": {"value": "微笑的女孩"}},
                {"id": "ref_input", "type": "text_input", "params": {"value": "https://example.com/char.png"}},
                {"id": "char_gen", "type": "character_gen", "params": {"consistency_weight": 0.8}},
                {"id": "preview", "type": "image_preview", "params": {}},
            ],
            "edges": [
                {"from": "prompt_input", "to": "char_gen", "from_port": "text", "to_port": "prompt"},
                {"from": "ref_input", "to": "char_gen", "from_port": "text", "to_port": "reference_image"},
                {"from": "char_gen", "to": "preview", "from_port": "image", "to_port": "image"},
            ],
        },
    ),
    WorkflowTemplate(
        template_id="video_compose_demo",
        name="视频合成",
        description="多帧图像合成视频",
        category="advanced",
        is_premium=True,
        icon="video",
        tags=["视频", "合成", "进阶"],
        workflow_data={
            "nodes": [
                {"id": "frames_input", "type": "text_input",
                 "params": {"value": "/uploads/frame1.png,/uploads/frame2.png"}},
                {"id": "compose", "type": "video_compose",
                 "params": {"fps": 24, "width": 1920, "height": 1080}},
            ],
            "edges": [
                {"from": "frames_input", "to": "compose", "from_port": "text", "to_port": "frames"},
            ],
        },
    ),
]


class TemplateManager:
    """模板管理器"""

    def __init__(self, templates: Optional[list[WorkflowTemplate]] = None):
        if templates is None:
            templates = deepcopy(BUILTIN_TEMPLATES)
        self.templates: dict[str, WorkflowTemplate] = {t.template_id: t for t in templates}

    def list_templates(
        self,
        category: Optional[str] = None,
        include_premium: bool = True,
        tag: Optional[str] = None,
    ) -> list[WorkflowTemplate]:
        """列出模板"""
        templates = list(self.templates.values())
        if category:
            templates = [t for t in templates if t.category == category]
        if not include_premium:
            templates = [t for t in templates if not t.is_premium]
        if tag:
            templates = [t for t in templates if tag in t.tags]
        return templates

    def get_template(self, template_id: str) -> Optional[WorkflowTemplate]:
        """获取模板"""
        return self.templates.get(template_id)

    def apply_template(
        self,
        template_id: str,
        customizations: Optional[dict] = None,
    ) -> dict:
        """应用模板，返回定制后的工作流

        Args:
            template_id: 模板 ID
            customizations: {
                "node_params": {node_id: {param_name: value}}
            }
        """
        template = self.get_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        workflow = deepcopy(template.workflow_data)

        if customizations and "node_params" in customizations:
            for node in workflow.get("nodes", []):
                node_id = node["id"]
                if node_id in customizations["node_params"]:
                    node.setdefault("params", {}).update(customizations["node_params"][node_id])

        return workflow

    def add_template(self, template: WorkflowTemplate) -> None:
        """添加自定义模板"""
        self.templates[template.template_id] = template

    def list_categories(self) -> list[str]:
        """列出所有分类"""
        return list(set(t.category for t in self.templates.values()))


# 全局单例
template_manager = TemplateManager()
