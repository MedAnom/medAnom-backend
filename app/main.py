# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.db import init_db
from app.models.user_store import seed_users

# 라우터 임포트
from app.api.routers import (
    auth,
    health,
    analyze,
    cost,
    advice,
    nearby,
    history,
)

app = FastAPI(title="MedAnom API")

# -----------------------------------------------------
#  CORS
# -----------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------------------------
#  초기화
# -----------------------------------------------------
seed_users()
init_db()

# -----------------------------------------------------
#  라우터 등록
# -----------------------------------------------------

# (1) 인증 관련
app.include_router(auth.router, prefix="/auth", tags=["auth"])

# (2) 건강 분석 / 모델 분석 / 비용
#     - /api/health         : 개인 건강 분석 + DB 저장 (Dashboard/Analysis 화면용)
#     - /api/analyze/health : 별도 모델 분석 (UMAP 등, 필요 시)
#     - /api/analyze/cost   : 비용 시뮬레이션
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(analyze.router, prefix="/api/analyze", tags=["ai"])
app.include_router(cost.router, prefix="/api/analyze", tags=["cost"])

# (3) 조언 / 병원 / 이력
#     - /api/advice         : 맞춤 예방법 
#     - /api/nearby/...     : 주변 병원
#     - /api/history/recent : 분석 이력
app.include_router(advice.router, prefix="/api/advice", tags=["advice"]) 
app.include_router(nearby.router, prefix="/api/nearby", tags=["nearby"])
app.include_router(history.router, prefix="/api/history", tags=["history"])