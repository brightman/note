"""Smoke test: server is alive and DB is reachable."""

import pytest


async def test_health_returns_ok(http):
    r = await http.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_unknown_route_returns_404(http):
    r = await http.get("/does_not_exist")
    assert r.status_code == 404
