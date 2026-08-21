# 前端集成实施计划：WebSocket / SSE / 首次启动向导

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将后端 Phase 7 已实现的 WebSocket/SSE/本地推理运行时检测能力接入前端 React 应用，并提供 4 步首启动向导，使 Web 和 Electron Desktop 两端共享同一套代码。

**Architecture:** 分层架构（UI → Hooks → Store → Transport → Backend）。Transport 层提供 WS 单例客户端 + SSE 工厂函数；Store 层用 zustand 管理连接状态/通知/任务进度；Hooks 层封装 5 个专用 hook；UI 层新增 4 个组件 + 1 个向导页面。Web/Desktop 通过 `isElectron` 检测分支共用代码。视觉采用科技蓝主色 + 默认浅色主题 + 中文优先字体。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic（后端）；React 18 + antd 5 + zustand + axios + lucide-react + react-markdown（前端）；Electron + electron-vite（桌面端）；vitest + @testing-library/react（前端测试）；pytest（后端测试）

**Spec:** `docs/superpowers/specs/2026-07-19-frontend-integration-design.md`

**Test Baseline:** 501 passing → 目标 536+（新增 35+，零回归）

---

## 文件结构总览

### 后端新增/修改（7 个文件）
| 路径 | 操作 | 职责 |
|---|---|---|
| `backend/app/models/user.py` | 修改 | 新增 4 字段 |
| `backend/app/schemas/user.py` | 修改 | 新增 2 schema |
| `backend/app/api/users.py` | 修改 | 新增 2 endpoint |
| `backend/app/engines/workflow/executor.py` | 修改 | publish workflow 事件 |
| `backend/app/services/task_service.py` | 修改 | publish task 进度 |
| `backend/app/services/billing_service.py` | 修改 | publish user 通知 |
| `backend/alembic/versions/006_add_user_preferences.py` | 新增 | 迁移脚本 |

### 前端新增（17 个文件）
| 路径 | 职责 |
|---|---|
| `frontend/src/styles/tokens.css` | CSS 变量（浅色/暗色主题） |
| `frontend/src/utils/runtime.ts` | isElectron + getBackendUrl |
| `frontend/src/api/websocket.ts` | WS 客户端单例 |
| `frontend/src/api/sse.ts` | SSE 工厂函数 |
| `frontend/src/stores/realtimeStore.ts` | 实时状态 store |
| `frontend/src/stores/themeStore.ts` | 主题切换 store |
| `frontend/src/hooks/useWebSocket.ts` | 频道订阅 |
| `frontend/src/hooks/useSSE.ts` | 流式请求 |
| `frontend/src/hooks/useTaskProgress.ts` | 任务进度 |
| `frontend/src/hooks/useWorkflowStream.ts` | 工作流进度 |
| `frontend/src/hooks/useNotifications.ts` | 实时通知 |
| `frontend/src/pages/FirstLaunchPage.tsx` | 4 步向导 |
| `frontend/src/components/common/NotificationBell.tsx` | 通知铃铛 |
| `frontend/src/components/common/RealtimeStatus.tsx` | WS 状态指示 |
| `frontend/src/components/common/ThemeToggle.tsx` | 主题切换按钮 |
| `frontend/src/components/dashboard/TaskProgressList.tsx` | 任务进度列表 |
| `frontend/src/components/project/ChatPanel.tsx` | 流式对话 |

### 前端修改（7 个文件）
| 路径 | 改动 |
|---|---|
| `frontend/src/main.tsx` | import tokens.css |
| `frontend/src/App.tsx` | ConfigProvider 主题动态切换 + 首启检测 |
| `frontend/src/routes/index.tsx` | 新增 /first-launch 路由 |
| `frontend/src/components/workflow/ExecutionPanel.tsx` | 接入 useWorkflowStream |
| `frontend/src/components/layout/TopBar.tsx` | 挂载 3 个新组件 |
| `frontend/src/pages/DashboardPage.tsx` | 挂载 TaskProgressList |
| `frontend/src/pages/ProjectEditorPage.tsx` | 挂载 ChatPanel |
| `frontend/tailwind.config.js` | 扩展 brand/accent/surface 色彩 |

### Desktop 修改（2 个文件）+ 删除（1 个目录）
| 路径 | 操作 |
|---|---|
| `desktop/src/renderer/` | 删除整个目录 |
| `desktop/src/main/first-launch.ts` | 重写为 hash 路由 |
| `desktop/src/preload/api.ts` | 暴露 7 个新 API |

### 法律协议（2 个文件）
| 路径 | 职责 |
|---|---|
| `frontend/src/legal/terms.md` | 用户协议 |
| `frontend/src/legal/privacy.md` | 隐私政策 |

### 测试文件（11 个）
| 路径 | 测试数 |
|---|---|
| `backend/tests/test_user_preferences.py` | 4 |
| `backend/tests/test_first_launch_api.py` | 3 |
| `backend/tests/test_workflow_ws_publish.py` | 3 |
| `frontend/tests/utils/runtime.test.ts` | 3 |
| `frontend/tests/api/websocket.test.ts` | 8 |
| `frontend/tests/api/sse.test.ts` | 6 |
| `frontend/tests/stores/realtimeStore.test.ts` | 5 |
| `frontend/tests/hooks/useWebSocket.test.tsx` | 4 |
| `frontend/tests/hooks/useTaskProgress.test.tsx` | 3 |
| `frontend/tests/hooks/useWorkflowStream.test.tsx` | 3 |
| `frontend/tests/hooks/useNotifications.test.tsx` | 3 |
| `frontend/tests/pages/FirstLaunchPage.test.tsx` | 6 |

---

## Task 1: 后端 User 模型扩展 + Schema + Alembic 迁移

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/schemas/user.py`
- Create: `backend/alembic/versions/006_add_user_preferences.py`
- Test: `backend/tests/test_user_preferences.py`（部分，模型层）

- [ ] **Step 1: 读取现有 User 模型**

Read: `backend/app/models/user.py`
确认现有字段和 Base 类导入路径（应为 `from app.models.base import Base`）。

- [ ] **Step 2: 修改 User 模型，新增 4 字段**

在 `backend/app/models/user.py` 的 User 类末尾（现有字段之后）追加：

```python
    # 前端集成：首启动与偏好设置
    first_launch_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
    preferred_provider: Mapped[str] = mapped_column(
        String(20), default="cloud", nullable=False, server_default="cloud"
    )
    telemetry_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, server_default="true"
    )
    cloud_sync_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False, server_default="false"
    )
```

确保文件顶部已导入 `Boolean`、`String`（若未导入则补充）。

- [ ] **Step 3: 修改 User schema，新增 2 个 Pydantic schema**

在 `backend/app/schemas/user.py` 末尾追加：

```python
from pydantic import Field, field_validator


class UserPreferencesUpdate(BaseModel):
    """用户偏好更新请求"""
    preferred_provider: str | None = Field(None, pattern="^(cloud|local|hybrid)$")
    telemetry_enabled: bool | None = None
    cloud_sync_enabled: bool | None = None


class FirstLaunchUpdate(BaseModel):
    """首启动完成标记"""
    completed: bool = True


class UserPreferencesResponse(BaseModel):
    """用户偏好响应"""
    first_launch_completed: bool
    preferred_provider: str
    telemetry_enabled: bool
    cloud_sync_enabled: bool

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: 创建 Alembic 迁移文件**

Create: `backend/alembic/versions/006_add_user_preferences.py`

```python
"""add user preferences columns

Revision ID: 006_user_prefs
Revises: 005_result_cache
Create Date: 2026-07-19
"""
from alembic import op
import sqlalchemy as sa


revision = "006_user_prefs"
down_revision = "005_result_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column(
        "first_launch_completed", sa.Boolean(),
        nullable=False, server_default=sa.text("false")))
    op.add_column("users", sa.Column(
        "preferred_provider", sa.String(length=20),
        nullable=False, server_default="cloud"))
    op.add_column("users", sa.Column(
        "telemetry_enabled", sa.Boolean(),
        nullable=False, server_default=sa.text("true")))
    op.add_column("users", sa.Column(
        "cloud_sync_enabled", sa.Boolean(),
        nullable=False, server_default=sa.text("false")))


def downgrade() -> None:
    op.drop_column("users", "cloud_sync_enabled")
    op.drop_column("users", "telemetry_enabled")
    op.drop_column("users", "preferred_provider")
    op.drop_column("users", "first_launch_completed")
```

- [ ] **Step 5: 运行测试验证无回归**

```powershell
cd c:\漫剧软件项目\backend
$env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"
py -3.14 -m pytest tests/ -x --tb=short
```

Expected: 501 passed, 0 failed

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/user.py backend/app/schemas/user.py backend/alembic/versions/006_add_user_preferences.py
git commit -m "feat(backend): add user preferences fields and migration"
```

---

## Task 2: 后端用户偏好与首启动 API

**Files:**
- Modify: `backend/app/api/users.py`
- Test: `backend/tests/test_user_preferences.py`
- Test: `backend/tests/test_first_launch_api.py`

- [ ] **Step 1: 读取现有 users.py API**

Read: `backend/app/api/users.py`
确认 router 定义、现有 endpoint、依赖注入（`get_current_user`）。

- [ ] **Step 2: 新增 PUT /me/preferences 和 PUT /me/first-launch endpoint**

在 `backend/app/api/users.py` 的 router 中追加：

```python
from app.schemas.user import UserPreferencesUpdate, FirstLaunchUpdate, UserPreferencesResponse


