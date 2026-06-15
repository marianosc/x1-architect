# Corre el MONKEY sobre la COLA (top pf_is de Ret_72/Ret_96) de los sobrevivientes a
# PF>=1.25, para separar SKILL de exposición al bull 2022-26 (branch 2 de NOTEBOOK).
# Re-simula cada candidato (el CSV de transferencia no guarda vectores) y corre
# monkey_test EXACTO como L3 (misma fricción/cadencia/exposición, umbrales 99/90).
# El juez es la TASA AGREGADA que pasa MONKEY_OOS vs el ~10% de azar (multiplicidad),
# NO "pasó alguno". USO: monkey_tail.py [csv] [top_pct] [n_monkeys]
import sys, os
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats as sps

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.x1_engine import simulate

CSV = sys.argv[1] if len(sys.argv) > 1 else "experimentos/transfer_xauusd_h1.csv"
TOP_PCT = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
N_MONKEYS = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
COOLDOWN, F_POINTS, SEED = 25, 1.0, 12345
MK_IS_MIN, MK_OOS_MIN = 99.0, 90.0
EXITS_TAIL = {'Ret_72', 'Ret_96'}

from modules.x1_validators import monkey_test, monkey_batch
import time as _time

df = pd.read_parquet("C:/temp/X1_FULL_XAUUSD_H1.parquet")
zone = df['Zone'].values
z_is, z_oos = zone == 1, zone == 2
close = df['Close'].values.astype(np.float64)
# IDÉNTICO a L3.G_RET_1: shift(-1) deja NaN en la última vela (replica producción).
ret_1 = (df['Close'].shift(-1).values - df['Close'].values) / (df['Close'].values + 1e-9)
ret_is, ret_oos = ret_1[z_is], ret_1[z_oos]
fr_is = F_POINTS / float(np.mean(close[z_is]))
fr_oos = F_POINTS / float(np.mean(close[z_oos]))
dfm = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
G = dfm.values.astype(np.float32)
cmap = {n: i for i, n in enumerate(dfm.columns)}
ri = {n: i for i, n in enumerate(dfm.columns) if 'Ret_' in n}

trans = pd.read_csv(CSV)
pool = trans[trans['exit'].isin(EXITS_TAIL)].copy()
thr = np.percentile(pool['pf_is'].values, 100 - TOP_PCT)
tail = pool[pool['pf_is'] >= thr].reset_index(drop=True)
print(f"=== MONKEY de la COLA | exits={sorted(EXITS_TAIL)} | top {TOP_PCT:.0f}% pf_is (>= {thr:.4f}) "
      f"| n_monkeys={N_MONKEYS} ===", flush=True)
print(f"Cola: {len(tail)} candidatos de {len(pool)} en Ret_72/96. Corriendo monkey IS+OOS...", flush=True)

# v108-B0: dos pasadas. (1) simulate serial -> arma los jobs del monkey;
# (2) monkey_batch corre TODOS los monkeys en paralelo (kernels nogil). El
# resultado es idéntico al loop serial (paridad probada) pero en minutos.
rows = [{'exit': r['exit'], 'pf_is': r['pf_is'], 'pf_oos': r['pf_oos'],
         'mk_is': -1.0, 'mk_oos': -1.0} for _, r in tail.iterrows()]
jobs, tags = [], []  # tags = (índice_fila, 'mk_is'/'mk_oos')
t_sim0 = _time.time()
for k, r in tail.iterrows():
    sim = simulate(G, cmap, ri, r['rule'], r['exit'], r['side'], cooldown=COOLDOWN, friction_points=F_POINTS)
    idx_e = np.where(sim['mask'])[0]
    durs, r_all = sim['durations'], sim['vector']
    for zmask, ret_z, fr, key in ((z_is, ret_is, fr_is, 'mk_is'), (z_oos, ret_oos, fr_oos, 'mk_oos')):
        ent = idx_e[zmask[idx_e]]
        if len(ent) < 1:
            continue
        pos = np.searchsorted(idx_e, ent)
        expo = int(max(1, round(float(np.mean(durs[pos])))))
        strat = float(r_all[zmask].sum())
        jobs.append(dict(ret_1=ret_z, n_trades=len(ent), exposure=expo, strat_total=strat,
                         side=r['side'], n_monkeys=N_MONKEYS, seed=SEED, friction_per_trade=fr))
        tags.append((k, key))
print(f"  simulate (serial): {len(tail)} candidatos en {_time.time()-t_sim0:.1f}s "
      f"-> {len(jobs)} monkey-jobs", flush=True)
t_mk0 = _time.time()
results = monkey_batch(jobs)  # PARALELO (threading + nogil)
print(f"  monkey ({N_MONKEYS} monos × {len(jobs)} jobs, PARALELO): {_time.time()-t_mk0:.1f}s", flush=True)
for (k, key), res in zip(tags, results):
    rows[k][key] = res['pvalue'] * 100.0

R = pd.DataFrame(rows)
n = len(R)
po = (R['mk_oos'] >= MK_OOS_MIN)
pi = (R['mk_is'] >= MK_IS_MIN)
both = po & pi
rate_oos = 100 * po.mean()
# Binomial: ¿la tasa que pasa MONKEY_OOS supera el 10% de azar (umbral 90%)?
binom = sps.binomtest(int(po.sum()), n, 0.10, alternative='greater').pvalue

print(f"\n--- Resultado MONKEY de la cola (n={n}) ---")
print(f"  mk_oos: mediana {R['mk_oos'].median():.1f} | Q3 {R['mk_oos'].quantile(.75):.1f} | máx {R['mk_oos'].max():.1f}")
print(f"  pasan MONKEY_OOS (>=90): {int(po.sum())}/{n} = {rate_oos:.1f}%   (azar esperado ~10%)")
print(f"  pasan MONKEY_IS  (>=99): {int(pi.sum())}/{n} = {100*pi.mean():.1f}%")
print(f"  pasan AMBOS (gate real L3): {int(both.sum())}/{n} = {100*both.mean():.1f}%")
print(f"  Binomial P(tasa_oos > 10% azar): p = {binom:.3e}")
print(f"\n=== VEREDICTO ===")
if rate_oos <= 13 or binom > 0.05:
    print(f"  Tasa MONKEY_OOS {rate_oos:.1f}% ~ azar (10%) -> la cola NO supera al timing aleatorio")
    print(f"  -> el pf_oos era EXPOSICIÓN al bull, no skill -> ANTI-EDGE confirmado -> v108.1 gramática")
else:
    print(f"  Tasa MONKEY_OOS {rate_oos:.1f}% >> 10% (p={binom:.1e}) -> hay SKILL que supera el azar en la cola")
    print(f"  -> re-confirmar a n=5000 los que pasan ambos; candidatos reales tras el muro")
R.to_csv("experimentos/monkey_tail_xauusd_h1.csv", index=False)
print("CSV: experimentos/monkey_tail_xauusd_h1.csv", flush=True)
