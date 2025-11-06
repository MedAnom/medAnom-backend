# app/schemas/auth.py
from pydantic import BaseModel
from typing import Optional

class Tokens(BaseModel):
    accessToken: str
    refreshToken: Optional[str] = None

class LoginReq(BaseModel):
    email: str
    password: str

class RegisterReq(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class GoogleLoginReq(BaseModel):
    credential: str

class RefreshReq(BaseModel):
    refreshToken: str

class MeRes(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
