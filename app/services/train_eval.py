from pathlib import Path
import json, joblib
import numpy as np, pandas as pd
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, precision_recall_curve, f1_score

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
ART  = ROOT / "artifacts"
ART.mkdir(exist_ok=True)

TARGETS = ["ANE", "IHD", "STK"]
FEATURES = ["SEX", "AGE_G", "HGB", "TCHOL", "TG", "HDL"]

def best_thr(y, p):
    pre, rec, thr = precision_recall_curve(y, p)[:3]
    f1 = (2*pre*rec)/(pre+rec+1e-9)
    i = int(np.nanargmax(f1[:-1]))
    return float(thr[i]), float(f1[i])

def run():
    tr = pd.read_csv(DATA/"혈액검사데이터_train.csv")
    te = pd.read_csv(DATA/"혈액검사데이터_test.csv")

    Xtr, Xte = tr[FEATURES].values, te[FEATURES].values

    metrics, thrs = {}, {}
    for t in TARGETS:
        ytr = tr[t].astype(int).values
        yte = te[t].astype(int).values

        pipe = Pipeline([("scaler", StandardScaler()),
                         ("clf", LogisticRegression(max_iter=1000))]).fit(Xtr, ytr)
        joblib.dump(pipe, ART/f"model_{t}.pkl")

        p_tr = pipe.predict_proba(Xtr)[:,1]
        p_te = pipe.predict_proba(Xte)[:,1]
        thr, f1 = best_thr(ytr, p_tr)
        thrs[t] = {"threshold": thr, "f1_train": f1}
        metrics[t] = {
            "auc_train": roc_auc_score(ytr, p_tr),
            "auc_test":  roc_auc_score(yte, p_te),
            "f1_test@thr": f1_score(yte, (p_te>=thr).astype(int))
        }

    with open(ART/"thresholds.json","w",encoding="utf-8") as f: json.dump(thrs, f, ensure_ascii=False, indent=2)
    with open(ART/"metrics.json","w",encoding="utf-8") as f: json.dump(metrics, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run()
