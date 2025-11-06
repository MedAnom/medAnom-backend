from typing import Dict, Optional
from app.models.user import User
from app.core.security import hash_password

_USERS: Dict[str, User] = {}

def seed_users():
    if "test@example.com" not in _USERS:
        u = User(
            id="u_001",
            email="test@example.com",
            name="Test User",
            password_hash=hash_password("pass1234"),
        )
        _USERS[u.email] = u

def get_by_email(email: str) -> Optional[User]:
    return _USERS.get((email or "").strip().lower())

def save_user(u: User) -> None:
    _USERS[u.email] = u

def next_id() -> str:
    return f"u_{len(_USERS)+1:03d}"
