"""
Y·NEX HTTP API 服务器
让手机、Shortcuts、其他设备可以通过网络调用Y·NEX能力。

端点（均需认证）：
    GET  /                  状态（无需认证）
    POST /chat              与 AI 对话
    POST /command           执行设备控制指令
    POST /wake              远程唤醒Y·NEX（触发播报）
    POST /event             触发事件（供自动化引擎使用）
    POST /mqtt              发布 MQTT 消息
    GET  /devices           列出已注册设备域
    GET  /rules             列出自动化规则
    POST /rules             添加自动化规则
    GET  /status            系统状态
    GET  /keys              列出 API Keys（owner）
    POST /keys              创建 API Key（owner）
    DELETE /keys/<id>       撤销 API Key（owner）

认证方式：Header X-API-Key: <key>，或信任 IP 直通（局域网）。
权限分级：owner > family > guest，详见 auth.py。

优先使用 Flask，未安装时回退到 Python 内置 http.server。
"""

import json
import os
import threading
import time
from typing import Dict, Any

from logger import logger
from config import settings


API_PORT = int(os.getenv("YNEX_API_PORT", "7788"))
_server_thread = None


def _json_response(data: Any, status: int = 200) -> Any:
    """Flask 响应"""
    try:
        from flask import jsonify
        response = jsonify(data)
        response.status_code = status
        return response
    except Exception:
        pass
    return data, status


