"""A1: Token 撤销闭环测试 - Phase 8 P7"""
import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import select

from app.core.security import create_access_token, create_refresh_token, decode_token
from app.models.revoked_token import RevokedToken


@pytest.fixture
def strong_settings(monkeypatch):
    """确保测试使用稳定 jwt 密钥"""
    from app.core.config import settings
    monkeypatch.setattr(settings, "jwt_secret_key", "test-secret-key-for-unit-tests-32+chars")
    monkeypatch.setattr(settings, "jwt_algorithm", "HS256")
    yield settings


async def _add_revoked(db_session, jti: str, token_type: str = "access", user_id: str = "1"):
    """辅助：插入一条撤销记录"""
    db_session.add(RevokedToken(
        jti=jti,
        user_id=user_id,
        token_type=token_type,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    await db_session.flush()


async def test_access_token_invalid_after_logout(db_session, strong_settings):
    """撤销后的 access token 应被拒绝"""
    from app.core.deps import get_current_user
    from app.models.user import User
    from fastapi import HTTPException

    # 准备一个用户
    user = User(username="alice", email="alice@example.com", password_hash="x", status="active")
    db_session.add(user)
    await db_session.flush()

    token = create_access_token(str(user.id))
    payload = decode_token(token)
    assert payload is not None
    jti = payload["jti"]

    # 撤销该 token
    await _add_revoked(db_session, jti, "access", str(user.id))

    # 调用 get_current_user 应抛 401
    with pytest.raises(HTTPException) as exc:
        await get_current_user(token=token, db=db_session)
    assert exc.value.status_code == 401


async def test_revoked_refresh_token_rejected(db_session, strong_settings):
    """撤销后的 refresh token 在 /auth/refresh 应被拒绝"""
    from app.api.auth import refresh_token
    from fastapi import HTTPException

    token = create_refresh_token("1")
    payload = decode_token(token)
    jti = payload["jti"]
    await _add_revoked(db_session, jti, "refresh", "1")

    with pytest.raises(HTTPException) as exc:
        await refresh_token(token, db=db_session)
    assert exc.value.status_code == 401
    assert "撤销" in exc.value.detail


async def test_non_revoked_token_still_valid(db_session, strong_settings):
    """未撤销的 access token 仍可用"""
    from app.core.deps import get_current_user
    from app.models.user import User

    user = User(username="bob", email="bob@example.com", password_hash="x", status="active")
    db_session.add(user)
    await db_session.flush()

    token = create_access_token(str(user.id))
    # 不撤销，直接调用应成功
    result = await get_current_user(token=token, db=db_session)
    assert result.id == user.id


async def test_websocket_rejects_revoked_token(db_session, strong_settings):
    """WebSocket 应拒绝已撤销的 token"""
    from app.api.websocket import _authenticate_with_db

    token = create_access_token("1")
    payload = decode_token(token)
    jti = payload["jti"]
    await _add_revoked(db_session, jti, "access", "1")

    result = await _authenticate_with_db(token, db_session)
    assert result is None


async def test_websocket_rejects_refresh_token_type(db_session, strong_settings):
    """WebSocket 应拒绝 refresh token（type != access）"""
    from app.api.websocket import _authenticate_with_db

    token = create_refresh_token("1")
    result = await _authenticate_with_db(token, db_session)
    assert result is None
