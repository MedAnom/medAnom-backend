import math
from typing import List, Dict, Any
import httpx
from fastapi import APIRouter, HTTPException, Query
from app.core.config import settings

router = APIRouter()

KAKAO_HOST = "https://dapi.kakao.com"

def _headers():
    if not settings.KAKAO_REST_KEY:
        raise HTTPException(500, detail="KAKAO_REST_KEY not configured")
    return {"Authorization": f"KakaoAK {settings.KAKAO_REST_KEY}"}

def _normalize(doc: Dict[str, Any]) -> Dict[str, Any]:
    # Kakao 로컬 결과 -> 프론트 공통 포맷으로 정규화
    return {
        "id": doc.get("id"),
        "name": doc.get("place_name"),
        "lat": float(doc.get("y")),
        "lng": float(doc.get("x")),
        "road_address": doc.get("road_address_name") or doc.get("address_name"),
        "phone": doc.get("phone"),
        "url": doc.get("place_url"),
        "distance": int(doc.get("distance")) if doc.get("distance") else None,
        "category": doc.get("category_name"),
    }

@router.get("/hospitals")
async def hospitals(
    lat: float = Query(..., description="위도 (y)"),
    lng: float = Query(..., description="경도 (x)"),
    query: str = Query("내과", description="검색어 (예: 내과/순환기내과/신경과/내분비내과)"),
    radius: int = Query(3000, ge=1, le=20000),
    size: int = Query(15, ge=1, le=45),
):
    """카카오 키워드 검색 + 카테고리(HP8=병원) 보강"""
    params_kw = {
        "query": query,
        "x": str(lng),
        "y": str(lat),
        "radius": str(radius),
        "size": str(size),
        "sort": "distance",
    }
    params_cat = {
        "category_group_code": "HP8",  # 병원/의원
        "x": str(lng),
        "y": str(lat),
        "radius": str(radius),
        "size": str(size),
        "sort": "distance",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1) 키워드
        r1 = await client.get(f"{KAKAO_HOST}/v2/local/search/keyword.json",
                              params=params_kw, headers=_headers())
        if r1.status_code == 200:
            docs1 = r1.json().get("documents", [])
        else:
            docs1 = []

        # 2) 카테고리(보강)
        r2 = await client.get(f"{KAKAO_HOST}/v2/local/search/category.json",
                              params=params_cat, headers=_headers())
        docs2 = r2.json().get("documents", []) if r2.status_code == 200 else []

    # 병합(중복 제거)
    seen = set()
    merged: List[Dict[str, Any]] = []
    for d in docs1 + docs2:
        pid = d.get("id")
        if pid in seen:
            continue
        seen.add(pid)
        merged.append(_normalize(d))

    # 가까운 순 정렬 (distance가 없으면 하버사인 계산)
    def dist(m):
        if m["distance"] is not None:
            return m["distance"]
        # fallback
        R = 6371000
        la1 = math.radians(lat); lo1 = math.radians(lng)
        la2 = math.radians(m["lat"]); lo2 = math.radians(m["lng"])
        return int(2*R*math.asin(math.sqrt(
            math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
        )))

    merged.sort(key=dist)
    return {"items": merged[:size]}
