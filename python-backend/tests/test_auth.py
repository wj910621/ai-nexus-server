"""
Python Backend 认证模块测试
覆盖JWT Token、数据模型等核心认证功能
"""

import os
import sys
sys.path.insert(0, '/workspace/python-backend')

os.environ["JWT_SECRET"] = "test-secret-key-12345"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["JWT_EXPIRE_MINUTES"] = "1440"


def test_create_token():
    print("1. 测试Token创建...")
    
    from app.config import settings
    settings.jwt_secret = "test-secret-key-12345"
    
    from app.services.auth import create_token
    from jose import jwt
    
    uid = 123
    
    token = create_token(uid)
    
    assert token is not None
    assert len(token) > 0
    
    decoded = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert decoded["sub"] == "123"
    assert "exp" in decoded
    
    print("  ✓ Token创建测试通过")


def test_decode_token():
    print("\n2. 测试Token解码...")
    
    from app.config import settings
    settings.jwt_secret = "test-secret-key-12345"
    
    from app.services.auth import create_token, decode_token
    from jose import jwt
    
    uid = 123
    
    token = create_token(uid)
    decoded = decode_token(token)
    
    assert decoded is not None
    assert decoded["sub"] == "123"
    
    try:
        decode_token("invalid_token")
        assert False, "应抛出异常"
    except Exception:
        pass
    
    try:
        decode_token(jwt.encode({"sub": "123"}, "wrong_secret", algorithm="HS256"))
        assert False, "应抛出异常"
    except Exception:
        pass
    
    print("  ✓ Token解码测试通过")


def test_schemas():
    print("\n3. 测试数据模型...")
    
    from app.schemas.auth import RegisterRequest, LoginRequest, UserResponse, TokenResponse
    from pydantic import ValidationError
    
    req = RegisterRequest(username="testuser", email="test@example.com", password="test123456")
    assert req.username == "testuser"
    assert req.email == "test@example.com"
    assert req.password == "test123456"
    
    try:
        RegisterRequest(username="ab", password="short")
        assert False, "应抛出异常"
    except ValidationError:
        pass
    
    login_req = LoginRequest(username="testuser", password="test123456")
    assert login_req.username == "testuser"
    
    user_resp = UserResponse(id=1, username="testuser", email="test@example.com", is_active=True)
    assert user_resp.id == 1
    assert user_resp.username == "testuser"
    
    print("  ✓ 数据模型测试通过")


def test_config():
    print("\n4. 测试配置加载...")
    
    from app.config import settings
    
    assert settings.jwt_secret is not None
    assert settings.jwt_algorithm == "HS256"
    assert settings.jwt_expire_minutes == 1440
    assert settings.database_url is not None
    
    print("  ✓ 配置加载测试通过")


def main():
    print("=" * 60)
    print("  Python Backend 认证模块测试")
    print("=" * 60)
    
    test_create_token()
    test_decode_token()
    test_schemas()
    test_config()
    
    print("\n" + "=" * 60)
    print("🎉 Python Backend 认证模块测试全部通过")
    print("=" * 60)


if __name__ == "__main__":
    main()