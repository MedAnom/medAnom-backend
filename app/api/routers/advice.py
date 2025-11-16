# app/api/routers/advice.py
from __future__ import annotations

from typing import List, Literal, Dict

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter()

# --------------------------------------------------
# 타입 정의
# --------------------------------------------------
TipType = Literal["exercise", "diet", "lifestyle", "medical"]


class Tip(BaseModel):
    type: TipType
    title: str
    desc: str
    evidence_level: str | None = None  # 예: A, B, C


class AdviceItem(BaseModel):
    disease_code: str        # I10, E11, E78, I63 ...
    disease_name: str        # "고혈압", "당뇨병" 등
    tips: List[Tip]


class AdviceResponse(BaseModel):
    items: List[AdviceItem]


# --------------------------------------------------
# 하드코딩된 예방법 데이터
#
# * 최소로 I10(고혈압), E11(당뇨병), E78(이상지질혈증), I63(뇌졸중 위험)
# --------------------------------------------------
_ADVICE: Dict[str, AdviceItem] = {
    # 고혈압 (혈압↑, 심혈관 질환 위험 ↑)
    "I10": AdviceItem(
        disease_code="I10",
        disease_name="고혈압(의심·관리 필요)",
        tips=[
            Tip(
                type="exercise",
                title="주 5일 이상, 하루 30분 빠르게 걷기",
                desc=(
                    "수축기 혈압을 낮추기 위해 주 5일 이상, 약간 숨이 찰 정도의 빠른 걷기나 가벼운 조깅을 1회 30분 이상 실천하세요. "
                    "혈압이 많이 높은 경우에는 무거운 웨이트 트레이닝보다는 걷기·자전거·수영 같은 유산소 운동이 우선입니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="exercise",
                title="주 2–3회 가벼운 근력 운동 추가",
                desc=(
                    "팔·다리·코어 위주의 가벼운 근력 운동을 8~10종목, 각 10~15회씩 2~3세트 실시하면 혈압 조절과 근육량 유지에 도움이 됩니다. "
                    "호흡을 멈춘 채 힘을 주는 동작(숨참기)은 혈압을 급격히 올릴 수 있어 피하세요."
                ),
                evidence_level="B",
            ),
            Tip(
                type="diet",
                title="하루 소금(나트륨) 5g 이하로 줄이기",
                desc=(
                    "국물·찌개·라면·젓갈·김치 섭취를 줄이고, 간장은 최소한으로 사용하세요. "
                    "라벨의 ‘나트륨’ 함량을 확인해 되도록 1회 제공량 400mg 이하 제품을 선택하는 것이 좋습니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="diet",
                title="가공식품 대신 신선한 채소·과일 위주 식단",
                desc=(
                    "통조림·햄·소시지·즉석식품에는 나트륨이 많이 들어 있습니다. "
                    "하루 2접시 이상(약 350~400g)의 채소와 1~2개의 과일을 섭취하면 혈압·콜레스테롤 개선에 도움이 됩니다."
                ),
                evidence_level="B",
            ),
            Tip(
                type="lifestyle",
                title="음주를 줄이고, 흡연은 반드시 금연",
                desc=(
                    "술은 하루 소주 1잔, 맥주 1캔 이내로 제한하거나 가능한 한 끊는 것이 좋습니다. "
                    "흡연은 혈관을 수축시키고 뇌졸중·심근경색 위험을 크게 높이므로 금연이 필수입니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="lifestyle",
                title="규칙적인 수면과 스트레스 관리",
                desc=(
                    "수면 부족과 만성 스트레스는 혈압을 지속적으로 올립니다. "
                    "하루 7시간 내외의 수면을 취하고, 명상·심호흡·가벼운 스트레칭 등으로 긴장을 풀어주세요."
                ),
                evidence_level="B",
            ),
            Tip(
                type="medical",
                title="정기적인 혈압 측정 및 약물치료 여부 상담",
                desc=(
                    "집에서 아침·저녁으로 혈압을 기록해 1~2주 간 추이를 확인하고, "
                    "수축기 140mmHg 이상 또는 이완기 90mmHg 이상이 반복되면 의료기관에서 검진·치료 여부를 상담하세요."
                ),
                evidence_level="A",
            ),
            Tip(
                type="medical",
                title="고지혈증·당뇨병 동반 여부 확인",
                desc=(
                    "고혈압은 고지혈증, 당뇨병과 함께 있을수록 뇌졸중·심근경색 위험이 크게 증가합니다. "
                    "혈액검사를 통해 총 콜레스테롤(TCHOL), 중성지방(TG), HDL, 공복혈당 등을 주기적으로 확인하세요."
                ),
                evidence_level="B",
            ),
        ],
    ),

    # 제2형 당뇨병 또는 전단계
    "E11": AdviceItem(
        disease_code="E11",
        disease_name="당뇨병 또는 당뇨병 전단계",
        tips=[
            Tip(
                type="exercise",
                title="식후 10분 안에 10~20분 걷기",
                desc=(
                    "혈당이 급격히 오르는 것을 막기 위해 식사 후 10분 이내에 가볍게 걷는 습관을 들이세요. "
                    "하루 총 30분 이상 유산소 운동(걷기, 자전거, 수영 등)을 목표로 합니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="exercise",
                title="주 2회 이상 근력 운동으로 근육량 유지",
                desc=(
                    "허벅지·엉덩이·등 근육을 사용하는 스쿼트, 런지, 벽 밀기 등 체중을 이용한 운동은 "
                    "인슐린 감수성을 개선하고 공복혈당을 낮추는 데 도움이 됩니다."
                ),
                evidence_level="B",
            ),
            Tip(
                type="diet",
                title="백미·단 음료 대신 통곡물·물·무가당 차",
                desc=(
                    "밥은 백미보다 현미·잡곡밥으로 바꾸고, 설탕이 들어간 음료·커피믹스·과일주스는 피하세요. "
                    "혈당지수가 낮은 식품 위주의 식단이 필요합니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="diet",
                title="야식·폭식 피하고 규칙적인 3끼 유지",
                desc=(
                    "야식·폭식은 공복혈당과 중성지방(TG)을 동시에 올립니다. 하루 3끼를 일정한 시간에 나누어 먹고, "
                    "배부르기 전 70~80% 정도에서 수저를 내려놓는 연습을 해보세요."
                ),
                evidence_level="B",
            ),
            Tip(
                type="lifestyle",
                title="체중의 5~7% 감량만으로도 큰 효과",
                desc=(
                    "BMI가 23 이상이거나 허리둘레가 큰 편이라면, 현재 체중의 5~7%만 줄여도 혈당과 지질 수치가 의미 있게 개선됩니다. "
                    "무리한 단식보다는 식단·운동을 병행한 서서히 감량이 안전합니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="lifestyle",
                title="수면시간 6시간 미만·과로 피하기",
                desc=(
                    "수면 부족·야간 근무·지속적인 과로는 인슐린 저항성을 악화시키고 식욕을 증가시킵니다. "
                    "가능한 규칙적인 수면·생활리듬을 유지하세요."
                ),
                evidence_level="B",
            ),
            Tip(
                type="medical",
                title="공복혈당·당화혈색소 정기 추적",
                desc=(
                    "공복혈당과 당화혈색소(HbA1c)를 3~6개월 간격으로 추적해 변화를 확인해야 합니다. "
                    "수치가 기준을 넘는 경우 약물치료가 필요할 수 있으므로 의료진과 상의하세요."
                ),
                evidence_level="A",
            ),
            Tip(
                type="medical",
                title="눈·신장·발 합병증 조기 검사",
                desc=(
                    "당뇨병이 오래 지속되면 망막병증, 신장질환, 족부 궤양 등의 합병증이 생길 수 있습니다. "
                    "정기적인 안과 검사와 소변검사, 발 상태 체크가 중요합니다."
                ),
                evidence_level="B",
            ),
        ],
    ),

    # 이상지질혈증
    "E78": AdviceItem(
        disease_code="E78",
        disease_name="이상지질혈증(콜레스테롤·중성지방 이상)",
        tips=[
            Tip(
                type="exercise",
                title="주 150분 이상 중등도 유산소 운동",
                desc=(
                    "총 콜레스테롤(TCHOL)과 중성지방(TG)을 낮추려면 주 5일, 1회 30분 이상 걷기·자전거·수영 등 "
                    "중등도 강도의 유산소 운동을 꾸준히 하는 것이 중요합니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="exercise",
                title="좌업 시간이 길다면 1시간마다 3~5분씩 움직이기",
                desc=(
                    "오래 앉아 있는 생활은 HDL(좋은 콜레스테롤)을 떨어뜨립니다. "
                    "1시간마다 일어나 스트레칭하거나 짧게 걷는 것만으로도 도움이 됩니다."
                ),
                evidence_level="B",
            ),
            Tip(
                type="diet",
                title="튀김·패스트푸드·트랜스지방 줄이기",
                desc=(
                    "튀김류, 패스트푸드, 마가린·쇼트닝이 들어간 과자류는 LDL(나쁜 콜레스테롤)과 TG를 올립니다. "
                    "가능한 한 삶기·찜·구이로 조리법을 바꾸세요."
                ),
                evidence_level="A",
            ),
            Tip(
                type="diet",
                title="등푸른 생선·견과류로 좋은 지방 섭취",
                desc=(
                    "고등어·연어·참치 같은 등푸른 생선과 호두·아몬드 같은 견과류는 오메가-3 지방이 풍부해 "
                    "중성지방을 낮추고 HDL을 올리는 데 도움이 됩니다. 단, 견과류는 하루 한 줌(20~30g) 정도가 적당합니다."
                ),
                evidence_level="B",
            ),
            Tip(
                type="lifestyle",
                title="과음·폭음은 TG 급상승의 주요 원인",
                desc=(
                    "술은 중성지방을 크게 올립니다. 주 2회 이상 음주를 하고 있다면 횟수와 양을 줄이는 것만으로도 "
                    "혈액검사 결과가 상당히 개선될 수 있습니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="lifestyle",
                title="규칙적인 체중 관리",
                desc=(
                    "허리둘레가 늘어날수록 LDL·TG는 오르고 HDL은 떨어집니다. "
                    "규칙적인 운동과 식습관 개선을 통해 허리둘레를 줄이는 것이 중요합니다."
                ),
                evidence_level="B",
            ),
            Tip(
                type="medical",
                title="지질 프로파일 정기 확인",
                desc=(
                    "총 콜레스테롤(TCHOL), 중성지방(TG), HDL, LDL 수치를 6~12개월 간격으로 확인해 추이를 보는 것이 좋습니다. "
                    "수치가 높다면 생활습관 개선과 함께 약물치료가 필요할 수 있습니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="medical",
                title="심혈관 질환 위험 평가",
                desc=(
                    "연령·성별·흡연 여부·혈압·당뇨병 유무 등을 종합해 10년 내 심혈관 질환 위험도를 평가받고, "
                    "위험도가 높은 경우 보다 적극적인 치료가 권장됩니다."
                ),
                evidence_level="B",
            ),
        ],
    ),

    # 허혈성 뇌졸중 위험
    "I63": AdviceItem(
        disease_code="I63",
        disease_name="허혈성 뇌졸중(뇌경색) 위험군",
        tips=[
            Tip(
                type="exercise",
                title="의사와 상의 후, 무리하지 않는 선에서 규칙적 운동",
                desc=(
                    "이미 심혈관 위험이 높은 경우에는 무리한 운동보다, 의료진과 상의해 본인에게 맞는 강도로 "
                    "걷기·자전거 등 유산소 운동을 시작하는 것이 안전합니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="diet",
                title="저염·저지방·지중해식 패턴에 가깝게",
                desc=(
                    "신선한 채소·과일, 통곡물, 올리브유, 생선·콩류는 뇌졸중 위험을 줄이는 데 도움이 됩니다. "
                    "붉은 고기·가공육·짠 음식은 가급적 줄이세요."
                ),
                evidence_level="A",
            ),
            Tip(
                type="lifestyle",
                title="갑작스러운 증상(얼굴 마비·말 어눌함·한쪽 팔다리 힘 빠짐) 즉시 119",
                desc=(
                    "갑작스러운 언어 장애, 얼굴 한쪽 마비, 한쪽 팔다리 힘 빠짐, 심한 두통 등이 나타나면 즉시 119에 신고하고 "
                    "가까운 응급실로 가야 합니다. 발병 후 치료까지 시간이 지날수록 후유증이 커집니다."
                ),
                evidence_level="A",
            ),
            Tip(
                type="medical",
                title="혈압·혈당·지질 수치의 적극적 관리",
                desc=(
                    "고혈압, 당뇨병, 이상지질혈증은 뇌졸중의 주요 위험 요인입니다. "
                    "처방된 약은 임의로 중단하지 말고, 정기 외래를 통해 목표 수치 도달 여부를 확인하세요."
                ),
                evidence_level="A",
            ),
            Tip(
                type="medical",
                title="필요 시 뇌혈관 영상·심장검사",
                desc=(
                    "의사가 필요하다고 판단하는 경우 뇌 MRI/CT, 경동맥 초음파, 심장 초음파, 심전도 등 정밀검사가 시행될 수 있습니다. "
                    "이는 혈전·혈관협착 등 뇌졸중 원인을 찾고 재발 위험을 줄이기 위한 과정입니다."
                ),
                evidence_level="B",
            ),
        ],
    ),
}


# --------------------------------------------------
# API 엔드포인트
# --------------------------------------------------
@router.get("", response_model=AdviceResponse)
def get_advice(
    codes: str = Query(..., description="예: I10,E11,I63,E78"),
):
    """
    쿼리스트링으로 들어온 코드들(I10,E11,...) 중
    _ADVICE에 등록된 것만 모아서 반환.

    하나도 매칭되지 않으면 빈 리스트를 넘겨서
    프론트에서는 '권장 사항이 없습니다.'가 뜨도록 함.
    """
    out: List[AdviceItem] = []

    for code in [c.strip() for c in codes.split(",") if c.strip()]:
        item = _ADVICE.get(code.upper())
        if item:
            out.append(item)

    return AdviceResponse(items=out)
