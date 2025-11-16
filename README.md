# MedAnom Backend (FastAPI)

CSV 업로드 → 이상치 탐지(IsolationForest) → UMAP 2D 임베딩까지 처리하는 FastAPI 백엔드입니다.  
로컬 계정(ID/비번) + **Google Identity Services**(구글 로그인) 인증을 지원하며, 인증 후에만 `/api/analyze` 사용이 가능합니다.

---

## 1) 빠른 시작

### 1-1. 환경 준비
- Python 3.10+ 권장
- (선택) 가상환경
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
`.env` 파일을 루트에 생성 (또는 `.env.example`를 복사)
```env
# .env
JWT_SECRET=change_this_to_a_strong_random_secret
JWT_EXPIRE_MIN=60

# Google Cloud Console에서 발급한 Web Client ID
GOOGLE_CLIENT_ID=YOUR_GOOGLE_CLIENT_ID

# (선택) CORS 도메인 제약을 두고 싶다면 FastAPI CORS 설정에서 allow_origins 수정
```

### 1-4. 실행
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```
- 헬스체크: `GET http://127.0.0.1:8001/api/health` → `{ "status": "ok" }`

---

## 2) Google 로그인 설정

1. Google Cloud Console → **APIs & Services** → **OAuth consent screen**: 앱 정보 설정.
2. **Credentials** → **Create Credentials → OAuth Client ID**
   - Application type: **Web application**
   - Authorized JavaScript origins: 예) `http://localhost:5173`
   - (Popup/One Tap 사용 시 보통 Redirect URI는 불필요)
3. 발급된 **Client ID**를 `.env`의 `GOOGLE_CLIENT_ID`에 설정.

프런트엔드는 `@react-oauth/google`에서 받은 `credential`(ID 토큰)을 `POST /auth/google`로 전달합니다.

---

## 3) API 명세

### 3-1. 인증
#### POST `/auth/login`
- Body(JSON):
  ```json
  { "email": "test@example.com", "password": "pass1234" }
  ```
- Response:
  ```json
  {
    "user": { "id": "u_001", "email": "test@example.com", "name": "Test User" },
    "tokens": { "accessToken": "JWT..." }
  }
  ```
> 샘플 유저: `test@example.com` / `pass1234` (인메모리)

#### POST `/auth/google`
- Body(JSON):
  ```json
  { "credential": "GOOGLE_ID_TOKEN" }
  ```
- 서버는 Google 공개키로 ID 토큰 검증(aud/iss/exp) 후 우리 **accessToken** 발급.
- Response 형식은 `/auth/login`과 동일.

#### GET `/auth/me` (인증 필요)
- Header: `Authorization: Bearer <accessToken>`
- Response:
  ```json
  { "id": "u_001", "email": "test@example.com", "name": "Test User" }
  ```

### 3-2. 분석
#### POST `/api/analyze` (인증 필요, multipart/form-data)
- Form fields:
  - `file`: CSV 파일(필수)
  - `contamination`: 0~0.5 권장 (기본 0.05)
  - `n_neighbors`: UMAP 이웃 수 (기본 15)
  - `min_dist`: UMAP min_dist (기본 0.1)
- Response 예시:
  ```json
  {
    "columns": ["col1","col2", "..."],
    "labels": [1,0,1, ...],          // 1=정상, 0=이상
    "scores": [0.12, 0.88, ...],     // 점수↑ = 이상↑
    "umap": [[x,y], [x,y], ...],     // 2D 임베딩
    "top_features": [["colX", 0.053], ["colY", 0.030], ...],
    "n_rows": 123,
    "user": { "id": "u_001", "email": "test@example.com" }
  }
  ```

---

## 4) cURL 예제

### 4-1. 로컬 로그인
```bash
curl -X POST http://127.0.0.1:8001/auth/login   -H "Content-Type: application/json"   -d '{"email":"test@example.com","password":"pass1234"}'
```
응답의 `tokens.accessToken`을 저장한다.

### 4-2. 분석 호출
```bash
ACCESS=YOUR_ACCESS_TOKEN
curl -X POST http://127.0.0.1:8001/api/analyze   -H "Authorization: Bearer $ACCESS"   -F "file=@/path/to/data.csv"   -F "contamination=0.05"   -F "n_neighbors=15"   -F "min_dist=0.1"
```

---

## 5) 폴더 구조 (간단)
```
.
├─ main.py
├─ requirements.txt
├─ .env               # 로컬 개발용 (민감정보, 절대 커밋 X)
├─ .env.example       # 템플릿 (커밋 O)
└─ README.md
```

> 운영 시: 인메모리 유저 → DB(User 테이블)로 교체, 토큰을 httpOnly Secure 쿠키 기반 세션으로 전환 권장.

---

## 6) 기술 스택
- FastAPI / Uvicorn
- Google Identity Services (ID Token 검증: `google-auth`)
- JWT: `PyJWT`
- Hashing: `passlib[bcrypt]`
- Data: `pandas`, `numpy`, `scikit-learn`, `umap-learn`

---

## 7) 자주 보는 오류
- **401 Invalid Google credential**: `GOOGLE_CLIENT_ID` 불일치, 만료, 로컬/도메인 미등록.
- **CSV 파싱 실패**: 인코딩 문제 → UTF-8-SIG 우선 시도. 헤더 공백 트림 처리.
- **UMAP/Sklearn 설치 문제**: OS별 `scipy` 빌드 에러 → `pip` 최신화, venv 사용 권장.
