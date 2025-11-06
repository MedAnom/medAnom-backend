# app/core/security.py
from datetime import datetime, timedelta, timezone
import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(pw: str) -> str:
    return pwd_ctx.hash(pw)

def verify_password(pw: str, pw_hash: str) -> bool:
    return pwd_ctx.verify(pw, pw_hash)

def _now():
    return datetime.now(timezone.utc)

def _encode(payload: dict) -> str:
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)

def _decode(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])

def create_access_token(*, sub: str, email: str) -> str:
    now = _now()
    exp = now + timedelta(minutes=settings.JWT_EXPIRE_MIN)
    return _encode({
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": "medanom-api",
        "typ": "access",
    })

def create_refresh_token(*, sub: str, email: str) -> str:
    now = _now()
    # 기본값 30일(분)
    refresh_minutes = getattr(settings, "JWT_REFRESH_EXPIRE_MIN", 43200)
    exp = now + timedelta(minutes=refresh_minutes)
    return _encode({
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": "medanom-api",
        "typ": "refresh",
    })

def decode_access_token(token: str) -> dict:
    try:
        claims = _decode(token)
        if claims.get("typ") != "access":
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="액세스 토큰이 아닙니다.")
        return claims
    except jwt.ExpiredSignatureError:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    except jwt.InvalidTokenError:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

def decode_refresh_token(token: str) -> dict:
    try:
        claims = _decode(token)
        if claims.get("typ") != "refresh":
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="리프레시 토큰이 아닙니다.")
        return claims
    except jwt.ExpiredSignatureError:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="리프레시 토큰 만료")
    except jwt.InvalidTokenError:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="유효하지 않은 리프레시 토큰")
