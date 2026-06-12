# FASE 2: re-auditoria bajo v107 (posicion unica) de los 2 finalistas H4
# honestos de solape de C1. La pregunta: ¿sobreviven al motor honesto?
import sys, os
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_test

FINALISTAS = [
    ("adx_34_sft >= 26.935992|minus_di_8_sft >= 19.712099", "A1"),
    ("aroon_120_sft >= -3.42|plus_di_34_sft <= 17.774609", "C1-s1"),
]
COOLDOWN, FRICTION = 6, 1.0

df = pd.read_parquet(r"C:\temp\X1_FULL_XAUUSD_H4.parquet")
zone = df["Zone"].values
z_is, z_oos = zone == 1, zone == 2
base = df.drop(columns=["DateTime", "Zone"], errors="ignore")
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if "Ret_" in n}
close = data[:, cm["Close"]].astype(np.float64)
ret_1 = np.zeros(len(close))
ret_1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)

print("regla | origen | trades v107 (vs viejo) | pf_is | mk_is | mk_oos | veredicto 99/90")
for rule, origen in FINALISTAS:
    res = {}
    for sp, tag in ((True, "v107"), (False, "viejo")):
        sim = simulate(data, cm, ri, rule, "SINTETICA_REVERSE", "LONG",
                       cooldown=COOLDOWN, friction_points=FRICTION, single_position=sp)
        res[tag] = sim
    sim = res["v107"]
    idx_e = np.where(sim["mask"])[0]
    r_all = sim["vector"]; durs = sim["durations"]
    r_is = r_all[z_is][r_all[z_is] != 0]
    pf_is = np.sum(r_is[r_is > 0]) / (abs(np.sum(r_is[r_is < 0])) + 1e-9) if len(r_is) else 0
    mk = {}
    for z_mask, tag in ((z_is, "is"), (z_oos, "oos")):
        e_z = idx_e[z_mask[idx_e]]
        if len(e_z) < 1:
            mk[tag] = float("nan"); continue
        pos = np.searchsorted(idx_e, e_z)
        expo = int(max(1, round(float(np.mean(durs[pos])))))
        fr = FRICTION / float(np.mean(close[z_mask]))
        r = monkey_test(ret_1[z_mask], len(e_z), expo, float(r_all[z_mask].sum()),
                        "LONG", n_monkeys=5000, seed=12345, friction_per_trade=fr)
        mk[tag] = r["pvalue"] * 100
    ok = "PASS" if (mk["is"] >= 99 and mk["oos"] >= 90) else "FAIL"
    print(f"{rule[:46]:<47} | {origen:5} | {sim['n_trades']:4d} (vs {res['viejo']['n_trades']}) "
          f"| {pf_is:5.2f} | {mk['is']:5.1f} | {mk['oos']:5.1f} | {ok}")
