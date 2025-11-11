# app/api/routers/nearby.py
import math
from typing import Any, Dict, List

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
    query: str = Query("내과"),
    radius: int = Query(3000, ge=1, le=20000),
    size: int = Query(15, ge=1, le=45),
):
    params_kw = {"query": query, "x": str(lng), "y": str(lat), "radius": str(radius), "size": str(size), "sort": "distance"}
    params_cat = {"category_group_code": "HP8", "x": str(lng), "y": str(lat), "radius": str(radius), "size": str(size), "sort": "distance"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        r1 = await client.get(f"{KAKAO_HOST}/v2/local/search/keyword.json",   params=params_kw, headers=_headers())
        r2 = await client.get(f"{KAKAO_HOST}/v2/local/search/category.json", params=params_cat, headers=_headers())

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
        la1 = math.radians(lat); lo1 = math.radians(lng)
        la2 = math.radians(m["lat"]); lo2 = math.radians(m["lng"])
        return int(2*R*math.asin(math.sqrt(
            math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
        )))
    merged.sort(key=dist)

    return {"items": merged[:size]}
