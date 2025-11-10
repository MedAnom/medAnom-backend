# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db
from app.models.user_store import seed_users

from app.api.routers.health import router as health_router
from app.api.routers.auth import router as auth_router
from app.api.routers.analyze import router as analyze_router
from app.api.routers.cost import router as cost_router

app = FastAPI(title="MedAnom API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 초기화
seed_users()
init_db()

# 라우터
app.include_router(health_router,  prefix="/api",  tags=["default"])
app.include_router(auth_router,    prefix="/auth", tags=["auth"])
app.include_router(analyze_router, prefix="/api",  tags=["default"])
app.include_router(cost_router,    prefix="/api",  tags=["cost"])
