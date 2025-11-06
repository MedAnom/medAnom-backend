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
