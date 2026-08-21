# backend/app/engines/workflow/registry.py
"""节点注册表 - 管理所有可用节点类型"""
from typing import Optional

from app.engines.workflow.node_base import BaseNode, NodeDefinition


class NodeRegistry:
    """节点注册表单例"""

    def __init__(self):
        self._nodes: dict[str, type[BaseNode]] = {}
        self._definitions: dict[str, NodeDefinition] = {}

    def register(self, node_class: type[BaseNode]) -> type[BaseNode]:
        """注册节点类型（可作为装饰器使用）"""
        definition = node_class.get_definition()
        node_type = definition.type
        if node_type in self._nodes:
            raise ValueError(f"节点类型已注册: {node_type}")
        self._nodes[node_type] = node_class
        self._definitions[node_type] = definition
        return node_class

    def get_node_class(self, node_type: str) -> Optional[type[BaseNode]]:
        """获取节点类"""
        return self._nodes.get(node_type)

    def get_definition(self, node_type: str) -> Optional[NodeDefinition]:
        """获取节点定义"""
        return self._definitions.get(node_type)

    def list_definitions(self) -> list[NodeDefinition]:
        """列出所有节点定义"""
        return list(self._definitions.values())

    def list_by_category(self, category: str) -> list[NodeDefinition]:
        """按分类列出节点定义"""
        return [d for d in self._definitions.values() if d.category.value == category]

    def is_registered(self, node_type: str) -> bool:
        """检查节点类型是否已注册"""
        return node_type in self._nodes

    def create_node(self, node_type: str, node_id: str, params: Optional[dict] = None) -> BaseNode:
        """创建节点实例"""
        node_class = self.get_node_class(node_type)
        if not node_class:
            raise ValueError(f"未注册的节点类型: {node_type}")
        return node_class(node_id, params)

    def clear(self) -> None:
        """清空注册表（测试用）"""
        self._nodes.clear()
        self._definitions.clear()


# 全局单例
node_registry = NodeRegistry()
