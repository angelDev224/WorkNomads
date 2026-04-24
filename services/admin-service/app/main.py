import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.submissions import router as submissions_router
from app.api.users import router as users_router
from app.db.models import AuditLog, Base
from app.db.session import engine

logger = structlog.get_logger()

app = FastAPI(
    title="WorkNomads Admin Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"url": "/admin/openapi.json"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(submissions_router)
app.include_router(users_router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        # Only create audit_log; other tables are owned by auth/submission services
        await conn.run_sync(AuditLog.__table__.create, checkfirst=True)
    logger.info("admin-service started")


@app.on_event("shutdown")
async def shutdown():
    await engine.dispose()


@app.get("/healthz", tags=["ops"])
async def healthz():
    return {"status": "ok", "service": "admin-service"}


@app.get("/readyz", tags=["ops"])
async def readyz():
    return {"status": "ready"}
