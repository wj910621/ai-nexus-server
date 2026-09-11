"""/ws WebSocket 端点 - JWT 认证 + 心跳

协议：
- 客户端通过 ``ws://host/ws?token=<JWT>`` 建立连接
- 服务端验证 JWT 后自动订阅 ``user:{user_id}`` 频道
- 客户端可发送以下消息：
    - {"type": "ping"}                      -> {"type": "pong"}
    - {"type": "subscribe", "channel": "..."} -> {"type": "subscribed", "channel": "..."}
    - {"type": "unsubscribe", "channel": "..."} -> {"type": "unsubscribed", "channel": "..."}

频道命名：``task:{id}`` / ``workflow:{id}`` / ``user:{id}`` /
``image:{user_id}`` / ``video:{user_id}``。系统广播频道不接受客户端订阅。
"""
import asyncio
import logging
import time
from collections import deque
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.config import settings
from app.core.metrics import (
    websocket_connections_active,
    websocket_messages_sent_total,
)
from app.core.security import decode_token, decode_ynex_story_token
from app.core.ws_manager import ws_manager
from app.models.background_task import BackgroundTask
from app.models.revoked_token import RevokedToken
from app.models.user import User
from app.models.workflow import WorkflowExecution as PersistedWorkflowExecution

router = APIRouter()
logger = logging.getLogger(__name__)


async def _authenticate(token: str) -> Optional[dict]:
    """Validate JWT (signature + type=access), return payload or None.

    注意：此函数不校验撤销表（无 db session），仅做无状态校验。
    撤销校验请使用 :func:`_authenticate_with_db`。
    """
    payload = (
        decode_ynex_story_token(token)
        if settings.billing_mode == "jarvis"
        else decode_token(token)
    )
    if payload is None:
        return None
    # Standalone WebSocket only accepts local access tokens. Y·NEX Story
    # sessions are audience-restricted and intentionally have no local type.
    if settings.billing_mode != "jarvis" and payload.get("type") != "access":
        return None
    return payload


async def _authenticate_with_db(token: str, db_session) -> Optional[dict]:
    """Validate JWT + 校验撤销表，返回 payload 或 None。

    A1: WebSocket 闭环校验，与 ``get_current_user`` 行为一致。
    """
    payload = await _authenticate(token)
    if payload is None:
        return None
    if settings.billing_mode == "jarvis":
        subject = str(payload.get("sub") or "")
        if not subject:
            return None
        result = await db_session.execute(
            select(User).where(User.external_subject == subject)
        )
        user = result.scalar_one_or_none()
        if user is None or user.status != "active":
            return None
        # All channel ownership rows use the local Story UUID.
        return {**payload, "sub": str(user.id), "ynex_sub": subject}

    jti = payload.get("jti")
    if jti:
        result = await db_session.execute(
            select(RevokedToken).where(RevokedToken.jti == jti)
        )
        if result.scalar_one_or_none() is not None:
            return None
    return payload


async def _can_subscribe(channel: str, user_id: str, db_session) -> bool:
    """Return whether a user owns the private resource represented by channel."""
    if channel in {f"user:{user_id}", f"image:{user_id}", f"video:{user_id}"}:
        return True

    prefix, separator, resource_id = channel.partition(":")
    if not separator or not resource_id:
        return False

    if prefix == "task":
        result = await db_session.execute(
            select(BackgroundTask.user_id).where(BackgroundTask.id == resource_id)
        )
        owner_id = result.scalar_one_or_none()
        return owner_id is not None and str(owner_id) == user_id

    if prefix == "workflow":
        # Prefer live state, then fall back to the durable ownership record.
        from app.engines.workflow.executor import workflow_executor

        execution = workflow_executor.get_execution(resource_id)
        if execution is not None:
            return execution.user_id == user_id
        try:
            from uuid import UUID
            execution_uuid = UUID(resource_id)
        except ValueError:
            return False
        result = await db_session.execute(
            select(PersistedWorkflowExecution.user_id).where(
                PersistedWorkflowExecution.id == execution_uuid
            )
        )
        owner_id = result.scalar_one_or_none()
        return owner_id is not None and str(owner_id) == user_id

    # Unknown channel types and privileged broadcasts such as "global" fail closed.
    return False


