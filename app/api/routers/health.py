# app/api/routers/health.py
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import json

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, conint, confloat
from sqlmodel import Session

from app.api.deps import get_current_user
from app.core.db import get_session, init_db
from app.models.health_record import HealthRecord
from app.models.user import User

router = APIRouter()

ART = Path(__file__).resolve().parents[2] / "artifacts"
DATA = Path(__file__).resolve().parents[2] / "data"
TRAIN_CSV = DATA / "혈액검사데이터_train.csv"

TARGETS = ["ANE", "IHD", "STK"]
FEATURES = ["SEX", "AGE_G", "HGB", "TCHOL", "TG", "HDL"]

_models: Dict[str, object] = {}
_thresholds: Dict[str, float] = {}
_train_df: pd.DataFrame | None = None
_prob_ref: Dict[str, np.ndarray] = {}

# 각 질환이 어떤 지표와 연결되는지
_RELATED_ANOM = {
    "ANE": ["HGB"],
    "IHD": ["TCHOL", "TG", "HDL"],
    "STK": ["TCHOL", "TG", "HDL"],
}


def age_to_group(age: int) -> int:
    return int(min(max(age, 0) // 10, 10))


def _percentile_of(arr: np.ndarray, val: float) -> float:
    if arr.size == 0:
        return float("nan")
    return float((arr < val).sum() / arr.size * 100.0)


def _peer_stats(df: pd.DataFrame, sex: int, age_g: int, patient: dict) -> dict:
    peers = df[(df["SEX"] == sex) & (df["AGE_G"] == age_g)]
    if len(peers) < 30:
        peers = df[df["SEX"] == sex]
    out: Dict[str, Optional[dict]] = {}
    for k in ["TCHOL", "TG", "HDL", "HGB"]:
        peer_values = peers[k].dropna().astype(float).to_numpy()
        if peer_values.size == 0:
            out[k] = None
            continue
        your = float(patient[k])
        pct = float((peer_values < your).sum() / peer_values.size * 100.0)
        out[k] = {
            "your_value": your,
            "peer_mean": float(peer_values.mean()),
            "peer_median": float(np.median(peer_values)),
            "percentile": pct,
            "sample_size": int(peer_values.size),
        }
    return out


@router.on_event("startup")
def _load():
    init_db()
    try:
        for t in TARGETS:
            _models[t] = joblib.load(ART / f"model_{t}.pkl")
        with open(ART / "thresholds.json", "r", encoding="utf-8") as f:
            tj = json.load(f)
        global _thresholds
        _thresholds = {k: float(v["threshold"]) for k, v in tj.items()}

        global _train_df, _prob_ref
        df = pd.read_csv(TRAIN_CSV)
        df = df[[*FEATURES, *TARGETS]].dropna()
        df["AGE_G"] = df["AGE_G"].astype(int)
        _train_df = df.copy()

        X = df[FEATURES].astype(float).to_numpy()
        for t in TARGETS:
            _prob_ref[t] = _models[t].predict_proba(X)[:, 1]
    except Exception as e:
        raise RuntimeError(f"모델/데이터 로딩 실패: {e}")


class Input(BaseModel):
    SEX: conint(ge=0, le=1)
    AGE: conint(ge=0, le=120)
    HGB: confloat(ge=0, le=200)
    TCHOL: conint(ge=0, le=1000)
    TG: conint(ge=0, le=3000)
    HDL: conint(ge=0, le=200)
    sleep_hours: Optional[confloat(ge=0, le=24)] = None
    exercise_days: Optional[conint(ge=0, le=7)] = None
    smoking: Optional[bool] = None
    alcohol_per_week: Optional[conint(ge=0, le=14)] = None
    stress: Optional[conint(ge=1, le=5)] = None
    measured_at: Optional[datetime] = None


# ✅ 위험 grade 계산 (0=저위험, 1=주의, 2=고위험)
def _risk_grade(target: str, prob: float, thr: float, anomalies: Dict[str, Dict[str, bool]]) -> int:
    related = _RELATED_ANOM.get(target, [])
    has_warn = any(anomalies[k]["warn"] for k in related if k in anomalies)

    if prob >= max(thr * 1.8, 0.30):
        return 2  # 고위험
    if prob >= thr:
        return 1
    if has_warn:
        return 1
    return 0


# ✅ 수정: 과도한 보정 제거, 부드러운 조정만 적용
def _adjust_prob(target: str, base_prob: float, payload: Input, anomalies: Dict[str, Dict[str, bool]]) -> float:
    """
    모델 예측값에 약간의 보정만 추가
    - 극단적인 수치 이상이 있을 때만 소폭 상향
    - 기본적으로는 모델 예측값을 신뢰
    """
    p = base_prob
    
    # 빈혈: 극단적으로 낮은 경우에만 소폭 상향
    if target == "ANE":
        hgb = float(payload.HGB)
        if hgb < 7:  # 매우 심각한 빈혈
            p = min(p * 1.5, 1.0)  # 1.5배 증가 (최대 1.0)
        elif hgb < 9:  # 심각한 빈혈
            p = min(p * 1.3, 1.0)  # 1.3배 증가
        elif hgb < 11:  # 경미한 빈혈
            p = min(p * 1.1, 1.0)  # 1.1배 증가

    # 심혈관/뇌졸중: 여러 지표가 동시에 나쁜 경우에만 소폭 상향
    else:
        tchol = int(payload.TCHOL)
        tg = int(payload.TG)
        hdl = int(payload.HDL)
        sex = int(payload.SEX)

        severity = 0
        if tchol >= 240:
            severity += 1
        if tg >= 200:
            severity += 1
        if (sex == 1 and hdl < 40) or (sex == 0 and hdl < 50):
            severity += 1

        # 3개 모두 나쁜 경우에만 상향
        if severity >= 3:
            p = min(p * 1.4, 1.0)  # 1.4배 증가
        elif severity == 2:
            p = min(p * 1.2, 1.0)  # 1.2배 증가
        elif severity == 1:
            p = min(p * 1.05, 1.0)  # 1.05배 증가

    # 0~1 범위 보장
    return float(min(max(p, 0.0), 1.0))


@router.post("/health")
def analyze_health(
    payload: Input,
    me: User = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if not _models or _train_df is None:
        raise HTTPException(503, "모델 준비 중")

    age_g = age_to_group(int(payload.AGE))
    x = np.array(
        [payload.SEX, age_g, payload.HGB, payload.TCHOL, payload.TG, payload.HDL],
        dtype=float,
    ).reshape(1, -1)

    # --------- 1) 이상치 (권장 범위 기준) ----------
    anomalies: Dict[str, Dict[str, bool]] = {
        "HGB": {"warn": payload.HGB < 11 or payload.HGB > 17},
        "TCHOL": {"warn": payload.TCHOL >= 200},
        "TG": {"warn": payload.TG >= 150},
        "HDL": {
            "warn": (
                (payload.SEX == 1 and payload.HDL < 40)
                or (payload.SEX == 0 and payload.HDL < 50)
            )
        },
    }
    warn_cnt = sum(1 for v in anomalies.values() if v["warn"])

    # --------- 2) 위험도 (모델 예측 + 경미한 보정) ----------
    risks: Dict[str, Dict[str, float | int]] = {}
    for t in TARGETS:
        base_p = float(_models[t].predict_proba(x)[0, 1])
        thr = _thresholds.get(t, 0.5)

        # ✅ 보정 적용 (이제는 부드럽게)
        adj_p = _adjust_prob(t, base_p, payload, anomalies)

        # 퍼센타일 계산
        perc = _percentile_of(_prob_ref[t], adj_p)

        risks[t] = {
            "prob": round(adj_p, 4),
            "label": int(adj_p >= thr),
            "thr": float(thr),
            "percentile": round(perc, 1),
        }

    # --------- 3) 건강 점수 ----------
    max_prob = max(risks[t]["prob"] for t in TARGETS)  # type: ignore
    
    # 기본 점수 (위험도 + 혈액 이상치 기반)
    base_score = 100 - int(float(max_prob) * 100) - warn_cnt * 8
    
    # 생활습관 페널티
    lifestyle_penalty = 0
    
    # 흡연: -10점
    if payload.smoking:
        lifestyle_penalty += 10
    
    # 운동: 주 2회 미만 -5점, 0회 -10점
    exercise = payload.exercise_days or 0
    if exercise == 0:
        lifestyle_penalty += 10
    elif exercise < 2:
        lifestyle_penalty += 5
    
    # 수면: 6시간 미만 -5점, 5시간 미만 -10점
    sleep = payload.sleep_hours or 7
    if sleep < 5:
        lifestyle_penalty += 10
    elif sleep < 6:
        lifestyle_penalty += 5
    
    # 음주: 주 4회 이상 -5점, 7회 이상 -10점
    alcohol = payload.alcohol_per_week or 0
    if alcohol >= 7:
        lifestyle_penalty += 10
    elif alcohol >= 4:
        lifestyle_penalty += 5
    
    # 스트레스: 4-5 -5점
    stress = payload.stress or 3
    if stress >= 4:
        lifestyle_penalty += 5
    
    health_score = base_score - lifestyle_penalty
    health_score = max(0, min(100, health_score))

    # --------- 4) 질환별 grade ----------
    risk_grade = {
        t: _risk_grade(t, float(risks[t]["prob"]), float(risks[t]["thr"]), anomalies)  # type: ignore
        for t in TARGETS
    }

    # --------- 5) 또래 비교 ----------
    peer = _peer_stats(
        _train_df,
        int(payload.SEX),
        age_g,
        {
            "TCHOL": payload.TCHOL,
            "TG": payload.TG,
            "HDL": payload.HDL,
            "HGB": payload.HGB,
        },
    )

    data_conf = {
        "total_database": int(len(_train_df)),
        "similar_patients": int(peer["TCHOL"]["sample_size"])
        if peer.get("TCHOL")
        else None,
        "confidence_score": float(
            min(
                0.99,
                max(
                    0.5,
                    (peer["TCHOL"]["sample_size"] if peer.get("TCHOL") else 0)
                    / 5000,
                ),
            )
        ),
    }

    peer_age_group = f"{age_g*10}대" if age_g < 10 else "90대 이상"

    # --------- 6) DB 저장 ----------
    rec = HealthRecord(
        user_id=str(me.id),
        sex=int(payload.SEX),
        age=int(payload.AGE),
        hgb=float(payload.HGB),
        tchol=int(payload.TCHOL),
        tg=int(payload.TG),
        hdl=int(payload.HDL),
        sleep_hours=payload.sleep_hours,
        exercise_days=payload.exercise_days,
        smoking=payload.smoking,
        alcohol_per_week=payload.alcohol_per_week,
        stress=payload.stress,
        prob_ane=float(risks["ANE"]["prob"]),  # type: ignore
        prob_ihd=float(risks["IHD"]["prob"]),  # type: ignore
        prob_stk=float(risks["STK"]["prob"]),  # type: ignore
        label_ane=int(risks["ANE"]["label"]),  # type: ignore
        label_ihd=int(risks["IHD"]["label"]),  # type: ignore
        label_stk=int(risks["STK"]["label"]),  # type: ignore
        health_score=int(health_score),
        summary_text=(
            f"가장 높은 위험도는 {max(risks, key=lambda k: risks[k]['prob'])}이며, "
            f"확률은 {round(max(float(risks[t]['prob']) for t in TARGETS) * 100)}%입니다."
        ),
        measured_at=payload.measured_at,
    )
    session.add(rec)
    session.commit()
    session.refresh(rec)

    return {
        "risks": risks,
        "anomalies": anomalies,
        "summary": {"health_score": health_score, "text": rec.summary_text},
        "peer_stats": peer,
        "data_confidence": data_conf,
        "peer_age_group": peer_age_group,
        "record_id": rec.id,
        "risk_grade": risk_grade,
    }