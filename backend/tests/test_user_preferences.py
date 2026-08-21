"""测试用户偏好 API

适配项目 conftest.py 的 db_session fixture 模式（in-memory SQLite + monkeypatch）。
通过 app.dependency_overrides 同时覆盖 get_current_user 与 get_db，
使 endpoint 与测试共享同一个 db_session，确保 current_user 与 db 附加到同一会话，
从而 db.refresh(current_user) 能正常工作。

注意：
- User 模型字段为 password_hash（非 hashed_password）
- app.core.security 函数为 hash_password（非 get_password_hash）
- asyncio_mode=auto，无需 @pytest.mark.asyncio
"""
import pytest_asyncio
from uuid import uuid4
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.deps import get_current_user, get_db
from app.core.security import hash_password
from app.models.user import User


@pytest_asyncio.fixture
async def auth_client(db_session):
    """创建测试用户并返回已认证客户端

    覆盖 get_current_user 返回真实 User（附加到 db_session），
    覆盖 get_db 返回 db_session，使 endpoint 的 db.commit/refresh 在同一会话生效。
    """
    user = User(
        username=f"prefuser_{uuid4().hex[:8]}",
        email=f"pref_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Test1234!"),
        first_launch_completed=False,
        preferred_provider="cloud",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    async def _override_user():
        return user

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_db] = _override_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_db, None)


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
    data = resp.json()
    assert data["preferred_provider"] == "cloud"
    assert data["first_launch_completed"] is False
