"""测试首启动 API

适配项目 conftest.py 的 db_session fixture 模式（in-memory SQLite + monkeypatch）。
通过 app.dependency_overrides 同时覆盖 get_current_user 与 get_db，
使 endpoint 与测试共享同一个 db_session。

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
        username=f"launchuser_{uuid4().hex[:8]}",
        email=f"launch_{uuid4().hex[:8]}@example.com",
        password_hash=hash_password("Test1234!"),
        first_launch_completed=False,
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
