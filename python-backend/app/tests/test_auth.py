"""
认证服务单元测试
覆盖密码哈希、验证、JWT 令牌创建与解码
"""
import pytest
from jose import JWTError
from fastapi import HTTPException
from unittest.mock import patch, MagicMock


class TestAuthService:
    @patch("app.services.auth.pwd")
    def test_hash_password(self, mock_pwd):
        mock_pwd.hash.return_value = "$2b$12$hash123"
        from app.services.auth import hash_password
        hashed = hash_password("test_password_123")
        assert hashed == "$2b$12$hash123"
        mock_pwd.hash.assert_called_once_with("test_password_123")

    @patch("app.services.auth.pwd")
    def test_verify_password_correct(self, mock_pwd):
        mock_pwd.verify.return_value = True
        from app.services.auth import verify_password
        result = verify_password("test_password_123", "$2b$12$hash123")
        assert result is True
        mock_pwd.verify.assert_called_once_with("test_password_123", "$2b$12$hash123")

    @patch("app.services.auth.pwd")
    def test_verify_password_incorrect(self, mock_pwd):
        mock_pwd.verify.return_value = False
        from app.services.auth import verify_password
        result = verify_password("wrong_password", "$2b$12$hash123")
        assert result is False
        mock_pwd.verify.assert_called_once_with("wrong_password", "$2b$12$hash123")

    @patch("app.services.auth.pwd")
    def test_verify_password_empty(self, mock_pwd):
        mock_pwd.verify.return_value = False
        from app.services.auth import verify_password
        result = verify_password("", "")
        assert result is False

    def test_create_token(self):
        from app.services.auth import create_token
        token = create_token(123)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_decode_token_valid(self):
        from app.services.auth import create_token, decode_token
        token = create_token(456)
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded["sub"] == "456"

    def test_decode_token_invalid(self):
        from app.services.auth import decode_token
        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid_token_abc123")
        assert exc_info.value.status_code == 401
        assert "Invalid token" in str(exc_info.value.detail)

    def test_decode_token_expired(self):
        from app.config import settings
        from app.services.auth import create_token, decode_token
        original_expire = settings.jwt_expire_minutes
        settings.jwt_expire_minutes = -1
        try:
            token = create_token(789)
            with pytest.raises(HTTPException) as exc_info:
                decode_token(token)
            assert exc_info.value.status_code == 401
        finally:
            settings.jwt_expire_minutes = original_expire


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
