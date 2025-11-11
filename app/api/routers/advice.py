# app/api/routers/advice.py
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Literal, Dict

router = APIRouter()

TipType = Literal["exercise", "diet", "lifestyle", "medical"]

class Tip(BaseModel):
    type: TipType
    title: str
    desc: str
    evidence_level: str | None = None

class AdviceItem(BaseModel):
    disease_code: str
    disease_name: str
    tips: List[Tip]

class AdviceResponse(BaseModel):
    items: List[AdviceItem]

_ADVICE: Dict[str, AdviceItem] = {
    # ... (네가 올린 내용 그대로)
}

@router.get("/advice", response_model=AdviceResponse)
def get_advice(codes: str = Query(..., description="예: I10,E11,I63,E78")):
    out: List[AdviceItem] = []
    for code in [c.strip() for c in codes.split(",") if c.strip()]:
        item = _ADVICE.get(code.upper())
        if item:
            out.append(item)
    if not out:
        raise HTTPException(status_code=404, detail="해당 코드의 예방법 데이터 없음")
    return AdviceResponse(items=out)
