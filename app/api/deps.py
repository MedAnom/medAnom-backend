# app/api/deps.py
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_access_token
from app.models.user_store import get_by_email
from app.models.user import User

security = HTTPBearer(auto_error=True)

def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> User:
    token = creds.credentials
    claims = decode_access_token(token)  # access 전용 검사
    email = claims.get("email")
    user = get_by_email(email) if email else None
    if not user:
        raise HTTPException(status_code=401, detail="인증 실패")
    return user
