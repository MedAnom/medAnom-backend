
# MedAnom Backend (FastAPI)

CSV 업로드를 통해 **이상치 탐지(IsolationForest)** 및 **UMAP 2D 임베딩 시각화**까지 수행하는  
연구·분석용 FastAPI 백엔드입니다.

본 백엔드는 **로컬 계정(ID/비밀번호)** 과  
**Google Identity Services(구글 로그인)** 인증을 모두 지원하며,  
인증된 사용자만 `/api/analyze` 엔드포인트에 접근할 수 있습니다.

---

## 1. 빠른 시작 (Quick Start)

### 1-1. 환경 준비
- Python **3.10 이상** 권장
- (선택) 가상환경 사용
```bash
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
```

### 1-2. 패키지 설치
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 1-3. 환경변수(.env) 설정
루트 디렉토리에 `.env` 파일 생성  
(`.env.example`을 복사하여 사용 권장)

```env
# JWT 설정
JWT_SECRET=change_this_to_a_strong_random_secret
JWT_EXPIRE_MIN=60

# Google Cloud Console에서 발급한 Web Client ID
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID
```

> ⚠️ `.env` 파일은 민감 정보가 포함되므로 **절대 커밋하지 않습니다.**

### 1-4. 서버 실행
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

- 헬스체크:
```
GET http://127.0.0.1:8001/api/health
→ { "status": "ok" }
```

---

## 2. Google 로그인 설정

1. **Google Cloud Console**
   - APIs & Services → OAuth consent screen
   - 앱 이름, 이메일 등 기본 정보 설정

2. **Credentials → Create Credentials → OAuth Client ID**
   - Application type: **Web application**
   - Authorized JavaScript origins:
     - 예: `http://localhost:5173`
   - (Popup / One Tap 방식 사용 시 Redirect URI 불필요)

3. 발급된 **Client ID**를 `.env`의 `GOOGLE_CLIENT_ID`에 설정

프런트엔드에서는  
`@react-oauth/google`에서 발급된 `credential(ID Token)`을  
`POST /auth/google`로 전달합니다.

---

## 3. API 명세

### 3-1. 인증(Authentication)

#### POST `/auth/login`
로컬 계정 로그인

**Request (JSON)**
```json
{
  "email": "test@example.com",
  "password": "pass1234"
}
```

**Response**
```json
{
  "user": {
    "id": "u_001",
    "email": "test@example.com",
    "name": "Test User"
  },
  "tokens": {
    "accessToken": "JWT_TOKEN"
  }
}
```

> 테스트 계정  
> `test@example.com / pass1234` (인메모리 유저)

---

#### POST `/auth/google`
Google 로그인

**Request (JSON)**
```json
{
  "credential": "GOOGLE_ID_TOKEN"
}
```

- Google 공개키로 ID Token 검증 (`aud`, `iss`, `exp`)
- 검증 성공 시 자체 **JWT accessToken** 발급

**Response**
- `/auth/login`과 동일한 구조

---

#### GET `/auth/me` (인증 필요)

**Header**
```
Authorization: Bearer <accessToken>
```

**Response**
```json
{
  "id": "u_001",
  "email": "test@example.com",
  "name": "Test User"
}
```

---

### 3-2. 이상치 분석

#### POST `/api/analyze`
CSV 기반 이상치 탐지 및 UMAP 시각화  
(인증 필요, `multipart/form-data`)

**Form fields**
- `file` : CSV 파일 (필수)
- `contamination` : 이상치 비율 (0~0.5 권장, 기본 0.05)
- `n_neighbors` : UMAP 이웃 수 (기본 15)
- `min_dist` : UMAP 최소 거리 (기본 0.1)

**Response 예시**
```json
{
  "columns": ["col1", "col2", "..."],
  "labels": [1, 0, 1],
  "scores": [0.12, 0.88, 0.31],
  "umap": [[1.2, -0.3], [0.1, 2.4], [-1.1, 0.7]],
  "top_features": [["colX", 0.053], ["colY", 0.030]],
  "n_rows": 123,
  "user": {
    "id": "u_001",
    "email": "test@example.com"
  }
}
```

- `labels`: 1 = 정상, 0 = 이상
- `scores`: 값이 클수록 이상치 성향 ↑

---

## 4. cURL 예제

### 4-1. 로컬 로그인
```bash
curl -X POST http://127.0.0.1:8001/auth/login   -H "Content-Type: application/json"   -d '{"email":"test@example.com","password":"pass1234"}'
```

### 4-2. 분석 요청
```bash
ACCESS=YOUR_ACCESS_TOKEN

curl -X POST http://127.0.0.1:8001/api/analyze   -H "Authorization: Bearer $ACCESS"   -F "file=@/path/to/data.csv"   -F "contamination=0.05"   -F "n_neighbors=15"   -F "min_dist=0.1"
```

---

## 5. 프로젝트 구조

```
.
├─ app/
│  ├─ main.py
│  ├─ api/
│  ├─ auth/
│  └─ services/
├─ requirements.txt
├─ .env.example
└─ README.md
```

> 운영 환경에서는  
> - 인메모리 유저 → **DB(User 테이블)**  
> - JWT Header 방식 → **httpOnly Secure Cookie 기반 세션**  
> 전환을 권장합니다.

---

## 6. 기술 스택

- **Backend**: FastAPI, Uvicorn
- **Auth**: Google Identity Services, PyJWT
- **Data / ML**:
  - pandas, numpy
  - scikit-learn (IsolationForest)
  - umap-learn