@router.put("/me/preferences", response_model=UserPreferencesResponse)
async def update_user_preferences(
    payload: UserPreferencesUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """更新当前用户偏好设置"""
    if payload.preferred_provider is not None:
        current_user.preferred_provider = payload.preferred_provider
    if payload.telemetry_enabled is not None:
        current_user.telemetry_enabled = payload.telemetry_enabled
    if payload.cloud_sync_enabled is not None:
        current_user.cloud_sync_enabled = payload.cloud_sync_enabled
    await db.commit()
    await db.refresh(current_user)
    return UserPreferencesResponse.model_validate(current_user)


@router.put("/me/first-launch", response_model=UserPreferencesResponse)
async def update_first_launch(
    payload: FirstLaunchUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserPreferencesResponse:
    """标记首启动完成（幂等）"""
    if payload.completed:
        current_user.first_launch_completed = True
    await db.commit()
    await db.refresh(current_user)
    return UserPreferencesResponse.model_validate(current_user)


@router.get("/me/preferences", response_model=UserPreferencesResponse)
async def get_user_preferences(
    current_user: User = Depends(get_current_user),
) -> UserPreferencesResponse:
    """获取当前用户偏好设置"""
    return UserPreferencesResponse.model_validate(current_user)
```

- [ ] **Step 3: 编写 test_user_preferences.py**

Create: `backend/tests/test_user_preferences.py`

```python
"""测试用户偏好 API"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token
from app.models.base import Base
from app.core.database import engine, AsyncSessionLocal
from app.models.user import User


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def auth_client():
    """创建测试用户并返回已认证客户端"""
    async with AsyncSessionLocal() as db:
        from app.core.security import get_password_hash
        user = User(
            email="test@example.com",
            username="testuser",
            hashed_password=get_password_hash("Test1234!"),
            first_launch_completed=False,
            preferred_provider="cloud",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        token = create_access_token(subject=str(user.id))
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


async def test_update_preferences_requires_auth():
    """未认证请求应返回 401"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put("/api/v1/users/me/preferences", json={})
        assert resp.status_code == 401


async def test_update_preferences_success(auth_client):
    """更新偏好成功"""
    resp = await auth_client.put("/api/v1/users/me/preferences", json={
        "preferred_provider": "hybrid",
        "telemetry_enabled": False,
        "cloud_sync_enabled": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["preferred_provider"] == "hybrid"
    assert data["telemetry_enabled"] is False
    assert data["cloud_sync_enabled"] is True


async def test_update_preferences_invalid_provider(auth_client):
    """无效 provider 应返回 422"""
    resp = await auth_client.put("/api/v1/users/me/preferences", json={
        "preferred_provider": "invalid",
    })
    assert resp.status_code == 422


async def test_get_preferences(auth_client):
    """获取偏好"""
    resp = await auth_client.get("/api/v1/users/me/preferences")
    assert resp.status_code == 200
    assert data["preferred_provider"] == "cloud"
    assert data["first_launch_completed"] is False
```

- [ ] **Step 4: 编写 test_first_launch_api.py**

Create: `backend/tests/test_first_launch_api.py`

```python
"""测试首启动 API"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.security import create_access_token, get_password_hash
from app.models.base import Base
from app.core.database import engine, AsyncSessionLocal
from app.models.user import User


@pytest.fixture(autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def auth_client():
    async with AsyncSessionLocal() as db:
        user = User(
            email="test2@example.com",
            username="testuser2",
            hashed_password=get_password_hash("Test1234!"),
            first_launch_completed=False,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        token = create_access_token(subject=str(user.id))
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.headers["Authorization"] = f"Bearer {token}"
        yield client


async def test_first_launch_requires_auth():
    """未认证应返回 401"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.put("/api/v1/users/me/first-launch", json={"completed": True})
        assert resp.status_code == 401


async def test_first_launch_mark_completed(auth_client):
    """标记首启动完成"""
    resp = await auth_client.put("/api/v1/users/me/first-launch", json={"completed": True})
    assert resp.status_code == 200
    assert resp.json()["first_launch_completed"] is True


async def test_first_launch_idempotent(auth_client):
    """重复调用幂等"""
    await auth_client.put("/api/v1/users/me/first-launch", json={"completed": True})
    resp = await auth_client.put("/api/v1/users/me/first-launch", json={"completed": True})
    assert resp.status_code == 200
    assert resp.json()["first_launch_completed"] is True
```

- [ ] **Step 5: 运行新测试**

```powershell
cd c:\漫剧软件项目\backend
$env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"
py -3.14 -m pytest tests/test_user_preferences.py tests/test_first_launch_api.py -v
```

Expected: 7 passed

- [ ] **Step 6: 全量回归**

```powershell
py -3.14 -m pytest tests/ -x --tb=short
```

Expected: 508 passed (501 + 7 new)

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/users.py backend/tests/test_user_preferences.py backend/tests/test_first_launch_api.py
git commit -m "feat(backend): add user preferences and first-launch APIs"
```

---

## Task 3: 后端 WS publish 扩展（workflow / task / billing）

**Files:**
- Modify: `backend/app/engines/workflow/executor.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/billing_service.py`
- Test: `backend/tests/test_workflow_ws_publish.py`

- [ ] **Step 1: 读取 executor.py 找到节点执行位置**

Read: `backend/app/engines/workflow/executor.py`
找到节点执行循环（通常是 `for node in dag.topological_sort():` 或类似）。

- [ ] **Step 2: 在 executor.py 中添加 WS publish**

在 executor.py 顶部导入（若未导入）：

```python
from app.api.websockets import ws_manager
```

在节点执行前后添加 publish 调用。示例（具体位置根据现有代码调整）：

```python
import asyncio
from datetime import datetime


async def execute_workflow(self, execution_id: str, ...):
    """工作流执行主循环"""
    channel = f"workflow:{execution_id}"
    completed = 0
    total = len(nodes)
    start_time = datetime.utcnow()
    
    for node in nodes:
        # 节点开始事件
        await ws_manager.publish(channel, {
            "type": "node_start",
            "node_id": node.id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        try:
            result = await self._execute_node(node, context)
            completed += 1
            
            # 节点完成事件
            await ws_manager.publish(channel, {
                "type": "node_complete",
                "node_id": node.id,
                "result": result,
                "duration_ms": int((datetime.utcnow() - node_start).total_seconds() * 1000),
            })
            
            # 进度事件
            await ws_manager.publish(channel, {
                "type": "progress",
                "completed": completed,
                "total": total,
                "progress": completed / total,
            })
            
        except Exception as e:
            # 节点失败事件
            await ws_manager.publish(channel, {
                "type": "node_error",
                "node_id": node.id,
                "error": str(e),
            })
            raise
    
    # 执行完成事件
    await ws_manager.publish(channel, {
        "type": "execution_complete",
        "status": "success",
        "total_duration_ms": int((datetime.utcnow() - start_time).total_seconds() * 1000),
    })
```

- [ ] **Step 3: 在 task_service.py 中添加进度 publish**

Read: `backend/app/services/task_service.py`
找到任务状态更新方法（通常是 `update_task_status` 或类似）。

在状态更新方法中追加：

```python
from app.api.websockets import ws_manager


async def update_task_progress(self, task_id: str, progress: float, stage: str = "", eta: int | None = None):
    """更新任务进度并推送到 WS"""
    # ... 现有数据库更新逻辑 ...
    
    await ws_manager.publish(f"task:{task_id}", {
        "type": "progress",
        "taskId": task_id,
        "progress": progress,
        "stage": stage,
        "eta": eta,
    })
```

- [ ] **Step 4: 在 billing_service.py 中添加通知 publish**

Read: `backend/app/services/billing_service.py`
找到额度检查/订阅检查方法。

在额度低和订阅到期处追加：

```python
from app.api.websockets import ws_manager


async def _notify_user_low_credit(self, user_id: str, current_credits: int, threshold: int):
    """额度低通知"""
    await ws_manager.publish(f"user:{user_id}", {
        "type": "notification",
        "data": {
            "id": f"credit_low_{user_id}_{int(datetime.utcnow().timestamp())}",
            "type": "credit_low",
            "title": "额度不足",
            "body": f"本月生成额度已用 {int(current_credits / threshold * 100)}%",
            "createdAt": int(datetime.utcnow().timestamp() * 1000),
            "read": False,
        },
    })


async def _notify_user_subscription_expiring(self, user_id: str, days_left: int):
    """订阅即将到期通知"""
    await ws_manager.publish(f"user:{user_id}", {
        "type": "notification",
        "data": {
            "id": f"sub_expiring_{user_id}_{int(datetime.utcnow().timestamp())}",
            "type": "subscription_expiring",
            "title": "订阅到期",
            "body": f"Pro 订阅 {days_left} 天后到期",
            "createdAt": int(datetime.utcnow().timestamp() * 1000),
            "read": False,
        },
    })
```

- [ ] **Step 5: 编写 test_workflow_ws_publish.py**

Create: `backend/tests/test_workflow_ws_publish.py`

```python
"""测试工作流 WS publish"""
import pytest
from unittest.mock import AsyncMock, patch
from app.engines.workflow.executor import WorkflowExecutor


@pytest.mark.asyncio
async def test_workflow_publishes_node_start():
    """节点开始时 publish node_start 事件"""
    executor = WorkflowExecutor()
    
    with patch("app.engines.workflow.executor.ws_manager") as mock_ws:
        mock_ws.publish = AsyncMock()
        
        # 模拟执行
        await executor._execute_workflow_for_test(
            execution_id="exec_test_1",
            nodes=[{"id": "node_1", "type": "generate_image"}],
        )
        
        # 验证 publish 被调用
        publish_calls = mock_ws.publish.call_args_list
        channel_names = [call.args[0] for call in publish_calls]
        assert "workflow:exec_test_1" in channel_names
        
        # 验证 node_start 事件
        node_start_events = [
            call for call in publish_calls
            if call.args[0] == "workflow:exec_test_1"
            and call.args[1].get("type") == "node_start"
        ]
        assert len(node_start_events) > 0


@pytest.mark.asyncio
async def test_workflow_publishes_node_complete():
    """节点完成时 publish node_complete 事件"""
    executor = WorkflowExecutor()
    
    with patch("app.engines.workflow.executor.ws_manager") as mock_ws:
        mock_ws.publish = AsyncMock()
        
        await executor._execute_workflow_for_test(
            execution_id="exec_test_2",
            nodes=[{"id": "node_1", "type": "generate_image"}],
        )
        
        publish_calls = mock_ws.publish.call_args_list
        complete_events = [
            call for call in publish_calls
            if call.args[0] == "workflow:exec_test_2"
            and call.args[1].get("type") == "node_complete"
        ]
        assert len(complete_events) > 0


@pytest.mark.asyncio
async def test_workflow_publishes_execution_complete():
    """工作流完成时 publish execution_complete 事件"""
    executor = WorkflowExecutor()
    
    with patch("app.engines.workflow.executor.ws_manager") as mock_ws:
        mock_ws.publish = AsyncMock()
        
        await executor._execute_workflow_for_test(
            execution_id="exec_test_3",
            nodes=[{"id": "node_1", "type": "generate_image"}],
        )
        
        publish_calls = mock_ws.publish.call_args_list
        complete_events = [
            call for call in publish_calls
            if call.args[0] == "workflow:exec_test_3"
            and call.args[1].get("type") == "execution_complete"
        ]
        assert len(complete_events) == 1
        assert complete_events[0].args[1]["status"] == "success"
```

- [ ] **Step 6: 运行测试**

```powershell
cd c:\漫剧软件项目\backend
$env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"
py -3.14 -m pytest tests/test_workflow_ws_publish.py -v
```

Expected: 3 passed

- [ ] **Step 7: 全量回归**

```powershell
py -3.14 -m pytest tests/ -x --tb=short
```

Expected: 511 passed (508 + 3 new)

- [ ] **Step 8: Commit**

```bash
git add backend/app/engines/workflow/executor.py backend/app/services/task_service.py backend/app/services/billing_service.py backend/tests/test_workflow_ws_publish.py
git commit -m "feat(backend): add WS publish for workflow/task/billing events"
```

---

## Task 4: 前端视觉设计 tokens + 主题切换

**Files:**
- Create: `frontend/src/styles/tokens.css`
- Create: `frontend/src/stores/themeStore.ts`
- Create: `frontend/src/components/common/ThemeToggle.tsx`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 tokens.css（CSS 变量定义）**

Create: `frontend/src/styles/tokens.css`

```css
/* ComicStudio AI 视觉设计 tokens - 科技蓝主色 + 默认浅色 */

:root {
  /* 主色 - 科技蓝 */
  --brand-primary: #3B82F6;
  --brand-primary-hover: #2563EB;
  --brand-primary-active: #1D4ED8;
  --brand-primary-light: #DBEAFE;
  --brand-gradient: linear-gradient(135deg, #3B82F6 0%, #6366F1 100%);

  /* 辅色 */
  --accent-cyan: #06B6D4;
  --accent-emerald: #10B981;
  --accent-amber: #F59E0B;
  --accent-rose: #EF4444;
  --accent-violet: #8B5CF6;

  /* 浅色主题（默认） */
  --bg-base: #FFFFFF;
  --bg-surface: #F9FAFB;
  --bg-elevated: #FFFFFF;
  --bg-hover: #F3F4F6;
  --bg-active: #E5E7EB;

  --border-subtle: #F3F4F6;
  --border-default: #E5E7EB;
  --border-strong: #D1D5DB;

  --text-primary: #111827;
  --text-secondary: #4B5563;
  --text-tertiary: #9CA3AF;
  --text-inverse: #FFFFFF;

  /* 阴影 */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 2px 4px -1px rgba(0, 0, 0, 0.04);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.08), 0 4px 6px -2px rgba(0, 0, 0, 0.04);
  --shadow-glow: 0 0 0 3px rgba(59, 130, 246, 0.15);

  /* 间距 */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --space-16: 64px;

  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
  --radius-xl: 12px;
  --radius-full: 9999px;

  /* 过渡 */
  --transition-fast: 150ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-base: 200ms cubic-bezier(0.4, 0, 0.2, 1);
  --transition-slow: 300ms cubic-bezier(0.4, 0, 0.2, 1);
}

[data-theme="dark"] {
  --bg-base: #0F172A;
  --bg-surface: #1E293B;
  --bg-elevated: #334155;
  --bg-hover: #334155;
  --bg-active: #475569;

  --border-subtle: #1E293B;
  --border-default: #334155;
  --border-strong: #475569;

  --text-primary: #F1F5F9;
  --text-secondary: #94A3B8;
  --text-tertiary: #64748B;

  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.4), 0 2px 4px -1px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.5), 0 4px 6px -2px rgba(0, 0, 0, 0.3);
  --shadow-glow: 0 0 0 3px rgba(59, 130, 246, 0.25);
}

body {
  background: var(--bg-base);
  color: var(--text-primary);
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Hiragino Sans GB',
               -apple-system, BlinkMacSystemFont, sans-serif;
  transition: background 200ms, color 200ms;
}

@keyframes pulse-dot {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

@keyframes blink {
  50% { opacity: 0; }
}
```

- [ ] **Step 2: 创建 themeStore.ts**

Create: `frontend/src/stores/themeStore.ts`

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type Theme = 'light' | 'dark'

interface ThemeState {
  theme: Theme
  setTheme: (t: Theme) => void
  toggleTheme: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: 'light', // 默认浅色
      setTheme: (theme) => {
        document.documentElement.setAttribute('data-theme', theme)
        set({ theme })
      },
      toggleTheme: () =>
        set((state) => {
          const next = state.theme === 'light' ? 'dark' : 'light'
          document.documentElement.setAttribute('data-theme', next)
          return { theme: next }
        }),
    }),
    {
      name: 'comicstudio-theme',
      onRehydrateStorage: () => (state) => {
        if (state) {
          document.documentElement.setAttribute('data-theme', state.theme)
        }
      },
    }
  )
)
```

- [ ] **Step 3: 创建 ThemeToggle 组件**

Install dependency first:

```powershell
cd c:\漫剧软件项目\frontend
npm install lucide-react clsx tailwind-merge
```

Create: `frontend/src/components/common/ThemeToggle.tsx`

```tsx
import { Sun, Moon } from 'lucide-react'
import { useThemeStore } from '@/stores/themeStore'
import styles from './ThemeToggle.module.css'

export default function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggleTheme)

  return (
    <button
      className={styles.toggle}
      onClick={toggleTheme}
      title={theme === 'light' ? '切换到暗色' : '切换到浅色'}
      aria-label="切换主题"
    >
      {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
    </button>
  )
}
```

Create: `frontend/src/components/common/ThemeToggle.module.css`

```css
.toggle {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: transparent;
  border: 1px solid var(--border-default);
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.toggle:hover {
  background: var(--bg-hover);
  color: var(--text-primary);
}
```

- [ ] **Step 4: 修改 main.tsx 引入 tokens.css**

Modify: `frontend/src/main.tsx`

```typescript
import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles/tokens.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)
```

- [ ] **Step 5: 修改 App.tsx 动态切换 antd 主题**

Read: `frontend/src/App.tsx`

Modify: `frontend/src/App.tsx`

```tsx
import { ConfigProvider, theme as antdTheme } from 'antd'
import zhCN from 'antd/locale/zh_CN'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter } from 'react-router-dom'
import AppRoutes from './routes'
import { useThemeStore } from './stores/themeStore'

const queryClient = new QueryClient()

export default function App() {
  const themeMode = useThemeStore((s) => s.theme)

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: themeMode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm,
        token: {
          colorPrimary: '#3B82F6',
          borderRadius: 6,
          fontFamily: "'PingFang SC', 'Microsoft YaHei', -apple-system, sans-serif",
        },
      }}
    >
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </QueryClientProvider>
    </ConfigProvider>
  )
}
```

- [ ] **Step 6: 扩展 tailwind.config.js**

Read: `frontend/tailwind.config.js`

Modify: 在 theme.extend 中追加：

```javascript
module.exports = {
  // ... 现有配置
  theme: {
    extend: {
      colors: {
        brand: {
          primary: 'var(--brand-primary)',
          hover: 'var(--brand-primary-hover)',
          active: 'var(--brand-primary-active)',
          light: 'var(--brand-primary-light)',
        },
        accent: {
          cyan: 'var(--accent-cyan)',
          emerald: 'var(--accent-emerald)',
          amber: 'var(--accent-amber)',
          rose: 'var(--accent-rose)',
          violet: 'var(--accent-violet)',
        },
        surface: {
          base: 'var(--bg-base)',
          surface: 'var(--bg-surface)',
          elevated: 'var(--bg-elevated)',
          hover: 'var(--bg-hover)',
          active: 'var(--bg-active)',
        },
      },
      boxShadow: {
        glow: 'var(--shadow-glow)',
      },
      animation: {
        'pulse-dot': 'pulse-dot 2s ease-in-out infinite',
        blink: 'blink 1s infinite',
      },
    },
  },
}
```

- [ ] **Step 7: 验证前端构建**

```powershell
cd c:\漫剧软件项目\frontend
npm run build
```

Expected: 构建成功，无 TypeScript 错误

- [ ] **Step 8: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/stores/themeStore.ts frontend/src/components/common/ThemeToggle.tsx frontend/src/components/common/ThemeToggle.module.css frontend/src/main.tsx frontend/src/App.tsx frontend/tailwind.config.js frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add visual design tokens and theme switching"
```

