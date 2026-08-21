"""认证 API 测试"""
import pytest
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_register_validation_error():
    """测试注册参数校验"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 缺少必填字段
        response = await client.post("/api/auth/register", json={"username": "ab"})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_missing_fields():
    """测试登录缺少字段"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/auth/login", json={"account": ""})
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_protected_endpoint_without_token():
    """测试未认证访问受保护接口"""
    from app.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/users/me")
        assert response.status_code == 401
