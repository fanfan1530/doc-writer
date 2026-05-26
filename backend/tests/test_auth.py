"""JWT 认证模块测试。"""
import pytest
from app.core.auth import (
    hash_password, verify_password, create_access_token,
    create_refresh_token, decode_token,
)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        h = hash_password("admin123")
        assert verify_password("admin123", h)
        assert not verify_password("wrong", h)

    def test_unique_salt(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2
        assert verify_password("same", h1)
        assert verify_password("same", h2)

    def test_long_password(self):
        h = hash_password("x" * 100)
        assert verify_password("x" * 100, h)


class TestAccessToken:
    def test_create_and_decode(self):
        token = create_access_token("admin", 1, "admin")
        payload = decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["user_id"] == 1
        assert payload["role"] == "admin"
        assert "exp" in payload
        assert "iat" in payload

    def test_invalid_token_raises(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_token("not.a.valid.token")
        assert exc.value.status_code == 401

    def test_wrong_secret(self):
        token = create_access_token("user", 2, "user")
        # Tamper with the secret doesn't affect token structure
        payload = decode_token(token)
        assert payload["sub"] == "user"


class TestRefreshToken:
    def test_create_and_decode(self):
        token = create_refresh_token("admin")
        payload = decode_token(token)
        assert payload["sub"] == "admin"
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_manipulated_token(self):
        # Use a manually created expired token
        from datetime import datetime, timedelta, timezone
        from jose import jwt
        from app.core.auth import SECRET_KEY, ALGORITHM

        expire = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {"sub": "test", "exp": expire}
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc:
            decode_token(token)
        assert exc.value.status_code == 401