---

## Task 5: 前端 Transport 层（runtime + websocket + sse）

**Files:**
- Create: `frontend/src/utils/runtime.ts`
- Create: `frontend/src/api/websocket.ts`
- Create: `frontend/src/api/sse.ts`
- Test: `frontend/tests/utils/runtime.test.ts`
- Test: `frontend/tests/api/websocket.test.ts`
- Test: `frontend/tests/api/sse.test.ts`

- [ ] **Step 1: 创建 runtime.ts（环境检测）**

Create: `frontend/src/utils/runtime.ts`

```typescript
/**
 * 运行时环境检测与抽象
 * Web 端 fallback 到浏览器默认行为
 * Desktop 端通过 preload bridge 调用 Electron 主进程
 */

declare global {
  interface Window {
    electronAPI?: {
      getBackendUrl?: () => string
      getRuntimeInfo?: () => Promise<RuntimeInfo>
      chooseDirectory?: () => Promise<string | null>
      saveSettings?: (s: unknown) => Promise<void>
      completeFirstLaunch?: () => Promise<void>
      downloadModel?: (name: string) => Promise<void>
      onBackendUrlChange?: (cb: (url: string) => void) => () => void
      showNotification?: (n: unknown) => void
    }
  }
}

export interface RuntimeInfo {
  hasGpu: boolean
  gpuName: string
  vramMB: number
  ramMB: number
  recommendedProvider: 'local-gpu' | 'local-cpu' | 'remote'
  platform: string
}

export const isElectron: boolean =
  typeof window !== 'undefined' && 'electronAPI' in window

/**
 * 获取后端 URL
 * - Web 端：返回空字符串（使用同源相对路径）
 * - Desktop 端：返回 http://127.0.0.1:{port}
 */
export function getBackendUrl(): string {
  return window.electronAPI?.getBackendUrl?.() ?? ''
}

/**
 * 获取 WebSocket URL
 */
export function getWebSocketUrl(token: string): string {
  const baseUrl = getBackendUrl()
  const wsBase = baseUrl.replace(/^http/, 'ws') || `${window.location.protocol.replace(/^http/, 'ws')}//${window.location.host}`
  return `${wsBase}/ws?token=${encodeURIComponent(token)}`
}

/**
 * 获取 SSE/API URL（拼接相对路径）
 */
export function getApiUrl(path: string): string {
  return `${getBackendUrl()}${path}`
}
```

- [ ] **Step 2: 创建 websocket.ts（WS 客户端单例）**

Create: `frontend/src/api/websocket.ts`

```typescript
import { getWebSocketUrl } from '@/utils/runtime'

export type WSStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed'

export interface WSMessage {
  type: 'subscribed' | 'unsubscribed' | 'pong' | 'error' | string
  channel?: string
  data?: unknown
  [key: string]: unknown
}

type ChannelHandler = (msg: WSMessage) => void

const HEARTBEAT_INTERVAL = 30000
const HEARTBEAT_TIMEOUT = 10000
const MAX_RECONNECT_ATTEMPTS = 5
const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000]

class WebSocketClient {
  private ws: WebSocket | null = null
  private status: WSStatus = 'idle'
  private token: string | null = null
  private channelRefs: Map<string, number> = new Map()
  private handlers: Map<string, Set<ChannelHandler>> = new Map()
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private heartbeatTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private statusListeners: Set<(s: WSStatus) => void> = new Set()

  async connect(token: string): Promise<void> {
    if (this.status === 'connected' || this.status === 'connecting') {
      if (this.token === token) return
      await this.disconnect()
    }
    this.token = token
    this.setStatus('connecting')
    return this._doConnect()
  }

  private _doConnect(): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.token) {
        reject(new Error('No token'))
        return
      }
      const url = getWebSocketUrl(this.token)
      this.ws = new WebSocket(url)

      this.ws.onopen = () => {
        this.setStatus('connected')
        this.reconnectAttempts = 0
        this._startHeartbeat()
        this._resubscribeAll()
        resolve()
      }

      this.ws.onmessage = (event) => {
        this._handleMessage(event.data)
      }

      this.ws.onclose = (event) => {
        this._cleanup()
        if (event.code === 4001) {
          // 认证失败，不重连
          this.setStatus('closed')
          this._dispatchStatusToListeners()
          return
        }
        this._scheduleReconnect()
      }

      this.ws.onerror = () => {
        // onclose 会随后触发，重连逻辑在 onclose 中处理
      }
    })
  }

  async disconnect(): Promise<void> {
    this._cleanup()
    if (this.ws) {
      this.ws.onclose = null
      this.ws.close()
      this.ws = null
    }
    this.setStatus('idle')
  }

  subscribe(channel: string, handler: ChannelHandler): () => void {
    // 引用计数
    const count = this.channelRefs.get(channel) ?? 0
    this.channelRefs.set(channel, count + 1)

    // 首次订阅发送 subscribe 消息
    if (count === 0 && this.status === 'connected') {
      this._send({ type: 'subscribe', channel })
    }

    // 注册 handler
    if (!this.handlers.has(channel)) {
      this.handlers.set(channel, new Set())
    }
    this.handlers.get(channel)!.add(handler)

    // 返回取消订阅函数
    return () => {
      const handlers = this.handlers.get(channel)
      if (handlers) {
        handlers.delete(handler)
        if (handlers.size === 0) {
          this.handlers.delete(channel)
        }
      }
      const newCount = (this.channelRefs.get(channel) ?? 1) - 1
      if (newCount <= 0) {
        this.channelRefs.delete(channel)
        if (this.status === 'connected') {
          this._send({ type: 'unsubscribe', channel })
        }
      } else {
        this.channelRefs.set(channel, newCount)
      }
    }
  }

  getStatus(): WSStatus {
    return this.status
  }

  onStatusChange(cb: (s: WSStatus) => void): () => void {
    this.statusListeners.add(cb)
    cb(this.status)
    return () => this.statusListeners.delete(cb)
  }

  async reconnectWithToken(token: string): Promise<void> {
    await this.disconnect()
    await this.connect(token)
  }

  private _send(msg: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(msg))
    }
  }

  private _handleMessage(raw: string): void {
    let msg: WSMessage
    try {
      msg = JSON.parse(raw)
    } catch {
      return
    }

    // 控制消息
    if (msg.type === 'pong') {
      this._clearHeartbeatTimeout()
      return
    }
    if (msg.type === 'subscribed' || msg.type === 'unsubscribed' || msg.type === 'error') {
      return
    }

    // 业务消息：按 channel 分发
    if (msg.channel) {
      const handlers = this.handlers.get(msg.channel)
      if (handlers) {
        handlers.forEach((h) => h(msg))
      }
    }
  }

  private _startHeartbeat(): void {
    this._clearHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      this._send({ type: 'ping' })
      this.heartbeatTimeoutTimer = setTimeout(() => {
        // 心跳超时，强制重连
        if (this.ws) {
          this.ws.close()
        }
      }, HEARTBEAT_TIMEOUT)
    }, HEARTBEAT_INTERVAL)
  }

  private _clearHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    this._clearHeartbeatTimeout()
  }

  private _clearHeartbeatTimeout(): void {
    if (this.heartbeatTimeoutTimer) {
      clearTimeout(this.heartbeatTimeoutTimer)
      this.heartbeatTimeoutTimer = null
    }
  }

  private _scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.setStatus('closed')
      return
    }
    const delay = RECONNECT_DELAYS[Math.min(this.reconnectAttempts, RECONNECT_DELAYS.length - 1)]
    this.setStatus('reconnecting')
    this.reconnectAttempts++
    this.reconnectTimer = setTimeout(() => {
      this._doConnect().catch(() => {
        // 连接失败，_doConnect 的 onclose 会再次调度重连
      })
    }, delay)
  }

  private _resubscribeAll(): void {
    for (const channel of this.channelRefs.keys()) {
      this._send({ type: 'subscribe', channel })
    }
  }

  private _cleanup(): void {
    this._clearHeartbeat()
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
  }

  private setStatus(s: WSStatus): void {
    this.status = s
    this._dispatchStatusToListeners()
  }

  private _dispatchStatusToListeners(): void {
    this.statusListeners.forEach((cb) => cb(this.status))
  }
}

export const wsClient = new WebSocketClient()
```

- [ ] **Step 3: 创建 sse.ts（SSE 工厂函数）**

Create: `frontend/src/api/sse.ts`

```typescript
import { getApiUrl } from '@/utils/runtime'
import { tokenStorage } from '@/utils/token'

export interface SSEOptions {
  url: string
  body?: unknown
  signal?: AbortSignal
  onMessage: (data: string) => void
  onError?: (err: Error) => void
  onDone?: () => void
}

const SSE_TIMEOUT = 60000

/**
 * 基于 fetch + ReadableStream 的 SSE 客户端
 * 不使用 EventSource（不支持自定义 header 和 POST）
 */
export async function fetchSSE(options: SSEOptions): Promise<void> {
  const { url, body, signal, onMessage, onError, onDone } = options

  const fullUrl = getApiUrl(url)
  const token = tokenStorage.getAccessToken()

  // 超时控制
  const timeoutController = new AbortController()
  const timeoutId = setTimeout(() => {
    timeoutController.abort()
  }, SSE_TIMEOUT)

  // 合并外部 signal 和超时 signal
  const combinedSignal = signal
    ? AbortSignal.any([signal, timeoutController.signal])
    : timeoutController.signal

  try {
    const response = await fetch(fullUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: combinedSignal,
    })

    if (!response.ok) {
      const err = new Error(`HTTP ${response.status}`)
      onError?.(err)
      return
    }

    if (!response.body) {
      onError?.(new Error('No response body'))
      return
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let lastDataTime = Date.now()

    // 重置超时计时器（每次收到数据时）
    const dataTimeoutController = new AbortController()
    const dataTimeoutId = setInterval(() => {
      if (Date.now() - lastDataTime > SSE_TIMEOUT) {
        dataTimeoutController.abort()
        clearInterval(dataTimeoutId)
      }
    }, 1000)

    try {
      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        lastDataTime = Date.now()
        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const event of events) {
          if (event.startsWith('data: ')) {
            onMessage(event.slice(6))
          }
        }
      }
      onDone?.()
    } finally {
      clearInterval(dataTimeoutId)
      clearTimeout(timeoutId)
    }
  } catch (err) {
    clearTimeout(timeoutId)
    if ((err as Error).name === 'AbortError') {
      onError?.(new Error('SSE aborted'))
    } else {
      onError?.(err as Error)
    }
  }
}
```

- [ ] **Step 4: 编写 runtime.test.ts**

Create: `frontend/tests/utils/runtime.test.ts`

```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'

