# backend/tests/test_workflow_execute_api.py
"""测试工作流执行 API"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.deps import get_current_user
from app.engines.workflow.executor import WorkflowExecution, ExecutionStatus
from app.engines.workflow.node_base import NodeDefinition, NodeCategory


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


@pytest.fixture
def mock_executor():
    executor = AsyncMock()
    mock_execution = MagicMock()
    mock_execution.execution_id = "exec-1"
    mock_execution.user_id = "test-user-id"
    mock_execution.status = ExecutionStatus.COMPLETED
    mock_execution.started_at = 1000.0
    mock_execution.completed_at = 1001.0
    mock_execution.duration = 1.0
    mock_execution.results = {"1": {"text": "echo"}}
    mock_execution.errors = {}
    mock_execution.node_records = {}
    mock_execution.error = None
    mock_execution.get_progress.return_value = {
        "execution_id": "exec-1", "status": "completed",
        "total": 1, "completed": 1, "progress": 1.0,
        "started_at": 1000.0, "completed_at": 1001.0, "duration": 1.0
    }
    executor.execute = AsyncMock(return_value=mock_execution)
    # get_execution 和 cancel 是同步方法，必须用 MagicMock 而非 AsyncMock
    executor.get_execution = MagicMock(return_value=mock_execution)
    executor.cancel = MagicMock(return_value=True)
    return executor


@pytest.mark.asyncio
async def test_execute_workflow_without_auth():
    """测试未认证执行"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/execute", json={"nodes": []})
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_execute_workflow_with_inline_nodes(auth_bypass, mock_executor):
    """测试使用内联节点执行"""
    with patch("app.api.workflows.workflow_executor", mock_executor), \
         patch("app.api.workflows.WorkflowExecutionService") as MockExecService:
        mock_service = AsyncMock()
        mock_service.create = AsyncMock()
        mock_service.update = AsyncMock()
        MockExecService.return_value = mock_service

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/workflows/execute", json={
                "nodes": [{"id": "1", "type": "text_input", "params": {"value": "hi"}}],
                "edges": []
            })
            assert response.status_code == 200
            data = response.json()
            assert data["code"] == 0
            assert data["data"]["status"] == "completed"
            assert data["data"]["execution_id"] == "exec-1"


@pytest.mark.asyncio
async def test_execute_workflow_missing_nodes(auth_bypass, mock_executor):
    """测试缺少 nodes 参数"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/execute", json={})
        assert response.status_code == 400


@pytest.mark.asyncio
async def test_get_execution_status(auth_bypass, mock_executor):
    """测试获取执行状态"""
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/workflows/executions/exec-1/status")
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["execution_id"] == "exec-1"
            assert data["data"]["progress"] == 1.0


@pytest.mark.asyncio
async def test_get_execution_status_not_found(auth_bypass, mock_executor):
    """测试获取不存在的执行状态"""
    mock_executor.get_execution.return_value = None
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/workflows/executions/nonexistent/status")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_execution_status_uses_persisted_record_after_restart(
    auth_bypass, mock_executor
):
    """状态查询在内存记录丢失后回退到持久化执行记录。"""
    from datetime import datetime

    mock_executor.get_execution.return_value = None
    persisted = MagicMock(
        id="12345678-1234-5678-1234-567812345678",
        status="completed",
        node_executions=[{"status": "completed"}],
        started_at=datetime(2026, 1, 1),
        completed_at=datetime(2026, 1, 1, 0, 0, 1),
        duration=1.0,
    )
    with patch("app.api.workflows.workflow_executor", mock_executor), \
         patch("app.api.workflows.WorkflowExecutionService") as Service:
        Service.return_value.get_owned = AsyncMock(return_value=persisted)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/workflows/executions/12345678-1234-5678-1234-567812345678/status"
            )
    assert response.status_code == 200
    assert response.json()["data"]["progress"] == 1.0


@pytest.mark.asyncio
async def test_get_execution_status_rejects_other_user(auth_bypass, mock_executor):
    """执行状态同样受所有权保护。"""
    mock_executor.get_execution.return_value.user_id = "another-user"
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/workflows/executions/exec-1/status")
            assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_execution(auth_bypass, mock_executor):
    """测试取消执行"""
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/workflows/executions/exec-1/cancel")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_cancel_execution_rejects_other_user(auth_bypass, mock_executor):
    """用户不能取消其他用户的执行。"""
    mock_executor.get_execution.return_value.user_id = "another-user"
    with patch("app.api.workflows.workflow_executor", mock_executor):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/workflows/executions/exec-1/cancel")
            assert response.status_code == 404
            mock_executor.cancel.assert_not_called()


@pytest.mark.asyncio
async def test_list_nodes(auth_bypass):
    """测试列出可用节点"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/workflows/nodes")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert isinstance(data["data"], list)
        # 应该包含内置节点
        types = [n["type"] for n in data["data"]]
        assert "text_to_image" in types
        assert "tts" in types
        assert "llm_chat" in types


@pytest.mark.asyncio
async def test_list_templates(auth_bypass):
    """测试列出模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/workflows/templates")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert len(data["data"]) >= 5


@pytest.mark.asyncio
async def test_list_templates_by_category(auth_bypass):
    """测试按分类列出模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/workflows/templates?category=basic")
        assert response.status_code == 200
        data = response.json()
        assert all(t["category"] == "basic" for t in data["data"])


@pytest.mark.asyncio
async def test_apply_template(auth_bypass):
    """测试应用模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/apply-template", json={
            "template_id": "basic_text_to_image"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 0
        assert "nodes" in data["data"]


@pytest.mark.asyncio
async def test_apply_template_not_found(auth_bypass):
    """测试应用不存在的模板"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/workflows/apply-template", json={
            "template_id": "nonexistent"
        })
        assert response.status_code == 404
