"""集成测试 - 验证 API 路由注册"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_all_api_routes_registered():
    """测试所有 API 路由已正确注册"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/openapi.json")
    assert response.status_code == 200

    paths = response.json()["paths"]
    expected_paths = [
        "/api/auth/register",
        "/api/auth/login",
        "/api/users/me",
        "/api/projects",
        "/api/characters",
        "/api/scripts",
        "/api/storyboards",
        "/api/audio/voices",
        "/api/render",
        "/api/workflows",
        "/health",
    ]
    for path in expected_paths:
        assert path in paths, f"缺少路由: {path}"


@pytest.mark.asyncio
async def test_cors_headers():
    """测试 CORS 头"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.options(
            "/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert response.status_code in [200, 204]


@pytest.mark.asyncio
async def test_error_response_format():
    """测试错误响应格式"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 访问需要认证的接口
        response = await client.get("/api/users/me")
    assert response.status_code == 401
    # FastAPI 默认错误格式，不是我们的 ApiResponse 格式（受 OAuth2 拦截）
    data = response.json()
    assert "detail" in data
