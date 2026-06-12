# FASE 3: auditoria de la anomalia EURUSD H4 (9.928 PASS es demasiado bueno).
# Chequea: (1) calidad/zonas del parquet, (2) un finalista bajo fricciones
# crecientes (la 0.0001 provisional puede estar subestimada), (3) su perfil.
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_test

df = pd.read_parquet(r"C:\temp\X1_FULL_EURUSD_H4.parquet")
dt = pd.to_datetime(df["DateTime"]).reset_index(drop=True)
zone = df["Zone"].values
print(f"velas {len(df)} | {dt.iloc[0]} -> {dt.iloc[-1]}")
for z in (0, 1, 2):
    idx = np.where(zone == z)[0]
    print(f"  Zona {z}: {dt[idx[0]].date()} -> {dt[idx[-1]].date()} | {len(idx)} velas")
close = df["Close"].values.astype(np.float64)
r1 = np.abs(np.diff(close) / close[:-1])
print(f"Close rango: {close.min():.4f}-{close.max():.4f} | "
      f"saltos>1%: {(r1 > 0.01).sum()} | velas planas: {(r1 == 0).sum()}")

base = df.drop(columns=["DateTime", "Zone"], errors="ignore")
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if "Ret_" in n}
ret_1 = np.zeros(len(close)); ret_1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
z_is, z_oos = zone == 1, zone == 2

top = pd.read_csv("experimentos/F3_EURH4/MASTER_EURUSD_H4_LONG_MOMENTUM.csv").iloc[0]
print(f"\nFinalista: {top['Entry']} | {top['Exit']} | PF_master {top['PF']}")
print("friccion (pts) | trades | pf_is | pf_oos | mk_is | mk_oos")
for fp in (0.0001, 0.0002, 0.0003, 0.0005):
    sim = simulate(data, cm, ri, top["Entry"], top["Exit"], top["Side"],
                   cooldown=3, friction_points=fp)
    idx_e = np.where(sim["mask"])[0]
    r_all = sim["vector"]; durs = sim["durations"]
    r_is = r_all[z_is][r_all[z_is] != 0]; r_oos = r_all[z_oos][r_all[z_oos] != 0]
    pf = lambda r: np.sum(r[r > 0]) / (abs(np.sum(r[r < 0])) + 1e-9) if len(r) else 0
    mk = {}
    for zm, tag in ((z_is, "is"), (z_oos, "oos")):
        e_z = idx_e[zm[idx_e]]
        if len(e_z) < 1: mk[tag] = np.nan; continue
        pos = np.searchsorted(idx_e, e_z)
        expo = int(max(1, round(float(np.mean(durs[pos])))))
        fr = fp / float(np.mean(close[zm]))
        r = monkey_test(ret_1[zm], len(e_z), expo, float(r_all[zm].sum()),
                        top["Side"], n_monkeys=2000, seed=12345, friction_per_trade=fr)
        mk[tag] = r["pvalue"] * 100
    print(f"{fp:14} | {sim['n_trades']:6d} | {pf(r_is):5.2f} | {pf(r_oos):6.2f} "
          f"| {mk['is']:5.1f} | {mk['oos']:5.1f}")
# perfil del trade medio: ¿el edge es mas chico que el spread realista?
sim = simulate(data, cm, ri, top["Entry"], top["Exit"], top["Side"],
               cooldown=3, friction_points=0.0)
r_nz = sim["vector"][sim["vector"] != 0]
print(f"\nSIN friccion: retorno medio/trade {r_nz.mean()*1e4:+.2f} bps | "
      f"mediana {np.median(r_nz)*1e4:+.2f} bps | dur media {sim['durations'].mean():.1f} velas")
print("(1 pip EURUSD = ~0.9 bps; si el edge bruto es ~1-3 bps, vive DENTRO del spread)")