describe('runtime utils', () => {
  beforeEach(() => {
    delete (window as any).electronAPI
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('isElectron 应为 false（无 electronAPI）', async () => {
    const { isElectron } = await import('@/utils/runtime')
    expect(isElectron).toBe(false)
  })

  it('isElectron 应为 true（有 electronAPI）', async () => {
    ;(window as any).electronAPI = { getBackendUrl: () => 'http://127.0.0.1:8000' }
    const { isElectron } = await import('@/utils/runtime')
    expect(isElectron).toBe(true)
  })

  it('getBackendUrl 默认返回空字符串', async () => {
    const { getBackendUrl } = await import('@/utils/runtime')
    expect(getBackendUrl()).toBe('')
  })

  it('getBackendUrl 返回 electronAPI 提供的 URL', async () => {
    ;(window as any).electronAPI = { getBackendUrl: () => 'http://127.0.0.1:8000' }
    const { getBackendUrl } = await import('@/utils/runtime')
    expect(getBackendUrl()).toBe('http://127.0.0.1:8000')
  })
})
```

- [ ] **Step 5: 编写 websocket.test.ts**

Create: `frontend/tests/api/websocket.test.ts`

```typescript
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { wsClient, WSStatus } from '@/api/websocket'

// Mock WebSocket
class MockWebSocket {
  static instances: MockWebSocket[] = []
  onopen: (() => void) | null = null
  onmessage: ((event: { data: string }) => void) | null = null
  onclose: ((event: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  readyState = 0
  sentMessages: string[] = []

  constructor(public url: string) {
    MockWebSocket.instances.push(this)
    setTimeout(() => {
      this.readyState = 1
      this.onopen?.()
    }, 0)
  }

  send(data: string) {
    this.sentMessages.push(data)
  }

  close() {
    this.readyState = 3
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) })
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

describe('WebSocketClient', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
  })

  afterEach(async () => {
    await wsClient.disconnect()
  })

  it('connect 后状态应为 connected', async () => {
    await wsClient.connect('test-token')
    expect(wsClient.getStatus()).toBe('connected')
  })

  it('subscribe 应发送 subscribe 消息', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    wsClient.subscribe('task:123', () => {})
    
    expect(mock.sentMessages).toContain(
      JSON.stringify({ type: 'subscribe', channel: 'task:123' })
    )
  })

  it('多次 subscribe 同一频道应只发送一次 subscribe', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const unsub1 = wsClient.subscribe('task:123', () => {})
    const unsub2 = wsClient.subscribe('task:123', () => {})
    
    const subscribeCount = mock.sentMessages.filter(
      m => m === JSON.stringify({ type: 'subscribe', channel: 'task:123' })
    ).length
    expect(subscribeCount).toBe(1)
    
    unsub1()
    unsub2()
  })

  it('所有 handler 取消订阅后应发送 unsubscribe', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const unsub1 = wsClient.subscribe('task:456', () => {})
    const unsub2 = wsClient.subscribe('task:456', () => {})
    
    unsub1()
    expect(mock.sentMessages).not.toContain(
      JSON.stringify({ type: 'unsubscribe', channel: 'task:456' })
    )
    
    unsub2()
    expect(mock.sentMessages).toContain(
      JSON.stringify({ type: 'unsubscribe', channel: 'task:456' })
    )
  })

  it('收到 channel 消息应调用对应 handler', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const handler = vi.fn()
    wsClient.subscribe('task:789', handler)
    
    mock.simulateMessage({ type: 'progress', channel: 'task:789', data: { progress: 0.5 } })
    
    expect(handler).toHaveBeenCalledWith({
      type: 'progress',
      channel: 'task:789',
      data: { progress: 0.5 },
    })
  })

  it('pong 消息不应转发给 handler', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    const handler = vi.fn()
    wsClient.subscribe('task:999', handler)
    
    mock.simulateMessage({ type: 'pong' })
    
    expect(handler).not.toHaveBeenCalled()
  })

  it('onStatusChange 应被通知', async () => {
    const listener = vi.fn()
    wsClient.onStatusChange(listener)
    
    await wsClient.connect('test-token')
    
    expect(listener).toHaveBeenCalledWith('connecting')
    expect(listener).toHaveBeenCalledWith('connected')
  })

  it('认证失败（4001）应标记 closed 且不重连', async () => {
    await wsClient.connect('test-token')
    const mock = MockWebSocket.instances[0]
    
    mock.onclose?.({ code: 4001 })
    
    expect(wsClient.getStatus()).toBe('closed')
  })
})
```

- [ ] **Step 6: 编写 sse.test.ts**

Create: `frontend/tests/api/sse.test.ts`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { fetchSSE } from '@/api/sse'

// Mock fetch
function createMockResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    start(controller) {
      chunks.forEach(chunk => controller.enqueue(encoder.encode(chunk)))
      controller.close()
    },
  })
  return new Response(stream, { status: 200 })
}

vi.mock('@/utils/token', () => ({
  tokenStorage: {
    getAccessToken: () => 'mock-token',
  },
}))

global.fetch = vi.fn()

describe('fetchSSE', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('正常流式接收 data 事件', async () => {
    const chunks = [
      'data: {"type":"token","content":"好"}\n\n',
      'data: {"type":"token","content":"的"}\n\n',
    ]
    ;(global.fetch as any).mockResolvedValue(createMockResponse(chunks))
    
    const messages: string[] = []
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: (data) => messages.push(data),
    })
    
    expect(messages).toEqual([
      '{"type":"token","content":"好"}',
      '{"type":"token","content":"的"}',
    ])
  })

  it('HTTP 错误应调用 onError', async () => {
    ;(global.fetch as any).mockResolvedValue(new Response('Server Error', { status: 500 }))
    
    const onError = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
      onError,
    })
    
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('AbortSignal 中断应调用 onError', async () => {
    const controller = new AbortController()
    controller.abort()
    ;(global.fetch as any).mockRejectedValue(
      Object.assign(new Error('aborted'), { name: 'AbortError' })
    )
    
    const onError = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      signal: controller.signal,
      onMessage: () => {},
      onError,
    })
    
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('请求应包含 Authorization header', async () => {
    ;(global.fetch as any).mockResolvedValue(createMockResponse([]))
    
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
    })
    
    expect(global.fetch).toHaveBeenCalledWith(
      expect.any(String),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: 'Bearer mock-token',
        }),
      })
    )
  })

  it('空响应体应调用 onError', async () => {
    ;(global.fetch as any).mockResolvedValue(new Response(null, { status: 200 }))
    
    const onError = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
      onError,
    })
    
    expect(onError).toHaveBeenCalledWith(expect.any(Error))
  })

  it('正常结束应调用 onDone', async () => {
    ;(global.fetch as any).mockResolvedValue(createMockResponse([]))
    
    const onDone = vi.fn()
    await fetchSSE({
      url: '/api/v1/chat',
      onMessage: () => {},
      onDone,
    })
    
    expect(onDone).toHaveBeenCalled()
  })
})
```

- [ ] **Step 7: 配置 vitest（若未配置）**

检查 `frontend/vitest.config.ts` 或 `frontend/vite.config.ts` 是否有 test 配置。若无，创建：

```powershell
cd c:\漫剧软件项目\frontend
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom
```

Create or modify: `frontend/vitest.config.ts`

```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

Create: `frontend/tests/setup.ts`

```typescript
import '@testing-library/jest-dom'
```

- [ ] **Step 8: 运行测试**

```powershell
cd c:\漫剧软件项目\frontend
npx vitest run tests/utils/runtime.test.ts tests/api/websocket.test.ts tests/api/sse.test.ts
```

Expected: 17 tests passed (3 + 8 + 6)

- [ ] **Step 9: Commit**

```bash
git add frontend/src/utils/runtime.ts frontend/src/api/websocket.ts frontend/src/api/sse.ts frontend/tests/utils/runtime.test.ts frontend/tests/api/websocket.test.ts frontend/tests/api/sse.test.ts frontend/vitest.config.ts frontend/tests/setup.ts frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add transport layer (runtime/websocket/sse) with tests"
```

---

## Task 6: 前端 Realtime Store

**Files:**
- Create: `frontend/src/stores/realtimeStore.ts`
- Test: `frontend/tests/stores/realtimeStore.test.ts`

- [ ] **Step 1: 创建 realtimeStore.ts**

Create: `frontend/src/stores/realtimeStore.ts`

```typescript
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { WSStatus } from '@/api/websocket'

export interface NotificationItem {
  id: string
  type: 'task_completed' | 'task_failed' | 'credit_low' | 'subscription_expiring' | 'system_maintenance'
  title: string
  body: string
  createdAt: number
  read: boolean
}

export interface TaskProgress {
  taskId: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number // 0-1
  stage: string
  eta?: number
  result?: unknown
  error?: string
}

const MAX_NOTIFICATIONS = 50

interface RealtimeState {
  wsStatus: WSStatus
  notifications: NotificationItem[]
  taskProgress: Record<string, TaskProgress>

  setWsStatus: (s: WSStatus) => void
  addNotification: (n: NotificationItem) => void
  markAllRead: () => void
  updateTaskProgress: (taskId: string, p: TaskProgress) => void
  removeTaskProgress: (taskId: string) => void
}

export const useRealtimeStore = create<RealtimeState>()(
  persist(
    (set) => ({
      wsStatus: 'idle',
      notifications: [],
      taskProgress: {},

      setWsStatus: (wsStatus) => set({ wsStatus }),

      addNotification: (n) =>
        set((state) => ({
          notifications: [...state.notifications, n].slice(-MAX_NOTIFICATIONS),
        })),

      markAllRead: () =>
        set((state) => ({
          notifications: state.notifications.map((n) => ({ ...n, read: true })),
        })),

      updateTaskProgress: (taskId, p) =>
        set((state) => ({
          taskProgress: { ...state.taskProgress, [taskId]: p },
        })),

      removeTaskProgress: (taskId) =>
        set((state) => {
          const { [taskId]: _, ...rest } = state.taskProgress
          return { taskProgress: rest }
        }),
    }),
    {
      name: 'comicstudio-realtime',
      partialize: (state) => ({ notifications: state.notifications }),
      // taskProgress 不持久化（临时状态）
    }
  )
)
```

- [ ] **Step 2: 编写测试**

Create: `frontend/tests/stores/realtimeStore.test.ts`

```typescript
import { describe, it, expect, beforeEach } from 'vitest'
import { useRealtimeStore, NotificationItem } from '@/stores/realtimeStore'

describe('realtimeStore', () => {
  beforeEach(() => {
    useRealtimeStore.setState({
      wsStatus: 'idle',
      notifications: [],
      taskProgress: {},
    })
  })

  it('addNotification 应追加到末尾（FIFO）', () => {
    const n1: NotificationItem = {
      id: '1', type: 'task_completed', title: 't1', body: 'b1', createdAt: 1, read: false,
    }
    const n2: NotificationItem = {
      id: '2', type: 'task_failed', title: 't2', body: 'b2', createdAt: 2, read: false,
    }
    
    useRealtimeStore.getState().addNotification(n1)
    useRealtimeStore.getState().addNotification(n2)
    
    const state = useRealtimeStore.getState()
    expect(state.notifications).toHaveLength(2)
    expect(state.notifications[0].id).toBe('1')
    expect(state.notifications[1].id).toBe('2')
  })

  it('notifications 超过 50 条应裁剪', () => {
    for (let i = 0; i < 55; i++) {
      useRealtimeStore.getState().addNotification({
        id: `${i}`, type: 'task_completed', title: `t${i}`, body: 'b', createdAt: i, read: false,
      })
    }
    
    const state = useRealtimeStore.getState()
    expect(state.notifications).toHaveLength(50)
    // 保留最后 50 条（5-54）
    expect(state.notifications[0].id).toBe('5')
    expect(state.notifications[49].id).toBe('54')
  })

  it('markAllRead 应将所有通知标记为已读', () => {
    useRealtimeStore.getState().addNotification({
      id: '1', type: 'task_completed', title: 't', body: 'b', createdAt: 1, read: false,
    })
    
    useRealtimeStore.getState().markAllRead()
    
    expect(useRealtimeStore.getState().notifications[0].read).toBe(true)
  })

  it('updateTaskProgress 应更新指定 taskId', () => {
    useRealtimeStore.getState().updateTaskProgress('task-1', {
      taskId: 'task-1', status: 'running', progress: 0.5, stage: 'generating',
    })
    
    const state = useRealtimeStore.getState()
    expect(state.taskProgress['task-1']).toEqual({
      taskId: 'task-1', status: 'running', progress: 0.5, stage: 'generating',
    })
  })

  it('removeTaskProgress 应移除指定 taskId', () => {
    useRealtimeStore.getState().updateTaskProgress('task-1', {
      taskId: 'task-1', status: 'completed', progress: 1, stage: 'done',
    })
    useRealtimeStore.getState().removeTaskProgress('task-1')
    
    expect(useRealtimeStore.getState().taskProgress['task-1']).toBeUndefined()
  })

  it('setWsStatus 应更新状态', () => {
    useRealtimeStore.getState().setWsStatus('connected')
    expect(useRealtimeStore.getState().wsStatus).toBe('connected')
  })
})
```

- [ ] **Step 3: 运行测试**

```powershell
cd c:\漫剧软件项目\frontend
npx vitest run tests/stores/realtimeStore.test.ts
```

Expected: 6 tests passed

- [ ] **Step 4: Commit**

```bash
git add frontend/src/stores/realtimeStore.ts frontend/tests/stores/realtimeStore.test.ts
git commit -m "feat(frontend): add realtimeStore with notifications and task progress"
```

---

## Task 7: 前端 Hooks 层（5 个 hooks）

**Files:**
- Create: `frontend/src/hooks/useWebSocket.ts`
- Create: `frontend/src/hooks/useSSE.ts`
- Create: `frontend/src/hooks/useTaskProgress.ts`
- Create: `frontend/src/hooks/useWorkflowStream.ts`
- Create: `frontend/src/hooks/useNotifications.ts`
- Test: `frontend/tests/hooks/useWebSocket.test.tsx`
- Test: `frontend/tests/hooks/useTaskProgress.test.tsx`
- Test: `frontend/tests/hooks/useWorkflowStream.test.tsx`
- Test: `frontend/tests/hooks/useNotifications.test.tsx`

- [ ] **Step 1: 创建 useWebSocket.ts**

Create: `frontend/src/hooks/useWebSocket.ts`

```typescript
import { useEffect, useState } from 'react'
import { wsClient, WSMessage } from '@/api/websocket'
import { tokenStorage } from '@/utils/token'

/**
 * 订阅指定 WS 频道
 * @param channel 频道名（如 'task:123'）；传 null 不订阅
 * @returns 最新消息
 */
export function useWebSocket(channel: string | null): WSMessage | null {
  const [lastMessage, setLastMessage] = useState<WSMessage | null>(null)

  useEffect(() => {
    if (!channel) return

    // 确保已认证并连接
    const token = tokenStorage.getAccessToken()
    if (token && wsClient.getStatus() === 'idle') {
      wsClient.connect(token).catch(() => {
        // 连接失败由重连机制处理
      })
    }

    const unsubscribe = wsClient.subscribe(channel, (msg) => {
      setLastMessage(msg)
    })

    return unsubscribe
  }, [channel])

  return lastMessage
}
```

- [ ] **Step 2: 创建 useSSE.ts**

Create: `frontend/src/hooks/useSSE.ts`

```typescript
import { useState, useRef, useCallback, useEffect } from 'react'
import { fetchSSE } from '@/api/sse'

interface UseSSEReturn {
  data: string
  done: boolean
  error: Error | null
  start: () => void
  abort: () => void
}

/**
 * 发起 SSE 流式请求
 * @param url 请求路径
 * @param body POST body
 */
export function useSSE(url: string, body?: unknown): UseSSEReturn {
  const [data, setData] = useState<string>('')
  const [done, setDone] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const start = useCallback(() => {
    const controller = new AbortController()
    abortRef.current = controller
    setData('')
    setDone(false)
    setError(null)

    fetchSSE({
      url,
      body,
      signal: controller.signal,
      onMessage: (chunk) => setData((prev) => prev + chunk),
      onError: setError,
      onDone: () => setDone(true),
    })
  }, [url, body])

  const abort = useCallback(() => {
    abortRef.current?.abort()
  }, [])

  useEffect(() => () => abort(), [abort])

  return { data, done, error, start, abort }
}
```

- [ ] **Step 3: 创建 useTaskProgress.ts**

Create: `frontend/src/hooks/useTaskProgress.ts`

```typescript
import { useEffect } from 'react'
import { useWebSocket } from './useWebSocket'
import { useRealtimeStore, TaskProgress } from '@/stores/realtimeStore'
import { wsClient } from '@/api/websocket'

/**
 * 订阅任务进度
 * @param taskId 任务 ID；传 null 不订阅
 */
