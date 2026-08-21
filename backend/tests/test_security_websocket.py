"""A6: WebSocket 加固测试 - Phase 8 P7"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.security import create_access_token, create_refresh_token


USER_UUID = "12345678-1234-5678-1234-567812345678"


@pytest.fixture
def strong_settings(monkeypatch):
    """稳定 jwt 密钥"""
    from app.core.config import settings
    monkeypatch.setattr(settings, "jwt_secret_key", "test-secret-key-for-unit-tests-32+chars")
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    yield settings


async def test_ws_rejects_refresh_token(strong_settings):
    """WebSocket 应拒绝 refresh token（_authenticate 校验 type==access）"""
    from app.api.websocket import _authenticate
    refresh = create_refresh_token("1")
    result = await _authenticate(refresh)
    assert result is None


async def test_ws_accepts_access_token(strong_settings):
    """WebSocket 应接受合法 access token"""
    from app.api.websocket import _authenticate
    access = create_access_token(USER_UUID)
    result = await _authenticate(access)
    assert result is not None
    assert result.get("type") == "access"


async def test_ws_rejects_cross_origin(strong_settings, monkeypatch):
    """跨域 origin 应被拒绝（close code 4003）"""
    from app.api.websocket import handle_websocket
    from app.core.config import settings

    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173")

    access = create_access_token(USER_UUID)

    ws = MagicMock()
    ws.query_params = {"token": access}
    ws.headers = {"origin": "http://evil.example.com"}
    ws.close = AsyncMock()

    await handle_websocket(ws)

    # 应调用 close，code=4003
    ws.close.assert_awaited()
    args, kwargs = ws.close.call_args
    code = args[0] if args else kwargs.get("code")
    assert code == 4003


async def test_ws_allows_desktop_origin(strong_settings, monkeypatch):
    """file:// origin 应被允许（桌面应用）"""
    from app.api.websocket import handle_websocket
    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.base import Base
    import app.models  # noqa

    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173")

    # 创建 in-memory DB 并 patch AsyncSessionLocal
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", SessionLocal)
    monkeypatch.setattr("app.api.websocket.AsyncSessionLocal", SessionLocal, raising=False)

    access = create_access_token(USER_UUID)
    ws = MagicMock()
    ws.query_params = {"token": access}
    ws.headers = {"origin": "file://desktop-app"}
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_json = AsyncMock(side_effect=Exception("stop"))

    # patch ws_manager.subscribe/unsubscribe
    with patch("app.api.websocket.ws_manager") as fake_mgr:
        fake_mgr.subscribe = AsyncMock()
        fake_mgr.unsubscribe = AsyncMock()
        await handle_websocket(ws)

    # file:// origin 应被允许，应调用 accept
    ws.accept.assert_awaited()
    await engine.dispose()


async def test_ws_ping_heartbeat(strong_settings, monkeypatch):
    """60s 无消息时应发送 ping 心跳"""
    from app.api.websocket import handle_websocket
    from app.core.config import settings
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.base import Base
    import app.models  # noqa

    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", SessionLocal)
    monkeypatch.setattr("app.api.websocket.AsyncSessionLocal", SessionLocal, raising=False)

    access = create_access_token(USER_UUID)

    ws = MagicMock()
    ws.query_params = {"token": access}
    ws.headers = {"origin": "http://localhost:5173"}
    ws.close = AsyncMock()
    ws.accept = AsyncMock()
    sent = []

    async def fake_send_json(msg):
        sent.append(msg)
        if msg.get("type") == "ping":
            # 收到 ping 后断开连接以结束测试
            raise Exception("stop-after-ping")

    async def fake_receive_json():
        # 模拟 60s 无消息
        await asyncio.sleep(0.1)
        raise asyncio.TimeoutError()

    ws.send_json = fake_send_json
    # 模拟首次 receive_json 超时
    call_count = {"n": 0}

    async def receive_then_timeout():
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise asyncio.TimeoutError()
        raise Exception("stop")

    ws.receive_json = receive_then_timeout

    with patch("app.api.websocket.ws_manager") as fake_mgr:
        fake_mgr.subscribe = AsyncMock()
        fake_mgr.unsubscribe = AsyncMock()
        # monkeypatch wait_for 的 timeout 为极短时间
        monkeypatch.setattr("app.api.websocket.asyncio.wait_for", lambda coro, timeout: coro)
        # 由于我们移除了 wait_for 的超时，需要 receive_json 自己抛 TimeoutError
        await handle_websocket(ws)

    # 应至少发送过 ping（首次 receive_json 抛 TimeoutError 后应发 ping）
    types_sent = [m.get("type") for m in sent]
    assert "ping" in types_sent
    await engine.dispose()


async def test_ws_rejects_revoked_token(strong_settings, monkeypatch):
    """已撤销的 access token 应被 WS 拒绝（close 4001）"""
    from datetime import datetime, timezone, timedelta
    from app.api.websocket import handle_websocket
    from app.core.config import settings
    from app.models.revoked_token import RevokedToken
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.models.base import Base
    import app.models  # noqa

    monkeypatch.setattr(settings, "cors_origins", "http://localhost:5173")

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", SessionLocal)
    monkeypatch.setattr("app.api.websocket.AsyncSessionLocal", SessionLocal, raising=False)

    access = create_access_token(USER_UUID)
    from app.core.security import decode_token
    payload = decode_token(access)
    jti = payload["jti"]

    # 插入撤销记录
    async with SessionLocal() as s:
        s.add(RevokedToken(
            jti=jti,
            user_id=USER_UUID,
            token_type="access",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        ))
        await s.commit()

    ws = MagicMock()
    ws.query_params = {"token": access}
    ws.headers = {"origin": "http://localhost:5173"}
    ws.close = AsyncMock()

    await handle_websocket(ws)

    ws.close.assert_awaited()
    args, kwargs = ws.close.call_args
    code = args[0] if args else kwargs.get("code")
    assert code == 4001
    await engine.dispose()


async def test_ws_channel_authorization_fails_closed():
    """仅允许用户自己的私有频道，未知及全局频道默认拒绝。"""
    from app.api.websocket import _can_subscribe

    db = AsyncMock()
    assert await _can_subscribe(f"user:{USER_UUID}", USER_UUID, db)
    assert await _can_subscribe(f"image:{USER_UUID}", USER_UUID, db)
    assert not await _can_subscribe("user:someone-else", USER_UUID, db)
    assert not await _can_subscribe("global", USER_UUID, db)
    assert not await _can_subscribe("unknown:value", USER_UUID, db)


async def test_ws_task_channel_requires_owner():
    """任务频道必须属于当前用户。"""
    from app.api.websocket import _can_subscribe

    result = MagicMock()
    result.scalar_one_or_none.return_value = USER_UUID
    db = MagicMock()
    db.execute = AsyncMock(return_value=result)

    assert await _can_subscribe("task:task_owned", USER_UUID, db)
    assert not await _can_subscribe("task:task_owned", "someone-else", db)
