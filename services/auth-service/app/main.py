import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import select

from app.api.auth import router as auth_router
from app.config import settings
from app.core.redis import close_redis
from app.core.security import hash_password
from app.db.models import Base, User
from app.db.session import AsyncSessionLocal, engine

logger = structlog.get_logger()


async def ensure_bootstrap_admin(
    db,
    bootstrap_email: str,
    bootstrap_password: str,
) -> bool:
    result = await db.execute(select(User).where(User.email == bootstrap_email))
    existing_user = result.scalar_one_or_none()
    if existing_user:
        return False

    bootstrap_user = User(
        email=bootstrap_email,
        password_hash=hash_password(bootstrap_password),
        role="admin",
        is_active=True,
    )
    db.add(bootstrap_user)
    await db.commit()
    return True


async def bootstrap_admin_from_settings() -> None:
    bootstrap_email = settings.bootstrap_admin_email
    bootstrap_password = settings.bootstrap_admin_password
    if not (bootstrap_email and bootstrap_password):
        logger.info("bootstrap admin skipped (missing env vars)")
        return

    async with AsyncSessionLocal() as db:
        created = await ensure_bootstrap_admin(db, bootstrap_email, bootstrap_password)
        if created:
            logger.info("bootstrap admin created", email=bootstrap_email)
        else:
            logger.info("bootstrap admin already exists", email=bootstrap_email)


app = FastAPI(
    title="WorkNomads Auth Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"url": "/auth/openapi.json"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

app.include_router(auth_router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await bootstrap_admin_from_settings()

    logger.info("auth-service started")


@app.on_event("shutdown")
async def shutdown():
    await close_redis()
    await engine.dispose()


@app.get("/healthz", tags=["ops"])
async def healthz():
    return {"status": "ok", "service": "auth-service"}


@app.get("/readyz", tags=["ops"])
async def readyz():
    return {"status": "ready"}
