import pytest
from app.utils.security import create_access_token, decode_access_token


class TestJWTCreateAndDecode:
    """JWT 签发与解析"""

    def test_create_and_decode(self):
        token = create_access_token({"sub": "user-123", "role": "student"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "user-123"
        assert payload["role"] == "student"
        assert "exp" in payload

    def test_decode_invalid_token(self):
        assert decode_access_token("invalid.token.here") is None

    def test_decode_empty_string(self):
        assert decode_access_token("") is None

    def test_decode_tampered_token(self):
        token = create_access_token({"sub": "user-123", "role": "admin"})
        tampered = token + "x"
        assert decode_access_token(tampered) is None

    def test_payload_preserves_all_fields(self):
        data = {"sub": "abc", "role": "guest", "extra": "value", "num": 42}
        token = create_access_token(data)
        payload = decode_access_token(token)
        assert payload["sub"] == "abc"
        assert payload["role"] == "guest"
        assert payload["extra"] == "value"
        assert payload["num"] == 42

    def test_custom_expiry(self):
        from datetime import timedelta

        token = create_access_token({"sub": "x"}, expires_delta=timedelta(seconds=1))
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "x"
