# app/api/routers/nearby.py
import math
from typing import Any, Dict, List

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.core.config import settings

router = APIRouter()
KAKAO_HOST = "https://dapi.kakao.com"

# ✅ 질환별 추천 진료과 매핑
DISEASE_TO_DEPARTMENT = {
    "ANE": ["내과", "혈액내과", "가정의학과"],
    "IHD": ["순환기내과", "심장내과", "내과"],
    "STK": ["신경과", "신경외과", "재활의학과"],
}

# ✅ 진료과별 검색 키워드
DEPARTMENT_KEYWORDS = {
    "내과": "내과",
    "혈액내과": "혈액내과",
    "가정의학과": "가정의학과",
    "순환기내과": "순환기내과",
    "심장내과": "심장내과",
    "신경과": "신경과",
    "신경외과": "신경외과",
    "재활의학과": "재활의학과",
}

def _headers():
    if not settings.KAKAO_REST_KEY:
        raise HTTPException(500, detail="KAKAO_REST_KEY not configured")
    return {"Authorization": f"KakaoAK {settings.KAKAO_REST_KEY}"}

def _normalize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "name": doc.get("place_name"),
        "lat": float(doc.get("y")),
        "lng": float(doc.get("x")),
        "address": doc.get("road_address_name") or doc.get("address_name"),
        "phone": doc.get("phone"),
        "place_url": doc.get("place_url"),
        "distance_m": int(doc.get("distance")) if doc.get("distance") else None,
        "category": doc.get("category_name"),
    }

@router.get("/hospitals")
async def hospitals(
    lat: float = Query(..., description="위도"),
    lng: float = Query(..., description="경도"),
    query: str = Query("내과", description="검색 키워드"),
    radius: int = Query(3000, ge=1, le=20000),
    size: int = Query(15, ge=1, le=45),
):
    """
    기본 병원 검색 API (기존 호환성 유지)
    """
    params_kw = {
        "query": query,
        "x": str(lng),
        "y": str(lat),
        "radius": str(radius),
        "size": str(size),
        "sort": "distance",
    }
    params_cat = {
        "category_group_code": "HP8",
        "x": str(lng),
        "y": str(lat),
        "radius": str(radius),
        "size": str(size),
        "sort": "distance",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        r1 = await client.get(
            f"{KAKAO_HOST}/v2/local/search/keyword.json",
            params=params_kw,
            headers=_headers(),
        )
        r2 = await client.get(
            f"{KAKAO_HOST}/v2/local/search/category.json",
            params=params_cat,
            headers=_headers(),
        )

    docs1 = r1.json().get("documents", []) if r1.status_code == 200 else []
    docs2 = r2.json().get("documents", []) if r2.status_code == 200 else []

    seen = set()
    merged: List[Dict[str, Any]] = []
    for d in docs1 + docs2:
        pid = d.get("id")
        if pid in seen:
            continue
        seen.add(pid)
        merged.append(_normalize(d))

    def dist(m):
        if m["distance_m"] is not None:
            return m["distance_m"]
        R = 6371000
        la1 = math.radians(lat)
        lo1 = math.radians(lng)
        la2 = math.radians(m["lat"])
        lo2 = math.radians(m["lng"])
        return int(
            2
            * R
            * math.asin(
                math.sqrt(
                    math.sin((la2 - la1) / 2) ** 2
                    + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
                )
            )
        )

    merged.sort(key=dist)
    return {"items": merged[:size]}


@router.get("/smart-hospitals")
async def smart_hospitals(
    lat: float = Query(..., description="위도"),
    lng: float = Query(..., description="경도"),
    prob_ane: float = Query(0.0, ge=0, le=1, description="빈혈 위험도"),
    prob_ihd: float = Query(0.0, ge=0, le=1, description="심혈관 위험도"),
    prob_stk: float = Query(0.0, ge=0, le=1, description="뇌졸중 위험도"),
    radius: int = Query(5000, ge=1000, le=20000),
    size: int = Query(15, ge=1, le=30),
):
    """
    ✅ 위험도 기반 맞춤 병원 추천
    - 가장 높은 위험도의 질환에 맞는 진료과 우선 검색
    - 여러 진료과를 통합 검색하여 중복 제거
    """
    # 1) 위험도 분석 → 추천 진료과 결정
    risks = {"ANE": prob_ane, "IHD": prob_ihd, "STK": prob_stk}
    sorted_risks = sorted(risks.items(), key=lambda x: x[1], reverse=True)

    # 상위 2개 질환의 진료과만 추천 (너무 많으면 검색 품질 저하)
    recommended_depts = []
    for disease, risk in sorted_risks[:2]:
        if risk > 0.1:  # 위험도 10% 이상만
            recommended_depts.extend(DISEASE_TO_DEPARTMENT.get(disease, []))

    # 기본값: 내과
    if not recommended_depts:
        recommended_depts = ["내과", "가정의학과"]

    # 중복 제거
    recommended_depts = list(dict.fromkeys(recommended_depts))

    # 2) 각 진료과별로 병원 검색
    all_docs = []
    async with httpx.AsyncClient(timeout=12.0) as client:
        for dept in recommended_depts[:3]:  # 최대 3개 진료과
            keyword = DEPARTMENT_KEYWORDS.get(dept, dept)
            params = {
                "query": f"{keyword} 병원",
                "x": str(lng),
                "y": str(lat),
                "radius": str(radius),
                "size": "15",
                "sort": "distance",
            }
            r = await client.get(
                f"{KAKAO_HOST}/v2/local/search/keyword.json",
                params=params,
                headers=_headers(),
            )
            if r.status_code == 200:
                all_docs.extend(r.json().get("documents", []))

    # 3) 중복 제거 + 거리 계산 + 필터링
    seen = set()
    merged: List[Dict[str, Any]] = []
    
    # ✅ 제외할 키워드 (치과, 피부과 등)
    exclude_keywords = ["치과", "피부과", "성형외과", "안과", "이비인후과", "정형외과", "한의원"]
    
    for d in all_docs:
        pid = d.get("id")
        if pid in seen:
            continue
        
        # ✅ 병원명에 제외 키워드가 포함되어 있으면 스킵
        name = d.get("place_name", "")
        category = d.get("category_name", "")
        
        if any(keyword in name for keyword in exclude_keywords):
            continue
        if any(keyword in category for keyword in exclude_keywords):
            continue
            
        seen.add(pid)

        normalized = _normalize(d)

        # 거리 계산 (카카오 API가 안 줬을 경우)
        if normalized["distance_m"] is None:
            R = 6371000
            la1 = math.radians(lat)
            lo1 = math.radians(lng)
            la2 = math.radians(normalized["lat"])
            lo2 = math.radians(normalized["lng"])
            normalized["distance_m"] = int(
                2
                * R
                * math.asin(
                    math.sqrt(
                        math.sin((la2 - la1) / 2) ** 2
                        + math.cos(la1)
                        * math.cos(la2)
                        * math.sin((lo2 - lo1) / 2) ** 2
                    )
                )
            )

        merged.append(normalized)

    # 4) 거리순 정렬
    merged.sort(key=lambda m: m["distance_m"] or 999999)

    return {
        "items": merged[:size],
        "recommended_departments": recommended_depts[:3],
        "primary_disease": sorted_risks[0][0] if sorted_risks else None,
    }