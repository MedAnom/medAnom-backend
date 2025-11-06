from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    google_sub: Optional[str] = None
    password_hash: Optional[str] = None
