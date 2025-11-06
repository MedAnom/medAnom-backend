from typing import List, Tuple
import numpy as np
import umap
from sklearn.preprocessing import RobustScaler
from sklearn.ensemble import IsolationForest

def permutation_importance(iforest: IsolationForest, Xs: np.ndarray, columns: List[str], seed: int = 42) -> List[Tuple[str, float]]:
    base = -iforest.score_samples(Xs).mean()
    rng = np.random.default_rng(seed)
    imps: List[Tuple[str, float]] = []
    n_feat = Xs.shape[1]
    max_cols = min(n_feat, 30)
    for i in range(max_cols):
        Xperm = Xs.copy()
        rng.shuffle(Xperm[:, i])
        s = -iforest.score_samples(Xperm).mean()
        imps.append((columns[i], float(s - base)))
    imps.sort(key=lambda x: x[1], reverse=True)
    return imps[:10]

def run_analyze(df_numeric, contamination: float, n_neighbors: int, min_dist: float):
    columns = list(df_numeric.columns)

    scaler = RobustScaler()
    Xs = scaler.fit_transform(df_numeric.values)

    if not (0 < contamination < 0.5):
        raise ValueError("contamination은 (0, 0.5) 권장")

    iforest = IsolationForest(
        contamination=contamination,
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
    )
    pred = iforest.fit_predict(Xs)       # 1=정상, -1=이상
    labels = (pred == 1).astype(int)     # 1=정상, 0=이상
    scores = (-iforest.score_samples(Xs)).astype(float).tolist()

    reducer = umap.UMAP(
        n_neighbors=int(n_neighbors),
        min_dist=float(min_dist),
        random_state=42,
        n_components=2,
        metric="euclidean",
        verbose=False,
    )
    emb = reducer.fit_transform(Xs).tolist()

    imp = permutation_importance(iforest, Xs, columns)
    return columns, labels.tolist(), scores, emb, imp
