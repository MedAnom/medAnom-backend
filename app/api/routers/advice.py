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
    evidence_level: str | None = None  # 'A/B/C' 등(권고 근거수준)

class AdviceItem(BaseModel):
    disease_code: str   # 예: I10, I63, E11 …
    disease_name: str
    tips: List[Tip]

class AdviceResponse(BaseModel):
    items: List[AdviceItem]

# ─────────────────────────────────────────────────────────
# 로컬 예방법 DB (필요하면 DB/파일로 이관 가능)
# ─────────────────────────────────────────────────────────
_ADVICE: Dict[str, AdviceItem] = {
    # 고혈압
    "I10": AdviceItem(
        disease_code="I10",
        disease_name="고혈압",
        tips=[
            Tip(type="exercise",  title="주 5회 30분 유산소",           desc="빠른 걷기/자전거/수영 등 중강도(주 150분 이상)", evidence_level="A"),
            Tip(type="exercise",  title="주 2~3회 근력운동",             desc="전신 대근육 위주, 세트 사이 1~2분 휴식", evidence_level="B"),
            Tip(type="diet",      title="나트륨 2g/일 이하",             desc="가공식품·국물류 제한, 영양성분표 나트륨 확인", evidence_level="A"),
            Tip(type="diet",      title="DASH 식단",                   desc="채소·과일·저지방유제품·통곡물↑, 포화지방·가공육↓", evidence_level="A"),
            Tip(type="lifestyle", title="체중 5~10% 감량",              desc="허리둘레(남<90cm, 여<85cm) 목표, 수면 7시간", evidence_level="B"),
            Tip(type="lifestyle", title="금연/절주",                    desc="흡연은 즉시 중단, 음주는 남 2잔·여 1잔 이내", evidence_level="A"),
            Tip(type="medical",   title="가정혈압 측정",                desc="아침·저녁 1주 기록 후 진료 시 상담", evidence_level="B"),
            Tip(type="medical",   title="합병증 위험 평가",              desc="지질·혈당·신장기능 동반 체크", evidence_level="A"),
        ],
    ),
    # 허혈성 뇌졸중(뇌경색)
    "I63": AdviceItem(
        disease_code="I63",
        disease_name="뇌경색(허혈성 뇌졸중)",
        tips=[
            Tip(type="exercise",  title="유산소 150~300분/주",           desc="가능 시 인터벌 트레이닝, 보행 균형 훈련 병행", evidence_level="B"),
            Tip(type="diet",      title="지중해/DASH 식단",              desc="불포화지방·견과·통곡물↑, 트랜스지방↓", evidence_level="A"),
            Tip(type="diet",      title="염분/당분/가공육 절감",          desc="음료의 액상과당·과도한 소금/당 섭취 제한", evidence_level="A"),
            Tip(type="lifestyle", title="금연 + 수면무호흡 확인",          desc="코골이/주간졸림 있으면 수면검사 고려", evidence_level="A"),
            Tip(type="lifestyle", title="스트레스 관리",                 desc="명상/호흡·상담치료 등으로 코르티솔 완화", evidence_level="B"),
            Tip(type="medical",   title="혈압·지질·혈당 엄격 관리",       desc="필요 시 항혈소판제/스타틴요법 평가", evidence_level="A"),
            Tip(type="medical",   title="심방세동 스크리닝",              desc="고령/두근거림 있으면 심전도 체크", evidence_level="B"),
        ],
    ),
    # 제2형 당뇨병
    "E11": AdviceItem(
        disease_code="E11",
        disease_name="제2형 당뇨병",
        tips=[
            Tip(type="exercise",  title="근력+유산소 병행",               desc="주 3회 근력(하체 포함), 주 5회 유산소", evidence_level="A"),
            Tip(type="diet",      title="저당·저정제탄수 + 식이섬유↑",     desc="GI/GL 관리, 단 음료/디저트/액상과당 제한", evidence_level="A"),
            Tip(type="diet",      title="단백질 분산 섭취",               desc="하루 1.0~1.2 g/kg, 끼니마다 배분", evidence_level="B"),
            Tip(type="lifestyle", title="수면 7~8시간/규칙 생활",          desc="야식/불규칙 수면은 인슐린 저항성↑", evidence_level="B"),
            Tip(type="lifestyle", title="체중 5~10% 감량",                desc="복부지방 감량이 공복혈당 개선에 유리", evidence_level="A"),
            Tip(type="medical",   title="정기 모니터링",                  desc="공복혈당·HbA1c(3~6개월), 미세알부민/안저검사", evidence_level="A"),
            Tip(type="medical",   title="저혈당 인지/예방",                desc="운동/금식/술 전 탄수화물 보충 가이드", evidence_level="B"),
        ],
    ),
    # 선택: 이상지질혈증(총콜↑/중성지방↑/HDL↓ 대응) – 필요 시 프론트에서 코드 추가 호출
    "E78": AdviceItem(
        disease_code="E78",
        disease_name="이상지질혈증",
        tips=[
            Tip(type="diet",      title="포화/트랜스지방 ↓, 불포화지방 ↑", desc="붉은고기/버터↓, 올리브/등푸른생선/견과↑", evidence_level="A"),
            Tip(type="diet",      title="수용성 식이섬유",                 desc="귀리·보리·콩류·채소로 LDL 개선", evidence_level="A"),
            Tip(type="exercise",  title="유산소 150분↑ + 체중감량",        desc="중성지방/TG 개선, HDL 증가", evidence_level="A"),
            Tip(type="medical",   title="스타틴·피브레이트 고려",         desc="동반 위험도에 따라 약물 병용 평가", evidence_level="A"),
        ],
    ),
}

@router.get("/advice", response_model=AdviceResponse)
def get_advice(codes: str = Query(..., description="질병코드 CSV 예: I10,E11,I63,E78")):
    out: List[AdviceItem] = []
    for code in [c.strip() for c in codes.split(",") if c.strip()]:
        item = _ADVICE.get(code.upper())
        if item:
            out.append(item)
    if not out:
        raise HTTPException(status_code=404, detail="해당 코드의 예방법 데이터 없음")
    return AdviceResponse(items=out)
