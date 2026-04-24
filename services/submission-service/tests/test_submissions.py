import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_list_submissions_unauthenticated(client):
    # No Authorization header → 401 Unauthenticated (Starlette HTTPBearer behaviour)
    resp = await client.get("/v1/submissions")
    assert resp.status_code == 401
