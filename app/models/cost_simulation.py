# app/models/cost_simulation.py
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class CostSimulation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    record_id: Optional[int] = None  # HealthRecord.id 참조(최근 분석 결과)

    # 시나리오 입력
    days_hosp: int = 0
    surgery: bool = False
    icu: bool = False
    rehab_days: int = 0
    disability_rate: float = 0.0     # 0~1
    negligence: float = 0.0          # 0~1

    # 리스크 스냅샷
    p_ane: float
    p_ihd: float
    p_stk: float

    # 출력
    cost_medical: int
    cost_non_economic: int  # 위자료/비경제적 손해
    cost_total: int
    premium_estimate: int    # 보험료 유사 지표(월)