async def handle_websocket(websocket: WebSocket) -> None:
    """Handle a single WS connection: auth -> accept -> subscribe -> loop."""
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001)
        return

    payload = await _authenticate(token)
    if payload is None:
        await websocket.close(code=4001)
        return

    # A6: origin 校验（防止跨站 WS 劫持）
    origin = websocket.headers.get("origin", "")
    if (
        origin
        and origin not in settings.cors_origins_list
        and not origin.startswith("file://")
    ):
        await websocket.close(code=4003)
        return

    user_id = str(payload.get("sub") or "")
    if not user_id:
        await websocket.close(code=4001)
        return

    # A1: 撤销表校验（需要 db session）
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        authenticated_payload = await _authenticate_with_db(token, db)
        if authenticated_payload is None:
            await websocket.close(code=4001)
            return
        payload = authenticated_payload

    user_id = str(payload.get("sub") or "")

    await websocket.accept()
    websocket_connections_active.inc()
    # Auto-subscribe user to their own channel
    subscribed = await ws_manager.subscribe(
        websocket,
        f"user:{user_id}",
        user_id=user_id,
        max_connections=settings.ws_max_connections_per_user,
        max_subscriptions=settings.ws_max_subscriptions_per_connection,
    )
    if not subscribed:
        websocket_connections_active.dec()
        await websocket.close(code=4008, reason="WebSocket connection limit exceeded")
        return

    message_times: deque[float] = deque()
    try:
        # A6: 心跳 - 每收到一条消息前最多等待 60s，否则发送 ping
        while True:
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(), timeout=60.0
                )
            except asyncio.TimeoutError:
                # 60s 无消息，发送心跳 ping
                try:
                    await websocket.send_json({"type": "ping"})
                except Exception:
                    break
                continue

            now = time.monotonic()
            while message_times and message_times[0] <= now - 60:
                message_times.popleft()
            message_times.append(now)
            if len(message_times) > settings.ws_max_messages_per_minute:
                await websocket.close(code=4008, reason="WebSocket message rate exceeded")
                break

            if not isinstance(message, dict):
                await websocket.send_json({"type": "error", "message": "Invalid message"})
                continue
            msg_type = message.get("type")
            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})
            elif msg_type == "subscribe":
                channel = message.get("channel", "")
                if not isinstance(channel, str) or len(channel) > settings.ws_max_channel_length:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Invalid channel",
                    })
                    continue
                async with AsyncSessionLocal() as db:
                    allowed = await _can_subscribe(channel, user_id, db)
                if not allowed:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Channel not found or access denied",
                    })
                    continue
                subscribed = await ws_manager.subscribe(
                    websocket,
                    channel,
                    user_id=user_id,
                    max_subscriptions=settings.ws_max_subscriptions_per_connection,
                )
                if not subscribed:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Subscription limit exceeded",
                    })
                    continue
                await websocket.send_json({
                    "type": "subscribed",
                    "channel": channel,
                })
            elif msg_type == "unsubscribe":
                channel = message.get("channel", "")
                await ws_manager.unsubscribe(websocket, channel)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "channel": channel,
                })
    except WebSocketDisconnect:
        await ws_manager.unsubscribe(websocket)
        websocket_connections_active.dec()
        logger.debug(f"WS disconnected user={user_id}")
    except Exception as exc:
        logger.warning(f"WS error: {exc}")
        await ws_manager.unsubscribe(websocket)
        websocket_connections_active.dec()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint with JWT auth via ?token=..."""
    await handle_websocket(websocket)
