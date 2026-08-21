# backend/tests/test_workflow_node_base.py
"""测试节点基类与注册表"""
import pytest
from app.engines.workflow.node_base import (
    BaseNode, NodeDefinition, PortDefinition, ParameterDefinition,
    NodeCategory, NodeStatus,
)
from app.engines.workflow.registry import NodeRegistry


class DummyNode(BaseNode):
    """测试用节点"""
    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="dummy",
            name="测试节点",
            category=NodeCategory.UTILITY,
            inputs=[PortDefinition(name="text", type="text")],
            outputs=[PortDefinition(name="text", type="text")],
            parameters=[ParameterDefinition(name="upper", type="bool", default=False)],
            is_async=False,
        )

    async def execute(self, inputs: dict) -> dict:
        text = inputs.get("text", "")
        if self.params.get("upper"):
            text = text.upper()
        return {"text": text}


def test_port_definition():
    """测试端口定义"""
    port = PortDefinition(name="image", type="image")
    assert port.name == "image"
    assert port.type == "image"
    assert port.required is True
    assert port.default is None


def test_node_definition():
    """测试节点定义"""
    defn = DummyNode.get_definition()
    assert defn.type == "dummy"
    assert defn.name == "测试节点"
    assert defn.category == NodeCategory.UTILITY
    assert len(defn.inputs) == 1
    assert defn.inputs[0].name == "text"
    assert defn.is_async is False


def test_node_status_enum():
    """测试节点状态枚举"""
    assert NodeStatus.IDLE.value == "idle"
    assert NodeStatus.RUNNING.value == "running"
    assert NodeStatus.COMPLETED.value == "completed"
    assert NodeStatus.FAILED.value == "failed"


@pytest.mark.asyncio
async def test_base_node_execute():
    """测试节点执行"""
    node = DummyNode("node-1", {"upper": True})
    assert node.id == "node-1"
    assert node.status == NodeStatus.IDLE

    result = await node.execute({"text": "hello"})
    assert result == {"text": "HELLO"}


def test_node_get_info():
    """测试节点信息"""
    node = DummyNode("node-1")
    info = node.get_info()
    assert info["id"] == "node-1"
    assert info["status"] == "idle"
    assert info["has_result"] is False
    assert info["error"] is None


def test_node_get_elapsed():
    """测试耗时计算"""
    node = DummyNode("node-1")
    assert node.get_elapsed() is None

    node.started_at = 100.0
    node.completed_at = 100.5
    assert node.get_elapsed() == 0.5


def test_registry_register_and_get():
    """测试注册表注册与获取"""
    registry = NodeRegistry()
    registry.register(DummyNode)

    assert registry.is_registered("dummy")
    assert registry.get_node_class("dummy") is DummyNode

    defn = registry.get_definition("dummy")
    assert defn is not None
    assert defn.type == "dummy"


def test_registry_list():
    """测试注册表列表"""
    registry = NodeRegistry()
    registry.register(DummyNode)

    definitions = registry.list_definitions()
    assert len(definitions) == 1
    assert definitions[0].type == "dummy"

    by_category = registry.list_by_category("utility")
    assert len(by_category) == 1


def test_registry_create_node():
    """测试创建节点实例"""
    registry = NodeRegistry()
    registry.register(DummyNode)

    node = registry.create_node("dummy", "test-id", {"upper": False})
    assert isinstance(node, DummyNode)
    assert node.id == "test-id"
    assert node.params == {"upper": False}


def test_registry_duplicate_register():
    """测试重复注册抛异常"""
    registry = NodeRegistry()
    registry.register(DummyNode)
    with pytest.raises(ValueError, match="已注册"):
        registry.register(DummyNode)


def test_registry_create_unknown_type():
    """测试创建未注册节点抛异常"""
    registry = NodeRegistry()
    with pytest.raises(ValueError, match="未注册"):
        registry.create_node("unknown", "id")
