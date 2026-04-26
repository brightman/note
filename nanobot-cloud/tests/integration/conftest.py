"""
Integration test fixtures — no Docker required.

Lifecycle (session-scoped):
  1. Start moto S3 server as a subprocess on port 9002
  2. Create the test bucket via boto3
  3. Create DB tables (SQLAlchemy create_all on local PostgreSQL)
  4. Start the FastAPI server as a subprocess on port 8001
  5. Wait until /health returns 200
  6. Yield to tests
  7. Stop server → stop moto

Requires:
  - Local PostgreSQL running with nanobot_test database
    (pg_ctlcluster 16 main start)
    (createdb -U postgres nanobot_test; createuser -U postgres nanobot)
  - pip install moto[s3,server] flask
"""

import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import pytest
import pytest_asyncio

# ── paths & env ───────────────────────────────────────────────────────────────

ROOT = Path(__file__).parent.parent.parent
CP_DIR = str(ROOT / "control-plane")

sys.path.insert(0, CP_DIR)

TEST_DB_URL = "postgresql+asyncpg://nanobot:nanobot@localhost:5432/nanobot_test"
MOTO_PORT = 9002
SERVER_PORT = 8001
BASE_URL = f"http://localhost:{SERVER_PORT}"

ENV = {
    **os.environ,
    "NC_DATABASE_URL": TEST_DB_URL,
    "NC_DATABASE_URL_SYNC": TEST_DB_URL.replace("+asyncpg", ""),
    "NC_S3_ENDPOINT": f"http://localhost:{MOTO_PORT}",
    "NC_S3_BUCKET": "nanobot-test",
    "NC_S3_ACCESS_KEY": "testing",
    "NC_S3_SECRET_KEY": "testing",
    "NC_JWT_SECRET": "integration-test-secret",
    "NC_ENCRYPTION_KEY": "integration-test-enc-key-padded==",
    "NC_VM_IDLE_TIMEOUT": "1800",
    "NC_VM_REAPER_INTERVAL": "60",
    "PYTHONPATH": CP_DIR,
    # Fake AWS region for moto
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _wait_http(url: str, timeout: int = 20) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2)
            if r.status_code < 500:
                return
        except Exception:
            pass
        time.sleep(0.3)
    raise TimeoutError(f"{url} never responded within {timeout}s")


# ── moto S3 server ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def moto_server():
    """Start moto S3 server on MOTO_PORT."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "moto.server", "-H", "127.0.0.1", "-p", str(MOTO_PORT)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "AWS_DEFAULT_REGION": "us-east-1"},
    )
    _wait_http(f"http://localhost:{MOTO_PORT}")
    print(f"\n[integration] moto S3 server ready on :{MOTO_PORT}")

    # Create test bucket
    import boto3, botocore
    s3 = boto3.client(
        "s3",
        endpoint_url=f"http://localhost:{MOTO_PORT}",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        region_name="us-east-1",
        config=botocore.config.Config(signature_version="s3v4"),
    )
    s3.create_bucket(Bucket="nanobot-test")
    print("[integration] test bucket created")

    yield

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[integration] moto server stopped")


# ── database tables ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def create_tables():
    """Create all tables; drop them on teardown."""
    from sqlalchemy import create_engine, text
    from storage.models import Base

    sync_url = TEST_DB_URL.replace("+asyncpg", "")
    engine = create_engine(sync_url)
    Base.metadata.drop_all(engine)   # clean slate
    Base.metadata.create_all(engine)
    engine.dispose()
    print("[integration] DB tables created")

    yield

    engine2 = create_engine(sync_url)
    Base.metadata.drop_all(engine2)
    engine2.dispose()
    print("[integration] DB tables dropped")


# ── FastAPI server ────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def server(moto_server, create_tables):
    """Start uvicorn on SERVER_PORT."""
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn",
            "api.main:app",
            "--host", "127.0.0.1",
            "--port", str(SERVER_PORT),
            "--log-level", "warning",
        ],
        cwd=CP_DIR,
        env=ENV,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _wait_http(f"{BASE_URL}/health", timeout=30)
    print(f"[integration] FastAPI server ready on :{SERVER_PORT}")

    yield BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
    print("[integration] FastAPI server stopped")


# ── HTTP clients ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def http(server):
    async with httpx.AsyncClient(base_url=server, timeout=15) as client:
        yield client


@pytest_asyncio.fixture
async def authed(server):
    """Fresh authenticated client + username per test."""
    username = f"u_{uuid.uuid4().hex[:10]}"
    password = "Test1234!"

    async with httpx.AsyncClient(base_url=server, timeout=15) as setup:
        r = await setup.post("/users/register",
                             json={"username": username, "password": password})
        assert r.status_code == 201, f"register failed: {r.text}"
        r = await setup.post("/users/login",
                             json={"username": username, "password": password})
        assert r.status_code == 200, f"login failed: {r.text}"
        token = r.json()["access_token"]

    async with httpx.AsyncClient(
        base_url=server,
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    ) as client:
        yield client, username
