import pytest
from uuid import UUID
from sqlalchemy import select

from app.api import auth as auth_api
from app.core.redis import get_redis
from app.core.security import verify_password
from app.db.models import User
from app.main import app
from app.main import ensure_bootstrap_admin


class FakeRedis:
    def __init__(self):
        self._data = {}

    async def get(self, key: str):
        return self._data.get(key)

    async def setex(self, key: str, ttl: int, value: str):
        self._data[key] = value


@pytest.fixture
def fake_redis():
    redis = FakeRedis()

    async def override_get_redis():
        return redis

    app.dependency_overrides[get_redis] = override_get_redis
    yield redis
    app.dependency_overrides.pop(get_redis, None)


@pytest.mark.asyncio
async def test_register(client):
    resp = await client.post("/v1/auth/register", json={"email": "user@example.com", "password": "Password1"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "user@example.com"
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_register_duplicate(client):
    payload = {"email": "dup@example.com", "password": "Password1"}
    await client.post("/v1/auth/register", json=payload)
    resp = await client.post("/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_login(client):
    await client.post("/v1/auth/register", json={"email": "login@example.com", "password": "Password1"})
    resp = await client.post("/v1/auth/login", json={"email": "login@example.com", "password": "Password1"})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    await client.post("/v1/auth/register", json={"email": "wrong@example.com", "password": "Password1"})
    resp = await client.post("/v1/auth/login", json={"email": "wrong@example.com", "password": "WrongPass1"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh(client, fake_redis):
    await client.post("/v1/auth/register", json={"email": "refresh@example.com", "password": "Password1"})
    login_resp = await client.post("/v1/auth/login", json={"email": "refresh@example.com", "password": "Password1"})
    refresh_token = login_resp.cookies.get("refresh_token")
    resp = await client.post("/v1/auth/refresh", cookies={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_refresh_no_cookie(client, fake_redis):
    client.cookies.clear()
    resp = await client.post("/v1/auth/refresh")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "No refresh token"


@pytest.mark.asyncio
async def test_logout(client, fake_redis):
    await client.post("/v1/auth/register", json={"email": "logout@example.com", "password": "Password1"})
    login_resp = await client.post("/v1/auth/login", json={"email": "logout@example.com", "password": "Password1"})
    refresh_token = login_resp.cookies.get("refresh_token")
    resp = await client.post("/v1/auth/logout", cookies={"refresh_token": refresh_token})
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_logout_no_cookie(client, fake_redis):
    resp = await client.post("/v1/auth/logout")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_verify(client):
    await client.post("/v1/auth/register", json={"email": "verify@example.com", "password": "Password1"})
    login_resp = await client.post("/v1/auth/login", json={"email": "verify@example.com", "password": "Password1"})
    token = login_resp.json()["access_token"]
    resp = await client.get("/v1/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "user_id" in data
    assert data["role"] == "user"


@pytest.mark.asyncio
async def test_verify_missing_header(client):
    resp = await client.get("/v1/auth/verify")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_verify_invalid_token(client):
    resp = await client.get("/v1/auth/verify", headers={"Authorization": "Bearer invalid.token.value"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me(client, monkeypatch):
    await client.post("/v1/auth/register", json={"email": "me@example.com", "password": "Password1"})
    login_resp = await client.post("/v1/auth/login", json={"email": "me@example.com", "password": "Password1"})
    verify_resp = await client.get(
        "/v1/auth/verify",
        headers={"Authorization": f"Bearer {login_resp.json()['access_token']}"},
    )
    user_id = verify_resp.json()["user_id"]

    def decode_with_uuid_sub(_token):
        return {"sub": UUID(user_id), "role": "user"}

    monkeypatch.setattr(auth_api, "decode_access_token", decode_with_uuid_sub)
    token = login_resp.json()["access_token"]
    resp = await client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "me@example.com"


@pytest.mark.asyncio
async def test_me_missing_header(client):
    resp = await client.get("/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token(client):
    resp = await client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_healthz(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ensure_bootstrap_admin_creates_admin_user(db_session):
    created = await ensure_bootstrap_admin(
        db_session,
        "bootstrap@example.com",
        "BootstrapPass1",
    )

    assert created is True
    result = await db_session.execute(select(User).where(User.email == "bootstrap@example.com"))
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.role == "admin"
    assert verify_password("BootstrapPass1", user.password_hash)


@pytest.mark.asyncio
async def test_ensure_bootstrap_admin_is_idempotent(db_session):
    first = await ensure_bootstrap_admin(
        db_session,
        "bootstrap2@example.com",
        "BootstrapPass1",
    )
    second = await ensure_bootstrap_admin(
        db_session,
        "bootstrap2@example.com",
        "BootstrapPass1",
    )

    assert first is True
    assert second is False
    result = await db_session.execute(select(User).where(User.email == "bootstrap2@example.com"))
    users = result.scalars().all()
    assert len(users) == 1
