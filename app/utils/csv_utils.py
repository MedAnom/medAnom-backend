import pandas as pd
import numpy as np
from fastapi import UploadFile, HTTPException

def load_csv(upload: UploadFile) -> pd.DataFrame:
    try:
        try:
            df = pd.read_csv(upload.file, encoding="utf-8-sig")
        except Exception:
            upload.file.seek(0)
            df = pd.read_csv(upload.file)
        df.columns = [str(c).strip() for c in df.columns]
        return df
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV 파싱 실패: {e}")

def select_numeric(df: pd.DataFrame) -> pd.DataFrame:
    X = df.select_dtypes(include=[np.number]).copy()
    if X.empty:
        raise HTTPException(status_code=400, detail="숫자형 컬럼이 없습니다. (혈압/혈당/지질 등 숫자열 필요)")
    X = X.dropna(axis=1, how="all")
    X = X.fillna(X.median(numeric_only=True))
    return X
