# Chequeo del factor de solapamiento de los finalistas H4 de A1:
# si la duracion media de la sintetica supera el cooldown (6), el motor
# apilo posiciones que el EA real no puede abrir -> mk_oos inflado.
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate

df = pd.read_parquet(r"C:\temp\X1_FULL_XAUUSD_H4.parquet")
base = df.drop(columns=["DateTime", "Zone"], errors="ignore")
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if "Ret_" in n}

CSVS = sys.argv[1:] if len(sys.argv) > 1 else [
    "experimentos/A1_H4/MASTER_XAUUSD_H4_LONG_MOMENTUM.csv",
    "experimentos/A1_H4/MASTER_XAUUSD_H4_LONG_TREND.csv"]
finales = pd.concat([pd.read_csv(p) for p in CSVS])

print("finalista | dur_media | dur_max | solape (cooldown 6)")
for _, r in finales.iterrows():
    sim = simulate(data, cm, ri, r["Entry"], r["Exit"], r["Side"],
                   cooldown=6, friction_points=1.0)
    d = sim["durations"]
    ratio = d.mean() / 6.0
    print(f"{str(r['Entry'])[:48]:<49} | {d.mean():5.1f} | {int(d.max()):3d} | {ratio:.1f}x")
