# app/api/routers/health.py
from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
import json, joblib, numpy as np, pandas as pd
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
    out = {}
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

@router.post("/health")   # ✅ 반드시 이 경로
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

    risks: Dict[str, Dict[str, float | int]] = {}
    for t in TARGETS:
        p1 = float(_models[t].predict_proba(x)[0, 1])
        thr = _thresholds.get(t, 0.5)
        perc = _percentile_of(_prob_ref[t], p1)
        risks[t] = {"prob": round(p1, 4), "label": int(p1 >= thr), "thr": float(thr), "percentile": round(perc, 1)}

    anomalies = {
        "HGB": {"warn": payload.HGB < 11 or payload.HGB > 17},
        "TCHOL": {"warn": payload.TCHOL >= 200},
        "TG": {"warn": payload.TG >= 150},
        "HDL": {"warn": (payload.SEX == 1 and payload.HDL < 40) or (payload.SEX == 0 and payload.HDL < 50)},
    }
    warn_cnt = sum(1 for v in anomalies.values() if v["warn"])
    health_score = max(0, 100 - int(max(risks[t]["prob"] for t in TARGETS) * 50) - warn_cnt * 5)

    peer = _peer_stats(_train_df, int(payload.SEX), age_g, {
        "TCHOL": payload.TCHOL, "TG": payload.TG, "HDL": payload.HDL, "HGB": payload.HGB
    })

    data_conf = {
        "total_database": int(len(_train_df)),
        "similar_patients": int(peer["TCHOL"]["sample_size"]) if peer.get("TCHOL") else None,
        "confidence_score": float(min(0.99, max(0.5, (peer["TCHOL"]["sample_size"] if peer.get("TCHOL") else 0)/5000)))
    }

    peer_age_group = f"{age_g*10}대" if age_g < 10 else "90대 이상"

    # ✅ DB 저장
    rec = HealthRecord(
        user_id=str(me.id), sex=int(payload.SEX), age=int(payload.AGE),
        hgb=float(payload.HGB), tchol=int(payload.TCHOL), tg=int(payload.TG), hdl=int(payload.HDL),
        sleep_hours=payload.sleep_hours, exercise_days=payload.exercise_days,
        smoking=payload.smoking, alcohol_per_week=payload.alcohol_per_week,
        stress=payload.stress, prob_ane=risks["ANE"]["prob"], prob_ihd=risks["IHD"]["prob"], prob_stk=risks["STK"]["prob"],
        label_ane=risks["ANE"]["label"], label_ihd=risks["IHD"]["label"], label_stk=risks["STK"]["label"],
        health_score=int(health_score), summary_text=f"가장 높은 위험도는 {max(risks, key=lambda k: risks[k]['prob'])}이며, 확률은 {round(max(risks[t]['prob'] for t in TARGETS)*100)}%입니다.",
        measured_at=payload.measured_at,
    )
    session.add(rec); session.commit(); session.refresh(rec)

    return {
        "risks": risks,
        "anomalies": anomalies,
        "summary": {"health_score": health_score, "text": rec.summary_text},
        "peer_stats": peer,                     # ✅ 또래 비교 추가
        "data_confidence": data_conf,
        "peer_age_group": peer_age_group,
        "record_id": rec.id,
    }
