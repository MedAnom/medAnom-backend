# app/core/config.py
import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# ----------------------------------------
# 🌱 .env 로드
# ----------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # 프로젝트 루트 추정
env_path = BASE_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"[BOOT] ✅ .env 파일 로드 성공: {env_path}")
else:
    print(f"[BOOT] ⚠️ .env 파일을 찾을 수 없음: {env_path}")

# ----------------------------------------
# ⚙️ 설정 클래스
# ----------------------------------------
class Settings(BaseModel):
    ENV: str = os.getenv("ENV", "dev")
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    # JWT 설정
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-me")
    JWT_EXPIRE_MIN: int = int(os.getenv("JWT_EXPIRE_MIN", "60"))
    JWT_REFRESH_EXPIRE_MIN: int = int(os.getenv("JWT_REFRESH_EXPIRE_MIN", "43200"))
    JWT_ALG: str = os.getenv("JWT_ALG", "HS256")

    # Google
    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ]

# ----------------------------------------
# ✅ 인스턴스 생성 및 로드 상태 출력
# ----------------------------------------
settings = Settings()

print("[BOOT] ✅ 환경변수 로드 상태 확인")
print(f" - ENV = {settings.ENV}")
print(f" - GOOGLE_CLIENT_ID = {(settings.GOOGLE_CLIENT_ID[:30] + '...') if settings.GOOGLE_CLIENT_ID else '❌ 비어있음'}")
print(f" - CORS_ORIGINS = {settings.CORS_ORIGINS}")
print("--------------------------------------------------\n")
