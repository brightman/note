# conftest.py — loaded before any collection, patches env vars and sys.path

import os
import sys

# Must set before any module imports settings
os.environ.setdefault("NC_DATABASE_URL", "postgresql+asyncpg://x:x@localhost/x")
os.environ.setdefault("NC_DATABASE_URL_SYNC", "postgresql://x:x@localhost/x")
os.environ.setdefault("NC_ENCRYPTION_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA==")
os.environ.setdefault("NC_JWT_SECRET", "test-secret-key")
os.environ.setdefault("NC_S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("NC_S3_ACCESS_KEY", "minioadmin")
os.environ.setdefault("NC_S3_SECRET_KEY", "minioadmin")
os.environ.setdefault("NC_VM_IDLE_TIMEOUT", "1800")
os.environ.setdefault("NC_VM_REAPER_INTERVAL", "60")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "control-plane"))
