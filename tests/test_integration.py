import asyncio
import pytest
from httpx import AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_concurrent_packets_no_crash(monkeypatch):
    async with AsyncClient(app=app, base_url="http://test") as ac:
        call_id = "test-call-1"

        packet1 = {"sequence": 1, "data": "hello", "timestamp": 1.0}
        packet2 = {"sequence": 1, "data": "hello-duplicate", "timestamp": 1.0}

        # send two concurrent requests for same sequence
        r1, r2 = await asyncio.gather(
            ac.post(f"/v1/call/stream/{call_id}", json=packet1),
            ac.post(f"/v1/call/stream/{call_id}", json=packet2),
        )

        assert r1.status_code == 202
        assert r2.status_code == 202