export function useTaskProgress(taskId: string | null): TaskProgress | undefined {
  const lastMsg = useWebSocket(taskId ? `task:${taskId}` : null)
  const removeTaskProgress = useRealtimeStore((s) => s.removeTaskProgress)

  useEffect(() => {
    if (!lastMsg || !taskId) return

    if (lastMsg.type === 'progress' && lastMsg.data) {
      useRealtimeStore.getState().updateTaskProgress(taskId, lastMsg.data as TaskProgress)
    }
  }, [lastMsg, taskId])

  // 任务完成后 3s 自动清理
  useEffect(() => {
    if (!taskId) return
    const progress = useRealtimeStore.getState().taskProgress[taskId]
    if (progress && (progress.status === 'completed' || progress.status === 'failed' || progress.status === 'cancelled')) {
      const timer = setTimeout(() => {
        removeTaskProgress(taskId)
      }, 3000)
      return () => clearTimeout(timer)
    }
  }, [lastMsg, taskId, removeTaskProgress])

  return useRealtimeStore((s) => (taskId ? s.taskProgress[taskId] : undefined))
}
```

- [ ] **Step 4: 创建 useWorkflowStream.ts**

Create: `frontend/src/hooks/useWorkflowStream.ts`

```typescript
import { useEffect, useState } from 'react'
import { useWebSocket } from './useWebSocket'

export interface WorkflowNodeState {
  nodeId: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  result?: unknown
  error?: string
  durationMs?: number
}

export interface WorkflowStreamState {
  nodes: Record<string, WorkflowNodeState>
  completed: number
  total: number
  progress: number
  status: 'idle' | 'running' | 'completed' | 'failed'
  totalDurationMs?: number
}

/**
 * 订阅工作流执行进度
 * @param executionId 执行 ID；传 null 不订阅
 */
export function useWorkflowStream(executionId: string | null): WorkflowStreamState {
  const lastMsg = useWebSocket(executionId ? `workflow:${executionId}` : null)
  const [state, setState] = useState<WorkflowStreamState>({
    nodes: {},
    completed: 0,
    total: 0,
    progress: 0,
    status: 'idle',
  })

  useEffect(() => {
    if (!lastMsg || !executionId) return

    setState((prev) => {
      switch (lastMsg.type) {
        case 'node_start':
          return {
            ...prev,
            status: 'running',
            nodes: {
              ...prev.nodes,
              [lastMsg.node_id as string]: {
                nodeId: lastMsg.node_id as string,
                status: 'running',
              },
            },
          }
        case 'node_complete':
          return {
            ...prev,
            nodes: {
              ...prev.nodes,
              [lastMsg.node_id as string]: {
                nodeId: lastMsg.node_id as string,
                status: 'completed',
                result: lastMsg.result,
                durationMs: lastMsg.duration_ms as number,
              },
            },
          }
        case 'node_error':
          return {
            ...prev,
            nodes: {
              ...prev.nodes,
              [lastMsg.node_id as string]: {
                nodeId: lastMsg.node_id as string,
                status: 'failed',
                error: lastMsg.error as string,
              },
            },
          }
        case 'progress':
          return {
            ...prev,
            completed: lastMsg.completed as number,
            total: lastMsg.total as number,
            progress: lastMsg.progress as number,
          }
        case 'execution_complete':
          return {
            ...prev,
            status: lastMsg.status as 'completed' | 'failed',
            totalDurationMs: lastMsg.total_duration_ms as number,
          }
        default:
          return prev
      }
    })
  }, [lastMsg, executionId])

  return state
}
```

- [ ] **Step 5: 创建 useNotifications.ts**

Create: `frontend/src/hooks/useNotifications.ts`

```typescript
import { useEffect } from 'react'
import { useWebSocket } from './useWebSocket'
import { useRealtimeStore, NotificationItem } from '@/stores/realtimeStore'
import { useAuthStore } from '@/stores/authStore'

/**
 * 订阅用户通知频道
 * 返回当前通知列表
 */
export function useNotifications() {
  const userId = useAuthStore((s) => s.user?.id)
  const lastMsg = useWebSocket(userId ? `user:${userId}` : null)

  useEffect(() => {
    if (!lastMsg) return

    if (lastMsg.type === 'notification' && lastMsg.data) {
      const notification = lastMsg.data as NotificationItem
      useRealtimeStore.getState().addNotification(notification)
      
      // Desktop 系统通知
      window.electronAPI?.showNotification?.(notification)
      
      // Web 浏览器通知（需用户授权）
      if (!window.electronAPI && 'Notification' in window && Notification.permission === 'granted') {
        new Notification(notification.title, { body: notification.body })
      }
    }
  }, [lastMsg])

  return useRealtimeStore((s) => s.notifications)
}
```

- [ ] **Step 6: 编写 useWebSocket.test.tsx**

Create: `frontend/tests/hooks/useWebSocket.test.tsx`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useWebSocket } from '@/hooks/useWebSocket'
import { wsClient, WSMessage } from '@/api/websocket'

vi.mock('@/utils/token', () => ({
  tokenStorage: {
    getAccessToken: () => 'mock-token',
  },
}))

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.spyOn(wsClient, 'getStatus').mockReturnValue('connected')
    vi.spyOn(wsClient, 'connect').mockResolvedValue(undefined)
  })

  it('channel 为 null 时不订阅', () => {
    const { result } = renderHook(() => useWebSocket(null))
    expect(result.current).toBeNull()
  })

  it('订阅后收到消息应更新 state', () => {
    let capturedHandler: ((msg: WSMessage) => void) | null = null
    vi.spyOn(wsClient, 'subscribe').mockImplementation((channel, handler) => {
      capturedHandler = handler
      return () => {}
    })
    
    const { result } = renderHook(() => useWebSocket('task:123'))
    
    expect(result.current).toBeNull()
    
    act(() => {
      capturedHandler?.({ type: 'progress', channel: 'task:123', data: { progress: 0.5 } })
    })
    
    expect(result.current).toEqual({
      type: 'progress',
      channel: 'task:123',
      data: { progress: 0.5 },
    })
  })

  it('unmount 应取消订阅', () => {
    const unsubscribe = vi.fn()
    vi.spyOn(wsClient, 'subscribe').mockReturnValue(unsubscribe)
    
    const { unmount } = renderHook(() => useWebSocket('task:456'))
    
    unmount()
    
    expect(unsubscribe).toHaveBeenCalled()
  })

  it('channel 变化应重新订阅', () => {
    const subscribe = vi.spyOn(wsClient, 'subscribe').mockReturnValue(() => {})
    
    const { rerender } = renderHook(({ channel }) => useWebSocket(channel), {
      initialProps: { channel: 'task:1' },
    })
    
    rerender({ channel: 'task:2' })
    
    expect(subscribe).toHaveBeenCalledWith('task:1', expect.any(Function))
    expect(subscribe).toHaveBeenCalledWith('task:2', expect.any(Function))
  })
})
```

- [ ] **Step 7: 编写 useTaskProgress.test.tsx**

Create: `frontend/tests/hooks/useTaskProgress.test.tsx`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useTaskProgress } from '@/hooks/useTaskProgress'
import { useRealtimeStore, TaskProgress } from '@/stores/realtimeStore'

// Mock useWebSocket
let mockLastMessage: any = null
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockLastMessage,
}))

describe('useTaskProgress', () => {
  beforeEach(() => {
    mockLastMessage = null
    useRealtimeStore.setState({ taskProgress: {} })
  })

  it('收到 progress 消息应更新 store', () => {
    const { rerender } = renderHook(() => useTaskProgress('task-1'))
    
    mockLastMessage = {
      type: 'progress',
      channel: 'task:task-1',
      data: {
        taskId: 'task-1',
        status: 'running',
        progress: 0.6,
        stage: 'generating',
      } as TaskProgress,
    }
    
    rerender()
    
    expect(useRealtimeStore.getState().taskProgress['task-1']).toEqual({
      taskId: 'task-1',
      status: 'running',
      progress: 0.6,
      stage: 'generating',
    })
  })

  it('taskId 为 null 应返回 undefined', () => {
    const { result } = renderHook(() => useTaskProgress(null))
    expect(result.current).toBeUndefined()
  })

  it('应返回 store 中的进度', () => {
    useRealtimeStore.setState({
      taskProgress: {
        'task-2': {
          taskId: 'task-2',
          status: 'running',
          progress: 0.3,
          stage: 'init',
        },
      },
    })
    
    const { result } = renderHook(() => useTaskProgress('task-2'))
    
    expect(result.current).toEqual({
      taskId: 'task-2',
      status: 'running',
      progress: 0.3,
      stage: 'init',
    })
  })
})
```

- [ ] **Step 8: 编写 useWorkflowStream.test.tsx**

Create: `frontend/tests/hooks/useWorkflowStream.test.tsx`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useWorkflowStream } from '@/hooks/useWorkflowStream'

let mockLastMessage: any = null
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockLastMessage,
}))

describe('useWorkflowStream', () => {
  beforeEach(() => {
    mockLastMessage = null
  })

  it('node_start 应将节点标记为 running', () => {
    const { rerender, result } = renderHook(() => useWorkflowStream('exec-1'))
    
    mockLastMessage = { type: 'node_start', node_id: 'node_1' }
    rerender()
    
    expect(result.current.nodes['node_1'].status).toBe('running')
    expect(result.current.status).toBe('running')
  })

  it('node_complete 应将节点标记为 completed', () => {
    const { rerender, result } = renderHook(() => useWorkflowStream('exec-2'))
    
    mockLastMessage = { type: 'node_start', node_id: 'node_1' }
    rerender()
    mockLastMessage = { type: 'node_complete', node_id: 'node_1', result: 'ok', duration_ms: 1000 }
    rerender()
    
    expect(result.current.nodes['node_1'].status).toBe('completed')
    expect(result.current.nodes['node_1'].durationMs).toBe(1000)
  })

  it('execution_complete 应更新整体状态', () => {
    const { rerender, result } = renderHook(() => useWorkflowStream('exec-3'))
    
    mockLastMessage = { type: 'execution_complete', status: 'success', total_duration_ms: 5000 }
    rerender()
    
    expect(result.current.status).toBe('success')
    expect(result.current.totalDurationMs).toBe(5000)
  })
})
```

- [ ] **Step 9: 编写 useNotifications.test.tsx**

Create: `frontend/tests/hooks/useNotifications.test.tsx`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useNotifications } from '@/hooks/useNotifications'
import { useRealtimeStore, NotificationItem } from '@/stores/realtimeStore'

let mockLastMessage: any = null
vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: () => mockLastMessage,
}))
vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: any) => selector({ user: { id: 'user-1' } }),
}))

describe('useNotifications', () => {
  beforeEach(() => {
    mockLastMessage = null
    useRealtimeStore.setState({ notifications: [] })
  })

  it('收到 notification 消息应追加到 store', () => {
    const { rerender } = renderHook(() => useNotifications())
    
    const notification: NotificationItem = {
      id: 'n-1',
      type: 'task_completed',
      title: '任务完成',
      body: '视频导出成功',
      createdAt: Date.now(),
      read: false,
    }
    
    mockLastMessage = { type: 'notification', data: notification }
    rerender()
    
    expect(useRealtimeStore.getState().notifications).toHaveLength(1)
    expect(useRealtimeStore.getState().notifications[0]).toEqual(notification)
  })

  it('非 notification 消息不应追加', () => {
    const { rerender } = renderHook(() => useNotifications())
    
    mockLastMessage = { type: 'progress', data: {} }
    rerender()
    
    expect(useRealtimeStore.getState().notifications).toHaveLength(0)
  })

  it('应返回 store 中的通知列表', () => {
    const notification: NotificationItem = {
      id: 'n-2',
      type: 'credit_low',
      title: '额度不足',
      body: '额度已用 80%',
      createdAt: Date.now(),
      read: false,
    }
    useRealtimeStore.setState({ notifications: [notification] })
    
    const { result } = renderHook(() => useNotifications())
    
    expect(result.current).toHaveLength(1)
    expect(result.current[0].id).toBe('n-2')
  })
})
```

- [ ] **Step 10: 运行所有 hooks 测试**

```powershell
cd c:\漫剧软件项目\frontend
npx vitest run tests/hooks/
```

Expected: 13 tests passed (4 + 3 + 3 + 3)

- [ ] **Step 11: Commit**

```bash
git add frontend/src/hooks/ frontend/tests/hooks/
git commit -m "feat(frontend): add 5 realtime hooks (useWebSocket/useSSE/useTaskProgress/useWorkflowStream/useNotifications)"
```

---

## Task 8: 前端首次启动向导 + 法律协议

**Files:**
- Create: `frontend/src/legal/terms.md`
- Create: `frontend/src/legal/privacy.md`
- Create: `frontend/src/pages/FirstLaunchPage.tsx`
- Modify: `frontend/src/routes/index.tsx`
- Modify: `frontend/src/App.tsx`（添加首启检测逻辑）
- Test: `frontend/tests/pages/FirstLaunchPage.test.tsx`

- [ ] **Step 1: 安装 react-markdown**

```powershell
cd c:\漫剧软件项目\frontend
npm install react-markdown remark-gfm
```

- [ ] **Step 2: 创建 terms.md**

Create: `frontend/src/legal/terms.md`

```markdown
# ComicStudio AI 用户协议

**最后更新：2026 年 7 月 19 日**

## 1. 服务说明

ComicStudio AI（以下简称"本服务"）是由 ComicStudio 提供的 AI 漫剧生成平台，包括但不限于图像生成、视频合成、文字转语音、工作流编排等功能。

## 2. 用户账号

- 用户需注册账号方可使用本服务
- 用户应提供真实、准确的注册信息
- 用户对其账号下的所有活动负责
- 禁止转让、出借账号

## 3. 订阅与付费

- 本服务提供 Free 和 Pro 两种订阅级别
- Free 用户享有有限的免费试用额度
- Pro 用户享有全部 AI 功能（包括本地推理、混合模式）
- 订阅费用一经支付不予退款（详见退款政策）

## 4. 退款政策

积分、会员等属于网络虚拟产品，一经购买无法退款。请用户在购买前充分了解产品功能。

## 5. 用户内容

- 用户上传的内容应拥有合法权利
- 用户生成的 AI 内容归用户所有
- 用户授权本服务处理内容以提供 AI 生成功能

## 6. 禁止行为

