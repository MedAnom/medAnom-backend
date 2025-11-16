# app/api/routers/analyze.py
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()

ART = Path(__file__).resolve().parents[2] / "artifacts"
TARGETS = ["ANE", "IHD", "STK"]
FEATURES = ["SEX", "AGE_G", "HGB", "TCHOL", "TG", "HDL"]

_models: Dict[str, object] = {}
_thresholds: Dict[str, float] = {}

# 참조(70k) 데이터
_ref_df: Optional[pd.DataFrame] = None
_ref_probas: Dict[str, np.ndarray] = {}
_total_db: int = 0


def age_to_group(age: int) -> int:
    """0~120세 → 10년단위 그룹(0~10)"""
    return int(min(max(age, 0) // 10, 10))


def _percentile(sorted_arr: np.ndarray, x: float) -> float:
    """오름차순 정렬 확률분포에서 x의 퍼센타일(0~100)"""
    if sorted_arr.size == 0:
        return float("nan")
    idx = np.searchsorted(sorted_arr, x, side="left")
    return float(idx / sorted_arr.size * 100.0)


@router.on_event("startup")
def _load_models():
    """모델/임계값/참조데이터 로딩 및 분포 사전계산"""
    global _models, _thresholds, _ref_df, _ref_probas, _total_db
    try:
        for t in TARGETS:
            _models[t] = joblib.load(ART / f"model_{t}.pkl")

        # thresholds.json: {"ANE":{"threshold":0.5}, ...}
        with open(ART / "thresholds.json", "r", encoding="utf-8") as f:
            tj = json.load(f)
        _thresholds = {k: float(v.get("threshold", 0.5)) for k, v in tj.items()}

        # 선택: ref_dataset.csv가 있을 때만 퍼센타일/또래통계 제공
        ref_csv = ART / "ref_dataset.csv"
        if ref_csv.exists():
            df = pd.read_csv(ref_csv)
            # 필요한 컬럼으로 제한
            df = df[["SEX", "AGE", "HGB", "TCHOL", "TG", "HDL"]].copy()
            df["AGE_G"] = df["AGE"].apply(lambda a: age_to_group(int(a)))
            _ref_df = df
            Xref = df[["SEX", "AGE_G", "HGB", "TCHOL", "TG", "HDL"]].astype(float).values
            _total_db = len(df)

            _ref_probas = {}
            for t in TARGETS:
                p = _models[t].predict_proba(Xref)[:, 1]
                _ref_probas[t] = np.sort(p)  # 퍼센타일 계산용
        else:
            _ref_df = None
            _ref_probas = {}
            _total_db = 0

    except Exception as e:
        raise RuntimeError(f"모델/참조데이터 로딩 실패: {e}")


# ---------- 스키마 ----------
class Input(BaseModel):
    SEX: int = Field(..., ge=0, le=1)
    AGE: int = Field(..., ge=0, le=120)
    HGB: float = Field(..., ge=0, le=200)
    TCHOL: int = Field(..., ge=0, le=1000)
    TG: int = Field(..., ge=0, le=3000)
    HDL: int = Field(..., ge=0, le=200)

    # 선택: 생활습관
    sleep_hours: Optional[float] = Field(None, ge=0, le=24)
    exercise_days: Optional[int] = Field(None, ge=0, le=7)
    smoking: Optional[bool] = None
    alcohol_per_week: Optional[int] = Field(None, ge=0, le=14)
    stress: Optional[int] = Field(None, ge=1, le=5)


def _summary_text(
    risks: Dict[str, Dict[str, float | int | None]],
    anomalies: Dict[str, Dict[str, bool]],
    lifestyle: Dict[str, object],
) -> str:
    msgs: list[str] = []
    top = max(risks.items(), key=lambda kv: kv[1]["prob"])
    msgs.append(f"가장 높은 위험도는 {top[0]}이며, 확률은 {round(top[1]['prob'] * 100)}%입니다.")
    warns = [k for k, v in anomalies.items() if v.get("warn")]
    if warns:
        msgs.append(f"주의 지표: {', '.join(warns)}")
    if lifestyle:
        if lifestyle.get("smoking"):
            msgs.append("흡연은 심혈관 위험을 높일 수 있어요.")
        if (lifestyle.get("exercise_days") or 0) < 2:
            msgs.append("주 2~3회 이상 유산소 운동을 권장합니다.")
        if (lifestyle.get("sleep_hours") or 0) < 6:
            msgs.append("수면 시간이 짧으면 대사 건강에 좋지 않습니다.")
    msgs.append("일반 건강 정보이며, 의료 상담은 전문가와 상의하세요.")
    return " ".join(msgs)


@router.post("/health")
def analyze(payload: Input, me: User = Depends(get_current_user)):
    if not _models:
        raise HTTPException(503, "모델 준비 중")

    age_g = age_to_group(int(payload.AGE))
    x = np.array(
        [payload.SEX, age_g, payload.HGB, payload.TCHOL, payload.TG, payload.HDL],
        dtype=float,
    ).reshape(1, -1)

    # 위험도
    risks: Dict[str, Dict[str, float | int | None]] = {}
    for t in TARGETS:
        p1 = float(_models[t].predict_proba(x)[0, 1])
        thr = _thresholds.get(t, 0.5)

        perc = None
        if t in _ref_probas and _ref_probas[t].size:
            perc = round(_percentile(_ref_probas[t], p1), 1)  # 0~100

        risks[t] = {
            "prob": round(p1, 4),
            "label": int(p1 >= thr),
            "thr": float(thr),
            "percentile": perc,
        }

    # 이상치(간단 규칙)
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
    summary_text = _summary_text(risks, anomalies, lifestyle)

    # 또래 비교(성별·연령대)
    peer_stats = None
    similar_n = None
    if _ref_df is not None:
        peers = _ref_df[(_ref_df["SEX"] == payload.SEX) & (_ref_df["AGE_G"] == age_g)]
        similar_n = int(len(peers))
        if similar_n > 0:

            def pct(values: pd.Series, v: float) -> float:
                return float((values < v).sum() / len(values) * 100.0)

            peer_stats = {
                "TCHOL": {
                    "your_value": float(payload.TCHOL),
                    "peer_mean": float(peers["TCHOL"].mean()),
                    "peer_median": float(peers["TCHOL"].median()),
                    "percentile": round(pct(peers["TCHOL"], payload.TCHOL), 1),
                    "sample_size": similar_n,
                },
                "TG": {
                    "your_value": float(payload.TG),
                    "peer_mean": float(peers["TG"].mean()),
                    "peer_median": float(peers["TG"].median()),
                    "percentile": round(pct(peers["TG"], payload.TG), 1),
                    "sample_size": similar_n,
                },
                "HDL": {
                    "your_value": float(payload.HDL),
                    "peer_mean": float(peers["HDL"].mean()),
                    "peer_median": float(peers["HDL"].median()),
                    "percentile": round(pct(peers["HDL"], payload.HDL), 1),
                    "sample_size": similar_n,
                },
                "HGB": {
                    "your_value": float(payload.HGB),
                    "peer_mean": float(peers["HGB"].mean()),
                    "peer_median": float(peers["HGB"].median()),
                    "percentile": round(pct(peers["HGB"], payload.HGB), 1),
                    "sample_size": similar_n,
                },
            }

    data_confidence = {
        "total_database": _total_db,
        "similar_patients": similar_n if similar_n is not None else None,
        "confidence_score": round(0.95 if _total_db >= 50000 else 0.7, 2),
    }

    return {
        "risks": risks,
        "anomalies": anomalies,
        "summary": {"health_score": health_score, "text": summary_text},
        "peer_stats": peer_stats,
        "data_confidence": data_confidence,
    }
