# app/api/routers/cost.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, conint, confloat
from typing import Optional, Dict
from pathlib import Path
import joblib
import numpy as np

from sqlmodel import Session, select
from app.core.db import get_session
from app.api.deps import get_current_user
from app.models.user import User
from app.models.health_record import HealthRecord

router = APIRouter()

ART = Path(__file__).resolve().parents[2] / "artifacts"
_COST_MODEL_PATHS = [
    ART / "cost_model.pkl",       # 기본
    ART / "cost_model_log1p.pkl", # 예비(로그타깃)
]

_cost_model = None
for p in _COST_MODEL_PATHS:
    if p.exists():
        try:
            _cost_model = joblib.load(p)
            break
        except Exception:
            _cost_model = None

# 룰 기반 폴백용 상수
BASE_EVENT_COST = {"ANE": 1_500_000, "IHD": 3_500_000, "STK": 5_200_000}
PER_DIEM          = {"ANE":   120_000, "IHD":   200_000, "STK":   240_000}
SURGERY_EXTRA     = {"ANE":   800_000, "IHD": 1_800_000, "STK": 2_300_000}
ICU_EXTRA         = {"ANE":   400_000, "IHD":   900_000, "STK": 1_200_000}
REHAB_PER_DAY     = {"ANE":    60_000, "IHD":   110_000, "STK":   130_000}

class SimInput(BaseModel):
    record_id: int
    days_hosp: conint(ge=0, le=365) = 0
    surgery: bool = False
    icu: bool = False
    rehab_days: conint(ge=0, le=365) = 0
    disability_rate: confloat(ge=0.0, le=1.0) = 0.0
    negligence: confloat(ge=0.0, le=1.0) = 0.0  # 본인 과실율(비율)

class SimOutput(BaseModel):
    medical: int
    non_economic: int
    total: int
    premium_monthly: int
    detail_cost: Dict[str, int]

def _rule_based_cost(prob_map: Dict[str, float], sim: SimInput) -> SimOutput:
    # 사건별 비용 합산 (기대값 = 사건별 비용 * 사건발생확률)
    detail = {}
    med_sum = 0.0
    for k in ["ANE","IHD","STK"]:
        base = BASE_EVENT_COST[k]
        c = base
        c += PER_DIEM[k] * sim.days_hosp
        if sim.surgery: c += SURGERY_EXTRA[k]
        if sim.icu:     c += ICU_EXTRA[k]
        c += REHAB_PER_DAY[k] * sim.rehab_days
        exp_c = c * float(prob_map.get(k, 0.0))
        detail[k] = int(round(exp_c))
        med_sum += exp_c

    # 비경제적 손해(간이): 기준 500만원 × 장해율
    non_econ = int(round(5_000_000 * sim.disability_rate))

    gross = med_sum + non_econ
    net   = int(round(gross * (1.0 - sim.negligence)))
    # 월 보험료 유사 지표(완전 임의): 연 총액의 1/100 / 12
    premium = int(round((net / 100) / 12))

    return SimOutput(
        medical=int(round(med_sum)),
        non_economic=non_econ,
        total=net,
        premium_monthly=premium,
        detail_cost=detail
    )

@router.post("/simulate/expense", response_model=SimOutput)
def simulate_expense(payload: SimInput,
                     me: User = Depends(get_current_user),
                     session: Session = Depends(get_session)):
    # 1) 최신 record 조회(권한 체크)
    rec = session.get(HealthRecord, payload.record_id)
    if not rec or str(rec.user_id) != str(me.id):
        raise HTTPException(404, "record not found")

    # 2) 사건별 확률
    prob_map = {"ANE": rec.prob_ane, "IHD": rec.prob_ihd, "STK": rec.prob_stk}

    # 3) ML 모델이 있으면 ML 기반 예측 → 없으면 룰 기반
    if _cost_model is None:
        return _rule_based_cost(prob_map, payload)

    # ── ML 특징 구성
    #   텍스트·카테고리 정보는 데이터셋 기반이므로 여기선 환자/시나리오 특징을 전달
    #   학습 파이프라인이 텍스트/카테고리 전처리를 포함하므로, 
    #   간단히 수치 시나리오만으로 보정 계수를 예측 → 사건별 룰비용에 가중
    X = [[
        rec.sex, rec.age, rec.hgb, rec.tchol, rec.tg, rec.hdl,
        payload.days_hosp, int(payload.surgery), int(payload.icu),
        payload.rehab_days, payload.disability_rate
    ]]
    try:
        pred_factor = float(_cost_model.predict(X)[0])
        # pred_factor가 절대 금액으로 나오면 그대로 사용, 
        # 상대 가중치로 사용하려면 0~1~수배 범위로 클리핑
        if pred_factor <= 0:
            pred_factor = 1.0
    except Exception:
        return _rule_based_cost(prob_map, payload)

    # 룰 기반 기대값에 ML 보정계수 곱
    rb = _rule_based_cost(prob_map, payload)
    medical_adj = int(round(rb.medical * (pred_factor / max(rb.medical, 1))))
    total_adj   = int(round(rb.total * (pred_factor / max(rb.total, 1))))
    prem_adj    = int(round(rb.premium_monthly * (pred_factor / max(rb.premium_monthly, 1))))

    # detail은 동일 방식으로 비례 조정
    det_adj = {k: int(round(v * (pred_factor / max(rb.medical, 1)))) for k, v in rb.detail_cost.items()}

    return SimOutput(
        medical=max(medical_adj, 0),
        non_economic=rb.non_economic,
        total=max(total_adj, 0),
        premium_monthly=max(prem_adj, 0),
        detail_cost=det_adj
    )
