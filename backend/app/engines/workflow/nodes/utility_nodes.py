# backend/app/engines/workflow/nodes/utility_nodes.py
"""工具节点"""
import time
from typing import Any

from app.engines.workflow.node_base import (
    BaseNode,
    NodeCategory,
    NodeDefinition,
    ParameterDefinition,
    PortDefinition,
)


class TextInputNode(BaseNode):
    """文本输入节点 - 工作流的输入源"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_input",
            name="文本输入",
            category=NodeCategory.INPUT,
            description="提供静态文本输入",
            icon="text",
            inputs=[],
            outputs=[PortDefinition(name="text", type="text")],
            parameters=[
                ParameterDefinition(name="value", type="text", default="", description="文本内容"),
            ],
            is_async=False,
            estimated_time=0.01,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        text = self.params.get("value", "")
        self.status = "completed"
        self.completed_at = time.time()
        self.result = {"text": text}
        return self.result


class TextConcatNode(BaseNode):
    """文本拼接节点"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="text_concat",
            name="文本拼接",
            category=NodeCategory.UTILITY,
            description="拼接多个文本输入",
            icon="concat",
            inputs=[
                PortDefinition(name="text1", type="text", required=False),
                PortDefinition(name="text2", type="text", required=False),
                PortDefinition(name="text3", type="text", required=False),
            ],
            outputs=[PortDefinition(name="text", type="text")],
            parameters=[
                ParameterDefinition(name="separator", type="text", default=", "),
            ],
            is_async=False,
            estimated_time=0.01,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        separator = self.params.get("separator", ", ")
        texts = [v for v in inputs.values() if v]
        self.status = "completed"
        self.completed_at = time.time()
        self.result = {"text": separator.join(texts)}
        return self.result


class ImagePreviewNode(BaseNode):
    """图像预览节点 - 用于中间结果展示"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="image_preview",
            name="图像预览",
            category=NodeCategory.OUTPUT,
            description="预览图像，不改变数据",
            icon="preview",
            inputs=[PortDefinition(name="image", type="image", required=True)],
            outputs=[PortDefinition(name="image", type="image")],
            parameters=[],
            is_async=False,
            estimated_time=0.01,
        )

    async def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        self.status = "running"
        self.started_at = time.time()
        image = inputs.get("image")
        if not image:
            raise ValueError("缺少 image 输入")
        self.status = "completed"
        self.completed_at = time.time()
        self.result = {"image": image}
        return self.result