def _create_flask_app():
    from flask import Flask, request
    from device_hub import parse_and_execute, list_domains
    from brain import get_ai_response
    from mqtt_bus import publish, get_status as mqtt_status
    from automation_engine import add_rule, list_rules, trigger_event
    from auth import (
        verify_request, check_permission, check_tool_access,
        create_api_key, revoke_api_key, list_api_keys,
        UserRole
    )
    from speech import speak
    import psutil

    app = Flask(__name__)

    def _auth(permission: str = None):
        """认证装饰器工厂"""
        def decorator(f):
            def wrapped(*args, **kwargs):
                # 仅允许从 Header 读取 API Key，禁止 URL/表单传参以避免日志泄露
                api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
                client_ip = request.remote_addr or "127.0.0.1"
                ok, role, err, api_key_obj = verify_request(api_key, client_ip)
                if not ok:
                    return _json_response({"error": err, "authenticated": False}, 401)
                if permission and not check_permission(role, permission):
                    return _json_response({"error": f"权限不足：需要 {permission}"}, 403)
                request._user_role = role
                request._api_key_obj = api_key_obj
                # 保存 key_hash 用于后续额度统计（不保存原始 key）
                from auth import _hash_key
                request._key_hash = _hash_key(api_key) if api_key else None
                return f(*args, **kwargs)
            wrapped.__name__ = f.__name__
            return wrapped
        return decorator

    # ---- 公开端点 ----

    @app.route("/", methods=["GET"])
    def index():
        return _json_response({
            "name": "Y·NEX Jarvis API",
            "status": "running",
            "version": "2.0",
            "port": API_PORT,
            "authenticated": False,
            "endpoints": ["/chat", "/command", "/wake", "/status"],
            "hint": "在 Header 添加 X-API-Key 进行认证"
        })

    # ---- 认证端点 ----

    @app.route("/chat", methods=["POST"])
    @_auth("chat")
    def chat():
        data = request.get_json(silent=True) or {}
        text = data.get("text", "")
        use_mock = data.get("mock", False)
        if not text:
            return _json_response({"error": "缺少 text 参数"}, 400)

        # API Key 额度检查：使用原子扣减消除 TOCTOU 竞态
        from auth import deduct_api_key_quota
        key_hash = getattr(request, "_key_hash", None)
        allowed, reason = deduct_api_key_quota(key_hash, tokens_needed=len(text) + 1000)
        if not allowed:
            return _json_response({"error": reason}, 402)

        reply = get_ai_response(text, use_mock=use_mock)
        # 补扣实际用量与预扣的差额
        tokens_used = len(text) + len(reply)
        extra = tokens_used - (len(text) + 1000)
        if extra > 0:
            from auth import record_api_key_usage
            record_api_key_usage(key_hash, extra)
        return _json_response({
            "user": text,
            "reply": reply,
            "role": request._user_role.value,
            "tokens": tokens_used
        })

    @app.route("/command", methods=["POST"])
    @_auth("command")
    def command():
        data = request.get_json(silent=True) or {}
        cmd = data.get("command", "")
        tool = data.get("tool", "")
        if not cmd and not tool:
            return _json_response({"error": "缺少 command 或 tool 参数"}, 400)
        # 检查工具权限（传入 Key 的 allowed_tools 白名单）
        allowed_tools = getattr(request._api_key_obj, "allowed_tools", None) if request._api_key_obj else None
        if tool and not check_tool_access(request._user_role, tool, allowed_tools):
            return _json_response({"error": f"权限不足：无法使用 {tool}"}, 403)
        result = parse_and_execute(cmd or tool)
        return _json_response({"command": cmd, "result": result, "role": request._user_role.value})

    @app.route("/wake", methods=["POST"])
    @_auth("wake_remote")
    def wake():
        """远程唤醒：通过语音播报通知用户Y·NEX已响应"""
        data = request.get_json(silent=True) or {}
        message = data.get("message", "先生，我在这里。")
        try:
            speak(message)
        except Exception:
            pass
        return _json_response({"wake": True, "message": message, "role": request._user_role.value})

    @app.route("/event", methods=["POST"])
    @_auth("automation_rules")
    def event():
        data = request.get_json(silent=True) or {}
        event_type = data.get("type", "")
        payload = data.get("payload", {})
        if not event_type:
            return _json_response({"error": "缺少 type 参数"}, 400)
        trigger_event(event_type, payload)
        return _json_response({"type": event_type, "triggered": True, "role": request._user_role.value})

    @app.route("/mqtt", methods=["POST"])
    @_auth("mqtt")
    def mqtt_pub():
        data = request.get_json(silent=True) or {}
        topic = data.get("topic", "")
        payload = data.get("payload", "")
        if not topic:
            return _json_response({"error": "缺少 topic 参数"}, 400)
        publish(topic, payload)
        return _json_response({"topic": topic, "published": True, "role": request._user_role.value})

    @app.route("/devices", methods=["GET"])
    @_auth("device_control")
    def devices():
        return _json_response({"domains": list_domains(), "role": request._user_role.value})

    @app.route("/rules", methods=["GET"])
    @_auth("automation_rules")
    def rules_get():
        return _json_response({"rules": list_rules(), "role": request._user_role.value})

    @app.route("/rules", methods=["POST"])
    @_auth("automation_rules")
    def rules_post():
        data = request.get_json(silent=True) or {}
        result = add_rule(data)
        return _json_response({"result": result, "role": request._user_role.value})

    @app.route("/status", methods=["GET"])
    @_auth("system_info")
    def status():
        try:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            uptime = time.time() - psutil.boot_time()
            hours = int(uptime // 3600)
            minutes = int((uptime % 3600) // 60)
        except Exception:
            cpu = mem = disk = None
            hours = minutes = 0
        return _json_response({
            "status": "running",
            "role": request._user_role.value,
            "system": {
                "cpu_percent": cpu,
                "memory_percent": mem.percent if mem else None,
                "disk_percent": disk.percent if disk else None,
                "uptime": f"{hours}h {minutes}m"
            }
        })

    # ---- Owner 管理端点 ----

    @app.route("/keys", methods=["GET"])
    @_auth("admin_users")
    def keys_list():
        return _json_response({"keys": list_api_keys()})

    @app.route("/keys", methods=["POST"])
    @_auth("admin_users")
    def keys_create():
        data = request.get_json(silent=True) or {}
        name = data.get("name", "未命名")
        role = data.get("role", "family")
        allowed_tools = data.get("allowed_tools")
        try:
            from auth import UserRole as UR
            raw, key_id = create_api_key(name, UR(role), allowed_tools)
            return _json_response({"created": True, "api_key": raw, "key_id": key_id, "hint": "仅此一次显示，请妥善保存"})
        except Exception as e:
            return _json_response({"error": str(e)}, 400)

    @app.route("/keys/<key_id>", methods=["DELETE"])
    @_auth("admin_users")
    def keys_revoke(key_id):
        ok = revoke_api_key(key_id)
        return _json_response({"revoked": ok, "key_id": key_id})

    return app


def start_api_server(blocking: bool = False):
    """启动 API 服务器"""
    global _server_thread

    def run():
        try:
            app = _create_flask_app()
            host = settings.api_bind_host
            logger.info(f"Y·NEX HTTP API 已启动（Flask）：{host}:{API_PORT}")
            app.run(host=host, port=API_PORT, debug=False, use_reloader=False)
        except ImportError:
            logger.error("Flask 未安装，API 服务器无法启动。请安装 Flask 后再试。")
            raise
        except Exception as e:
            logger.error(f"API 服务器启动失败：{e}")
            raise

    if blocking:
        run()
    else:
        if _server_thread is None or not _server_thread.is_alive():
            _server_thread = threading.Thread(target=run, daemon=True)
            _server_thread.start()


if __name__ == "__main__":
    start_api_server(blocking=True)
