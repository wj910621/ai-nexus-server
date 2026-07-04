"""
Y·NEX 本地AI核心服务 v1.0
把Y·NEX 所有本地能力封装成HTTP API，供 Y·NEX Desktop / Web / 手机多端调用。

启动方式：
  python ynex_server.py          # 默认端口 7777
  python ynex_server.py --port 8000

API文档：启动后访问 http://localhost:7777/docs
"""

import os
import sys
import time
import json
import uuid
import base64
import argparse
import ipaddress
import threading
from datetime import datetime
from typing import Any, Dict, List

# 加载 .env 配置（必须在其他业务模块导入之前，确保 AUTH_API_KEY_PEPPER 等环境变量可用）
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from flask import (Flask, request, jsonify, Response, stream_with_context,
                   render_template_string, send_from_directory)
from flask_cors import CORS

app = Flask(__name__)

# 服务启动时间与请求指标
_service_start_time = time.time()
_request_count = 0
_error_count = 0
_request_lock = threading.Lock()

from logger import logger, log_request, log_error
from config import settings
from brain import get_ai_response, TOOLS
from skills import SKILL_MAP
import memory as memory_module
from local_llm import get_local_llm, recommend_models, detect_hardware
from super_agent import get_super_agent
from auth import verify_request, check_permission, UserRole
from security import is_path_safe, is_command_safe, sanitize_input
from task_scheduler import get_scheduler, start_worker
from ops import generate_startup_report, print_startup_report, get_backup_manager

# =============================================================================
# 应用安全配置
# =============================================================================

app.config["MAX_CONTENT_LENGTH"] = settings.max_content_length_mb * 1024 * 1024

# CORS 配置
# 安全：禁止同时启用 origin="*" 与 supports_credentials，否则浏览器虽会拒绝，
# 但配置层面仍属不安全。当显式配置为 "*" 时，关闭 credentials 以符合 CORS 规范。
if settings.cors_origins == "*":
    _origins = "*"
    _supports_credentials = False
    logger.warning("CORS 配置为 '*' 且已关闭 supports_credentials，生产环境应改为具体域名白名单")
else:
    _origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    _supports_credentials = True
CORS(app, resources={r"/api/*": {"origins": _origins}}, supports_credentials=_supports_credentials)

# 信任网段解析
_TRUSTED_NETWORKS = []
for subnet in settings.trusted_subnets.split(","):
    subnet = subnet.strip()
    if not subnet:
        continue
    try:
        _TRUSTED_NETWORKS.append(ipaddress.ip_network(subnet, strict=False))
    except ValueError as e:
        logger.warning(f"信任网段配置错误 '{subnet}': {e}")

# 不需要认证的公开端点（支持通配符）
_PUBLIC_ENDPOINTS = {
    "/",
    "/docs",
    "/api/health",
    "/api/auth/verify",
}


def _is_public_endpoint(path: str) -> bool:
    """检查端点是否允许匿名访问"""
    if path in _PUBLIC_ENDPOINTS:
        return True
    # 通配符匹配
    for pub in _PUBLIC_ENDPOINTS:
        if pub.endswith("*") and path.startswith(pub[:-1]):
            return True
    return False


def _require_owner():
    """敏感操作要求 OWNER 权限"""
    role = getattr(request, "_user_role", UserRole.GUEST)
    if role != UserRole.OWNER:
        return jsonify({"ok": False, "error": "需要 owner 权限"}), 403
    return None


def _client_ip() -> str:
    """
    获取真实客户端 IP。

    安全策略：
      - 直接来源（remote_addr）始终可信；
      - X-Forwarded-For / X-Real-IP 仅在请求来自信任网段（反向代理）时才采用，
        否则攻击者可通过伪造 XFF 头冒充 127.0.0.1 等 IP 绕过基于 IP 的权限判断。
    """
    remote = request.remote_addr or "127.0.0.1"
    if _ip_in_trusted_subnet(remote):
        # 仅当直连来源是可信代理时，才解析代理链
        if "X-Forwarded-For" in request.headers:
            # 取代理链最左端的客户端 IP（已由可信代理追加）
            return request.headers["X-Forwarded-For"].split(",")[0].strip()
        if "X-Real-IP" in request.headers:
            return request.headers["X-Real-IP"].strip()
    return remote


def _ip_in_trusted_subnet(ip: str) -> bool:
    """检查 IP 是否在信任网段内"""
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _TRUSTED_NETWORKS)
    except ValueError:
        return False


@app.before_request
def _before_request():
    """请求前置处理：认证、请求 ID、日志、指标"""
    global _request_count
    with _request_lock:
        _request_count += 1

    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())[:8]
    request._request_id = request_id
    request._start_time = time.time()

    # 公开端点放行
    if _is_public_endpoint(request.path):
        request._user_role = UserRole.OWNER
        return None

    # API 限流检查
    try:
        from rate_limiter import check_rate_limit, get_client_id
        client_id = get_client_id(request)
        allowed, limit_info = check_rate_limit(client_id)
        request._rate_limit_info = limit_info
        if not allowed:
            headers = {
                "X-RateLimit-Limit": str(limit_info.get("limit", 0)),
                "X-RateLimit-Remaining": str(limit_info.get("remaining", 0)),
                "X-RateLimit-Reset": str(limit_info.get("reset_at", 0)),
            }
            log_error(request_id, f"触发限流: {client_id}")
            return jsonify({"ok": False, "error": "请求过于频繁，请稍后再试"}), 429, headers
    except Exception as e:
        logger.warning(f"限流检查失败，放行: {e}")

    # 信任网段放行
    ip = _client_ip()
    if _ip_in_trusted_subnet(ip):
        request._user_role = UserRole.OWNER
        return None

    # 仅从 Header 读取 API Key，禁止 URL 参数传参以避免日志泄露
    api_key = request.headers.get("X-API-Key")
    if not settings.api_key_required and not api_key:
        request._user_role = UserRole.GUEST
        return None

    ok, role, err, _api_key_obj = verify_request(api_key, ip)
    if not ok:
        log_error(request_id, f"认证失败: {err} (IP: {ip})")
        return jsonify({"ok": False, "error": err, "authenticated": False}), 401

    request._user_role = role
    return None


