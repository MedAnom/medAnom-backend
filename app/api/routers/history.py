# app/api/routers/history.py
from __future__ import annotations
from typing import List
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.db import get_session
from app.models.health_record import HealthRecord
from app.models.user import User

router = APIRouter()

@router.get("/recent")
def recent_history(
    limit: int = Query(30, ge=1, le=200),
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    q = (
        select(HealthRecord)
        .where(HealthRecord.user_id == str(me.id))
        .order_by(HealthRecord.measured_at.desc())
        .order_by(HealthRecord.created_at.desc())
        .limit(limit)
    )
    rows: List[HealthRecord] = session.exec(q).all()

    # ✅ 프론트의 HistoryRow[] 형식으로 반환
    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "measured_at": r.measured_at.isoformat() if r.measured_at else None,
            "sex": r.sex,
            "age": r.age,
            "hgb": r.hgb,
            "tchol": r.tchol,
            "tg": r.tg,
            "hdl": r.hdl,
            "prob": {"ANE": r.prob_ane, "IHD": r.prob_ihd, "STK": r.prob_stk},
            "label": {"ANE": r.label_ane, "IHD": r.label_ihd, "STK": r.label_stk},
            "health_score": r.health_score,
            "summary_text": r.summary_text,
        }
        for r in rows
    ]
