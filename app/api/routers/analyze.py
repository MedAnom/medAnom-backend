'''
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from typing import List, Tuple

from app.api.deps import get_current_user
from app.models.user import User
from app.utils.csv_utils import load_csv, select_numeric
from app.services.analyze_service import run_analyze
from app.schemas.analyze import AnalyzeOut

router = APIRouter()

@router.post("/analyze", response_model=AnalyzeOut)
async def analyze(
    file: UploadFile = File(...),
    contamination: float = Form(0.05),
    n_neighbors: int = Form(15),
    min_dist: float = Form(0.1),
    me: User = Depends(get_current_user),
):
    df = load_csv(file)
    X = select_numeric(df)
    columns, labels, scores, emb, imp = run_analyze(X, contamination, n_neighbors, min_dist)

    return AnalyzeOut(
        columns=columns,
        labels=labels,
        scores=scores,
        umap=emb,
        top_features=imp,
        n_rows=len(df),
        user={"id": me.id, "email": me.email},
    )
'''
# app/api/routers/analyze.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, conint, confloat
from typing import Dict, Any
import numpy as np
import pandas as pd
from pathlib import Path

# 간단 모델: StandardScaler + LogisticRegression 파이프라인
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

router = APIRouter()

# ---------- 데이터/모델 준비 ----------
DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TRAIN_CSV = DATA_DIR / "혈액검사데이터_train.csv"

TARGETS = ["ANE", "IHD", "STK"]
FEATURES = ["SEX", "AGE_G", "HGB", "TCHOL", "TG", "HDL"]

_models: Dict[str, Pipeline] = {}
_scaler_for_anomaly = None
_feat_stats = None

def _load_and_train():
    global _models, _scaler_for_anomaly, _feat_stats
    df = pd.read_csv(TRAIN_CSV)

    # 피처/타깃 분리
    X = df[FEATURES].copy()
    # 이상치 탐지용 통계(간단 z-score 기준)
    _feat_stats = {
        c: {"mean": float(X[c].mean()), "std": float(X[c].std(ddof=0))}
        for c in FEATURES
    }
    _scaler_for_anomaly = StandardScaler().fit(X.values)

    for target in TARGETS:
        y = df[target].astype(int).values
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000))
        ])
        pipe.fit(X.values, y)
        _models[target] = pipe

@router.on_event("startup")
def _startup():
    try:
        _load_and_train()
    except Exception as e:
        raise RuntimeError(f"모델 로딩 실패: {e}")

# ---------- 스키마 ----------
class HealthInput(BaseModel):
    SEX: conint(ge=0, le=1) = Field(..., description="0=여, 1=남 (데이터 기준)")
    AGE_G: conint(ge=0, le=10) = Field(..., description="연령대 그룹 (데이터 스케일에 맞게)")
    HGB: confloat(ge=0, le=30) = ...
    TCHOL: conint(ge=0, le=1000) = ...
    TG: conint(ge=0, le=3000) = ...
    HDL: conint(ge=0, le=200) = ...

class RiskBlock(BaseModel):
    prob: float
    label: int

class AnalysisOutput(BaseModel):
    risks: Dict[str, RiskBlock]
    anomalies: Dict[str, Any]
    summary: Dict[str, Any]

# ---------- 유틸 ----------
def _zscore(value: float, mean: float, std: float) -> float:
    if std == 0:
        return 0.0
    return (value - mean) / std

def _anomaly_report(x: Dict[str, float]) -> Dict[str, Any]:
    # z-score 절대값이 2 이상이면 경고 (간단 규칙)
    flags = {}
    for f in FEATURES:
        m = _feat_stats[f]["mean"]
        s = _feat_stats[f]["std"]
        z = abs(_zscore(x[f], m, s))
        flags[f] = {"z": round(z, 2), "warn": z >= 2}
    return flags

# ---------- 엔드포인트 ----------
@router.post("/analyze/health", response_model=AnalysisOutput)
def analyze_health(payload: HealthInput):
    if not _models:
        raise HTTPException(503, "모델 준비 중")

    x = [payload.SEX, payload.AGE_G, payload.HGB, payload.TCHOL, payload.TG, payload.HDL]
    x_arr = np.array(x, dtype=float).reshape(1, -1)

    risks: Dict[str, RiskBlock] = {}
    for t in TARGETS:
        pipe = _models[t]
        proba = float(pipe.predict_proba(x_arr)[0, 1])
        label = int(proba >= 0.5)
        risks[t] = RiskBlock(prob=round(proba, 4), label=label)

    anomalies = _anomaly_report({
        "SEX": payload.SEX, "AGE_G": payload.AGE_G, "HGB": payload.HGB,
        "TCHOL": payload.TCHOL, "TG": payload.TG, "HDL": payload.HDL
    })

    # 간단 요약: 가장 높은 위험, 경고 수, 건강 포인트
    top = sorted(risks.items(), key=lambda kv: kv[1].prob, reverse=True)[0]
    warn_cnt = sum(1 for v in anomalies.values() if v["warn"])
    health_score = max(0, 100 - int(top[1].prob * 50) - warn_cnt * 5)

    summary = {
        "top_risk": top[0],
        "top_risk_prob": round(top[1].prob, 3),
        "warning_count": warn_cnt,
        "health_score": health_score
    }

    return AnalysisOutput(risks=risks, anomalies=anomalies, summary=summary)
