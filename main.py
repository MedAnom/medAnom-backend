# main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from typing import List, Tuple, Optional, Dict
from datetime import datetime, timedelta
import os
import pandas as pd
import numpy as np
import jwt

from passlib.context import CryptContext
from google.oauth2 import id_token
from google.auth.transport import requests as grequests

from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import IsolationForest
import umap

# ---------------------------
# 기본 설정 / 시크릿 / 보안
# ---------------------------
JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
JWT_EXPIRE_MIN = int(os.getenv("JWT_EXPIRE_MIN", "60"))
JWT_ALG = "HS256"
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")  # 표준폼 아님, 의존성에만 사용

app = FastAPI(title="MedAnom API")

# --- CORS (프론트 연결용) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 개발 중엔 * 허용. 운영 시 FE 도메인만 허용
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# 인메모리 유저 저장소 (예시)
# 운영 시 DB로 교체
# ---------------------------
class User(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    google_sub: Optional[str] = None
    password_hash: Optional[str] = None

# 샘플 유저 1명: email=test@example.com / pw=pass1234
USERS: Dict[str, User] = {}
def _seed_users():
    u = User(
        id="u_001",
        email="test@example.com",
        name="Test User",
        password_hash=pwd_ctx.hash("pass1234"),
    )
    USERS[u.email] = u
_seed_users()

# ---------------------------
# 모델 & 유틸
# ---------------------------
class LoginReq(BaseModel):
    email: str
    password: str

class GoogleLoginReq(BaseModel):
    credential: str = Field(..., description="Google ID Token(JWT)")

class Tokens(BaseModel):
    accessToken: str
    refreshToken: Optional[str] = None  # 확장 여지

class MeRes(BaseModel):
    id: str
    email: str
    name: Optional[str] = None

def create_access_token(sub: str, email: str) -> str:
    now = datetime.utcnow()
    exp = now + timedelta(minutes=JWT_EXPIRE_MIN)
    payload = {
        "sub": sub,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": "medanom-api",
        "typ": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="토큰이 만료되었습니다.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="유효하지 않은 토큰입니다.")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    claims = decode_access_token(token)
    email = claims.get("email")
    if not email or email not in USERS:
        raise HTTPException(status_code=401, detail="인증 실패")
    return USERS[email]

# ---------------------------
# 헬스체크
# ---------------------------
@app.get("/api/health")
def health():
    return {"status": "ok"}

# ---------------------------
# 인증 API
# ---------------------------
@app.post("/auth/login", response_model=dict)
def auth_login(req: LoginReq):
    user = USERS.get(req.email)
    if not user or not user.password_hash or not pwd_ctx.verify(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="이메일 또는 비밀번호가 올바르지 않습니다.")
    access = create_access_token(sub=user.id, email=user.email)
    return {
        "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
        "tokens": Tokens(accessToken=access).model_dump(),
    }

@app.get("/auth/me", response_model=MeRes)
def auth_me(me: User = Depends(get_current_user)):
    return MeRes(id=me.id, email=me.email, name=me.name)

@app.post("/auth/google", response_model=dict)
def auth_google(req: GoogleLoginReq):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="서버 미설정: GOOGLE_CLIENT_ID 없음")

    try:
        claims = id_token.verify_oauth2_token(
            req.credential, grequests.Request(), GOOGLE_CLIENT_ID
        )
        # aud/iss 확인
        if claims.get("aud") != GOOGLE_CLIENT_ID:
            raise ValueError("Invalid audience")
        if claims.get("iss") not in ["https://accounts.google.com", "accounts.google.com"]:
            raise ValueError("Invalid issuer")
        email = claims.get("email")
        email_verified = claims.get("email_verified", False)
        sub = claims.get("sub")
        name = claims.get("name")

        if not email or not email_verified:
            raise ValueError("이메일 검증 실패")

        # 유저 연동(존재하면 사용, 없으면 생성)
        user = USERS.get(email)
        if not user:
            user = User(id=f"u_{len(USERS)+1:03d}", email=email, name=name, google_sub=sub)
            USERS[email] = user
        else:
            if not user.google_sub:
                user.google_sub = sub  # 최초 연동

        access = create_access_token(sub=user.id, email=user.email)
        return {
            "user": MeRes(id=user.id, email=user.email, name=user.name).model_dump(),
            "tokens": Tokens(accessToken=access).model_dump(),
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid Google credential: {e}")

# ---------------------------
# CSV 업로드/분석 로직
# ---------------------------
def _load_csv(upload: UploadFile) -> pd.DataFrame:
    try:
        try:
            df = pd.read_csv(upload.file, encoding="utf-8-sig")
        except Exception:
            upload.file.seek(0)
            df = pd.read_csv(upload.file)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV 파싱 실패: {e}")

def _select_numeric(df: pd.DataFrame) -> pd.DataFrame:
    X = df.select_dtypes(include=[np.number]).copy()
    if X.empty:
        raise HTTPException(status_code=400, detail="숫자형 컬럼이 없습니다. (혈압/혈당/지질 등 숫자열 필요)")
    X = X.dropna(axis=1, how="all")
    X = X.fillna(X.median(numeric_only=True))
    return X

def _permutation_importance(iforest: IsolationForest, Xs: np.ndarray, columns: List[str], seed: int = 42) -> List[Tuple[str, float]]:
    base = -iforest.score_samples(Xs).mean()
    rng = np.random.default_rng(seed)
    imps: List[Tuple[str, float]] = []
    n_feat = Xs.shape[1]
    max_cols = min(n_feat, 30)
    for i in range(max_cols):
        Xperm = Xs.copy()
        rng.shuffle(Xperm[:, i])
        s = -iforest.score_samples(Xperm).mean()
        imps.append((columns[i], float(s - base)))
    imps.sort(key=lambda x: x[1], reverse=True)
    return imps[:10]

@app.post("/api/analyze")
async def analyze(
    file: UploadFile = File(...),
    contamination: float = Form(0.05),
    n_neighbors: int = Form(15),
    min_dist: float = Form(0.1),
    me: User = Depends(get_current_user),  # 🔒 인증 필수
):
    # 1) CSV 로드
    df = _load_csv(file)
    n_rows = len(df)

    # 2) 숫자 컬럼만 추출 + 전처리
    X = _select_numeric(df)
    columns = list(X.columns)

    # 3) 스케일링
    scaler = RobustScaler()
    Xs = scaler.fit_transform(X.values)

    # 4) 이상탐지 (IsolationForest)
    if contamination <= 0 or contamination >= 0.5:
        raise HTTPException(status_code=400, detail="contamination은 (0, 0.5) 범위가 권장됩니다.")
    iforest = IsolationForest(
        contamination=contamination,
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )
    pred = iforest.fit_predict(Xs)      # 1=정상, -1=이상
    labels = (pred == 1).astype(int)    # 1=정상, 0=이상 (프론트 규약)
    scores = (-iforest.score_samples(Xs)).astype(float).tolist()

    # 5) UMAP 임베딩 (2D)
    reducer = umap.UMAP(
        n_neighbors=int(n_neighbors),
        min_dist=float(min_dist),
        random_state=42,
        n_components=2,
        metric="euclidean",
        verbose=False,
    )
    emb = reducer.fit_transform(Xs).tolist()

    # 6) 간단 변수 중요도 (Permutation)
    imp = _permutation_importance(iforest, Xs, columns)

    return {
        "columns": columns,
        "labels": labels.tolist(),
        "scores": scores,
        "umap": emb,
        "top_features": imp,
        "n_rows": int(n_rows),
        "user": {"id": me.id, "email": me.email},  # 예시: 호출자 정보
    }
