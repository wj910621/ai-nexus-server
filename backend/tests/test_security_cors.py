"""A2: CORS 收敛测试 - Phase 8 P7"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _build_app(allow_origins=None):
    """构造带 CORS 中间件的测试 app，复用 main.py 配置。"""
    from app.core.config import settings
    from fastapi.middleware.cors import CORSMiddleware

    app = FastAPI()

    @app.get("/ping")
    async def ping():
        return {"ok": True}

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins if allow_origins is not None else settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Subscription-JWT"],
        expose_headers=["X-Request-ID", "X-Subscription-JWT"],
    )
    return app


def test_cors_allowed_methods():
    """CORS 仅允许显式列出的方法（不再用 *）"""
    app = _build_app()
    client = TestClient(app)
    # OPTIONS preflight
    r = client.options(
        "/ping",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code in (200, 204)
    allow_methods = r.headers.get("access-control-allow-methods", "")
    # 不应包含通配符
    assert "*" not in allow_methods
    for m in ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        assert m in allow_methods


def test_cors_allowed_headers():
    """CORS 仅允许显式列出的请求头"""
    app = _build_app()
    client = TestClient(app)
    r = client.options(
        "/ping",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization, Content-Type, X-Request-ID, X-Subscription-JWT",
        },
    )
    assert r.status_code in (200, 204)
    allow_headers = r.headers.get("access-control-allow-headers", "")
    assert "Authorization" in allow_headers
    assert "Content-Type" in allow_headers
    assert "X-Request-ID" in allow_headers
    assert "X-Subscription-JWT" in allow_headers
    # 不允许任意自定义头（例如 X-Evil-Header 不在 allow list 中）
    r2 = client.options(
        "/ping",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Evil-Header",
        },
    )
    allow_headers2 = r2.headers.get("access-control-allow-headers", "")
    assert "X-Evil-Header" not in allow_headers2


def test_cors_expose_headers():
    """CORS expose_headers 暴露 X-Request-ID 与 X-Subscription-JWT"""
    app = _build_app()
    client = TestClient(app)
    r = client.get("/ping", headers={"Origin": "http://localhost:5173"})
    expose = r.headers.get("access-control-expose-headers", "")
    assert "X-Request-ID" in expose
    assert "X-Subscription-JWT" in expose


def test_cors_preflight_options():
    """OPTIONS 预检应返回 200/204 并带 CORS 头"""
    app = _build_app()
    client = TestClient(app)
    r = client.options(
        "/ping",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert r.status_code in (200, 204)
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_origin_reflected():
    """允许的 origin 应被反射；未允许的 origin 不应被反射"""
    app = _build_app(allow_origins=["http://localhost:5173"])
    client = TestClient(app)
    # 允许的 origin
    r = client.get("/ping", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    # 未允许的 origin - CORS 中间件不应回送 allow-origin
    r2 = client.get("/ping", headers={"Origin": "http://evil.example.com"})
    assert r2.headers.get("access-control-allow-origin") is None


def test_main_app_cors_not_wildcard():
    """主应用 main.app 的 CORS 配置不应使用通配符"""
    from app.main import app
    # 找到 CORSMiddleware 实例并校验配置
    from starlette.middleware.cors import CORSMiddleware
    found = False
    m = app.user_middleware
    for mw in m:
        if mw.cls is CORSMiddleware:
            found = True
            # starlette Middleware 对象：options 字典保存 kwargs
            opts = getattr(mw, "options", None) or getattr(mw, "kwargs", None) or {}
            am = opts.get("allow_methods", [])
            ah = opts.get("allow_headers", [])
            assert "*" not in am, "CORS allow_methods 不应使用 *"
            assert "*" not in ah, "CORS allow_headers 不应使用 *"
            assert "X-Request-ID" in ah
            assert "X-Subscription-JWT" in ah
            eh = opts.get("expose_headers", [])
            assert "X-Request-ID" in eh
            assert "X-Subscription-JWT" in eh
    assert found, "应注册 CORSMiddleware"