@app.after_request
def _after_request(response):
    """请求后置处理：追加请求 ID、日志、错误指标"""
    global _error_count
    if response.status_code >= 400:
        with _request_lock:
            _error_count += 1

    request_id = getattr(request, "_request_id", "-")
    start_time = getattr(request, "_start_time", None)
    duration = round(time.time() - start_time, 4) if start_time else None

    response.headers["X-Request-ID"] = request_id

    limit_info = getattr(request, "_rate_limit_info", None)
    if limit_info:
        response.headers["X-RateLimit-Limit"] = str(limit_info.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(limit_info.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(limit_info.get("reset_at", 0))

    log_request(
        request_id=request_id,
        method=request.method,
        path=request.path,
        ip=_client_ip(),
        status_code=response.status_code,
        extra={"duration": duration} if duration else {},
    )
    return response


def _error_response(message: str, status_code: int = 400, extra: dict = None):
    """统一错误响应"""
    request_id = getattr(request, "_request_id", "-")
    body = {"ok": False, "error": message, "request_id": request_id}
    if extra:
        body.update(extra)
    return jsonify(body), status_code


def _ok_response(data: dict = None):
    """统一成功响应"""
    body = {"ok": True}
    if data:
        body.update(data)
    return jsonify(body)


@app.errorhandler(413)
def _payload_too_large(e):
    return _error_response("请求体过大", 413, {"max_mb": settings.max_content_length_mb})


@app.errorhandler(404)
def _not_found(e):
    return _error_response("接口不存在", 404)


@app.errorhandler(405)
def _method_not_allowed(e):
    return _error_response("请求方法不允许", 405)


@app.errorhandler(500)
def _server_error(e):
    request_id = getattr(request, "_request_id", "-")
    log_error(request_id, f"服务端错误: {e}", extra={"traceback": str(e)})
    return _error_response("服务器内部错误", 500)


@app.errorhandler(Exception)
def _global_error(e):
    request_id = getattr(request, "_request_id", "-")
    log_error(request_id, f"未捕获异常: {e}", extra={"traceback": str(e)})
    # 安全：不向客户端返回原始异常信息，避免泄露内部实现（堆栈/SQL/路径等），
    # 仅返回通用错误提示，详细错误已记录到服务端日志。
    return _error_response("服务器内部错误", 500)


# =============================================================================
# 全局状态
# =============================================================================

local_llm = get_local_llm()
super_agent = get_super_agent()
task_scheduler = get_scheduler()
start_worker(check_interval=5)

# 插件系统热加载
_plugin_manager = None
try:
    from plugin_system import get_plugin_manager, auto_load
    auto_load()
    _plugin_manager = get_plugin_manager()
    logger.info(f"插件系统已加载: {len(_plugin_manager.plugins)} 个插件")
except Exception as e:
    logger.warning(f"插件系统加载失败: {e}")

# 数据库自动备份
_backup_manager = get_backup_manager()
_backup_manager.start_auto_backup()

# 简单的请求限流
_request_counts: Dict[str, tuple] = {}
_request_lock = threading.Lock()


def run_skill(skill_name: str, **kwargs):
    """统一调用技能的辅助函数"""
    if skill_name not in SKILL_MAP:
        raise ValueError(f"技能 '{skill_name}' 不存在")
    func = SKILL_MAP[skill_name]
    return func(**kwargs)


# =============================================================================
# 健康检查
# =============================================================================

@app.route("/")
def index():
    return jsonify({
        "name": "Y·NEX 本地AI核心服务",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "local_llm_available": local_llm.is_available,
        "timestamp": datetime.now().isoformat(),
    })


@app.route("/api/health")
def health():
    hw = detect_hardware()
    return jsonify({
        "status": "healthy",
        "hardware": {
            "ram_gb": hw.total_ram_gb,
            "vram_gb": hw.vram_gb,
            "cpu_cores": hw.cpu_cores,
            "has_gpu": hw.has_gpu,
            "gpu_name": hw.gpu_name,
        },
        "local_llm": local_llm.get_status(),
        "skills_count": len(SKILL_MAP),
        "tools_count": len(TOOLS),
    })


# =============================================================================
# 认证管理 API
# =============================================================================

@app.route("/api/auth/verify", methods=["GET"])
def auth_verify():
    """验证当前请求的身份"""
    role = getattr(request, "_user_role", UserRole.GUEST)
    return jsonify({
        "ok": True,
        "authenticated": role != UserRole.GUEST,
        "role": role.value,
        "api_key_required": settings.api_key_required,
    })


@app.route("/api/auth/keys", methods=["GET"])
def auth_list_keys():
    """列出所有 API Key（仅 OWNER）"""
    role = getattr(request, "_user_role", UserRole.GUEST)
    if role != UserRole.OWNER:
        return jsonify({"ok": False, "error": "需要 owner 权限"}), 403
    from auth import list_api_keys
    return jsonify({"ok": True, "keys": list_api_keys()})


@app.route("/api/auth/keys", methods=["POST"])
def auth_create_key():
    """创建 API Key（仅 OWNER）"""
    role = getattr(request, "_user_role", UserRole.GUEST)
    if role != UserRole.OWNER:
        return jsonify({"ok": False, "error": "需要 owner 权限"}), 403
    from auth import create_api_key, UserRole
    data = request.json or {}
    name = data.get("name", "未命名")
    role_str = data.get("role", "family")
    raw, key_id = create_api_key(name, UserRole(role_str))
    return jsonify({
        "ok": True,
        "key": raw,
        "key_id": key_id,
        "warning": "请立即保存 Key，之后无法再次查看",
    })


@app.route("/api/auth/keys/<key_id>", methods=["DELETE"])
def auth_revoke_key(key_id):
    """撤销 API Key（仅 OWNER）"""
    role = getattr(request, "_user_role", UserRole.GUEST)
    if role != UserRole.OWNER:
        return jsonify({"ok": False, "error": "需要 owner 权限"}), 403
    from auth import revoke_api_key
    # auth.revoke_api_key 已通过 api_key.key_id 字段精确匹配，
    # 旧代码错误地用 hash_key.startswith(key_id) 比较哈希前缀，
    # 概率约 1/4294967296，导致撤销功能完全失效。
    ok = revoke_api_key(key_id)
    if not ok:
        return jsonify({"ok": False, "error": "Key 不存在"}), 404
    return jsonify({"ok": True})


# =============================================================================
# 文本对话 API
# =============================================================================

@app.route("/api/chat", methods=["POST"])
def api_chat():
    """
    普通文本对话
    {
        "message": "你好",
        "history": [{"role": "user", "content": "..."}, ...],
        "use_local": false,
        "use_mock": false
    }
    """
    data = request.json or {}
    message = data.get("message", "").strip()
    history = data.get("history", [])
    use_local = data.get("use_local", False)
    use_mock = data.get("use_mock", False)

    if not message:
        return _error_response("message不能为空", 400)

    try:
        if use_local and local_llm.is_available:
            messages = [{"role": h["role"], "content": h["content"]} for h in history]
            messages.append({"role": "user", "content": message})
            reply, source = local_llm.chat(messages, use_api_fallback=False)
        else:
            reply = get_ai_response(message, use_mock=use_mock)
            source = "api"

        try:
            messages = memory_module.get_memory()
            messages.append({"role": "user", "content": message})
            messages.append({"role": "assistant", "content": reply})
            memory_module.save_memory(messages[-settings.max_history * 2:])
        except Exception as e:
            logger.warning(f"保存对话历史失败: {e}")

        return _ok_response({
            "reply": reply,
            "source": source,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.error(f"/api/chat 失败: {e}")
        # 安全：不向客户端返回原始异常，避免泄露内部实现
        return _error_response("对话处理失败，请稍后重试", 500)


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """
    流式文本对话
    """
    data = request.json or {}
    message = data.get("message", "").strip()
    use_local = data.get("use_local", False)
    use_mock = data.get("use_mock", False)

    if not message:
        return _error_response("message不能为空", 400)

    def generate():
        try:
            if use_local and local_llm.is_available:
                messages = [{"role": "user", "content": message}]
                for token, source in local_llm.chat_stream(messages):
                    yield f"data: {json.dumps({'content': token, 'source': source}, ensure_ascii=False)}\n\n"
                    time.sleep(0.01)
            else:
                reply = get_ai_response(message, use_mock=use_mock)
                for char in reply:
                    yield f"data: {json.dumps({'content': char, 'source': 'api'}, ensure_ascii=False)}\n\n"
                    time.sleep(0.01)

            yield f"data: {json.dumps({'content': '', 'done': True}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            request_id = getattr(request, "_request_id", "-")
            logger.error(f"/api/chat/stream 失败: {e}")
            yield f"data: {json.dumps({'ok': False, 'error': str(e), 'request_id': request_id}, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


# =============================================================================
# M5: 代码补全 / 语义搜索 / 语音转代码 API
# =============================================================================

@app.route("/api/code/completion", methods=["POST"])
def api_code_completion():
    """
    AI 内联代码补全（FIM 格式）
    """
    data = request.json or {}
    prompt = data.get("prompt", "").strip()
    max_tokens = data.get("max_tokens", 64)
    temperature = data.get("temperature", 0.1)
    stop = data.get("stop", ["\n\n\n"])

    if not prompt:
        return _error_response("prompt不能为空", 400)

    try:
        result = get_ai_response(prompt, max_tokens=max_tokens, temperature=temperature, stop=stop)
        # 提取纯代码，去除 markdown 包裹
        code_match = re.search(r"```[\w]*\n?([\s\S]*?)\n?```", result)
        text = (code_match.group(1) if code_match else result).strip()
        return jsonify({"text": text, "tokens": len(text) // 3})
    except Exception as e:
        logger.error(f"/api/code/completion 失败: {e}")
        return jsonify({"text": "", "error": str(e)})


@app.route("/api/code/search", methods=["POST"])
def api_code_search():
    """
    语义代码搜索：在项目工作区中搜索相关代码
    """
    data = request.json or {}
    query = data.get("query", "").strip()
    workspace_path = data.get("workspacePath", "").strip()

    if not query:
        return _error_response("query不能为空", 400)

    results = []
    try:
        if workspace_path and os.path.isdir(workspace_path):
            # 遍历项目文件，搜索关键词匹配
            code_exts = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.cpp', '.c', '.h', '.html', '.css', '.json', '.yaml', '.yml', '.md'}
            for root, dirs, files in os.walk(workspace_path):
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', '__pycache__', 'venv', '.git', 'dist', 'build')]
                for file in files:
                    ext = os.path.splitext(file)[1].lower()
                    if ext not in code_exts:
                        continue
                    fp = os.path.join(root, file)
                    try:
                        with open(fp, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                    except Exception:
                        continue
                    # 简单关键词匹配 + 行号提取
                    lines = content.split('\n')
                    query_lower = query.lower()
                    for i, line in enumerate(lines):
                        if query_lower in line.lower():
                            results.append({
                                "path": os.path.relpath(fp, workspace_path),
                                "line": i + 1,
                                "snippet": line.strip()[:200],
                                "score": 1.0
                            })
                    if len(results) >= 50:
                        break
                if len(results) >= 50:
                    break
        return jsonify({"results": results[:50], "count": len(results[:50]), "query": query})
    except Exception as e:
        logger.error(f"/api/code/search 失败: {e}")
        return jsonify({"results": [], "error": str(e)})


@app.route("/api/voice/to-code", methods=["POST"])
def api_voice_to_code():
    """
    语音转代码：通过语音描述生成代码
    """
    data = request.json or {}
    description = data.get("description", "").strip()
    language = data.get("language", "python")
    context = data.get("context", "")

    if not description:
        return _error_response("description不能为空", 400)

    prompt = f"""你是一个代码生成专家。请根据以下中文描述，生成对应的{language}代码。

语言: {language}
描述: {description}
{context if context else ''}

请直接输出代码，不要添加解释。代码用```{language}```包裹。"""

    try:
        result = get_ai_response(prompt, max_tokens=2048, temperature=0.2)
        code_match = re.search(r"```[\w]*\n?([\s\S]*?)\n?```", result)
        code = (code_match.group(1) if code_match else result).strip()
        return jsonify({"code": code, "language": language, "description": description})
    except Exception as e:
        logger.error(f"/api/voice/to-code 失败: {e}")
        return jsonify({"code": "", "error": str(e)})


# =============================================================================
# 技能调用 API
# =============================================================================

@app.route("/api/skills", methods=["GET"])
def list_skills():
    """列出所有可用技能"""
    skills = []
    for name, func in SKILL_MAP.items():
        skills.append({
            "name": name,
            "description": (func.__doc__ or "").strip().split("\n")[0],
        })
    return jsonify({"skills": skills, "count": len(skills)})


@app.route("/api/skills/<skill_name>", methods=["POST"])
def call_skill(skill_name):
    """调用指定技能"""
    data = request.json or {}
    if skill_name not in SKILL_MAP:
        return jsonify({"error": f"技能 '{skill_name}' 不存在"}), 404

    try:
        result = run_skill(skill_name, **data)
        return jsonify({
            "skill": skill_name,
            "result": result,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.error(f"调用技能 {skill_name} 失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/skills/run", methods=["POST"])
def run_skill_by_name():
    """通过name参数调用技能"""
    data = request.json or {}
    skill_name = data.pop("name", "")
    if not skill_name or skill_name not in SKILL_MAP:
        return jsonify({"error": f"技能 '{skill_name}' 不存在"}), 404

    try:
        result = run_skill(skill_name, **data)
        return jsonify({
            "skill": skill_name,
            "result": result,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.error(f"调用技能 {skill_name} 失败: {e}")
        return jsonify({"error": str(e)}), 500


# =============================================================================
# 本地LLM管理 API
# =============================================================================

@app.route("/api/local_llm/status", methods=["GET"])
def local_llm_status_api():
    """本地LLM状态"""
    return jsonify(local_llm.get_status())


@app.route("/api/local_llm/models", methods=["GET"])
def local_llm_models():
    """推荐模型列表"""
    hw = detect_hardware()
    models = recommend_models(hw)
    return jsonify({
        "hardware": {
            "ram_gb": hw.total_ram_gb,
            "vram_gb": hw.vram_gb,
            "cpu_cores": hw.cpu_cores,
        },
        "recommended": models,
        "installed": local_llm.available_models,
    })


@app.route("/api/local_llm/setup", methods=["POST"])
def local_llm_setup():
    """自动配置本地LLM"""
    success, msg = local_llm.setup()
    return jsonify({"success": success, "message": msg})


# =============================================================================
# 超级Agent API
# =============================================================================

@app.route("/api/agent/task", methods=["POST"])
def agent_task():
    """执行复杂任务"""
    data = request.json or {}
    task = data.get("task", "").strip()
    if not task:
        return jsonify({"error": "task不能为空"}), 400

    try:
        result = super_agent.execute(task)
        return jsonify({"task": task, "result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/chat", methods=["POST"])
def agent_chat_api():
    """带工具调用的Agent对话"""
    data = request.json or {}
    message = data.get("message", "").strip()
    if not message:
        return jsonify({"error": "message不能为空"}), 400

    try:
        result = super_agent.chat_with_tools(message)
        return jsonify({"reply": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/agent/tools", methods=["GET"])
def list_agent_tools():
    """列出Agent可用工具"""
    from super_agent import get_tool_registry
    registry = get_tool_registry()
    return _ok_response({"tools": registry.list_tools()})


# =============================================================================
# 任务调度 API
# =============================================================================

@app.route("/api/tasks", methods=["POST"])
def create_task():
    """创建异步任务 {request: "...", max_retries: 2}"""
    data = request.json or {}
    task_request = data.get("request", "").strip()
    if not task_request:
        return _error_response("request 不能为空", 400)
    max_retries = data.get("max_retries", 2)
    task = task_scheduler.create_task(task_request, max_retries=max_retries)
    return _ok_response({"task_id": task.id, "status": task.status, "request": task.request})


@app.route("/api/tasks", methods=["GET"])
def list_tasks():
    """列出任务 {status: optional, limit: 50}"""
    status = request.args.get("status")
    limit = request.args.get("limit", 50, type=int)
    tasks = task_scheduler.list_tasks(status=status, limit=limit)
    return _ok_response({
        "tasks": [
            {
                "id": t.id,
                "request": t.request,
                "status": t.status,
                "result": t.result,
                "error": t.error,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
                "retry_count": t.retry_count,
            }
            for t in tasks
        ],
        "count": len(tasks),
    })


@app.route("/api/tasks/<task_id>", methods=["GET"])
def get_task(task_id):
    """获取任务详情"""
    task = task_scheduler.get_task(task_id)
    if not task:
        return _error_response("任务不存在", 404)
    return _ok_response({
        "id": task.id,
        "request": task.request,
        "status": task.status,
        "result": task.result,
        "error": task.error,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "retry_count": task.retry_count,
        "max_retries": task.max_retries,
    })


@app.route("/api/tasks/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    """取消任务"""
    if task_scheduler.cancel_task(task_id):
        return _ok_response({"message": "任务已取消"})
    return _error_response("任务不存在或无法取消", 400)


@app.route("/api/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id):
    """删除任务"""
    if task_scheduler.delete_task(task_id):
        return _ok_response({"message": "任务已删除"})
    return _error_response("任务不存在", 404)


# =============================================================================
# 记忆管理 API
# =============================================================================

@app.route("/api/memory", methods=["GET", "POST"])
def memory_api():
    """记忆查询/添加（基于当前memory.py的简化接口）"""
    if request.method == "GET":
        query = request.args.get("query", "")
        limit = request.args.get("n", 20, type=int)
        try:
            messages = memory_module.get_memory()
            if query:
                query_lower = query.lower()
                messages = [m for m in messages if query_lower in m.get("content", "").lower()]
            return jsonify({"query": query, "count": len(messages), "results": messages[-limit:]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif request.method == "POST":
        data = request.json or {}
        text = data.get("text", "").strip()
        key = data.get("key", "long_term")
        if not text:
            return jsonify({"error": "text不能为空"}), 400
        try:
            memory_module.set_profile(key, text)
            return jsonify({"success": True, "message": "已保存到用户画像/记忆"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500


@app.route("/api/memory/conversations", methods=["GET"])
def memory_conversations():
    """获取短期对话历史"""
    limit = request.args.get("limit", 20, type=int)
    try:
        messages = memory_module.get_memory()
        return jsonify({"count": len(messages), "conversations": messages[-limit:]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =============================================================================
# 语音交互 API
# =============================================================================

@app.route("/api/voice/listen", methods=["POST"])
def voice_listen():
    """
    监听语音并返回识别文本和AI回复
    {
        "duration": 5,
        "timeout": 10
    }
    """
    try:
        from speech import recognize_speech_from_mic
        text = recognize_speech_from_mic(
            duration=request.json.get("duration", 5),
            timeout=request.json.get("timeout", 10)
        )
        if not text:
            return jsonify({"text": "", "reply": "", "error": "没有识别到语音"})

        reply = get_ai_response(text)
        try:
            messages = memory_module.get_memory()
            messages.append({"role": "user", "content": text})
            messages.append({"role": "assistant", "content": reply})
            memory_module.save_memory(messages[-settings.max_history * 2:])
        except Exception as e:
            logger.warning(f"保存语音对话历史失败: {e}")

        return jsonify({
            "text": text,
            "reply": reply,
            "source": "api",
        })
    except Exception as e:
        logger.error(f"语音监听失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/voice/speak", methods=["POST"])
def voice_speak():
    """
    文本转语音并播放
    {
        "text": "你好",
        "voice": "zh-CN-YunxiNeural"
    }
    """
    data = request.json or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text不能为空"}), 400

    try:
        from speech import speak_text
        # 默认后台异步播放，不阻塞 HTTP 响应
        speak_text(text, voice=data.get("voice"), async_mode=data.get("async", True))
        return jsonify({"success": True, "text": text, "async": data.get("async", True)})
    except Exception as e:
        logger.error(f"语音播放失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/voice/engine/status", methods=["GET"])
def voice_engine_status_api():
    """获取语音引擎状态"""
    try:
        from voice_engine import voice_engine_status
        return jsonify({"ok": True, **voice_engine_status()})
    except Exception as e:
        logger.error(f"语音引擎状态获取失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/voice/engine/start", methods=["POST"])
def voice_engine_start_api():
    """启动语音引擎 {wake_words: ['hey_jarvis' (Porcupine内置关键词)], sensitivity: 0.5}"""
    data = request.json or {}
    try:
        from voice_engine import start_voice_engine
        start_voice_engine(
            wake_words=data.get("wake_words", ["jarvis"]),
            sensitivity=data.get("sensitivity", 0.5),
        )
        return jsonify({"ok": True, "message": "语音引擎已启动"})
    except Exception as e:
        logger.error(f"语音引擎启动失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/voice/engine/stop", methods=["POST"])
def voice_engine_stop_api():
    """停止语音引擎"""
    try:
        from voice_engine import stop_voice_engine
        stop_voice_engine()
        return jsonify({"ok": True, "message": "语音引擎已停止"})
    except Exception as e:
        logger.error(f"语音引擎停止失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/voice/conversation/start", methods=["POST"])
def voice_conversation_start():
    """启动实时语音对话循环"""
    try:
        from voice_conversation import get_voice_conversation
        conv = get_voice_conversation()
        started = conv.start()
        return _ok_response({"started": started, "state": conv.state})
    except Exception as e:
        logger.error(f"启动语音对话失败: {e}")
        return _error_response(str(e), 500)


@app.route("/api/voice/conversation/stop", methods=["POST"])
def voice_conversation_stop():
    """停止实时语音对话循环"""
    try:
        from voice_conversation import get_voice_conversation
        conv = get_voice_conversation()
        stopped = conv.stop()
        return _ok_response({"stopped": stopped, "state": conv.state})
    except Exception as e:
        logger.error(f"停止语音对话失败: {e}")
        return _error_response(str(e), 500)


@app.route("/api/voice/conversation/status", methods=["GET"])
def voice_conversation_status():
    """获取实时语音对话状态"""
    try:
        from voice_conversation import get_voice_conversation
        conv = get_voice_conversation()
        return _ok_response(conv.state)
    except Exception as e:
        logger.error(f"获取语音对话状态失败: {e}")
        return _error_response(str(e), 500)


# =============================================================================
# 系统控制 API
# =============================================================================

@app.route("/api/system/info", methods=["GET"])
def system_info():
    """获取系统信息"""
    try:
        result = run_skill("get_system_info")
        return jsonify({"info": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/system/execute", methods=["POST"])
def system_execute():
    """执行系统命令（危险，仅 OWNER 可用）"""
    denied = _require_owner()
    if denied:
        return denied

    data = request.json or {}
    command = data.get("command", "")
    if not command:
        return jsonify({"ok": False, "error": "command不能为空"}), 400

    command = sanitize_input(command, max_length=2000)
    if not is_command_safe(command):
        logger.warning(f"危险命令被拒绝: {command}")
        return jsonify({"ok": False, "error": "命令包含危险操作，已被拦截"}), 403

    try:
        result = run_skill("run_command", command=command)
        return jsonify({"ok": True, "command": command, "result": result})
    except Exception as e:
        logger.error(f"命令执行失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 文件操作 API
# =============================================================================

@app.route("/api/files/list", methods=["GET"])
def files_list():
    """列出目录"""
    path = request.args.get("path", ".")
    if not is_path_safe(path):
        return jsonify({"ok": False, "error": "非法路径或越界访问"}), 403
    try:
        result = run_skill("list_files", path=path)
        return jsonify({"ok": True, "path": path, "result": result})
    except Exception as e:
        logger.error(f"列出目录失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/files/read", methods=["GET"])
def files_read():
    """读取文件"""
    path = request.args.get("path", "")
    if not path:
        return jsonify({"ok": False, "error": "path不能为空"}), 400
    if not is_path_safe(path):
        return jsonify({"ok": False, "error": "非法路径或越界访问"}), 403
    try:
        result = run_skill("read_file", path=path)
        return jsonify({"ok": True, "path": path, "result": result})
    except Exception as e:
        logger.error(f"读取文件失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/files/write", methods=["POST"])
def files_write():
    """写入文件（仅 OWNER）"""
    denied = _require_owner()
    if denied:
        return denied

    data = request.json or {}
    path = data.get("path", "")
    if not path:
        return jsonify({"ok": False, "error": "path不能为空"}), 400
    if not is_path_safe(path):
        return jsonify({"ok": False, "error": "非法路径或越界访问"}), 403

    content = data.get("content", "")
    try:
        result = run_skill("write_file", path=path, content=content)
        return jsonify({"ok": True, "path": path, "result": result})
    except Exception as e:
        logger.error(f"写入文件失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# PC 自动化
# =============================================================================

@app.route("/api/pc/state", methods=["GET"])
def pc_state():
    """获取当前 PC 状态快照"""
    try:
        from pc_automation import get_current_pc_state
        return jsonify({"ok": True, "state": get_current_pc_state()})
    except Exception as e:
        logger.error(f"/api/pc/state 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pc/clipboard", methods=["GET"])
def pc_clipboard():
    """获取剪贴板历史"""
    try:
        from pc_automation import get_clipboard_history
        limit = request.args.get("limit", 10, type=int)
        return jsonify({"ok": True, "history": get_clipboard_history(limit)})
    except Exception as e:
        logger.error(f"/api/pc/clipboard 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pc/hotkeys", methods=["POST"])
def pc_hotkeys_register():
    """注册全局热键 {combo, action}"""
    data = request.json or {}
    combo = data.get("combo", "").strip()
    action = data.get("action", "")
    if not combo or not action:
        return jsonify({"ok": False, "error": "combo 和 action 不能为空"}), 400

    try:
        from pc_automation import register_hotkey
        from pc_control import control_pc

        def callback():
            logger.info(f"热键 {combo} 触发动作: {action}")
            control_pc(action)

        msg = register_hotkey(combo, callback)
        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        logger.error(f"/api/pc/hotkeys 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pc/hotkeys", methods=["DELETE"])
def pc_hotkeys_unregister():
    """注销全局热键 {combo}"""
    data = request.json or {}
    combo = data.get("combo", "").strip()
    if not combo:
        return jsonify({"ok": False, "error": "combo 不能为空"}), 400
    try:
        from pc_automation import unregister_hotkey
        msg = unregister_hotkey(combo)
        return jsonify({"ok": True, "message": msg})
    except Exception as e:
        logger.error(f"注销热键失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/pc/automation/status", methods=["GET"])
def pc_automation_status():
    """PC 自动化状态"""
    try:
        from pc_automation import automation_status
        return jsonify({"ok": True, **automation_status()})
    except Exception as e:
        logger.error(f"/api/pc/automation/status 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 浏览器自动化
# =============================================================================

@app.route("/api/browser/goto", methods=["POST"])
def browser_goto():
    """打开网页 {url}"""
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "url 不能为空"}), 400
    try:
        from browser_automation import goto
        return jsonify(goto(url))
    except Exception as e:
        logger.error(f"浏览器 goto 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/text", methods=["GET"])
def browser_text():
    """获取页面文本 ?max_chars=3000"""
    try:
        from browser_automation import get_page_text
        max_chars = request.args.get("max_chars", 3000, type=int)
        return jsonify({"ok": True, "text": get_page_text(max_chars)})
    except Exception as e:
        logger.error(f"浏览器 text 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/screenshot", methods=["POST"])
def browser_screenshot():
    """截图 {full_page: false}"""
    data = request.json or {}
    try:
        from browser_automation import screenshot
        result = screenshot(full_page=data.get("full_page", False))
        return jsonify(result)
    except Exception as e:
        logger.error(f"浏览器截图失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/click", methods=["POST"])
def browser_click():
    """点击元素 {text, selector}"""
    data = request.json or {}
    try:
        from browser_automation import click_text, click
        if data.get("text"):
            return jsonify(click_text(data["text"]))
        elif data.get("selector"):
            return jsonify(click(data["selector"]))
        return jsonify({"ok": False, "error": "需要 text 或 selector"}), 400
    except Exception as e:
        logger.error(f"浏览器点击失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/scroll", methods=["POST"])
def browser_scroll():
    """滚动 {direction, amount}"""
    data = request.json or {}
    try:
        from browser_automation import scroll
        return jsonify(scroll(
            direction=data.get("direction", "down"),
            amount=data.get("amount", 500),
        ))
    except Exception as e:
        logger.error(f"浏览器滚动失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/tabs", methods=["GET"])
def browser_tabs_list():
    """列出标签页"""
    try:
        from browser_automation import list_tabs
        return jsonify({"ok": True, "tabs": list_tabs()})
    except Exception as e:
        logger.error(f"浏览器标签失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/tabs/new", methods=["POST"])
def browser_tabs_new():
    """新建标签页 {url}"""
    data = request.json or {}
    try:
        from browser_automation import new_tab
        return jsonify(new_tab(data.get("url")))
    except Exception as e:
        logger.error(f"新建标签失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/tabs/switch", methods=["POST"])
def browser_tabs_switch():
    """切换标签页 {index}"""
    data = request.json or {}
    try:
        from browser_automation import switch_tab
        return jsonify(switch_tab(data.get("index", 0)))
    except Exception as e:
        logger.error(f"切换标签失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/close", methods=["POST"])
def browser_close():
    """关闭浏览器"""
    try:
        from browser_automation import close_browser
        close_browser()
        return jsonify({"ok": True, "message": "浏览器已关闭"})
    except Exception as e:
        logger.error(f"关闭浏览器失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/task", methods=["POST"])
def browser_task():
    """执行浏览器任务 {task}"""
    data = request.json or {}
    task = data.get("task", "").strip()
    if not task:
        return jsonify({"ok": False, "error": "task 不能为空"}), 400
    try:
        from browser_automation import run_browser_task
        result = run_browser_task(task)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.error(f"浏览器任务失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/browser/status", methods=["GET"])
def browser_status_api():
    """浏览器状态"""
    try:
        from browser_automation import browser_status
        return jsonify({"ok": True, **browser_status()})
    except Exception as e:
        logger.error(f"浏览器状态失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 知识库
# =============================================================================

@app.route("/api/knowledge/search", methods=["GET", "POST"])
def knowledge_search():
    """知识库检索 ?query=xxx&top_k=3&mode=hybrid 或 POST {query, top_k, mode, rerank, expand, aggregate}"""
    query = ""
    top_k = 3
    mode = "hybrid"
    rerank = True
    expand = True
    aggregate = True
    if request.method == "POST":
        data = request.json or {}
        query = data.get("query", "")
        top_k = data.get("top_k", 3)
        mode = data.get("mode", "hybrid")
        rerank = data.get("rerank", True)
        expand = data.get("expand", True)
        aggregate = data.get("aggregate", True)
    else:
        query = request.args.get("query", "")
        top_k = request.args.get("top_k", 3, type=int)
        mode = request.args.get("mode", "hybrid")
        rerank = request.args.get("rerank", "true").lower() == "true"
        expand = request.args.get("expand", "true").lower() == "true"
        aggregate = request.args.get("aggregate", "true").lower() == "true"

    if mode not in ("vector", "keyword", "hybrid"):
        return jsonify({"ok": False, "error": "mode 必须是 vector / keyword / hybrid 之一"}), 400

    if not query:
        return jsonify({"ok": False, "error": "query 不能为空"}), 400
    try:
        from knowledge_base import search_knowledge
        results = search_knowledge(
            query,
            top_k=top_k,
            mode=mode,
            rerank=rerank,
            expand=expand,
            aggregate=aggregate,
        )
        return jsonify({"ok": True, "query": query, "mode": mode, "results": results})
    except Exception as e:
        logger.error(f"知识库检索失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/knowledge/ingest", methods=["POST"])
def knowledge_ingest():
    """导入文档到知识库 {path: 文件路径或目录}"""
    data = request.json or {}
    path = data.get("path", "").strip()
    if not path:
        return jsonify({"ok": False, "error": "path 不能为空"}), 400
    try:
        from knowledge_enhancer import ingest_file, ingest_directory
        if os.path.isdir(path):
            result = ingest_directory(path)
        else:
            result = ingest_file(path)
        return jsonify(result)
    except Exception as e:
        logger.error(f"知识库导入失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/knowledge/webpage", methods=["POST"])
def knowledge_webpage():
    """抓取网页并加入知识库 {url}"""
    data = request.json or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "url 不能为空"}), 400
    try:
        from knowledge_enhancer import add_webpage_to_knowledge
        return jsonify(add_webpage_to_knowledge(url))
    except Exception as e:
        logger.error(f"网页入库失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/knowledge/sources", methods=["GET"])
def knowledge_sources():
    """列出知识库来源"""
    try:
        from knowledge_enhancer import list_knowledge_sources
        return jsonify({"ok": True, "sources": list_knowledge_sources()})
    except Exception as e:
        logger.error(f"列出知识库失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/knowledge/status", methods=["GET"])
def knowledge_status_api():
    """知识库状态"""
    try:
        from knowledge_enhancer import knowledge_status
        return jsonify(knowledge_status())
    except Exception as e:
        logger.error(f"知识库状态失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/knowledge/summarize", methods=["POST"])
def knowledge_summarize():
    """文本摘要 {text, max_sentences}"""
    data = request.json or {}
    text = data.get("text", "")
    max_sentences = data.get("max_sentences", 5)
    if not text:
        return jsonify({"ok": False, "error": "text 不能为空"}), 400
    try:
        from knowledge_enhancer import summarize_text
        summary = summarize_text(text, max_sentences)
        return jsonify({"ok": True, "summary": summary, "original_length": len(text), "summary_length": len(summary)})
    except Exception as e:
        logger.error(f"摘要失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/knowledge/source", methods=["DELETE"])
def knowledge_delete_source():
    """删除知识库来源 {source}"""
    data = request.json or {}
    source = data.get("source", "")
    if not source:
        return jsonify({"ok": False, "error": "source 不能为空"}), 400
    try:
        from knowledge_enhancer import delete_knowledge_source
        return jsonify(delete_knowledge_source(source))
    except Exception as e:
        logger.error(f"删除知识库失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 移动端设备管理
# =============================================================================

@app.route("/api/mobile/devices", methods=["GET"])
def mobile_list_devices():
    """列出所有注册的移动设备"""
    try:
        from mobile_integration import list_devices
        platform = request.args.get("platform")
        return jsonify({"devices": list_devices(platform)})
    except Exception as e:
        logger.error(f"获取设备列表失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/register", methods=["POST"])
def mobile_register_device():
    """注册移动设备"""
    data = request.json or {}
    device_id = data.get("device_id") or str(uuid.uuid4())[:12]
    device_info = {k: v for k, v in data.items() if k != "device_id"}
    try:
        from mobile_integration import register_device
        device = register_device(device_id, device_info)
        return jsonify({"ok": True, "device": device})
    except Exception as e:
        logger.error(f"设备注册失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mobile/heartbeat", methods=["POST"])
def mobile_heartbeat():
    """设备心跳保活"""
    data = request.json or {}
    device_id = data.get("device_id", "")
    if not device_id:
        return jsonify({"ok": False, "error": "device_id 不能为空"}), 400
    try:
        from mobile_integration import device_heartbeat
        extra = {k: v for k, v in data.items() if k != "device_id"}
        device = device_heartbeat(device_id, extra)
        if device:
            return jsonify({"ok": True, "device": device})
        return jsonify({"ok": False, "error": "设备未注册"}), 404
    except Exception as e:
        logger.error(f"心跳失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mobile/devices/<device_id>", methods=["DELETE"])
def mobile_unregister_device(device_id):
    """注销设备"""
    try:
        from mobile_integration import unregister_device
        ok = unregister_device(device_id)
        return jsonify({"ok": ok})
    except Exception as e:
        logger.error(f"注销设备失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 推送通知
# =============================================================================

@app.route("/api/mobile/push", methods=["POST"])
def mobile_push_notification():
    """推送通知到手机（多通道）"""
    data = request.json or {}
    title = data.get("title", "Y·NEX通知")
    body = data.get("body", "")
    if not body:
        return jsonify({"ok": False, "error": "body 不能为空"}), 400
    try:
        from mobile_integration import push_notification
        results = push_notification(
            title, body,
            sound=data.get("sound"),
            icon=data.get("icon"),
            group=data.get("group"),
            url=data.get("url"),
            template=data.get("template", "txt")
        )
        return jsonify({"ok": True, "results": results})
    except Exception as e:
        logger.error(f"推送失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 手机远程控制 PC
# =============================================================================

@app.route("/api/mobile/pc/action", methods=["POST"])
def mobile_pc_action():
    """
    手机远程控制 PC
    action: lock / shutdown / restart / sleep / screenshot /
            volume_up / volume_down / volume_mute / open_app / type_text
    """
    data = request.json or {}
    action = data.get("action", "")
    params = data.get("params", {})
    if not action:
        return jsonify({"ok": False, "error": "action 不能为空"}), 400
    try:
        from mobile_integration import remote_pc_action
        result = remote_pc_action(action, params)
        return jsonify(result)
    except Exception as e:
        logger.error(f"远程控制失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 位置服务与地理围栏
# =============================================================================

@app.route("/api/mobile/location", methods=["POST"])
def mobile_update_location():
    """更新设备位置"""
    data = request.json or {}
    device_id = data.get("device_id", "")
    lat = data.get("lat")
    lon = data.get("lon")
    accuracy = data.get("accuracy")
    if not device_id or lat is None or lon is None:
        return jsonify({"ok": False, "error": "缺少必要参数"}), 400
    try:
        from mobile_integration import update_device_location, check_geofences
        device = update_device_location(device_id, float(lat), float(lon), accuracy)
        events = check_geofences(device_id, float(lat), float(lon))
        return jsonify({"ok": True, "device": device, "events": events})
    except Exception as e:
        logger.error(f"位置更新失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mobile/geofences", methods=["GET", "POST"])
def mobile_geofences():
    """地理围栏管理"""
    if request.method == "GET":
        try:
            from mobile_integration import _geofences
            return jsonify({"geofences": [
                {k: v for k, v in f.items() if k != "inside"}
                for f in _geofences
            ]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500
    else:
        data = request.json or {}
        name = data.get("name", "")
        lat = data.get("lat")
        lon = data.get("lon")
        radius = data.get("radius", 100)
        if not name or lat is None or lon is None:
            return jsonify({"ok": False, "error": "缺少必要参数"}), 400
        try:
            from mobile_integration import add_geofence
            fence = add_geofence(
                name, float(lat), float(lon), float(radius),
                enter_action=data.get("enter_action"),
                exit_action=data.get("exit_action")
            )
            return jsonify({"ok": True, "fence": {k: v for k, v in fence.items() if k != "inside"}})
        except Exception as e:
            logger.error(f"添加围栏失败: {e}")
            return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 通知转发
# =============================================================================

@app.route("/api/mobile/notifications", methods=["GET"])
def mobile_notification_history():
    """获取通知历史"""
    limit = int(request.args.get("limit", 20))
    try:
        from mobile_integration import get_notification_history
        return jsonify({"notifications": get_notification_history(limit)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/notify", methods=["POST"])
def mobile_forward_notification():
    """转发 PC 通知到手机"""
    data = request.json or {}
    title = data.get("title", "通知")
    body = data.get("body", "")
    priority = data.get("priority", "normal")
    if not body:
        return jsonify({"ok": False, "error": "body 不能为空"}), 400
    try:
        from mobile_integration import forward_notification
        notif = forward_notification(title, body, priority)
        return jsonify({"ok": True, "notification": notif})
    except Exception as e:
        logger.error(f"通知转发失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 文件传输
# =============================================================================

@app.route("/api/mobile/files", methods=["GET"])
def mobile_list_transfer_files():
    """列出传输目录文件"""
    try:
        from mobile_integration import list_transfer_files
        return jsonify({"files": list_transfer_files()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/mobile/upload", methods=["POST"])
def mobile_upload_file():
    """手机上传文件到 PC"""
    try:
        from mobile_integration import upload_file
        if "file" in request.files:
            f = request.files["file"]
            result = upload_file(f.filename, f.read(), request.form.get("device_id"))
            return jsonify(result)
        else:
            data = request.json or {}
            filename = data.get("filename", "upload.bin")
            content = data.get("content", "")
            encoding = data.get("encoding", "base64")
            if encoding == "base64":
                file_data = base64.b64decode(content)
            else:
                file_data = content.encode("utf-8")
            result = upload_file(filename, file_data, data.get("device_id"))
            return jsonify(result)
    except Exception as e:
        logger.error(f"文件上传失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/mobile/download/<filename>")
def mobile_download_file(filename):
    """从 PC 下载文件到手机"""
    try:
        from mobile_integration import get_transfer_file
        data = get_transfer_file(filename)
        if data is None:
            return jsonify({"ok": False, "error": "文件不存在"}), 404
        from flask import send_file
        import io
        return send_file(
            io.BytesIO(data),
            download_name=filename,
            as_attachment=True
        )
    except Exception as e:
        logger.error(f"文件下载失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 插件系统
# =============================================================================

@app.route("/api/plugins", methods=["GET"])
def plugins_list():
    """列出所有已安装插件"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        return jsonify({"plugins": mgr.list_plugins()})
    except Exception as e:
        logger.error(f"获取插件列表失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/plugins/skills", methods=["GET"])
def plugins_skills():
    """列出所有插件注册的技能"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        return jsonify({"skills": mgr.list_skills()})
    except Exception as e:
        logger.error(f"获取技能列表失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/plugins/<plugin_id>/enable", methods=["POST"])
def plugins_enable(plugin_id):
    """启用插件"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        ok = mgr.enable_plugin(plugin_id)
        return jsonify({"ok": ok})
    except Exception as e:
        logger.error(f"启用插件失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/plugins/<plugin_id>/disable", methods=["POST"])
def plugins_disable(plugin_id):
    """禁用插件"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        ok = mgr.disable_plugin(plugin_id)
        return jsonify({"ok": ok})
    except Exception as e:
        logger.error(f"禁用插件失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/plugins/<plugin_id>/reload", methods=["POST"])
def plugins_reload(plugin_id):
    """热重载插件"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        ok = mgr.reload_plugin(plugin_id)
        return jsonify({"ok": ok})
    except Exception as e:
        logger.error(f"重载插件失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/plugins/<plugin_id>", methods=["DELETE"])
def plugins_uninstall(plugin_id):
    """卸载插件"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        ok = mgr.uninstall_plugin(plugin_id)
        return jsonify({"ok": ok})
    except Exception as e:
        logger.error(f"卸载插件失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/plugins/install", methods=["POST"])
def plugins_install():
    """从 URL 安装插件（仅 OWNER）"""
    denied = _require_owner()
    if denied:
        return denied

    data = request.json or {}
    url = data.get("url", "")
    if not url:
        return jsonify({"ok": False, "error": "url 不能为空"}), 400

    from security import is_plugin_url_safe
    if not is_plugin_url_safe(url):
        return jsonify({"ok": False, "error": "插件 URL 不安全，仅允许 http/https 且不能是本地地址"}), 403

    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        result = mgr.install_plugin_from_url(url)
        return jsonify(result)
    except Exception as e:
        logger.error(f"安装插件失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/plugins/<plugin_id>/config", methods=["GET", "POST"])
def plugins_config(plugin_id):
    """插件配置管理"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()

        if request.method == "GET":
            key = request.args.get("key")
            config = mgr.get_plugin_config(plugin_id, key)
            return jsonify({"ok": True, "config": config})
        else:
            data = request.json or {}
            if "key" in data and "value" in data:
                mgr.set_plugin_config(plugin_id, data["key"], data["value"])
            elif isinstance(data.get("config"), dict):
                mgr.config_store.update(plugin_id, data["config"])
            return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"插件配置操作失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/plugins/call/<skill_name>", methods=["POST"])
def plugins_call_skill(skill_name):
    """调用插件技能"""
    try:
        from plugin_system import get_plugin_manager
        mgr = get_plugin_manager()
        data = request.json or {}
        result = mgr.call_skill(skill_name, **data)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.error(f"调用插件技能失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 运维接口
# =============================================================================

@app.route("/api/ops/startup-report", methods=["GET"])
def ops_startup_report():
    """获取启动配置校验报告"""
    try:
        report = generate_startup_report()
        return jsonify({
            "ok": report.ok,
            "errors": report.errors,
            "warnings": report.warnings,
            "info": report.info,
        })
    except Exception as e:
        logger.error(f"生成启动报告失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ops/backup", methods=["POST"])
def ops_backup_now():
    """立即执行数据备份（仅 OWNER）"""
    owner_err = _require_owner()
    if owner_err:
        return owner_err
    try:
        record = _backup_manager.backup()
        return jsonify({
            "ok": True,
            "backup_id": record.id,
            "path": record.path,
            "size_bytes": record.size_bytes,
            "created_at": record.created_at,
        })
    except Exception as e:
        logger.error(f"手动备份失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ops/backups", methods=["GET"])
def ops_list_backups():
    """列出所有备份（仅 OWNER）"""
    owner_err = _require_owner()
    if owner_err:
        return owner_err
    try:
        records = _backup_manager.list_backups()
        return jsonify({
            "ok": True,
            "backups": [
                {
                    "id": r.id,
                    "created_at": r.created_at,
                    "path": r.path,
                    "size_bytes": r.size_bytes,
                }
                for r in records
            ],
        })
    except Exception as e:
        logger.error(f"列出备份失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ops/backups/<backup_id>/restore", methods=["POST"])
def ops_restore_backup(backup_id):
    """恢复指定备份到 restored/ 目录（仅 OWNER，不覆盖原数据）"""
    owner_err = _require_owner()
    if owner_err:
        return owner_err
    try:
        result = _backup_manager.restore(backup_id)
        if result["ok"]:
            return jsonify(result)
        return jsonify(result), 404
    except Exception as e:
        logger.error(f"恢复备份失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/ops/backups/<backup_id>", methods=["DELETE"])
def ops_delete_backup(backup_id):
    """删除指定备份（仅 OWNER）"""
    owner_err = _require_owner()
    if owner_err:
        return owner_err
    try:
        from pathlib import Path
        zip_path = Path(_backup_manager.backup_dir) / f"ynex_backup_{backup_id}.zip"
        if not zip_path.exists():
            return jsonify({"ok": False, "error": "备份不存在"}), 404
        zip_path.unlink()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"删除备份失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 性能监控
# =============================================================================

@app.route("/api/performance/stats", methods=["GET"])
def performance_stats():
    """获取性能监控统计"""
    try:
        from performance import get_monitor
        monitor = get_monitor()
        return jsonify(monitor.get_stats())
    except Exception as e:
        logger.error(f"获取性能统计失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/performance/stats", methods=["DELETE"])
def performance_reset_stats():
    """重置性能统计"""
    try:
        from performance import get_monitor
        monitor = get_monitor()
        monitor.reset()
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"重置性能统计失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/performance/gc", methods=["POST"])
def performance_gc():
    """手动触发 GC 内存回收"""
    try:
        from performance import get_memory_optimizer
        optimizer = get_memory_optimizer()
        count = optimizer.cleanup()
        return jsonify({"ok": True, "collected": count})
    except Exception as e:
        logger.error(f"GC 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 多模态 / 视觉
# =============================================================================

@app.route("/api/vision/models", methods=["GET"])
def vision_models():
    """列出可用的多模态模型"""
    try:
        from multimodal import list_vision_models, is_vision_available, is_ocr_available
        return jsonify({
            "ok": True,
            "vision_available": is_vision_available(),
            "ocr_available": is_ocr_available(),
            "models": list_vision_models(),
        })
    except Exception as e:
        logger.error(f"获取视觉模型失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/vision/analyze", methods=["POST"])
def vision_analyze():
    """分析图片内容"""
    try:
        from multimodal import analyze_image
        data = request.json or {}
        image_path = data.get("image_path", "")
        prompt = data.get("prompt", "请详细描述这张图片的内容")
        model = data.get("model")
        
        if not image_path:
            # 检查是否上传了文件
            if 'image' in request.files:
                f = request.files['image']
                import os
                os.makedirs("data/uploads", exist_ok=True)
                safe_name = os.path.basename(f.filename)  # 防路径遍历
                save_path = os.path.join("data/uploads", f"upload_{int(time.time())}_{safe_name}")
                f.save(save_path)
                image_path = save_path
            else:
                return jsonify({"ok": False, "error": "缺少 image_path 或 image 文件"}), 400

        result = analyze_image(image_path, prompt, model)
        return jsonify({
            "ok": True,
            "description": result.description,
            "model_used": result.model_used,
            "confidence": result.confidence,
            "image_path": image_path,
        })
    except Exception as e:
        logger.error(f"图片分析失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/vision/ocr", methods=["POST"])
def vision_ocr():
    """OCR 文字识别"""
    try:
        from multimodal import ocr_image
        data = request.json or {}
        image_path = data.get("image_path", "")
        
        if not image_path:
            if 'image' in request.files:
                f = request.files['image']
                import os
                os.makedirs("data/uploads", exist_ok=True)
                safe_name = os.path.basename(f.filename)  # 防路径遍历
                save_path = os.path.join("data/uploads", f"ocr_{int(time.time())}_{safe_name}")
                f.save(save_path)
                image_path = save_path
            else:
                return jsonify({"ok": False, "error": "缺少 image_path 或 image 文件"}), 400

        result = ocr_image(image_path)
        return jsonify(result)
    except Exception as e:
        logger.error(f"OCR 失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/vision/screenshot", methods=["POST"])
def vision_screenshot():
    """截屏并分析"""
    try:
        from multimodal import analyze_screen
        data = request.json or {}
        prompt = data.get("prompt", "描述一下当前屏幕显示的内容")
        result = analyze_screen(prompt)
        return jsonify(result)
    except Exception as e:
        logger.error(f"截图分析失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/vision/camera", methods=["POST"])
def vision_camera():
    """摄像头拍照并分析"""
    try:
        from multimodal import analyze_camera
        data = request.json or {}
        prompt = data.get("prompt", "描述一下摄像头拍到的内容")
        camera_index = data.get("camera_index", 0)
        result = analyze_camera(prompt, camera_index)
        return jsonify(result)
    except Exception as e:
        logger.error(f"摄像头分析失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/vision/generate-image", methods=["POST"])
def vision_generate_image():
    """文本生成图片 {prompt, width, height, seed, style}"""
    try:
        from multimodal import generate_image
        data = request.json or {}
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"ok": False, "error": "prompt 不能为空"}), 400

        width = data.get("width", 1024)
        height = data.get("height", 1024)
        seed = data.get("seed")
        style = data.get("style", "")

        # 限制尺寸，避免滥用
        width = max(256, min(2048, int(width)))
        height = max(256, min(2048, int(height)))

        result = generate_image(prompt, width=width, height=height, seed=seed, style=style)
        return jsonify(result)
    except Exception as e:
        logger.error(f"图片生成失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 缓存管理 API
# =============================================================================

@app.route("/api/cache/stats", methods=["GET"])
def cache_stats_endpoint():
    """获取缓存命中统计"""
    try:
        from cache import cache_stats
        return jsonify({"ok": True, "stats": cache_stats()})
    except Exception as e:
        logger.error(f"获取缓存统计失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/cache/clear", methods=["POST"])
def cache_clear_endpoint():
    """清空缓存（OWNER 权限）"""
    denied = _require_owner()
    if denied:
        return denied
    try:
        from cache import cache_clear
        cache_clear()
        return jsonify({"ok": True, "message": "缓存已清空"})
    except Exception as e:
        logger.error(f"清空缓存失败: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# =============================================================================
# 健康检查与监控指标
# =============================================================================

@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health_check():
    """健康检查：服务、Ollama、本地LLM、数据库状态"""
    checks = {
        "service": "ok",
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": round(time.time() - _service_start_time, 2),
    }

    # Ollama 状态
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=2)
        checks["ollama"] = "ok" if resp.status_code == 200 else "error"
    except Exception:
        checks["ollama"] = "offline"

    # 本地 LLM 状态
    # 注意：local_llm.is_available 是 @property（属性），不能用方法调用
    try:
        from local_llm import get_local_llm
        llm = get_local_llm()
        checks["local_llm"] = {
            "available": llm.is_available,
            "current_model": getattr(llm, "current_model", ""),
            "cache_stats": llm.get_cache_stats() if hasattr(llm, 'get_cache_stats') else {},
        }
    except Exception as e:
        checks["local_llm"] = {"available": False, "error": str(e)}

    # 数据库/任务调度状态
    # 注意：TaskScheduler 是无状态单例（永远可用），没有 is_running 方法
    try:
        scheduler = get_scheduler()
        # 检查是否有正在执行的任务作为"运行中"标志
        running_tasks = scheduler.list_tasks(status="running") if hasattr(scheduler, "list_tasks") else []
        checks["scheduler"] = "ok"
        checks["scheduler_running_tasks"] = len(running_tasks) if isinstance(running_tasks, list) else 0
    except Exception as e:
        checks["scheduler"] = f"error: {e}"

    # 健康判断：service 字段为 "ok" 即视为服务可用（200）。
    # 子系统（ollama/local_llm）不可用属于"降级"而非"宕机"，通过 ok 字段体现。
    service_ok = checks.get("service") == "ok"
    subsystems_ok = all(
        v == "ok" or (isinstance(v, dict) and v.get("available") is True)
        for v in checks.values() if isinstance(v, (str, dict)) and v is not checks.get("service")
    )
    all_ok = service_ok and subsystems_ok
    status_code = 200 if service_ok else 503
    return jsonify({"ok": all_ok, "degraded": service_ok and not subsystems_ok, **checks}), status_code


@app.route("/metrics", methods=["GET"])
@app.route("/api/metrics", methods=["GET"])
def metrics_endpoint():
    """Prometheus 风格的监控指标"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        sys_stats = {
            "cpu_percent": cpu,
            "memory_percent": mem.percent,
            "memory_used_mb": mem.used // 1024 // 1024,
            "memory_total_mb": mem.total // 1024 // 1024,
            "disk_percent": disk.percent,
        }
    except Exception as e:
        sys_stats = {"error": str(e)}

    with _request_lock:
        req_stats = {
            "total_requests": _request_count,
            "error_count": _error_count,
            "error_rate": round(_error_count / max(_request_count, 1), 4),
        }

    try:
        from cache import cache_stats
        cache = cache_stats()
    except Exception as e:
        cache = {"error": str(e)}

    output = [
        "# Y·NEX 本地AI核心服务指标",
        f"ynex_requests_total {req_stats['total_requests']}",
        f"ynex_errors_total {req_stats['error_count']}",
        f"ynex_uptime_seconds {round(time.time() - _service_start_time, 2)}",
    ]

    for k, v in sys_stats.items():
        if isinstance(v, (int, float)):
            output.append(f"ynex_system_{k} {v}")

    for k, v in cache.get("memory", {}).items():
        if isinstance(v, (int, float)):
            output.append(f"ynex_cache_memory_{k} {v}")

    return Response("\n".join(output), mimetype="text/plain")


# =============================================================================
# API文档页面
# =============================================================================

DOCS_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Y·NEX 本地AI核心服务 API文档</title>
<style>
body{font-family:sans-serif;background:#0a0a1a;color:#e0e0ff;padding:40px;max-width:1200px;margin:0 auto}
h1{color:#00ffff}h2{color:#00aacc;margin-top:30px;border-bottom:1px solid #00ffff33;padding-bottom:10px}
.endpoint{margin:20px 0;padding:20px;background:#0d1525;border:1px solid #00ffff22;border-radius:10px}
.method{display:inline-block;padding:4px 12px;border-radius:4px;font-weight:bold;font-size:12px;margin-right:10px}
.get{background:#00ff8833;color:#00ff88}
.post{background:#0088ff33;color:#0088ff}
.delete{background:#ff444433;color:#ff4444}
.url{font-family:monospace;color:#00ffff;font-size:14px}
.desc{color:#88aacc;margin-top:8px;font-size:14px}
pre{background:#000;padding:12px;border-radius:6px;overflow-x:auto;color:#d0e0ff;font-size:12px}
</style>
</head>
<body>
<h1>Y·NEX 本地AI核心服务 API文档 v1.0</h1>
<p style="color:#6688aa">所有API都以 <code>/api</code> 开头，支持跨域调用（CORS）。</p>

<h2>健康检查</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/</span><span class="url">/api/health</span><div class="desc">服务状态与硬件信息</div></div>

<h2>文本对话</h2>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/chat</span><div class="desc">普通对话</div><pre>{"message":"你好","use_local":false,"use_mock":false}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/chat/stream</span><div class="desc">流式对话（SSE）</div><pre>{"message":"你好"}</pre></div>

<h2>技能调用</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/skills</span><div class="desc">列出所有技能</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/skills/{skill_name}</span><div class="desc">调用指定技能</div><pre>{"city":"北京"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/skills/run</span><div class="desc">按名称调用技能</div><pre>{"name":"get_weather","city":"北京"}</pre></div>

<h2>本地LLM</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/local_llm/status</span><div class="desc">本地LLM状态</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/local_llm/models</span><div class="desc">推荐模型列表</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/local_llm/setup</span><div class="desc">自动配置本地LLM</div></div>

<h2>超级Agent</h2>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/agent/task</span><div class="desc">执行复杂任务</div><pre>{"task":"帮我写一个Python爬虫"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/agent/chat</span><div class="desc">带工具调用的对话</div><pre>{"message":"北京天气怎么样"}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/agent/tools</span><div class="desc">列出Agent工具</div></div>

<h2>记忆管理</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/memory?query=关键词&n=5</span><div class="desc">搜索长期记忆</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/memory</span><div class="desc">添加长期记忆</div><pre>{"text":"今天学习的内容..."}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/memory/conversations?user_id=api_user&limit=20</span><div class="desc">短期对话历史</div></div>

<h2>语音交互</h2>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/voice/listen</span><div class="desc">语音输入识别</div><pre>{"duration":5,"timeout":10}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/voice/speak</span><div class="desc">语音播报</div><pre>{"text":"你好"}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/voice/engine/status</span><div class="desc">语音引擎状态</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/voice/engine/start</span><div class="desc">启动语音引擎</div><pre>{"wake_words":["jarvis"],"sensitivity":0.5}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/voice/engine/stop</span><div class="desc">停止语音引擎</div></div>

<h2>系统控制</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/system/info</span><div class="desc">系统信息</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/system/execute</span><div class="desc">执行系统命令（谨慎）</div><pre>{"command":"dir"}</pre></div>

<h2>PC 自动化</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/pc/state</span><div class="desc">当前 PC 状态快照</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/pc/clipboard?limit=10</span><div class="desc">剪贴板历史</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/pc/hotkeys</span><div class="desc">注册全局热键</div><pre>{"combo":"&lt;ctrl&gt;+&lt;shift&gt;+m","action":"mute"}</pre></div>
<div class="endpoint"><span class="method delete">DELETE</span><span class="url">/api/pc/hotkeys</span><div class="desc">注销全局热键</div><pre>{"combo":"&lt;ctrl&gt;+&lt;shift&gt;+m"}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/pc/automation/status</span><div class="desc">自动化状态</div></div>

<h2>浏览器自动化</h2>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/goto</span><div class="desc">打开网页</div><pre>{"url":"https://example.com"}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/browser/text</span><div class="desc">页面文本</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/screenshot</span><div class="desc">截图</div><pre>{"full_page":false}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/click</span><div class="desc">点击元素</div><pre>{"text":"登录"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/scroll</span><div class="desc">滚动</div><pre>{"direction":"down","amount":500}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/browser/tabs</span><div class="desc">标签页列表</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/tabs/new</span><div class="desc">新建标签页</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/tabs/switch</span><div class="desc">切换标签</div><pre>{"index":0}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/task</span><div class="desc">执行自然语言任务</div><pre>{"task":"搜索天气并截图"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/browser/close</span><div class="desc">关闭浏览器</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/browser/status</span><div class="desc">浏览器状态</div></div>

<h2>知识库 RAG</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/knowledge/search?query=xxx&amp;top_k=3&amp;mode=hybrid</span><div class="desc">检索知识库（mode=vector/keyword/hybrid）</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/knowledge/ingest</span><div class="desc">导入文档（PDF/Word/PPT/EPUB/TXT/MD）</div><pre>{"path":"文档路径或目录"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/knowledge/webpage</span><div class="desc">抓取网页入库</div><pre>{"url":"https://example.com"}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/knowledge/sources</span><div class="desc">列出知识库来源</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/knowledge/status</span><div class="desc">知识库状态</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/knowledge/summarize</span><div class="desc">文本摘要（抽取式）</div><pre>{"text":"长文本...","max_sentences":5}</pre></div>
<div class="endpoint"><span class="method delete">DELETE</span><span class="url">/api/knowledge/source</span><div class="desc">删除知识库来源</div><pre>{"source":"url或路径"}</pre></div>

<h2>移动端集成</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/mobile/devices</span><div class="desc">列出所有注册设备</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/register</span><div class="desc">注册/更新设备</div><pre>{"device_id":"phone_001","platform":"android","name":"我的手机"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/heartbeat</span><div class="desc">设备心跳保活</div><pre>{"device_id":"phone_001","battery":85}</pre></div>
<div class="endpoint"><span class="method delete">DELETE</span><span class="url">/api/mobile/devices/{id}</span><div class="desc">注销设备</div></div>

<h2>推送通知</h2>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/push</span><div class="desc">多通道推送（Bark/Server酱/PushPlus/企微/钉钉）</div><pre>{"title":"标题","body":"内容","sound":"alarm"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/notify</span><div class="desc">转发PC通知到手机</div><pre>{"title":"通知","body":"内容","priority":"normal"}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/mobile/notifications?limit=20</span><div class="desc">通知历史记录</div></div>

<h2>手机远程控制</h2>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/pc/action</span><div class="desc">远程控制PC（锁屏/关机/截图/音量等）</div><pre>{"action":"lock","params":{}}</pre></div>

<h2>位置服务</h2>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/location</span><div class="desc">上报设备位置</div><pre>{"device_id":"phone_001","lat":39.9,"lon":116.4,"accuracy":10}</pre></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/mobile/geofences</span><div class="desc">地理围栏列表</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/geofences</span><div class="desc">添加地理围栏</div><pre>{"name":"家","lat":39.9,"lon":116.4,"radius":100}</pre></div>

<h2>文件传输</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/mobile/files</span><div class="desc">传输目录文件列表</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/mobile/upload</span><div class="desc">手机上传文件到PC（支持FormData或base64）</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/mobile/download/{filename}</span><div class="desc">从PC下载文件到手机</div></div>

<h2>插件系统</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/plugins</span><div class="desc">列出所有已安装插件</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/plugins/skills</span><div class="desc">列出所有插件注册的技能</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/plugins/install</span><div class="desc">从URL安装插件</div><pre>{"url":"https://.../plugin.zip"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/plugins/{id}/enable</span><div class="desc">启用插件</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/plugins/{id}/disable</span><div class="desc">禁用插件</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/plugins/{id}/reload</span><div class="desc">热重载插件</div></div>
<div class="endpoint"><span class="method delete">DELETE</span><span class="url">/api/plugins/{id}</span><div class="desc">卸载插件</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/plugins/{id}/config</span><div class="desc">获取插件配置</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/plugins/{id}/config</span><div class="desc">设置插件配置</div><pre>{"key":"xxx","value":"yyy"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/plugins/call/{skill_name}</span><div class="desc">调用插件技能</div><pre>{"param1":"value1"}</pre></div>

<h2>性能监控</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/performance/stats</span><div class="desc">获取API性能统计（QPS/响应时间/错误率）</div></div>
<div class="endpoint"><span class="method delete">DELETE</span><span class="url">/api/performance/stats</span><div class="desc">重置性能统计</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/performance/gc</span><div class="desc">手动触发GC内存回收</div></div>

<h2>多模态/视觉</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/vision/models</span><div class="desc">列出可用的多模态模型和OCR状态</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/vision/analyze</span><div class="desc">分析图片内容（支持多模态模型）</div><pre>{"image_path":"xxx.jpg","prompt":"描述这张图片"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/vision/ocr</span><div class="desc">OCR文字识别</div><pre>{"image_path":"xxx.jpg"}</pre></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/vision/screenshot</span><div class="desc">截屏并分析（图片理解+OCR）</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/vision/camera</span><div class="desc">摄像头拍照并分析</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/vision/generate-image</span><div class="desc">文本生成图片（Pollinations.ai 免费接口）</div><pre>{"prompt":"a cat in space","width":1024,"height":1024,"style":"anime"}</pre></div>

<h2>缓存管理</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/cache/stats</span><div class="desc">获取缓存命中统计</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/cache/clear</span><div class="desc">清空缓存（OWNER）</div></div>

<h2>限流保护</h2>
<p>默认每个 IP / API Key 每分钟 {settings.rate_limit_requests_per_minute} 次请求，突发缓冲 {settings.rate_limit_burst} 次。响应头包含 X-RateLimit-*。</p>

<h2>运维接口（OWNER）</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/ops/startup-report</span><div class="desc">启动配置校验报告</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/ops/backup</span><div class="desc">立即执行数据备份</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/ops/backups</span><div class="desc">列出所有备份</div></div>
<div class="endpoint"><span class="method delete">DELETE</span><span class="url">/api/ops/backups/{id}</span><div class="desc">删除指定备份</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/ops/backups/{id}/restore</span><div class="desc">恢复备份到 restored/ 目录（不覆盖原数据）</div></div>

<h2>健康监控</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/health</span><div class="desc">健康检查（服务/Ollama/本地LLM/调度器）</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/metrics</span><div class="desc">Prometheus 风格监控指标</div></div>

<h2>前端页面</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/mobile</span><div class="desc">移动端 PWA 遥控页面</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/demo</span><div class="desc">桌面端演示客户端</div></div>

<h2>文件操作</h2>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/files/list?path=.</span><div class="desc">列出目录</div></div>
<div class="endpoint"><span class="method get">GET</span><span class="url">/api/files/read?path=文件路径</span><div class="desc">读取文件</div></div>
<div class="endpoint"><span class="method post">POST</span><span class="url">/api/files/write</span><div class="desc">写入文件</div><pre>{"path":"test.txt","content":"hello"}</pre></div>

</body>
</html>
"""


@app.route("/docs")
def docs():
    return render_template_string(DOCS_HTML)


# =============================================================================
# 启动
# =============================================================================

@app.route("/mobile")
def mobile_page():
    """移动端 PWA 遥控页面"""
    return send_from_directory(".", "mobile.html")


@app.route("/mobile-manifest.json")
def mobile_manifest():
    return send_from_directory(".", "mobile-manifest.json", mimetype="application/manifest+json")


@app.route("/mobile-sw.js")
def mobile_service_worker():
    return send_from_directory(".", "mobile-sw.js", mimetype="application/javascript")


@app.route("/icon.svg")
def app_icon():
    return send_from_directory(".", "icon.svg", mimetype="image/svg+xml")


@app.route("/demo")
def demo_page():
    """桌面端演示客户端"""
    return send_from_directory(".", "ynex-demo.html")


def run_server(port: int = 7777, host: str = None, use_waitress: bool = True):
    # 默认监听地址：优先用参数，其次配置文件 api_bind_host，最后 127.0.0.1（安全默认）。
    # 如需局域网/公网访问，请通过 --host 0.0.0.0 或 .env 显式开启，并配合防火墙与 Nginx。
    if host is None:
        host = getattr(settings, "api_bind_host", None) or "127.0.0.1"
    # 启动配置校验报告
    try:
        report = generate_startup_report()
        print_startup_report(report)
    except Exception as e:
        logger.warning(f"启动报告生成失败: {e}")

    print("=" * 60)
    print("  Y·NEX 本地AI核心服务 v1.0")
    print("=" * 60)
    print(f"  API地址: http://{host}:{port}")
    print(f"  文档地址: http://{host}:{port}/docs")
    print(f"  移动端遥控: http://{host}:{port}/mobile")
    print(f"  认证模式: {'强制API Key' if settings.api_key_required else '信任网段+可选Key'}")
    print(f"  信任网段: {settings.trusted_subnets}")
    print(f"  请求体限制: {settings.max_content_length_mb}MB")
    print("=" * 60)
    print("  支持能力:")
    print("    ✓ 文本/流式对话")
    print("    ✓ 49个技能调用")
    print("    ✓ 本地LLM推理")
    print("    ✓ 超级Agent任务执行")
    print("    ✓ 记忆管理")
    print("    ✓ 语音交互 / 唤醒词引擎")
    print("    ✓ PC 自动化 / 全局热键 / 剪贴板历史")
    print("    ✓ 系统控制")
    print("    ✓ 文件操作")
    print("    ✓ 认证与权限管理")
    print("=" * 60)

    if use_waitress:
        try:
            import waitress
            logger.info(f"使用 Waitress WSGI 服务器 ({host}:{port})")
            waitress.serve(app, host=host, port=port, threads=8, clear_untrusted_proxy_headers=True)
            return
        except ImportError:
            print("⚠ waitress 未安装，降级到 Flask 开发服务器（仅用于开发测试）")
            logger.warning("waitress 未安装，使用 Flask 开发服务器")

    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Y·NEX 本地AI核心服务")
    parser.add_argument("--port", type=int, default=7777, help="服务端口")
    parser.add_argument("--host", type=str, default=None, help="监听地址（默认 127.0.0.1，如需外部访问请显式传 0.0.0.0 并配合防火墙）")
    parser.add_argument("--dev", action="store_true", help="使用 Flask 开发服务器")
    args = parser.parse_args()
    run_server(args.port, args.host, use_waitress=not args.dev)
