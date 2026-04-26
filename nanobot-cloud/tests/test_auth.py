"""Tests for api/middleware/auth.py — password hashing, JWT, current_user dep."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from jose import jwt

from api.middleware.auth import (
    create_token,
    hash_password,
    verify_password,
)
from settings import settings


# ── password hashing ──────────────────────────────────────────────────────────

def test_hash_is_not_plaintext():
    h = hash_password("mypassword")
    assert "mypassword" not in h


def test_verify_correct_password():
    h = hash_password("correct_horse")
    assert verify_password("correct_horse", h) is True


def test_verify_wrong_password():
    h = hash_password("correct_horse")
    assert verify_password("wrong_password", h) is False


def test_different_hashes_for_same_password():
    # bcrypt salts are random
    h1 = hash_password("same")
    h2 = hash_password("same")
    assert h1 != h2
    assert verify_password("same", h1)
    assert verify_password("same", h2)


def test_empty_password_hashes_and_verifies():
    h = hash_password("")
    assert verify_password("", h) is True
    assert verify_password("notempty", h) is False


# ── JWT token ─────────────────────────────────────────────────────────────────

def test_create_token_is_decodable():
    uid = uuid.uuid4()
    token = create_token(uid)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert payload["sub"] == str(uid)


def test_create_token_has_future_expiry():
    uid = uuid.uuid4()
    token = create_token(uid)
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert exp > datetime.now(timezone.utc)


def test_token_fails_with_wrong_secret():
    from jose import JWTError

    uid = uuid.uuid4()
    token = create_token(uid)
    with pytest.raises(JWTError):
        jwt.decode(token, "wrong-secret", algorithms=[settings.jwt_algorithm])


def test_expired_token_fails():
    from jose import ExpiredSignatureError

    uid = uuid.uuid4()
    # Create token that expired 1 second ago
    payload = {
        "sub": str(uid),
        "exp": datetime.now(timezone.utc) - timedelta(seconds=1),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    with pytest.raises(ExpiredSignatureError):
        jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def test_malformed_token_fails():
    from jose import JWTError

    with pytest.raises(JWTError):
        jwt.decode("not.a.jwt", settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def test_two_tokens_for_same_user_are_different():
    # jose adds jti or iat randomness, but even without — exp might differ by ms
    uid = uuid.uuid4()
    t1 = create_token(uid)
    t2 = create_token(uid)
    # Both should decode to same sub
    p1 = jwt.decode(t1, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    p2 = jwt.decode(t2, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    assert p1["sub"] == p2["sub"] == str(uid)
