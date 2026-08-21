# backend/tests/test_workflow_integration.py
"""Phase 3 端到端集成测试"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deps import get_current_user
from app.engines.base import GenerationResult
from app.engines.workflow.executor import WorkflowExecutor, ExecutionStatus
from app.engines.workflow.registry import NodeRegistry
from app.engines.workflow.nodes import register_all_nodes
from app.engines.workflow.nodes.generation_nodes import TextToImageNode
from app.engines.workflow.nodes.utility_nodes import TextInputNode, ImagePreviewNode


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = "test-user-id"
    user.username = "testuser"
    user.status = "active"
    return user


@pytest.fixture
def auth_bypass(mock_user):
    app.dependency_overrides[get_current_user] = lambda: mock_user
    yield mock_user
    app.dependency_overrides.clear()


def test_register_all_nodes():
    """测试注册所有内置节点"""
    registry = NodeRegistry()
    register_all_nodes(registry)
    definitions = registry.list_definitions()
    types = [d.type for d in definitions]
    # 验证所有节点类型都已注册
    assert "text_to_image" in types
    assert "tts" in types
    assert "llm_chat" in types
    assert "video_compose" in types
    assert "character_gen" in types
    assert "text_input" in types
    assert "text_concat" in types
    assert "image_preview" in types


@pytest.mark.asyncio
async def test_full_workflow_with_mock_engines():
    """测试完整工作流（mock 引擎）：text_input → text_to_image → image_preview"""
    # 准备注册表
    registry = NodeRegistry()
    register_all_nodes(registry)

    # mock 图像引擎
    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/test.png",
        content_type="image/png", metadata={"model": "flux"}
    ))

    executor = WorkflowExecutor(registry=registry)

    workflow = {
        "nodes": [
            {"id": "input", "type": "text_input", "params": {"value": "a cute cat"}},
            {"id": "gen", "type": "text_to_image", "params": {"model": "flux"}},
            {"id": "preview", "type": "image_preview", "params": {}},
        ],
        "edges": [
            {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"},
            {"from": "gen", "to": "preview", "from_port": "image", "to_port": "image"},
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_image_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.results["input"]["text"] == "a cute cat"
    assert execution.results["gen"]["image"] == "/uploads/images/test.png"
    assert execution.results["preview"]["image"] == "/uploads/images/test.png"
    assert execution.duration is not None

    # 验证图像引擎被调用时 prompt 正确传递
    mock_image_engine.text2img.assert_called_once()
    call_kwargs = mock_image_engine.text2img.call_args.kwargs
    assert call_kwargs["prompt"] == "a cute cat"


@pytest.mark.asyncio
async def test_api_full_workflow_execution(auth_bypass):
    """测试通过 API 执行完整工作流"""
    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/api_test.png",
        content_type="image/png", metadata={}
    ))

    with patch("app.api.workflows.workflow_executor") as mock_executor, \
         patch("app.api.workflows.WorkflowExecutionService") as MockService, \
         patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:

        # mock executor 返回成功
        async def mock_execute(
            workflow_data, external_inputs=None, execution_id=None, user_id=None
        ):
            from app.engines.workflow.executor import WorkflowExecution
            exec_obj = WorkflowExecution(
                execution_id=execution_id or "api-test-1",
                workflow_data=workflow_data,
                user_id=user_id,
                status=ExecutionStatus.COMPLETED,
                started_at=1000.0,
                completed_at=1001.0,
                duration=1.0,
            )
            exec_obj.results = {
                "input": {"text": "test"},
                "gen": {"image": "/uploads/images/api_test.png"},
            }
            return exec_obj

        mock_executor.execute = mock_execute
        mock_manager.get_image_engine.return_value = mock_image_engine

        mock_service = AsyncMock()
        mock_service.create = AsyncMock()
        mock_service.update = AsyncMock()
        MockService.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/workflows/execute", json={
                "nodes": [
                    {"id": "input", "type": "text_input", "params": {"value": "test"}},
                    {"id": "gen", "type": "text_to_image", "params": {}},
                ],
                "edges": [
                    {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"}
                ]
            })

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert data["data"]["status"] == "completed"
        assert data["data"]["results"]["gen"]["image"] == "/uploads/images/api_test.png"


@pytest.mark.asyncio
async def test_workflow_with_node_failure():
    """测试工作流节点失败的传播"""
    registry = NodeRegistry()
    register_all_nodes(registry)

    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=False, data=b"", content_type="", metadata={},
        error="Image generation API timeout"
    ))

    executor = WorkflowExecutor(registry=registry)

    workflow = {
        "nodes": [
            {"id": "input", "type": "text_input", "params": {"value": "test"}},
            {"id": "gen", "type": "text_to_image", "params": {}},
        ],
        "edges": [
            {"from": "input", "to": "gen", "from_port": "text", "to_port": "prompt"}
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_image_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.FAILED
    assert "gen" in execution.errors
    assert "Image generation API timeout" in execution.errors["gen"]
    # 输入节点应该成功
    assert execution.results.get("input", {}).get("text") == "test"


@pytest.mark.asyncio
async def test_parallel_nodes_execution():
    """测试并行节点执行"""
    registry = NodeRegistry()
    register_all_nodes(registry)

    mock_image_engine = AsyncMock()
    mock_image_engine.text2img = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/images/par.png",
        content_type="image/png", metadata={}
    ))

    executor = WorkflowExecutor(registry=registry)

    # 两个并行输入 → 一个汇聚节点
    workflow = {
        "nodes": [
            {"id": "in1", "type": "text_input", "params": {"value": "prompt1"}},
            {"id": "in2", "type": "text_input", "params": {"value": "prompt2"}},
            {"id": "gen1", "type": "text_to_image", "params": {}},
            {"id": "gen2", "type": "text_to_image", "params": {}},
        ],
        "edges": [
            {"from": "in1", "to": "gen1", "from_port": "text", "to_port": "prompt"},
            {"from": "in2", "to": "gen2", "from_port": "text", "to_port": "prompt"},
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_image_engine.return_value = mock_image_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.COMPLETED
    # 两个生成节点都应该执行
    assert mock_image_engine.text2img.call_count == 2


@pytest.mark.asyncio
async def test_template_apply_and_execute(auth_bypass):
    """测试应用模板并执行"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. 获取模板列表
        resp = await client.get("/api/workflows/templates")
        templates = resp.json()["data"]
        assert len(templates) > 0

        # 2. 应用第一个基础模板
        basic = next(t for t in templates if t["template_id"] == "basic_text_to_image")
        apply_resp = await client.post("/api/workflows/apply-template", json={
            "template_id": basic["template_id"]
        })
        assert apply_resp.status_code == 200
        workflow_data = apply_resp.json()["data"]
        assert "nodes" in workflow_data
        assert len(workflow_data["nodes"]) == 3


