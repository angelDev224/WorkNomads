import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.submissions import router as submission_router
from app.core.messaging import close_messaging
from app.db.models import Base
from app.db.session import engine

logger = structlog.get_logger()

app = FastAPI(
    title="WorkNomads Submission Service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    swagger_ui_parameters={"url": "/submissions/openapi.json"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")
app.include_router(submission_router)


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("submission-service started")


@app.on_event("shutdown")
async def shutdown():
    await close_messaging()
    await engine.dispose()


@app.get("/healthz", tags=["ops"])
async def healthz():
    return {"status": "ok", "service": "submission-service"}


@app.get("/readyz", tags=["ops"])
async def readyz():
    return {"status": "ready"}
