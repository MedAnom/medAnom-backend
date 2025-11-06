from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token
from app.models.user_store import get_by_email
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")  # 실제 로그인 엔드포인트

def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    claims = decode_access_token(token)
    email = claims.get("email")
    user = get_by_email(email) if email else None
    if not user:
        raise HTTPException(status_code=401, detail="인증 실패")
    return user
