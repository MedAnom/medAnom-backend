from sqlmodel import SQLModel, create_engine, Session
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[2] / "db.sqlite"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

def init_db():
    SQLModel.metadata.create_all(engine)

def get_session():
    with Session(engine) as s:
        yield s
# --- [자동 컬럼 추가] measured_at 없을 경우 생성
from sqlalchemy import text

def ensure_measured_at_column():
    with engine.begin() as conn:
        res = conn.exec_driver_sql("PRAGMA table_info(healthrecord);")
        cols = [row[1] for row in res.fetchall()]
        if "measured_at" not in cols:
            conn.exec_driver_sql("ALTER TABLE healthrecord ADD COLUMN measured_at TIMESTAMP NULL;")
            print("[DB] ✅ measured_at 컬럼 추가 완료")

# init_db() 이후 한 번 실행
ensure_measured_at_column()