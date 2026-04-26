"""Unit tests for config/crypto.py — Fernet encrypt/decrypt."""

import json
import pytest
from config.crypto import decrypt_env, encrypt_env


def test_roundtrip_simple():
    env = {"API_KEY": "sk-abc123", "DEBUG": "true"}
    token = encrypt_env(env)
    assert isinstance(token, str)
    assert decrypt_env(token) == env


def test_roundtrip_empty():
    env = {}
    assert decrypt_env(encrypt_env(env)) == env


def test_roundtrip_unicode():
    env = {"名前": "テスト", "emoji": "🔑"}
    assert decrypt_env(encrypt_env(env)) == env


def test_tokens_differ_each_call():
    # Fernet uses random IV — same plaintext produces different ciphertext
    env = {"KEY": "VALUE"}
    t1 = encrypt_env(env)
    t2 = encrypt_env(env)
    assert t1 != t2
    # But both decrypt correctly
    assert decrypt_env(t1) == decrypt_env(t2) == env


def test_tampered_token_raises():
    from cryptography.fernet import InvalidToken

    env = {"KEY": "VALUE"}
    token = encrypt_env(env)
    bad = token[:-4] + "XXXX"
    with pytest.raises(Exception):
        decrypt_env(bad)


def test_nested_values():
    env = {"DB_URL": "postgresql://user:pass@host:5432/db"}
    assert decrypt_env(encrypt_env(env)) == env
