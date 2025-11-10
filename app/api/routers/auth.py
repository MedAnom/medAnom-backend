# app/api/routers/auth.py
from fastapi import APIRouter, HTTPException, Depends
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
import traceback, sys

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
from app.schemas.auth import (
    LoginReq, RegisterReq, GoogleLoginReq,
    Tokens, MeRes, RefreshReq
)
from app.api.deps import get_current_user


router = APIRouter()

# ------------------------------
# 🌱 .env 로딩 확인용 로그
# ------------------------------
print("[BOOT] ✅ 환경변수 로드 상태 확인")
print(f" - GOOGLE_CLIENT_ID: {settings.GOOGLE_CLIENT_ID[:30]}..." if settings.GOOGLE_CLIENT_ID else " - GOOGLE_CLIENT_ID ❌ 비어있음")
print(f" - CORS_ORIGINS: {settings.CORS_ORIGINS}")
print("--------------------------------------------------\n")


@router.post("/register", response_model=dict)
def auth_register(req: RegisterReq):
    email = (req.email or "").strip().lower()
    pw = req.password or ""
    name = (req.name or "").strip() or None

    print(f"[REGISTER] email={email}, name={name}")

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

    print(f"[REGISTER] ✅ user={user.email} 등록 완료")
    return {
        "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
        "tokens": Tokens(accessToken=access, refreshToken=refresh).model_dump(),
    }


@router.post("/login", response_model=dict)
def auth_login(req: LoginReq):
    email = (req.email or "").strip().lower()
    print(f"[LOGIN] email={email}")
    user = get_by_email(email)

    if not user or not user.password_hash or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")

    access = create_access_token(sub=user.id, email=user.email)
    refresh = create_refresh_token(sub=user.id, email=user.email)
    print(f"[LOGIN] ✅ 로그인 성공: {email}")

    return {
        "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
        "tokens": Tokens(accessToken=access, refreshToken=refresh).model_dump(),
    }


@router.get("/me", response_model=MeRes)
def auth_me(user: User = Depends(get_current_user)):
    print(f"[ME] {user.email}")
    return MeRes(id=user.id, email=user.email, name=user.name)


# ------------------------------
# 🔍 GOOGLE LOGIN 디버깅 버전
# ------------------------------
@router.post("/google", response_model=dict)
def auth_google(req: GoogleLoginReq):
    print("\n[GoogleLogin] ▶ 요청 수신")

    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="서버 미설정: GOOGLE_CLIENT_ID 없음")

    # credential 비었는지 검사
    if not req.credential:
        print("[GoogleLogin][ERROR] credential 없음 (프론트 403 또는 origin 문제)")
        raise HTTPException(status_code=400, detail="Google credential 없음(승인된 origin 설정 확인)")

    try:
        print("[GoogleLogin] 🔑 토큰 검증 시작")
        claims = id_token.verify_oauth2_token(
            req.credential, grequests.Request(), settings.GOOGLE_CLIENT_ID
        )

        aud = claims.get("aud")
        iss = claims.get("iss")
        email = claims.get("email")
        email_verified = claims.get("email_verified", False)
        sub = claims.get("sub")
        name = claims.get("name")

        # 클레임 정보 출력
        print(f"[GoogleLogin] aud={aud}")
        print(f"[GoogleLogin] iss={iss}")
        print(f"[GoogleLogin] email={email}, verified={email_verified}")

        # 검증
        if aud != settings.GOOGLE_CLIENT_ID:
            print("[GoogleLogin][ERROR] aud 불일치")
            raise HTTPException(status_code=401, detail="Google aud 불일치(클라이언트ID 확인)")
        if iss not in ["https://accounts.google.com", "accounts.google.com"]:
            print("[GoogleLogin][ERROR] iss 불일치")
            raise HTTPException(status_code=401, detail="Google iss 불일치")
        if not email or not email_verified:
            print("[GoogleLogin][ERROR] 이메일 미인증")
            raise HTTPException(status_code=401, detail="Google 이메일 미인증")

        # 사용자 upsert
        user = get_by_email(email)
        if not user:
            print(f"[GoogleLogin] 신규 사용자: {email}")
            user = User(id=next_id(), email=email, name=name, google_sub=sub)
            save_user(user)
        else:
            print(f"[GoogleLogin] 기존 사용자: {email}")
            if not user.google_sub:
                user.google_sub = sub
                save_user(user)

        # 토큰 발급
        access = create_access_token(sub=user.id, email=user.email)
        refresh = create_refresh_token(sub=user.id, email=user.email)

        print(f"[GoogleLogin] ✅ 로그인 성공: {email}")
        return {
            "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
            "tokens": Tokens(accessToken=access, refreshToken=refresh).model_dump(),
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        # 예외 trace 전부 출력
        tb = "".join(traceback.format_exception(*sys.exc_info()))
        print("[GoogleLogin][EXCEPTION]", e)
        print(tb)
        raise HTTPException(status_code=500, detail=f"Google 로그인 처리 중 서버 오류: {e}")


@router.post("/refresh", response_model=dict)
def auth_refresh(body: RefreshReq):
    print("[REFRESH] 토큰 재발급 시도")

    claims = decode_refresh_token(body.refreshToken)
    email = claims.get("email")
    sub = claims.get("sub")

    user = get_by_email(email) if email else None
    if not user or user.id != sub:
        raise HTTPException(status_code=401, detail="리프레시 토큰 검증 실패")

    new_access = create_access_token(sub=user.id, email=user.email)
    print(f"[REFRESH]  {email} access 토큰 재발급 완료")

    return {
        "tokens": Tokens(accessToken=new_access, refreshToken=body.refreshToken).model_dump()
    }
