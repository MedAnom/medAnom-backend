# reset_db.py
"""
건강 기록 DB 초기화 스크립트
사용법: python reset_db.py
"""
from pathlib import Path
from sqlmodel import Session, select, delete
from app.core.db import engine, init_db
from app.models.health_record import HealthRecord

def reset_health_records():
    """모든 건강 기록 삭제"""
    init_db()
    
    with Session(engine) as session:
        # 기존 레코드 개수 확인
        stmt = select(HealthRecord)
        existing = session.exec(stmt).all()
        count = len(existing)
        
        if count == 0:
            print("❌ 삭제할 건강 기록이 없습니다.")
            return
        
        print(f"⚠️  {count}개의 건강 기록을 삭제합니다...")
        
        # 확인 요청
        confirm = input("정말로 삭제하시겠습니까? (yes/no): ")
        if confirm.lower() != "yes":
            print("❌ 취소되었습니다.")
            return
        
        # 모든 레코드 삭제
        stmt = delete(HealthRecord)
        session.exec(stmt)
        session.commit()
        
        print(f"✅ {count}개의 건강 기록이 삭제되었습니다.")
        print("💡 이제 새로운 분석을 진행하면 올바른 점수가 계산됩니다.")

if __name__ == "__main__":
    reset_health_records()