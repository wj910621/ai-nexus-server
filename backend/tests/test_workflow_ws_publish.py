# backend/tests/test_workflow_ws_publish.py
"""测试工作流 WS publish - 验证执行器在节点/执行事件中正确推送 WS 消息。"""
import pytest
from unittest.mock import AsyncMock, patch

from app.engines.workflow.executor import WorkflowExecutor
from app.engines.workflow.node_base import (
    BaseNode, NodeDefinition, PortDefinition, NodeCategory,
)
from app.engines.workflow.registry import NodeRegistry


class EchoNode(BaseNode):
    """测试节点 - 返回输入"""

    @classmethod
    def get_definition(cls) -> NodeDefinition:
        return NodeDefinition(
            type="echo",
            name="Echo",
            category=NodeCategory.UTILITY,
            inputs=[PortDefinition(name="text", type="text", required=False)],
            outputs=[PortDefinition(name="text", type="text")],
            is_async=False,
        )

    async def execute(self, inputs: dict) -> dict:
        return {"text": inputs.get("text", "echo")}


@pytest.fixture
def registry():
    reg = NodeRegistry()
    reg.register(EchoNode)
    return reg


@pytest.fixture
def executor(registry):
    return WorkflowExecutor(registry=registry)


async def test_workflow_publishes_node_start(executor):
    """节点开始时 publish node_start 事件"""
    workflow = {
        "nodes": [{"id": "1", "type": "echo", "params": {}}],
        "edges": [],
    }

    with patch("app.engines.workflow.executor.ws_manager") as mock_ws:
        mock_ws.publish = AsyncMock()

        await executor.execute(workflow, execution_id="exec_test_1")

        publish_calls = mock_ws.publish.call_args_list
        channel_names = [call.args[0] for call in publish_calls]
        assert "workflow:exec_test_1" in channel_names

        node_start_events = [
            call for call in publish_calls
            if call.args[0] == "workflow:exec_test_1"
            and call.args[1].get("type") == "node_start"
        ]
        assert len(node_start_events) > 0
        assert node_start_events[0].args[1]["node_id"] == "1"


async def test_workflow_publishes_node_complete(executor):
    """节点完成时 publish node_complete 事件"""
    workflow = {
        "nodes": [{"id": "1", "type": "echo", "params": {}}],
        "edges": [],
    }

    with patch("app.engines.workflow.executor.ws_manager") as mock_ws:
        mock_ws.publish = AsyncMock()

        await executor.execute(workflow, execution_id="exec_test_2")

        publish_calls = mock_ws.publish.call_args_list
        complete_events = [
            call for call in publish_calls
            if call.args[0] == "workflow:exec_test_2"
            and call.args[1].get("type") == "node_complete"
        ]
        assert len(complete_events) > 0
        assert complete_events[0].args[1]["node_id"] == "1"
        assert complete_events[0].args[1]["result"] == {"text": "echo"}


async def test_workflow_publishes_execution_complete(executor):
    """工作流完成时 publish execution_complete 事件"""
    workflow = {
        "nodes": [{"id": "1", "type": "echo", "params": {}}],
        "edges": [],
    }

    with patch("app.engines.workflow.executor.ws_manager") as mock_ws:
        mock_ws.publish = AsyncMock()

        await executor.execute(workflow, execution_id="exec_test_3")

        publish_calls = mock_ws.publish.call_args_list
        complete_events = [
            call for call in publish_calls
            if call.args[0] == "workflow:exec_test_3"
            and call.args[1].get("type") == "execution_complete"
        ]
        assert len(complete_events) == 1
        assert complete_events[0].args[1]["status"] == "success"
