from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class HealthRecord(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

    sex: int
    age: int
    hgb: float
    tchol: int
    tg: int
    hdl: int

    sleep_hours: Optional[float] = None
    exercise_days: Optional[int] = None
    smoking: Optional[bool] = None
    alcohol_per_week: Optional[int] = None
    stress: Optional[int] = None

    prob_ane: float
    prob_ihd: float
    prob_stk: float
    label_ane: int
    label_ihd: int
    label_stk: int
    health_score: int
    summary_text: str
