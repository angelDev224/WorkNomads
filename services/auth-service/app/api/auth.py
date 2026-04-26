from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.config import settings
from app.db.models import RefreshToken, User
from app.db.session import get_db
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    VerifyResponse,
)

router = APIRouter(prefix="/v1/auth", tags=["auth"])
logger = structlog.get_logger()
bearer_scheme = HTTPBearer(auto_error=False)

COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.app_env != "development",
        samesite="strict",
        max_age=settings.refresh_token_expire_days * 86400,
        path="/v1/auth",
    )


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.email == body.email))
    user: User | None = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, refresh_hash = create_refresh_token()

    rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(rt)
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):

    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh token")

    token_hash = hash_token(refresh_token)

    # Check Redis blacklist first (fast path)
    if await redis.get(f"revoked:{token_hash}"):
        raise HTTPException(status_code=401, detail="Token revoked")

    result = await db.execute(
        select(RefreshToken).where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked.is_(False),
        )
    )
    rt: RefreshToken | None = result.scalar_one_or_none()

    if not rt or rt.expires_at.replace(tzinfo=timezone.utc) < datetime.now(
        timezone.utc
    ):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user_result = await db.execute(select(User).where(User.id == rt.user_id))
    user: User | None = user_result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or disabled")

    # Rotate: revoke old, issue new
    rt.revoked = True
    await db.commit()

    access_token = create_access_token(str(user.id), user.role)
    raw_refresh, refresh_hash = create_refresh_token()

    new_rt = RefreshToken(
        user_id=user.id,
        token_hash=refresh_hash,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(new_rt)
    await db.commit()

    _set_refresh_cookie(response, raw_refresh)
    return TokenResponse(access_token=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
):
    if refresh_token:
        token_hash = hash_token(refresh_token)
        result = await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        rt = result.scalar_one_or_none()
        if rt:
            rt.revoked = True
            await db.commit()
        # Also blacklist in Redis with TTL
        await redis.setex(
            f"revoked:{token_hash}",
            settings.refresh_token_expire_days * 86400,
            "1",
        )

    response.delete_cookie(COOKIE_NAME, path="/v1/auth")


@router.get("/verify", response_model=VerifyResponse)
async def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    """Internal endpoint called by api-gateway to validate Bearer tokens."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return VerifyResponse(user_id=payload["sub"], role=payload["role"])


@router.get("/me", response_model=UserResponse)
async def me(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing token")
    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user