- 不得生成违法、色情、暴力、侵权内容
- 不得滥用 API、进行恶意攻击
- 不得反向工程、爬取数据

## 7. 服务变更与终止

- 本服务保留变更、暂停、终止服务的权利
- 用户违反协议时本服务可限制或终止账号

## 8. 免责声明

- AI 生成内容可能存在错误，用户应自行判断
- 本服务不对数据丢失负责，建议用户定期备份

## 9. 联系方式

如有疑问，请联系：support@comicstudio.ai
```

- [ ] **Step 3: 创建 privacy.md**

Create: `frontend/src/legal/privacy.md`

```markdown
# ComicStudio AI 隐私政策

**最后更新：2026 年 7 月 19 日**

## 1. 收集的信息

- **账号信息**：邮箱、用户名、加密的密码
- **使用数据**：生成历史、偏好设置、订阅状态
- **设备信息**：GPU 型号、RAM、平台（仅 Desktop 端，用于运行时检测）
- **遥测数据**：匿名使用统计（可关闭）

## 2. 信息使用

- 提供和改进 AI 生成功能
- 处理订阅和计费
- 提供客户支持
- 改进产品体验

## 3. 信息存储

- 云端数据存储在加密数据库中
- Desktop 端本地数据存储在用户指定目录
- 用户可随时导出或删除自己的数据

## 4. 信息共享

- 不会向第三方出售用户数据
- 仅在法律要求时披露必要信息
- AI 生成请求可能发送至第三方 AI 提供商（不含个人身份信息）

## 5. 数据安全

- 使用 HTTPS 加密传输
- 密码使用 bcrypt 加密存储
- 定期进行安全审计

## 6. 用户权利

- 访问、更正、删除个人数据
- 关闭遥测数据收集
- 注销账号

## 7. Cookie

- 本服务使用 localStorage 存储认证 token 和用户偏好
- 不使用第三方广告 Cookie

## 8. 儿童隐私

- 本服务不面向 13 岁以下儿童
- 如发现儿童信息将主动删除

## 9. 政策变更

- 隐私政策更新时将通知用户
- 重大变更需用户重新同意

## 10. 联系方式

隐私问题请联系：privacy@comicstudio.ai
```

- [ ] **Step 4: 创建 FirstLaunchPage.tsx**

Create: `frontend/src/pages/FirstLaunchPage.tsx`

```tsx
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Steps, Button, Card, Checkbox, Radio, Input, message, Spin } from 'antd'
import { Cloud, HardDrive, Shuffle, Crown, CheckCircle } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { isElectron, RuntimeInfo } from '@/utils/runtime'
import { apiClient } from '@/api/client'
import { useAuthStore } from '@/stores/authStore'
import termsMd from '@/legal/terms.md'
import privacyMd from '@/legal/privacy.md'

const { TextArea } = Input

type Provider = 'cloud' | 'local' | 'hybrid'