def test_all_node_definitions_valid():
    """测试所有节点定义有效"""
    registry = NodeRegistry()
    register_all_nodes(registry)
    for defn in registry.list_definitions():
        assert defn.type, f"节点 {defn.name} 缺少 type"
        assert defn.name, f"节点 {defn.type} 缺少 name"
        assert defn.category, f"节点 {defn.type} 缺少 category"
        # 至少有一个输入或输出端口
        assert defn.inputs or defn.outputs, f"节点 {defn.type} 没有任何端口"


@pytest.mark.asyncio
async def test_complex_workflow_text_to_speech():
    """测试文本转语音工作流"""
    registry = NodeRegistry()
    register_all_nodes(registry)

    mock_tts_engine = AsyncMock()
    mock_tts_engine.synthesize = AsyncMock(return_value=GenerationResult(
        success=True, data="/uploads/audio/test.mp3",
        content_type="audio/mp3", metadata={}
    ))

    executor = WorkflowExecutor(registry=registry)
    workflow = {
        "nodes": [
            {"id": "input", "type": "text_input", "params": {"value": "你好，世界"}},
            {"id": "tts", "type": "tts", "params": {"voice": "zh-CN-XiaoxiaoNeural"}},
        ],
        "edges": [
            {"from": "input", "to": "tts", "from_port": "text", "to_port": "text"}
        ]
    }

    with patch("app.engines.workflow.nodes.generation_nodes.engine_manager") as mock_manager:
        mock_manager.get_tts_engine.return_value = mock_tts_engine
        execution = await executor.execute(workflow)

    assert execution.status == ExecutionStatus.COMPLETED
    assert execution.results["tts"]["audio"] == "/uploads/audio/test.mp3"
    mock_tts_engine.synthesize.assert_called_once()
    assert mock_tts_engine.synthesize.call_args.kwargs["text"] == "你好，世界"
