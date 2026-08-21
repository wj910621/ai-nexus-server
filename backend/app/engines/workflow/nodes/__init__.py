# backend/app/engines/workflow/nodes/__init__.py
"""内置节点集合"""
from app.engines.workflow.nodes.generation_nodes import (
    CharacterGenNode,
    LLMChatNode,
    TextToImageNode,
    TTSNode,
    VideoComposeNode,
)
from app.engines.workflow.nodes.utility_nodes import (
    ImagePreviewNode,
    TextConcatNode,
    TextInputNode,
)


def register_all_nodes(registry):
    """注册所有内置节点到注册表"""
    node_classes = [
        TextToImageNode, TTSNode, LLMChatNode, VideoComposeNode, CharacterGenNode,
        TextConcatNode, TextInputNode, ImagePreviewNode,
    ]
    for cls in node_classes:
        if not registry.is_registered(cls.get_definition().type):
            registry.register(cls)


__all__ = [
    "TextToImageNode", "TTSNode", "LLMChatNode", "VideoComposeNode", "CharacterGenNode",
    "TextConcatNode", "TextInputNode", "ImagePreviewNode",
    "register_all_nodes",
]
