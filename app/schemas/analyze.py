from pydantic import BaseModel
from typing import List, Tuple, Dict

class AnalyzeOut(BaseModel):
    columns: List[str]
    labels: List[int]          # 1=정상, 0=이상
    scores: List[float]        # 높을수록 이상
    umap: List[List[float]]    # [[x,y], ...]
    top_features: List[Tuple[str, float]]
    n_rows: int
    user: Dict[str, str]
