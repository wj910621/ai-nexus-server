"""WebSocket 连接管理器 - 频道发布订阅

频道命名约定：
- task:{task_id}   — 任务进度推送
- user:{user_id}   — 用户私人通知
- image:{user_id}  — 图像生成进度
- video:{user_id}  — 视频合成进度
- global           — 仅服务端广播，不接受客户端订阅

自动清理断线连接。
"""
import asyncio
import logging
from collections import defaultdict
from typing import Any, Optional

from fastapi import WebSocket

from app.core.metrics import websocket_messages_sent_total

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket 连接管理器（频道订阅模式）。

    所有写操作（subscribe/unsubscribe 以及 publish 失败后的清理）都通过
    同一把 ``asyncio.Lock`` 串行化，避免并发修改 ``_channels`` / ``_user_conns``。
    """

    def __init__(self) -> None:
        self._channels: dict[str, set[WebSocket]] = defaultdict(set)
        self._user_conns: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        websocket: WebSocket,
        channel: str,
        user_id: Optional[str] = None,
        max_connections: Optional[int] = None,
        max_subscriptions: Optional[int] = None,
    ) -> bool:
        """Atomically subscribe, optionally enforcing per-user/connection limits."""
        async with self._lock:
            normalized_user_id = str(user_id) if user_id is not None else None
            if normalized_user_id is not None:
                user_connections = self._user_conns[normalized_user_id]
                if (
                    websocket not in user_connections
                    and max_connections is not None
                    and len(user_connections) >= max_connections
                ):
                    return False
            if max_subscriptions is not None:
                current_subscriptions = sum(
                    websocket in connections for connections in self._channels.values()
                )
                if (
                    websocket not in self._channels.get(channel, set())
                    and current_subscriptions >= max_subscriptions
                ):
                    return False
            self._channels[channel].add(websocket)
            if normalized_user_id is not None:
                self._user_conns[normalized_user_id].add(websocket)
        logger.debug(f"WS subscribed to {channel} (user={user_id})")
        return True

    async def unsubscribe(
        self,
        websocket: WebSocket,
        channel: Optional[str] = None,
    ) -> None:
        """退订频道。``channel=None`` 表示从所有频道退订。"""
        async with self._lock:
            if channel is None:
                for ch in list(self._channels.keys()):
                    self._channels[ch].discard(websocket)
                    if not self._channels[ch]:
                        del self._channels[ch]
                for uid in list(self._user_conns.keys()):
                    self._user_conns[uid].discard(websocket)
                    if not self._user_conns[uid]:
                        del self._user_conns[uid]
            else:
                connections = self._channels.get(channel)
                if connections is None:
                    return
                connections.discard(websocket)
                if not connections:
                    del self._channels[channel]

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """向频道所有订阅者推送消息，自动剔除断线连接。"""
        subscribers = list(self._channels.get(channel, set()))
        dead: list[WebSocket] = []
        for ws in subscribers:
            try:
                await ws.send_json(message)
                websocket_messages_sent_total.labels(type=message.get("type", "message")).inc()
            except Exception as exc:
                logger.debug(f"WS publish failed on {channel}: {exc}")
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._channels[channel].discard(ws)
                    for conns in self._user_conns.values():
                        conns.discard(ws)

    async def publish_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        """向指定用户的所有连接推送消息。"""
        conns = list(self._user_conns.get(str(user_id), set()))
        for ws in conns:
            try:
                await ws.send_json(message)
                websocket_messages_sent_total.labels(type=message.get("type", "message")).inc()
            except Exception:
                pass

    async def broadcast(self, message: dict[str, Any]) -> None:
        """向所有连接广播消息。"""
        all_ws: set[WebSocket] = set()
        for conns in self._channels.values():
            all_ws.update(conns)
        for ws in all_ws:
            try:
                await ws.send_json(message)
                websocket_messages_sent_total.labels(type=message.get("type", "message")).inc()
            except Exception:
                pass

    def get_subscriber_count(self, channel: str) -> int:
        """返回某频道的订阅者数量。"""
        return len(self._channels.get(channel, set()))

    def get_total_connections(self) -> int:
        """返回当前所有活跃 WebSocket 连接数。"""
        all_ws: set[WebSocket] = set()
        for conns in self._channels.values():
            all_ws.update(conns)
        return len(all_ws)

    def get_user_connection_count(self, user_id: str) -> int:
        return len(self._user_conns.get(str(user_id), set()))


# 模块级单例
ws_manager = WebSocketManager()
