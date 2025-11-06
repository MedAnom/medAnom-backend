from pydantic import BaseModel, Field
from typing import Optional

class LoginReq(BaseModel):
    email: str
    password: str

class RegisterReq(BaseModel):
    email: str
    password: str
    name: Optional[str] = None

class GoogleLoginReq(BaseModel):
    credential: str = Field(..., description="Google ID Token(JWT)")

class Tokens(BaseModel):
    accessToken: str
    refreshToken: Optional[str] = None

class MeRes(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
