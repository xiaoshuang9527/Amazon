"""安全工具测试：密码哈希、JWT、Fernet 加密。"""

import pytest
from cryptography.fernet import Fernet

from app.core.config import settings
from app.core.exceptions import AuthError
from app.core.security import (
    create_access_token,
    decode_access_token,
    decrypt_secret,
    encrypt_secret,
    hash_password,
    verify_password,
)


# --------------------------------------------------------------------------- #
# 密码
# --------------------------------------------------------------------------- #
def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed.startswith("pbkdf2_sha256$")
    assert "secret123" not in hashed
    assert verify_password("secret123", hashed) is True


def test_verify_password_rejects_wrong_password():
    hashed = hash_password("secret123")
    assert verify_password("secret124", hashed) is False


def test_hash_is_salted():
    """相同密码两次哈希结果不同（随机盐）。"""
    assert hash_password("same-password") != hash_password("same-password")


@pytest.mark.parametrize("bad_hash", ["", "not-a-hash", "md5$1$a$b", "pbkdf2_sha256$bad"])
def test_verify_password_handles_malformed_hash(bad_hash):
    assert verify_password("secret123", bad_hash) is False


# --------------------------------------------------------------------------- #
# JWT
# --------------------------------------------------------------------------- #
def test_create_and_decode_access_token():
    token = create_access_token(42, extra={"scope": "test"})
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["scope"] == "test"
    assert payload["exp"] > payload["iat"]


def test_decode_access_token_rejects_tampered_token():
    token = create_access_token(7)
    with pytest.raises(AuthError):
        decode_access_token(token + "tampered")


def test_decode_access_token_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(settings, "JWT_EXPIRE_MINUTES", -1)
    token = create_access_token(1)
    with pytest.raises(AuthError):
        decode_access_token(token)


# --------------------------------------------------------------------------- #
# Fernet
# --------------------------------------------------------------------------- #
def test_encrypt_decrypt_roundtrip():
    plain = "Atzr|refresh-token-demo"
    cipher = encrypt_secret(plain)
    assert cipher != plain
    assert decrypt_secret(cipher) == plain


def test_cipher_is_not_deterministic():
    """Fernet 每次加密结果不同，但都能解回原文。"""
    plain = "same-value"
    first, second = encrypt_secret(plain), encrypt_secret(plain)
    assert first != second
    assert decrypt_secret(first) == decrypt_secret(second) == plain


def test_decrypt_secret_rejects_wrong_key(monkeypatch):
    cipher = encrypt_secret("token")
    monkeypatch.setattr(settings, "FERNET_KEY", Fernet.generate_key().decode())
    with pytest.raises(AuthError):
        decrypt_secret(cipher)


def test_decrypt_secret_rejects_garbage():
    with pytest.raises(AuthError):
        decrypt_secret("this-is-not-a-valid-fernet-token")
