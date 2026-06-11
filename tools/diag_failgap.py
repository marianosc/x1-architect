# Diagnostico del muro FAIL_GAP del ciclo 1: localiza DONDE cae el gap maximo
# de equity (entre picos) para reglas reales, contra Stag_Global=5000.
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import x1_engine as eng

MASTER = r"Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON\COSECHA\MASTER_XAUUSD_H1_SHORT_MOMENTUM.csv"

df = pd.read_parquet(r"C:\temp\X1_FULL_XAUUSD_H1.parquet")
dt = pd.to_datetime(df["DateTime"]).reset_index(drop=True)
zone = df["Zone"].values
for z in (0, 1, 2):
    idx = np.where(zone == z)[0]
    print(f"Zona {z}: {dt[idx[0]]} -> {dt[idx[-1]]} | {len(idx)} velas")

base = df.drop(columns=["DateTime", "Zone"], errors="ignore")
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if "Ret_" in n}

mast = pd.read_csv(MASTER)
print("\nStag_Global=5000 | friccion 1.0 | cooldown 25")
print("regla | max_gap | tramo del gap")
for _, r in mast.head(10).iterrows():
    try:
        sim = eng.simulate(data, cm, ri, r["Entry"], r["Exit"], r["Side"],
                           cooldown=25, friction_points=1.0)
    except ValueError:
        continue
    ra = sim["vector"]
    eq = np.cumsum(ra)
    peaks = np.maximum.accumulate(eq)
    hits = np.where(np.diff(peaks, prepend=-1e-9) > 0)[0]
    if len(hits) > 1:
        gaps = np.diff(hits)
        k = int(np.argmax(gaps))
        g = int(gaps[k])
        seg = f"{dt[hits[k]].date()} -> {dt[hits[k+1]].date()}"
        g_now = len(ra) - 1 - hits[-1]
        if g_now > g:
            g, seg = int(g_now), f"{dt[hits[-1]].date()} -> FIN (gap_to_now)"
    else:
        g, seg = len(ra), "sin picos en toda la historia"
    verdict = "FAIL_GAP" if g > 5000 else "pasa gap"
    print(f"  {str(r['Entry'])[:44]:<45} | {g:6d} | {seg} | {verdict}")
