from fastapi import APIRouter, HTTPException
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from app.core.config import settings
from app.core.security import create_access_token, verify_password, hash_password
from app.models.user_store import get_by_email, save_user, next_id
from app.models.user import User
from app.schemas.auth import LoginReq, RegisterReq, GoogleLoginReq, Tokens, MeRes

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
    return {
        "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
        "tokens": Tokens(accessToken=access).model_dump(),
    }

@router.post("/login", response_model=dict)
def auth_login(req: LoginReq):
    user = get_by_email(req.email)
    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    access = create_access_token(sub=user.id, email=user.email)
    return {
        "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
        "tokens": Tokens(accessToken=access).model_dump(),
    }

@router.get("/me", response_model=MeRes)
def auth_me(user: User = ...):
    # /auth/me는 deps.get_current_user로 보호 → analyze 라우터 참고
    # 여기선 라우터만 두고, 실제 보호는 analyze에서 보여줌.
    raise HTTPException(status_code=501, detail="Use /api/analyze to verify auth.")
    # 필요하면 /auth/me를 별도 router로 분리해서 deps 적용해도 됨.

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
        return {
            "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
            "tokens": Tokens(accessToken=access).model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google credential: {e}")