export default function FirstLaunchPage() {
  const navigate = useNavigate()
  const user = useAuthStore((s) => s.user)
  const [current, setCurrent] = useState(0)
  const [agreedTerms, setAgreedTerms] = useState(false)
  const [agreedPrivacy, setAgreedPrivacy] = useState(false)
  const [runtimeInfo, setRuntimeInfo] = useState<RuntimeInfo | null>(null)
  const [detecting, setDetecting] = useState(false)
  const [detectError, setDetectError] = useState<string | null>(null)
  const [provider, setProvider] = useState<Provider>('cloud')
  const [dataDir, setDataDir] = useState('')
  const [telemetry, setTelemetry] = useState(true)
  const [autoUpdate, setAutoUpdate] = useState(true)
  const [cloudSync, setCloudSync] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  // Step 2 自动检测（仅 Desktop）
  useEffect(() => {
    if (current === 1 && isElectron) {
      setDetecting(true)
      window.electronAPI?.getRuntimeInfo?.()
        .then((info) => {
          setRuntimeInfo(info)
          setDetecting(false)
          // 根据 GPU 推荐默认 provider
          if (info.hasGpu && info.vramMB >= 8192) {
            setProvider('hybrid')
          }
        })
        .catch(() => {
          setDetectError('检测失败，将使用远程 API')
          setDetecting(false)
        })
    }
  }, [current])

  const isPro = user?.subscription_tier === 'pro'

  const canNext = () => {
    switch (current) {
      case 0:
        return agreedTerms && agreedPrivacy
      case 1:
        return true // 检测失败也允许下一步
      case 2:
        return true
      case 3:
        return true
      default:
        return false
    }
  }

  const handleNext = () => {
    if (current < 3) {
      setCurrent(current + 1)
    } else {
      handleComplete()
    }
  }

  const handlePrev = () => {
    if (current > 0) setCurrent(current - 1)
  }

  const handleComplete = async () => {
    setSubmitting(true)
    try {
      // 1. 保存偏好到后端
      await apiClient.put('/api/v1/users/me/preferences', {
        preferred_provider: provider,
        telemetry_enabled: telemetry,
        cloud_sync_enabled: cloudSync,
      })

      // 2. Desktop: 保存本地设置 + 标记首启完成
      if (isElectron) {
        await window.electronAPI!.saveSettings?.({ dataDir, telemetry, autoUpdate })
        await window.electronAPI!.completeFirstLaunch?.()
      }

      // 3. 标记首启完成
      await apiClient.put('/api/v1/users/me/first-launch', { completed: true })

      message.success('设置完成！')
      navigate('/dashboard')
    } catch (err) {
      message.error('保存失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  const steps = [
    {
      title: '欢迎与法律',
      content: (
        <div>
          <h2 style={{ fontSize: 22, fontWeight: 700, marginBottom: 8 }}>
            欢迎使用 ComicStudio AI
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 24 }}>
            一站式 AI 漫剧生成平台 · 让创作更简单
          </p>
          <Card title="用户协议" style={{ marginBottom: 16, maxHeight: 200, overflow: 'auto' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{termsMd}</ReactMarkdown>
          </Card>
          <Card title="隐私政策" style={{ marginBottom: 16, maxHeight: 200, overflow: 'auto' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{privacyMd}</ReactMarkdown>
          </Card>
          <Checkbox checked={agreedTerms} onChange={(e) => setAgreedTerms(e.target.checked)}>
            我已阅读并同意《用户协议》
          </Checkbox>
          <br />
          <Checkbox checked={agreedPrivacy} onChange={(e) => setAgreedPrivacy(e.target.checked)}>
            我已阅读并同意《隐私政策》
          </Checkbox>
        </div>
      ),
    },
    {
      title: '运行时检测',
      content: isElectron ? (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>系统检测</h2>
          {detecting ? (
            <div style={{ textAlign: 'center', padding: 32 }}>
              <Spin size="large" />
              <p style={{ marginTop: 16, color: 'var(--text-secondary)' }}>正在检测本地 AI 运行时...</p>
            </div>
          ) : (
            <Card>
              {runtimeInfo ? (
                <div>
                  <p><strong>GPU:</strong> {runtimeInfo.gpuName || '未检测到'}</p>
                  <p><strong>VRAM:</strong> {runtimeInfo.vramMB} MB</p>
                  <p><strong>RAM:</strong> {runtimeInfo.ramMB} MB</p>
                  <p><strong>平台:</strong> {runtimeInfo.platform}</p>
                  <p><strong>推荐:</strong> {runtimeInfo.recommendedProvider}</p>
                </div>
              ) : (
                <p style={{ color: 'var(--accent-amber)' }}>{detectError}</p>
              )}
            </Card>
          )}
          <Button onClick={() => location.reload()} style={{ marginTop: 16 }}>重新检测</Button>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <p style={{ color: 'var(--text-secondary)' }}>Web 端跳过运行时检测</p>
        </div>
      ),
    },
    {
      title: 'AI Provider',
      content: (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 8 }}>选择 AI 方案</h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: 20 }}>
            选择适合你的 AI 推理方案，可随时在设置中更改
          </p>
          
          <Card
            style={{
              marginBottom: 12,
              border: provider === 'cloud' ? '2px solid var(--accent-emerald)' : '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span><Cloud size={20} style={{ marginRight: 8 }} />云 API</span>
              {provider === 'cloud' && <span style={{ color: 'var(--accent-emerald)', fontSize: 12 }}>推荐</span>}
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ✓ 高质量 SDXL/Qwen 模型 · 3-5s/图 · 无需本地 GPU<br />
              💳 需 Pro 订阅（¥39/月起）或使用免费试用额度
            </p>
            <Button type="primary" size="small" onClick={() => setProvider('cloud')}>
              选择
            </Button>
          </Card>

          <Card
            style={{
              marginBottom: 12,
              opacity: isPro ? 1 : 0.5,
              border: provider === 'local' ? '2px solid var(--brand-primary)' : '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span><HardDrive size={20} style={{ marginRight: 8 }} />本地推理</span>
              <Crown size={14} style={{ color: 'var(--accent-violet)' }} />
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ✓ 离线可用 · 零 API 成本<br />
              ⚠ 需要 8GB+ VRAM · GPU ~8s/图<br />
              {isPro ? '💳 Pro 福利' : '🔒 Free 用户不可用'}
            </p>
            {isPro ? (
              <Button size="small" onClick={() => setProvider('local')}>选择</Button>
            ) : (
              <Button size="small" onClick={() => navigate('/billing')}>升级 Pro 解锁</Button>
            )}
          </Card>

          <Card
            style={{
              marginBottom: 12,
              opacity: isPro ? 1 : 0.5,
              border: provider === 'hybrid' ? '2px solid var(--brand-primary)' : '1px solid var(--border-default)',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
              <span><Shuffle size={20} style={{ marginRight: 8 }} />混合模式</span>
              <Crown size={14} style={{ color: 'var(--accent-violet)' }} />
            </div>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              ✓ 优先本地推理 · 自动 fallback 云端<br />
              ✓ 最佳性价比 · 智能调度<br />
              {isPro ? '💳 Pro 专属' : '🔒 Free 用户不可用'}
            </p>
            {isPro && (
              <Button size="small" onClick={() => setProvider('hybrid')}>选择</Button>
            )}
          </Card>
        </div>
      ),
    },
    {
      title: '数据与隐私',
      content: (
        <div>
          <h2 style={{ fontSize: 18, fontWeight: 600, marginBottom: 16 }}>数据与隐私设置</h2>
          
          {isElectron && (
            <Card title="数据存储位置" style={{ marginBottom: 16 }}>
              <Radio.Group
                value={dataDir ? 'custom' : 'default'}
                onChange={(e) => {
                  if (e.target.value === 'custom') {
                    window.electronAPI?.chooseDirectory?.().then((dir) => {
                      if (dir) setDataDir(dir)
                    })
                  } else {
                    setDataDir('')
                  }
                }}
              >
                <Radio value="default">默认（~/Documents/ComicStudio）</Radio>
                <Radio value="custom">自定义 {dataDir && `(${dataDir})`}</Radio>
              </Radio.Group>
            </Card>
          )}

          <Card title="遥测数据" style={{ marginBottom: 16 }}>
            <Checkbox checked={telemetry} onChange={(e) => setTelemetry(e.target.checked)}>
              发送匿名使用统计（帮助我们改进）
            </Checkbox>
          </Card>

          {isElectron && (
            <Card title="自动更新" style={{ marginBottom: 16 }}>
              <Checkbox checked={autoUpdate} onChange={(e) => setAutoUpdate(e.target.checked)}>
                自动检查更新
              </Checkbox>
            </Card>
          )}

          <Card title="云端同步" style={{ marginBottom: 16 }}>
            <Checkbox
              checked={cloudSync}
              onChange={(e) => setCloudSync(e.target.checked)}
              disabled={!isPro}
            >
              启用项目云端同步 {isPro ? '' : '（Pro 功能）'}
            </Checkbox>
          </Card>
        </div>
      ),
    },
  ]

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '32px 48px' }}>
      <Steps current={current} items={steps.map((s) => ({ title: s.title }))} style={{ marginBottom: 32 }} />
      
      <div style={{ minHeight: 300 }}>
        {steps[current].content}
      </div>

      <div style={{ marginTop: 24, paddingTop: 16, borderTop: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between' }}>
        <Button onClick={handlePrev} disabled={current === 0}>← 上一步</Button>
        <Button
          type="primary"
          onClick={handleNext}
          disabled={!canNext()}
          loading={submitting}
        >
          {current === 3 ? '完成 →' : '下一步 →'}
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: 修改 routes/index.tsx 添加 /first-launch 路由**

Modify: `frontend/src/routes/index.tsx`

```typescript
import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { Spin } from 'antd'
import ProtectedRoute from '@/components/common/ProtectedRoute'
import MainLayout from '@/components/layout/MainLayout'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const RegisterPage = lazy(() => import('@/pages/RegisterPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const ProjectListPage = lazy(() => import('@/pages/ProjectListPage'))
const ProjectEditorPage = lazy(() => import('@/pages/ProjectEditorPage'))
const FirstLaunchPage = lazy(() => import('@/pages/FirstLaunchPage'))

const Loading = () => (
  <div className="flex items-center justify-center h-screen">
    <Spin size="large" />
  </div>
)

export default function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/first-launch" element={<FirstLaunchPage />} />

        <Route
          element={
            <ProtectedRoute>
              <MainLayout />
            </ProtectedRoute>
          }
        >
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/projects" element={<ProjectListPage />} />
          <Route path="/projects/:projectId" element={<ProjectEditorPage />} />
        </Route>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Suspense>
  )
}
```

- [ ] **Step 6: 编写 FirstLaunchPage.test.tsx**

Create: `frontend/tests/pages/FirstLaunchPage.test.tsx`

```typescript
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import FirstLaunchPage from '@/pages/FirstLaunchPage'

vi.mock('@/api/client', () => ({
  apiClient: { put: vi.fn().mockResolvedValue({}) },
}))

vi.mock('@/stores/authStore', () => ({
  useAuthStore: (selector: any) => selector({ user: { id: 'u1', subscription_tier: 'free' } }),
}))

vi.mock('@/utils/runtime', () => ({
  isElectron: false,
}))

function renderPage() {
  return render(
    <MemoryRouter>
      <FirstLaunchPage />
    </MemoryRouter>
  )
}

describe('FirstLaunchPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('Step 1 未勾选协议时下一步应禁用', () => {
    renderPage()
    const nextBtn = screen.getByText('下一步 →')
    expect(nextBtn).toBeDisabled()
  })

  it('Step 1 勾选协议后可进入下一步', () => {
    renderPage()
    
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0]) // 同意用户协议
    fireEvent.click(checkboxes[1]) // 同意隐私政策
    
    const nextBtn = screen.getByText('下一步 →')
    expect(nextBtn).not.toBeDisabled()
    
    fireEvent.click(nextBtn)
    
    // Step 2 Web 端跳过，应显示 Step 2 内容
    expect(screen.getByText('Web 端跳过运行时检测')).toBeInTheDocument()
  })

  it('Step 3 Free 用户本地推理应置灰', async () => {
    renderPage()
    
    // 快速跳到 Step 3
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])
    fireEvent.click(screen.getByText('下一步 →'))
    fireEvent.click(screen.getByText('下一步 →'))
    
    await waitFor(() => {
      expect(screen.getByText('升级 Pro 解锁')).toBeInTheDocument()
    })
  })

  it('Step 3 Pro 用户应看到三个可选项', async () => {
    vi.mocked(await import('@/stores/authStore')).useAuthStore = (selector: any) =>
      selector({ user: { id: 'u1', subscription_tier: 'pro' } })
    
    renderPage()
    
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])
    fireEvent.click(screen.getByText('下一步 →'))
    fireEvent.click(screen.getByText('下一步 →'))
    
    await waitFor(() => {
      const selectButtons = screen.getAllByText('选择')
      expect(selectButtons.length).toBeGreaterThanOrEqual(3)
    })
  })

  it('Web 端 Step 2 应自动跳过', async () => {
    renderPage()
    
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])
    fireEvent.click(screen.getByText('下一步 →'))
    
    expect(screen.getByText('Web 端跳过运行时检测')).toBeInTheDocument()
  })

  it('完成应调用 API', async () => {
    const { apiClient } = await import('@/api/client')
    renderPage()
    
    // 快速走到最后一步
    const checkboxes = screen.getAllByRole('checkbox')
    fireEvent.click(checkboxes[0])
    fireEvent.click(checkboxes[1])
    fireEvent.click(screen.getByText('下一步 →'))
    fireEvent.click(screen.getByText('下一步 →'))
    fireEvent.click(screen.getByText('下一步 →'))
    
    const completeBtn = screen.getByText('完成 →')
    fireEvent.click(completeBtn)
    
    await waitFor(() => {
      expect(apiClient.put).toHaveBeenCalledWith('/api/v1/users/me/preferences', expect.any(Object))
      expect(apiClient.put).toHaveBeenCalledWith('/api/v1/users/me/first-launch', { completed: true })
    })
  })
})
```

- [ ] **Step 7: 运行测试**

```powershell
cd c:\漫剧软件项目\frontend
npx vitest run tests/pages/FirstLaunchPage.test.tsx
```

Expected: 6 tests passed

- [ ] **Step 8: Commit**

```bash
git add frontend/src/legal/ frontend/src/pages/FirstLaunchPage.tsx frontend/src/routes/index.tsx frontend/tests/pages/FirstLaunchPage.test.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(frontend): add FirstLaunchPage with 4-step wizard and legal docs"
```

---

## Task 9: Desktop 端修复（删除旧 renderer + 重写 first-launch + 扩展 preload）

**Files:**
- Delete: `desktop/src/renderer/`（整个目录）
- Modify: `desktop/src/main/first-launch.ts`
- Modify: `desktop/src/preload/api.ts`

- [ ] **Step 1: 删除错误的 desktop/src/renderer/ 目录**

```powershell
cd c:\漫剧软件项目
Remove-Item -Recurse -Force desktop\src\renderer
```

- [ ] **Step 2: 读取现有 first-launch.ts**

Read: `desktop/src/main/first-launch.ts`

- [ ] **Step 3: 重写 first-launch.ts 使用 hash 路由**

Modify: `desktop/src/main/first-launch.ts`

```typescript
import { BrowserWindow, ipcMain, app } from 'electron'
import Store from 'electron-store'
import { DEV_SERVER_URL, PROD_RENDERER_ENTRY } from './constants'
import { createMainWindow, getMainWindow } from './window'

const store = new Store<{ firstLaunchCompleted: boolean }>({
  defaults: { firstLaunchCompleted: false },
})

/**
 * 检查是否需要首启动向导
 */
export function shouldShowFirstLaunch(): boolean {
  return !store.get('firstLaunchCompleted')
}

/**
 * 加载首启动向导页面（通过 hash 路由复用主 renderer）
 */
export function loadFirstLaunch(mainWindow: BrowserWindow): void {
  const isDev = !app.isPackaged
  if (isDev) {
    mainWindow.loadURL(`${DEV_SERVER_URL}#/first-launch`)
  } else {
    mainWindow.loadFile(PROD_RENDERER_ENTRY, { hash: '/first-launch' })
  }
}

/**
 * 注册首启动相关的 IPC handlers
 */
export function registerFirstLaunchHandlers(): void {
  ipcMain.handle('first-launch:complete', async () => {
    store.set('firstLaunchCompleted', true)
    
    // 加载主页
    const mainWindow = getMainWindow()
    if (mainWindow) {
      const isDev = !app.isPackaged
      if (isDev) {
        mainWindow.loadURL(DEV_SERVER_URL)
      } else {
        mainWindow.loadFile(PROD_RENDERER_ENTRY)
      }
    }
    return true
  })
}
```

- [ ] **Step 4: 修改 desktop/src/main/index.ts 集成首启动检测**

Read: `desktop/src/main/index.ts`

Modify: 在 `createMainWindow()` 后添加首启动检测：

```typescript
import { shouldShowFirstLaunch, loadFirstLaunch, registerFirstLaunchHandlers } from './first-launch'

// 在 app.whenReady() 的回调中：
app.whenReady().then(() => {
  registerFirstLaunchHandlers()
  const mainWindow = createMainWindow()
  
  if (shouldShowFirstLaunch()) {
    loadFirstLaunch(mainWindow)
  }
  // 否则 createMainWindow 内部已加载默认页面
})
```

- [ ] **Step 5: 读取并扩展 preload/api.ts**

Read: `desktop/src/preload/api.ts`

Modify: `desktop/src/preload/api.ts` 添加 7 个新 API：

```typescript
import { contextBridge, ipcRenderer, dialog, BrowserWindow } from 'electron'
import Store from 'electron-store'
import path from 'path'
import { getBackendPort } from '../main/backend-process'

const store = new Store<{
  dataDir?: string
  telemetry?: boolean
  autoUpdate?: boolean
}>({ defaults: { telemetry: true, autoUpdate: true } })

const api = {
  // === 现有 API（保留） ===
  // ... 保留所有现有 API ...

  // === 新增：前端集成 API ===
  
  /** 获取后端 URL */
  getBackendUrl: (): string => {
    const port = getBackendPort()
    return `http://127.0.0.1:${port}`
  },

  /** 获取运行时信息（调用后端 /api/v1/models/runtime） */
  getRuntimeInfo: async () => {
    const port = getBackendPort()
    const resp = await fetch(`http://127.0.0.1:${port}/api/v1/models/runtime`)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    return await resp.json()
  },

  /** 选择目录 */
  chooseDirectory: async (): Promise<string | null> => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
    })
    return result.canceled ? null : result.filePaths[0]
  },

  /** 保存设置 */
  saveSettings: async (settings: { dataDir?: string; telemetry?: boolean; autoUpdate?: boolean }) => {
    if (settings.dataDir !== undefined) store.set('dataDir', settings.dataDir)
    if (settings.telemetry !== undefined) store.set('telemetry', settings.telemetry)
    if (settings.autoUpdate !== undefined) store.set('autoUpdate', settings.autoUpdate)
  },

  /** 标记首启动完成 */
  completeFirstLaunch: async (): Promise<void> => {
    await ipcRenderer.invoke('first-launch:complete')
  },

  /** 下载模型 */
  downloadModel: async (name: string): Promise<void> => {
    await ipcRenderer.invoke('model:download', name)
  },

  /** 监听后端 URL 变化 */
  onBackendUrlChange: (cb: (url: string) => void) => {
    const handler = (_: unknown, url: string) => cb(url)
    ipcRenderer.on('backend:url-changed', handler)
    return () => ipcRenderer.removeListener('backend:url-changed', handler)
  },

  /** 显示系统通知 */
  showNotification: (notification: { title: string; body: string }) => {
    new BrowserWindow({ show: false }).webContents.send('show-notification', notification)
    // 或使用 Notification API
  },
}

contextBridge.exposeInMainWorld('electronAPI', api)
```

- [ ] **Step 6: 验证 desktop 构建**

```powershell
cd c:\漫剧软件项目\desktop
npm run build
```

Expected: 构建成功，无 TypeScript 错误

- [ ] **Step 7: Commit**

```bash
git add desktop/src/main/first-launch.ts desktop/src/main/index.ts desktop/src/preload/api.ts
git rm -r desktop/src/renderer/
git commit -m "fix(desktop): remove erroneous renderer dir, rewrite first-launch with hash routing, extend preload bridge"
```

---

## Task 10: 前端 UI 组件（NotificationBell + RealtimeStatus + TaskProgressList + ChatPanel）

**Files:**
- Create: `frontend/src/components/common/NotificationBell.tsx`
- Create: `frontend/src/components/common/RealtimeStatus.tsx`
- Create: `frontend/src/components/dashboard/TaskProgressList.tsx`
- Create: `frontend/src/components/project/ChatPanel.tsx`

- [ ] **Step 1: 创建 NotificationBell.tsx**

Create: `frontend/src/components/common/NotificationBell.tsx`

```tsx
import { useState } from 'react'
import { Badge, Dropdown, Button, List, Typography } from 'antd'
import { Bell } from 'lucide-react'
import { useNotifications } from '@/hooks/useNotifications'
import { useRealtimeStore } from '@/stores/realtimeStore'

const { Text } = Typography

export default function NotificationBell() {
  const notifications = useNotifications()
  const markAllRead = useRealtimeStore((s) => s.markAllRead)
  const unreadCount = notifications.filter((n) => !n.read).length

  const icon = (
    <Badge count={unreadCount} size="small" offset={[-2, 2]}>
      <Bell size={18} />
    </Badge>
  )

  const dropdownContent = (
    <div style={{ width: 320, background: 'var(--bg-elevated)', borderRadius: 8, boxShadow: 'var(--shadow-lg)' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-default)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Text strong>通知 ({unreadCount} 未读)</Text>
        <Button type="link" size="small" onClick={markAllRead}>全部已读</Button>
      </div>
      <List
        size="small"
        dataSource={notifications.slice(-10).reverse()}
        renderItem={(n) => (
          <List.Item style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-subtle)', background: n.read ? 'transparent' : 'rgba(59, 130, 246, 0.06)' }}>
            <List.Item.Meta
              title={<Text strong style={{ fontSize: 13 }}>{n.title}</Text>}
              description={<Text type="secondary" style={{ fontSize: 12 }}>{n.body}</Text>}
            />
          </List.Item>
        )}
        locale={{ emptyText: '暂无通知' }}
      />
    </div>
  )

  return <Dropdown overlay={dropdownContent} trigger={['click']} placement="bottomRight">{icon}</Dropdown>
}
```

- [ ] **Step 2: 创建 RealtimeStatus.tsx**

Create: `frontend/src/components/common/RealtimeStatus.tsx`

```tsx
import { Tooltip } from 'antd'
import { useRealtimeStore } from '@/stores/realtimeStore'
import { wsClient } from '@/api/websocket'

const STATUS_CONFIG = {
  connected: { color: 'var(--accent-emerald)', label: '已连接' },
  connecting: { color: 'var(--accent-amber)', label: '连接中...' },
  reconnecting: { color: 'var(--accent-amber)', label: '重连中...' },
  closed: { color: 'var(--accent-rose)', label: '连接断开' },
  idle: { color: 'var(--text-tertiary)', label: '未连接' },
}

export default function RealtimeStatus() {
  const wsStatus = useRealtimeStore((s) => s.wsStatus)
  const config = STATUS_CONFIG[wsStatus]

  return (
    <Tooltip title={`${config.label}${wsStatus === 'closed' ? '（点击重试）' : ''}`}>
      <div
        style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: config.color,
          cursor: wsStatus === 'closed' ? 'pointer' : 'default',
          animation: wsStatus === 'connecting' || wsStatus === 'reconnecting' ? 'pulse-dot 2s ease-in-out infinite' : 'none',
        }}
        onClick={() => {
          if (wsStatus === 'closed') {
            const token = localStorage.getItem('access_token')
            if (token) wsClient.connect(token)
          }
        }}
      />
    </Tooltip>
  )
}
```

- [ ] **Step 3: 创建 TaskProgressList.tsx**

Create: `frontend/src/components/dashboard/TaskProgressList.tsx`

```tsx
import { useEffect, useState } from 'react'
import { Card, Progress, Empty, Button } from 'antd'
import { Video, Image, FileText, Mic, CheckCircle } from 'lucide-react'
import { apiClient } from '@/api/client'
import { useTaskProgress } from '@/hooks/useTaskProgress'

interface Task {
  id: string
  type: 'video' | 'image' | 'tts' | 'export'
  title: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

const ICON_MAP = {
  video: Video,
  image: Image,
  tts: Mic,
  export: FileText,
}

function TaskItem({ task }: { task: Task }) {
  const progress = useTaskProgress(task.status === 'running' ? task.id : null)
  const Icon = ICON_MAP[task.type]

  if (task.status === 'completed') {
    return (
      <div style={{ marginBottom: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
          <span><Icon size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />{task.title}</span>
          <span style={{ color: 'var(--accent-emerald)' }}><CheckCircle size={14} /> 完成</span>
        </div>
      </div>
    )
  }

  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, marginBottom: 4 }}>
        <span><Icon size={14} style={{ marginRight: 6, verticalAlign: 'middle' }} />{task.title}</span>
        <span style={{ color: 'var(--brand-primary)' }}>{Math.round((progress?.progress ?? 0) * 100)}%</span>
      </div>
      <Progress
        percent={Math.round((progress?.progress ?? 0) * 100)}
        size="small"
        strokeColor={{ from: '#3B82F6', to: '#6366F1' }}
      />
      {progress?.eta && (
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
          预计 {progress.eta}s
        </div>
      )}
    </div>
  )
}

