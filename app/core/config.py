# app/core/config.py
import os
import json
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# ----------------------------------------
# 🌱 .env 로드
# ----------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # repo root 예상
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[BOOT] ✅ .env 파일 로드 성공: {env_path}")
else:
    print(f"[BOOT] ⚠️ .env 파일을 찾을 수 없음: {env_path}")

def _parse_cors(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        # JSON 배열 문자열 형태 지원: '["http://localhost:5173"]'
        v = json.loads(raw)
        if isinstance(v, list):
            return [str(x) for x in v]
    except Exception:
        pass
    return [p.strip() for p in raw.split(",") if p.strip()]

class Settings(BaseModel):
    ENV: str = os.getenv("ENV", "dev")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))
    JWT_REFRESH_EXPIRE_MIN: int = int(os.getenv("JWT_REFRESH_EXPIRE_MIN", "43200"))
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")

    # Google
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # Kakao Local REST API
    KAKAO_REST_KEY: str = os.getenv("KAKAO_REST_KEY", "")
    KAKAO_HOST: str = os.getenv("KAKAO_HOST", "https://dapi.kakao.com")

    # CORS
    CORS_ORIGINS: list[str] = _parse_cors(os.getenv("CORS_ORIGINS")) or [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

settings = Settings()

def _mask(s: str, keep: int = 4) -> str:
    if not s:
        return "❌ 비어있음"
    return s[:keep] + "…" if len(s) > keep else s

print("[BOOT] ✅ 환경변수 로드 상태 확인")
print(f" - ENV = {settings.ENV}")
print(f" - GOOGLE_CLIENT_ID = {_mask(settings.GOOGLE_CLIENT_ID)}")
print(f" - KAKAO_REST_KEY   = {_mask(settings.KAKAO_REST_KEY)}")
print(f" - KAKAO_HOST       = {settings.KAKAO_HOST}")
print(f" - CORS_ORIGINS     = {settings.CORS_ORIGINS}")
print("--------------------------------------------------\n")
