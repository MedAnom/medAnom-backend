# app/api/routers/health.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List

import json
import joblib
import numpy as np
from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, conint, confloat
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.db import get_session, init_db
from app.models.health_record import HealthRecord
from app.models.user import User

router = APIRouter()

ART = Path(__file__).resolve().parents[2] / "artifacts"
TARGETS = ["ANE", "IHD", "STK"]

_models: Dict[str, object] = {}
_thresholds: Dict[str, float] = {}


def age_to_group(age: int) -> int:
    """0~120세 나이를 10년 단위 그룹(0~10)으로 변환"""
    return int(min(max(age, 0) // 10, 10))


def simple_summary(risks, anomalies, lifestyle) -> str:
    msgs = []
    # 위험도 요약
    top = max(risks.items(), key=lambda kv: kv[1]["prob"])
    msgs.append(f"가장 높은 위험도는 {top[0]}이며, 확률은 {round(top[1]['prob'] * 100)}%입니다.")
    # 이상치 포인트(간단 표시)
    warns = [k for k, v in anomalies.items() if v.get("warn")]
    if warns:
        msgs.append(f"주의가 필요한 지표: {', '.join(warns)}")
    # 생활습관 코멘트
    if lifestyle:
        if lifestyle.get("smoking"):
            msgs.append("흡연은 심혈관 위험을 높일 수 있어요.")
        if (lifestyle.get("exercise_days") or 0) < 2:
            msgs.append("주 2~3회 이상 유산소 운동을 권장합니다.")
        if (lifestyle.get("sleep_hours") or 0) < 6:
            msgs.append("수면 시간이 짧으면 대사 건강에 좋지 않습니다.")
    msgs.append("개인 건강 정보이며, 의료 조언이 필요하면 전문가와 상담하세요.")
    return " ".join(msgs)


@router.on_event("startup")
def _load():
    """모델과 임계값 로딩"""
    init_db()
    try:
        for t in TARGETS:
            _models[t] = joblib.load(ART / f"model_{t}.pkl")
        with open(ART / "thresholds.json", "r", encoding="utf-8") as f:
            tj = json.load(f)
        global _thresholds
        _thresholds = {k: float(v["threshold"]) for k, v in tj.items()}
    except Exception as e:
        raise RuntimeError(f"모델 로딩 실패: {e}")


class Input(BaseModel):
    # 기본 지표
    SEX: conint(ge=0, le=1)
    AGE: conint(ge=0, le=120)
    HGB: confloat(ge=0, le=30)
    TCHOL: conint(ge=0, le=1000)
    TG: conint(ge=0, le=3000)
    HDL: conint(ge=0, le=200)
    # 생활습관(선택)
    sleep_hours: Optional[confloat(ge=0, le=24)] = None
    exercise_days: Optional[conint(ge=0, le=7)] = None
    smoking: Optional[bool] = None
    alcohol_per_week: Optional[conint(ge=0, le=14)] = None
    stress: Optional[conint(ge=1, le=5)] = None
    # 검사일(선택, 없으면 서버 created_at 사용)
    measured_at: Optional[datetime] = None


@router.post("/analyze/health")
def analyze_health(
    payload: Input,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not _models:
        raise HTTPException(503, "모델 준비 중")

    # 입력 전처리
    age_g = age_to_group(int(payload.AGE))
    x = np.array(
        [payload.SEX, age_g, payload.HGB, payload.TCHOL, payload.TG, payload.HDL],
        dtype=float,
    ).reshape(1, -1)

    # 예측
    risks: Dict[str, Dict[str, float | int]] = {}
    for t in TARGETS:
        p1 = float(_models[t].predict_proba(x)[0, 1])
        thr = _thresholds.get(t, 0.5)
        risks[t] = {"prob": round(p1, 4), "label": int(p1 >= thr), "thr": float(thr)}

    # 간단 이상치: 추천 범위를 벗어나면 warn (도메인 기준)
    anomalies = {
        "HGB": {"warn": payload.HGB < 11 or payload.HGB > 17},
        "TCHOL": {"warn": payload.TCHOL >= 200},
        "TG": {"warn": payload.TG >= 150},
        "HDL": {
            "warn": (payload.SEX == 1 and payload.HDL < 40)
            or (payload.SEX == 0 and payload.HDL < 50)
        },
    }
    warn_cnt = sum(1 for v in anomalies.values() if v["warn"])
    health_score = max(
        0,
        100 - int(max(risks[t]["prob"] for t in TARGETS) * 50) - warn_cnt * 5,
    )

    lifestyle = {
        "sleep_hours": payload.sleep_hours,
        "exercise_days": payload.exercise_days,
        "smoking": payload.smoking,
        "alcohol_per_week": payload.alcohol_per_week,
        "stress": payload.stress,
    }
    summary_text = simple_summary(risks, anomalies, lifestyle)

    # DB 저장
    rec = HealthRecord(
        user_id=str(me.id),
        sex=int(payload.SEX),
        age=int(payload.AGE),
        hgb=float(payload.HGB),
        tchol=int(payload.TCHOL),
        tg=int(payload.TG),
        hdl=int(payload.HDL),
        sleep_hours=float(payload.sleep_hours) if payload.sleep_hours is not None else None,
        exercise_days=int(payload.exercise_days) if payload.exercise_days is not None else None,
        smoking=payload.smoking,
        alcohol_per_week=int(payload.alcohol_per_week) if payload.alcohol_per_week is not None else None,
        stress=int(payload.stress) if payload.stress is not None else None,
        prob_ane=float(risks["ANE"]["prob"]),
        prob_ihd=float(risks["IHD"]["prob"]),
        prob_stk=float(risks["STK"]["prob"]),
        label_ane=int(risks["ANE"]["label"]),
        label_ihd=int(risks["IHD"]["label"]),
        label_stk=int(risks["STK"]["label"]),
        health_score=int(health_score),
        summary_text=summary_text,
        measured_at=payload.measured_at,  
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)

    return {
        "risks": risks,
        "anomalies": anomalies,
        "summary": {"health_score": health_score, "text": summary_text},
        "record_id": rec.id,
    }


@router.get("/history/recent")
def recent_history(
    limit: int = Query(30, ge=1, le=200),
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    """
    최근 기록 – measured_at이 있는 경우 이를 우선 정렬/표시.
    measured_at DESC, created_at DESC 순서로 소팅.
    """
    # 정렬 기준: measured_at이 NULL이면 created_at을 사용하도록 두 단계 정렬
    q = (
        select(HealthRecord)
        .where(HealthRecord.user_id == str(me.id))
        .order_by(HealthRecord.measured_at.desc())  # NULL 우선순위는 DB별 상이, 아래 created_at로 보완
        .order_by(HealthRecord.created_at.desc())
        .limit(limit)
    )
    rows: List[HealthRecord] = session.exec(q).all()

    return [
        {
            "id": r.id,
            "created_at": r.created_at.isoformat(),
            "measured_at": r.measured_at.isoformat() if r.measured_at else None,  # ✅ 추가
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