export default function TaskProgressList() {
  const [tasks, setTasks] = useState<Task[]>([])

  useEffect(() => {
    apiClient.get('/api/v1/tasks?status=running')
      .then((resp) => setTasks(resp.data?.items ?? []))
      .catch(() => setTasks([]))
  }, [])

  return (
    <Card title="后台任务" size="small">
      {tasks.length === 0 ? (
        <Empty description="暂无运行中任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      ) : (
        tasks.map((task) => <TaskItem key={task.id} task={task} />)
      )}
    </Card>
  )
}
```

- [ ] **Step 4: 创建 ChatPanel.tsx**

Create: `frontend/src/components/project/ChatPanel.tsx`

```tsx
import { useState } from 'react'
import { Input, Button, Typography } from 'antd'
import { Send, Square, Sparkles } from 'lucide-react'
import { useSSE } from '@/hooks/useSSE'

const { Text } = Typography
const { TextArea } = Input

interface Message {
  role: 'user' | 'assistant'
  content: string
}

export default function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const { data, done, error, start, abort } = useSSE('/api/v1/chat?stream=true')

  const handleSend = () => {
    if (!input.trim()) return
    const userMessage: Message = { role: 'user', content: input }
    setMessages((prev) => [...prev, userMessage, { role: 'assistant', content: '' }])
    start()
    setInput('')
  }

  // SSE 数据追加到最新 AI 消息
  useEffect(() => {
    if (data) {
      setMessages((prev) => {
        const last = prev[prev.length - 1]
        if (last?.role === 'assistant') {
          return [...prev.slice(0, -1), { ...last, content: last.content + data }]
        }
        return prev
      })
    }
  }, [data])

  const isStreaming = !done && (data !== '' || error === null)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--bg-surface)' }}>
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border-default)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <Sparkles size={16} style={{ color: 'var(--accent-cyan)' }} />
        <Text strong>AI 助手</Text>
      </div>

      <div style={{ flex: 1, padding: 16, overflowY: 'auto' }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              marginBottom: 12,
              padding: '10px 14px',
              borderRadius: 12,
              maxWidth: '85%',
              background: msg.role === 'user' ? 'var(--brand-primary)' : 'var(--bg-elevated)',
              color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
              alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
              marginLeft: msg.role === 'user' ? 'auto' : 0,
              border: msg.role === 'assistant' ? '1px solid var(--border-default)' : 'none',
            }}
          >
            {msg.content}
            {msg.role === 'assistant' && isStreaming && i === messages.length - 1 && (
              <span style={{ display: 'inline-block', width: 2, height: 14, background: 'var(--accent-cyan)', marginLeft: 2, animation: 'blink 1s infinite', verticalAlign: 'text-bottom' }} />
            )}
          </div>
        ))}
        {error && (
          <div style={{ color: 'var(--accent-rose)', fontSize: 12, marginTop: 8 }}>
            [错误: {error.message}]
          </div>
        )}
      </div>

      <div style={{ padding: 12, borderTop: '1px solid var(--border-default)' }}>
        <div style={{ display: 'flex', gap: 8, marginBottom: 8 }}>
          <TextArea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入消息，或描述你想要的内容..."
            autoSize={{ minRows: 1, maxRows: 4 }}
            disabled={isStreaming}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
          />
          {isStreaming ? (
            <Button danger onClick={abort} icon={<Square size={14} />}>停止</Button>
          ) : (
            <Button type="primary" onClick={handleSend} icon={<Send size={14} />} disabled={!input.trim()}>
              发送
            </Button>
          )}
        </div>
        {isStreaming && (
          <Text type="secondary" style={{ fontSize: 11 }}>
            📡 SSE 流式中 · {data.length} chars
          </Text>
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: 验证构建**

```powershell
cd c:\漫剧软件项目\frontend
npm run build
```

Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/common/NotificationBell.tsx frontend/src/components/common/RealtimeStatus.tsx frontend/src/components/dashboard/TaskProgressList.tsx frontend/src/components/project/ChatPanel.tsx
git commit -m "feat(frontend): add NotificationBell, RealtimeStatus, TaskProgressList, ChatPanel components"
```

---

## Task 11: 前端集成改造（ExecutionPanel + TopBar + DashboardPage + ProjectEditorPage）

**Files:**
- Modify: `frontend/src/components/workflow/ExecutionPanel.tsx`
- Modify: `frontend/src/components/layout/TopBar.tsx`
- Modify: `frontend/src/pages/DashboardPage.tsx`
- Modify: `frontend/src/pages/ProjectEditorPage.tsx`

- [ ] **Step 1: 读取并改造 ExecutionPanel.tsx**

Read: `frontend/src/components/workflow/ExecutionPanel.tsx`

Modify: `frontend/src/components/workflow/ExecutionPanel.tsx`

在原有同步执行逻辑基础上接入 `useWorkflowStream`：

```tsx
import { useState } from 'react'
import { Button, Progress, Tooltip, Card, Tag } from 'antd'
import { Play, Square, CheckCircle, Loader, Circle, XCircle } from 'lucide-react'
import { workflowEngineApi } from '@/api/workflows'
import { useWorkflowStream } from '@/hooks/useWorkflowStream'

export default function ExecutionPanel({ workflowId }: { workflowId: string }) {
  const [executionId, setExecutionId] = useState<string | null>(null)
  const stream = useWorkflowStream(executionId)

  const handleExecute = async () => {
    try {
      const resp = await workflowEngineApi.execute(workflowId)
      setExecutionId(resp.data.execution_id)
    } catch (err) {
      // 错误处理
    }
  }

  const handleCancel = () => {
    setExecutionId(null)
  }

  const isRunning = stream.status === 'running'

  return (
    <Card title="执行进度" size="small">
      <div style={{ marginBottom: 12, display: 'flex', gap: 8, alignItems: 'center' }}>
        {isRunning ? (
          <Button danger icon={<Square size={14} />} onClick={handleCancel}>取消</Button>
        ) : (
          <Button type="primary" icon={<Play size={14} />} onClick={handleExecute}>执行工作流</Button>
        )}
        {isRunning && (
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            进度: {stream.completed}/{stream.total} · {Math.round(stream.progress * 100)}%
          </span>
        )}
      </div>

      {isRunning && (
        <Progress
          percent={Math.round(stream.progress * 100)}
          strokeColor={{ from: '#3B82F6', to: '#6366F1' }}
          style={{ marginBottom: 16 }}
        />
      )}

      <div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 6, textTransform: 'uppercase' }}>节点详情</div>
        {Object.values(stream.nodes).map((node) => (
          <div
            key={node.nodeId}
            style={{
              padding: '8px 12px',
              marginBottom: 4,
              borderRadius: 4,
              background: 'var(--bg-surface)',
              border: `1px solid ${
                node.status === 'completed' ? 'var(--accent-emerald)' :
                node.status === 'running' ? 'var(--brand-primary)' :
                node.status === 'failed' ? 'var(--accent-rose)' : 'var(--border-default)'
              }`,
              display: 'flex',
              alignItems: 'center',
              gap: 8,
              fontSize: 13,
            }}
          >
            {node.status === 'completed' && <CheckCircle size={14} color="var(--accent-emerald)" />}
            {node.status === 'running' && <Loader size={14} color="var(--brand-primary)" className="animate-spin" />}
            {node.status === 'pending' && <Circle size={14} color="var(--text-tertiary)" />}
            {node.status === 'failed' && <XCircle size={14} color="var(--accent-rose)" />}
            <span>{node.nodeId}</span>
            {node.durationMs && (
              <span style={{ marginLeft: 'auto', color: 'var(--text-tertiary)', fontSize: 11 }}>
                {node.durationMs}ms
              </span>
            )}
            {node.error && (
              <Tooltip title={node.error}>
                <Tag color="error" style={{ marginLeft: 'auto' }}>失败</Tag>
              </Tooltip>
            )}
          </div>
        ))}
      </div>
    </Card>
  )
}
```

- [ ] **Step 2: 修改 TopBar.tsx 挂载新组件**

Read: `frontend/src/components/layout/TopBar.tsx`

Modify: 在 TopBar 右侧添加 `RealtimeStatus` + `NotificationBell` + `ThemeToggle`：

```tsx
import RealtimeStatus from '@/components/common/RealtimeStatus'
import NotificationBell from '@/components/common/NotificationBell'
import ThemeToggle from '@/components/common/ThemeToggle'

// 在 TopBar 组件的右侧区域添加：
<div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
  <RealtimeStatus />
  <NotificationBell />
  <ThemeToggle />
  {/* 现有的用户头像等 */}
</div>
```

- [ ] **Step 3: 修改 DashboardPage.tsx 挂载 TaskProgressList**

Read: `frontend/src/pages/DashboardPage.tsx`

Modify: 在 DashboardPage 的右侧栏添加：

```tsx
import TaskProgressList from '@/components/dashboard/TaskProgressList'

// 在布局的右侧区域添加：
<TaskProgressList />
```

- [ ] **Step 4: 修改 ProjectEditorPage.tsx 挂载 ChatPanel**

Read: `frontend/src/pages/ProjectEditorPage.tsx`

Modify: 在 ProjectEditorPage 的右侧栏添加：

```tsx
import ChatPanel from '@/components/project/ChatPanel'

// 在布局的右侧区域添加：
<div style={{ width: 380, borderLeft: '1px solid var(--border-default)' }}>
  <ChatPanel />
</div>
```

- [ ] **Step 5: 验证前端构建**

```powershell
cd c:\漫剧软件项目\frontend
npm run build
```

Expected: 构建成功

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/workflow/ExecutionPanel.tsx frontend/src/components/layout/TopBar.tsx frontend/src/pages/DashboardPage.tsx frontend/src/pages/ProjectEditorPage.tsx
git commit -m "feat(frontend): integrate realtime components into ExecutionPanel/TopBar/Dashboard/ProjectEditor"
```

---

## Task 12: 全量回归测试与验收

**Files:** 无新增，仅运行测试

- [ ] **Step 1: 后端全量测试**

```powershell
cd c:\漫剧软件项目\backend
$env:PYTHONPATH = "c:\漫剧软件项目\backend\.deps;c:\漫剧软件项目\backend"
py -3.14 -m pytest tests/ -v --tb=short
```

Expected: 511 passed (501 基线 + 10 新增后端测试: 7 用户偏好 + 3 工作流 WS)

- [ ] **Step 2: 前端全量测试**

```powershell
cd c:\漫剧软件项目\frontend
npx vitest run
```

Expected: 36 tests passed (3 runtime + 8 ws + 6 sse + 6 store + 4 useWebSocket + 3 useTaskProgress + 3 useWorkflowStream + 3 useNotifications + 6 FirstLaunchPage - 6 已包含在 useWebSocket 等中)

实际目标：~35 个前端测试全部通过

- [ ] **Step 3: 前端 TypeScript 类型检查**

```powershell
cd c:\漫剧软件项目\frontend
npx tsc --noEmit
```

Expected: 0 errors（或仅 Phase 1-6 预存的类型警告）

- [ ] **Step 4: 前端构建验证**

```powershell
cd c:\漫剧软件项目\frontend
npm run build
```

Expected: 构建成功，输出到 `dist/`

- [ ] **Step 5: Desktop 构建验证**

```powershell
cd c:\漫剧软件项目\desktop
npm run build
```

Expected: main/preload/renderer 三部分构建成功

- [ ] **Step 6: 验收检查清单**

对照 spec 第 16 节成功标准逐项验证：

- [ ] 536+ 测试通过（新增 35+，零回归）
- [ ] Web 端首次访问可完成 4 步向导（Step 2 自动跳过）
- [ ] Desktop 端首启检测 GPU 并展示推荐 provider
- [ ] WS 连接成功后 TopBar 显示绿点
- [ ] 后台任务进度实时推送到 Dashboard
- [ ] 工作流执行进度实时更新到 ExecutionPanel
- [ ] ChatPanel 支持 SSE 流式输出 + 中断
- [ ] NotificationBell 接收推送并显示未读数
- [ ] WS 断开自动重连 + 红点提示
- [ ] Web/Desktop 两端无崩溃、无控制台错误
- [ ] Free 用户在向导中看到本地推理置灰 + "升级 Pro"按钮
- [ ] Pro 用户在向导中可选三个 provider 方案
- [ ] 默认浅色主题，可切换暗色
- [ ] 视觉规范符合 spec Section 17（科技蓝主色、中文优先字体、性能优先动画）

- [ ] **Step 7: Final Commit**

```bash
git add -A
git commit -m "test: final regression - all 536+ tests passing, visual design verified"
```

---

## 总结

本实施计划共 **12 个 Task**，覆盖：

| Task | 内容 | 新增测试 |
|---|---|---|
| 1 | 后端 User 模型 + Schema + 迁移 | - |
| 2 | 后端用户偏好 + 首启动 API | 7 |
| 3 | 后端 WS publish 扩展 | 3 |
| 4 | 前端视觉设计 tokens + 主题切换 | - |
| 5 | 前端 Transport 层（runtime/ws/sse） | 17 |
| 6 | 前端 Realtime Store | 6 |
| 7 | 前端 Hooks 层（5 个 hooks） | 13 |
| 8 | 前端首次启动向导 + 法律协议 | 6 |
| 9 | Desktop 修复（删除旧 renderer + 重写 first-launch + 扩展 preload） | - |
| 10 | 前端 UI 组件（4 个） | - |
| 11 | 前端集成改造 | - |
| 12 | 全量回归测试 | - |

**测试目标**：501 → 536+（新增 52 个：10 后端 + 42 前端，零回归）

**关键交付**：
- WebSocket 实时推送（任务进度、工作流、通知）
- SSE 流式对话（支持中断）
- 4 步首启动向导（含商业策略）
- 视觉设计系统（科技蓝 + 浅色默认 + 中文优先 + 性能优先动画）
- Web/Desktop 双端共用