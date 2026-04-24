import pytest


@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_submissions_requires_auth(client):
    # No Authorization header → 401 Unauthenticated (Starlette HTTPBearer behaviour)
    resp = await client.get("/v1/admin/submissions")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_users_requires_auth(client):
    resp = await client.get("/v1/admin/users")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submissions_requires_admin_role(client):
    # Valid JWT but role=user → 403 Forbidden
    from jose import jwt
    token = jwt.encode({"sub": "user-id", "role": "user"}, "test-secret-key-for-local-dev", algorithm="HS256")
    resp = await client.get("/v1/admin/submissions", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_users_requires_admin_role(client):
    from jose import jwt
    token = jwt.encode({"sub": "user-id", "role": "user"}, "test-secret-key-for-local-dev", algorithm="HS256")
    resp = await client.get("/v1/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
