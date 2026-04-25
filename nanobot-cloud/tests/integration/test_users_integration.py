"""Integration tests: user registration, login, /me — real DB."""

import uuid
import pytest


# ── register ──────────────────────────────────────────────────────────────────

async def test_register_creates_user(http):
    username = f"reg_{uuid.uuid4().hex[:8]}"
    r = await http.post("/users/register", json={"username": username, "password": "pass"})
    assert r.status_code == 201
    body = r.json()
    assert body["username"] == username
    assert "id" in body
    # id should be a valid UUID
    uuid.UUID(body["id"])


async def test_register_duplicate_username_returns_409(http):
    username = f"dup_{uuid.uuid4().hex[:8]}"
    await http.post("/users/register", json={"username": username, "password": "pw"})
    r = await http.post("/users/register", json={"username": username, "password": "pw"})
    assert r.status_code == 409


async def test_register_also_creates_default_config(http, authed):
    client, username = authed
    # The default agent config should be an empty object (created by register)
    r = await client.get("/config/agent")
    assert r.status_code == 200
    assert isinstance(r.json()["config"], dict)


async def test_register_also_creates_default_prompt(http, authed):
    client, _ = authed
    r = await client.get("/config/prompt")
    assert r.status_code == 200
    # Default prompt is non-empty
    assert len(r.json()["prompt"]) > 0


# ── login ─────────────────────────────────────────────────────────────────────

async def test_login_correct_credentials(http):
    username = f"login_{uuid.uuid4().hex[:8]}"
    await http.post("/users/register", json={"username": username, "password": "secret"})
    r = await http.post("/users/login", json={"username": username, "password": "secret"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"
    assert len(body["access_token"]) > 20


async def test_login_wrong_password_returns_401(http):
    username = f"wp_{uuid.uuid4().hex[:8]}"
    await http.post("/users/register", json={"username": username, "password": "correct"})
    r = await http.post("/users/login", json={"username": username, "password": "wrong"})
    assert r.status_code == 401


async def test_login_nonexistent_user_returns_401(http):
    r = await http.post("/users/login", json={"username": "ghost_xyz_999", "password": "pw"})
    assert r.status_code == 401


async def test_login_token_is_valid_jwt(http):
    from jose import jwt

    username = f"jwt_{uuid.uuid4().hex[:8]}"
    await http.post("/users/register", json={"username": username, "password": "pw"})
    r = await http.post("/users/login", json={"username": username, "password": "pw"})
    token = r.json()["access_token"]

    # Decode without verification to check structure
    payload = jwt.get_unverified_claims(token)
    assert "sub" in payload
    assert "exp" in payload
    uuid.UUID(payload["sub"])  # sub should be a valid UUID


# ── /me ───────────────────────────────────────────────────────────────────────

async def test_me_returns_logged_in_user(authed):
    client, username = authed
    r = await client.get("/users/me")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == username
    uuid.UUID(body["id"])


async def test_me_without_token_returns_403(http):
    r = await http.get("/users/me")
    assert r.status_code in (401, 403)


async def test_me_with_invalid_token_returns_401(http):
    r = await http.get(
        "/users/me",
        headers={"Authorization": "Bearer not.a.valid.token"},
    )
    assert r.status_code == 401


async def test_two_users_are_isolated(http):
    """Users created independently have different IDs."""
    u1 = f"iso1_{uuid.uuid4().hex[:6]}"
    u2 = f"iso2_{uuid.uuid4().hex[:6]}"
    r1 = await http.post("/users/register", json={"username": u1, "password": "pw"})
    r2 = await http.post("/users/register", json={"username": u2, "password": "pw"})
    assert r1.json()["id"] != r2.json()["id"]
