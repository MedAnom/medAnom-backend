# app/api/routers/auth.py
from fastapi import APIRouter, HTTPException, Depends
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    hash_password,
    decode_refresh_token,
)
from app.models.user_store import get_by_email, save_user, next_id
from app.models.user import User
from app.schemas.auth import LoginReq, RegisterReq, GoogleLoginReq, Tokens, MeRes, RefreshReq
from app.api.deps import get_current_user

router = APIRouter()

@router.post("/register", response_model=dict)
def auth_register(req: RegisterReq):
    email = (req.email or "").strip().lower()
    pw = req.password or ""
    name = (req.name or "").strip() or None
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="올바른 이메일을 입력하세요.")
    if len(pw) < 8:
        raise HTTPException(status_code=400, detail="비밀번호는 8자 이상이어야 합니다.")
    if get_by_email(email):
        raise HTTPException(status_code=409, detail="이미 존재하는 이메일입니다.")

    user = User(id=next_id(), email=email, name=name, password_hash=hash_password(pw))
    save_user(user)

    access = create_access_token(sub=user.id, email=user.email)
    refresh = create_refresh_token(sub=user.id, email=user.email)
    return {
        "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
        "tokens": Tokens(accessToken=access, refreshToken=refresh).model_dump(),
    }

@router.post("/login", response_model=dict)
def auth_login(req: LoginReq):
    email = (req.email or "").strip().lower()
    user = get_by_email(email)
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    access = create_access_token(sub=user.id, email=user.email)
    refresh = create_refresh_token(sub=user.id, email=user.email)
    return {
        "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
        "tokens": Tokens(accessToken=access, refreshToken=refresh).model_dump(),
    }

@router.get("/me", response_model=MeRes)
def auth_me(user: User = Depends(get_current_user)):
    return MeRes(id=user.id, email=user.email, name=user.name)

@router.post("/google", response_model=dict)
def auth_google(req: GoogleLoginReq):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="서버 미설정: GOOGLE_CLIENT_ID 없음")
    try:
        claims = id_token.verify_oauth2_token(req.credential, grequests.Request(), settings.GOOGLE_CLIENT_ID)
        if claims.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise ValueError("Invalid audience")
        if claims.get("iss") not in ["https://accounts.google.com", "accounts.google.com"]:
            raise ValueError("Invalid issuer")
        email = claims.get("email")
        email_verified = claims.get("email_verified", False)
        sub = claims.get("sub")
        name = claims.get("name")
        if not email or not email_verified:
            raise ValueError("이메일 검증 실패")

        user = get_by_email(email)
        if not user:
            user = User(id=next_id(), email=email, name=name, google_sub=sub)
            save_user(user)
        elif not user.google_sub:
            user.google_sub = sub
            save_user(user)

        access = create_access_token(sub=user.id, email=user.email)
        refresh = create_refresh_token(sub=user.id, email=user.email)
        return {
            "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
            "tokens": Tokens(accessToken=access, refreshToken=refresh).model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google credential: {e}")

@router.post("/refresh", response_model=dict)
def auth_refresh(body: RefreshReq):
    # refresh 검증
    claims = decode_refresh_token(body.refreshToken)
    email = claims.get("email")
    sub = claims.get("sub")
    user = get_by_email(email) if email else None
    if not user or user.id != sub:
        raise HTTPException(status_code=401, detail="리프레시 토큰 검증 실패")

    # access 재발급 (+ 선택: refresh도 로테이트 가능)
    new_access = create_access_token(sub=user.id, email=user.email)
    return {
        "tokens": Tokens(accessToken=new_access, refreshToken=body.refreshToken).model_dump()
    }
