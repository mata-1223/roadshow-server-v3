from __future__ import annotations
"""
roadshow-server-v3
AX Tech Connect 시연용 백엔드 (마이K Intent Taxonomy 116개 기반)

시나리오: cs-myk-v3
구조: 3-Layer (Foundation / Inference / Serving)
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from data.executor import init_db
from routes import sessions, intents, scenarios, admin
from ws.handler import router as ws_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """앱 수명주기: 기동 시 DB 초기화(스키마+카탈로그 시드), 종료 로깅."""
    logger.info(f"Starting roadshow-server-v3 (scenario={settings.SCENARIO_ID})")
    init_db()
    logger.info(f"DB initialized: {settings.DB_PATH}")
    if settings.WARMUP_ON_START:                  # 배포 후 첫 설문 없이 모델 준비
        from core.warmup import warmup_models
        warmup_models()
    yield
    logger.info("Shutting down roadshow-server-v3")


app = FastAPI(
    title="roadshow-server-v3",
    description="AX Tech Connect 시연용 백엔드 (마이K Intent Taxonomy 116개)",
    version="3.0.0",
    lifespan=lifespan,
)

_cors_origins = (
    [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    if settings.CORS_ORIGINS
    else ["*"]
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scenarios.router, prefix="/api/scenarios", tags=["scenarios"])
app.include_router(sessions.router,  prefix="/api/sessions",  tags=["sessions"])
app.include_router(intents.router,   prefix="/api/intents",   tags=["intents"])
app.include_router(admin.router,     prefix="/api/admin",     tags=["admin"])
app.include_router(ws_router)


@app.get("/health")
async def health() -> dict:
    """헬스 체크 — 상태·시나리오·환경."""
    return {
        "status":      "ok",
        "scenario_id": settings.SCENARIO_ID,
        "env":         settings.ENV,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.RELOAD,
    )
