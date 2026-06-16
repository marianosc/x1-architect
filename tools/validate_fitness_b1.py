# ##########################################################################
# SYSTEM: X1-ARCHITECT | VALIDACIÓN B1 (control previo al GA)
# FILE: tools/validate_fitness_b1.py
# ROL: Confirmar que el fitness v108 (solo Z1) ORDENA por skill honesto y NO
#      por beta de régimen. Compara contra dos referencias en Z2:
#        - pf_oos  : la métrica naive que elegía beta (PF en Z2).
#        - mk_oos_Z2 (n=1000): la VERDAD honesta (monkey OOS real).
#      ⚠️ El monkey de Z2 se computa SOLO acá para validar; el fitness/GA
#      JAMÁS tocan Z2 (holdout final B4).
# USO: python tools/validate_fitness_b1.py [n_sample] [n_monkeys_fit]
# ##########################################################################
import os, sys
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch
from modules.fitness_v108 import fitness_population

N_SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 4000
N_FIT = int(sys.argv[2]) if len(sys.argv) > 2 else 400
N_TRUTH = 1000
CFG = {'cooldown': 25, 'f_points': 1.0}
PARQUET = r"C:\temp\X1_FULL_XAUUSD_H1.parquet"
POOLS = [r"C:\temp\X1_RAW_XAUUSD_LONG_MOMENTUM.parquet",
         r"C:\temp\X1_RAW_XAUUSD_LONG_TREND.parquet"]

df = pd.read_parquet(PARQUET)
zone = df['Zone'].values
z_is, z_oos = zone == 1, zone == 2
z1_start, z1_end = int(np.argmax(z_is)), int(np.where(z_is)[0][-1] + 1)
base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}
close = data[:, cm['Close']].astype(np.float64)
ret_1 = np.zeros(len(close)); ret_1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
fr_oos = CFG['f_points'] / float(np.mean(close[z_oos]))

pool = pd.concat([pd.read_parquet(p) for p in POOLS], ignore_index=True)
pool = pool.sample(n=min(N_SAMPLE, len(pool)), random_state=42).reset_index(drop=True)
cands = list(zip(pool['Entry'], pool['Side'], pool['Exit']))
print(f"Pool {len(pool):,} | Z1 [{z1_start},{z1_end}) {z1_end-z1_start} velas | "
      f"exits: {pool['Exit'].value_counts().to_dict()}", flush=True)

# --- FITNESS v108 (SOLO Z1, n={N_FIT}) ---
import time; t0 = time.time()
fit = fitness_population(cands, data, cm, ri, z1_start, z1_end, CFG, n_monkeys=N_FIT, lam=0.0)
print(f"fitness_population: {len(cands)} candidatos en {time.time()-t0:.0f}s", flush=True)

# --- Referencias: pf_IS (la métrica SOLO-Z1 que el minero usa hoy) y, como
#     VERDAD honesta, el monkey de Z2 n=1000 + pf_oos (identificador de beta).
#     Tanto pf_is como fitness son SOLO-Z1: comparación justa de predictores. ---
pf_is = np.full(len(cands), np.nan)
pf_oos = np.full(len(cands), np.nan)
jobs, tags = [], []
for ci, (rule, side, exit_l) in enumerate(cands):
    try:
        sim = simulate(data, cm, ri, rule, exit_l, side, cooldown=CFG['cooldown'], friction_points=CFG['f_points'])
    except ValueError:
        continue
    idx_e = np.where(sim['mask'])[0]; r_all = sim['vector']; durs = sim['durations']
    r_i = r_all[z_is][r_all[z_is] != 0]
    if len(r_i) >= 2:
        pf_is[ci] = r_i[r_i > 0].sum() / (abs(r_i[r_i < 0].sum()) + 1e-9)
    r_o = r_all[z_oos][r_all[z_oos] != 0]
    if len(r_o) >= 2:
        pf_oos[ci] = r_o[r_o > 0].sum() / (abs(r_o[r_o < 0].sum()) + 1e-9)
    ent = idx_e[z_oos[idx_e]]
    if len(ent) >= 5:
        pos = np.searchsorted(idx_e, ent)
        expo = int(max(1, round(float(np.mean(durs[pos])))))
        jobs.append(dict(ret_1=ret_1[z_oos], n_trades=len(ent), exposure=expo,
                         strat_total=float(r_all[z_oos].sum()), side=side,
                         n_monkeys=N_TRUTH, seed=777 + ci, friction_per_trade=fr_oos))
        tags.append(ci)
res = monkey_batch(jobs)
mk_oos_z2 = np.full(len(cands), np.nan)
for ci, r in zip(tags, res):
    mk_oos_z2[ci] = r['pvalue'] * 100.0

R = pd.DataFrame({'exit': pool['Exit'], 'fitness': [f['fitness_core'] for f in fit],
                  'n_valid': [f['n_valid'] for f in fit], 'pf_is': pf_is,
                  'pf_oos': pf_oos, 'mk_oos_z2': mk_oos_z2})
R = R[R['mk_oos_z2'].notna() & R['pf_is'].notna()].reset_index(drop=True)
print(f"\nEvaluables (con Z1 e Z2 medibles): {len(R)}", flush=True)


def sp(a, b):
    m = R[[a, b]].dropna(); rho, p = stats.spearmanr(m[a], m[b]); return rho, p


print("\n=== PREDICCIÓN HONESTA Z1->Z2 (solo-Z1 vs la verdad mk_oos_z2) ===")
print("  (pf_oos no cuenta: ve Z2 directo. La pelea justa es pf_is vs fitness, ambos solo-Z1.)")
rho_pfis, p_pfis = sp('pf_is', 'mk_oos_z2')
rho_fit, p_fit = sp('fitness', 'mk_oos_z2')
print(f"  Spearman(pf_is  [naive minero], mk_oos_z2) = {rho_pfis:+.3f} (p={p_pfis:.1e})")
print(f"  Spearman(fitness[B1]          , mk_oos_z2) = {rho_fit:+.3f} (p={p_fit:.1e})")
print(f"  Spearman(pf_oos [ve Z2, ref]  , mk_oos_z2) = {sp('pf_oos','mk_oos_z2')[0]:+.3f}")

TOPK = 50
r96 = lambda d: 100 * (d['exit'] == 'Ret_96').mean()
top_pfis = R.nlargest(TOPK, 'pf_is')
top_fit = R.nlargest(TOPK, 'fitness')
print(f"\n=== TOP {TOPK} por la métrica SOLO-Z1 (lo que el minero elegiría) ===")
print(f"  por pf_is (naive minero): mk_oos_z2 medio {top_pfis['mk_oos_z2'].mean():5.1f} | "
      f"%Ret_96 {r96(top_pfis):.0f}% | pasan mk_oos_z2>=90: {int((top_pfis['mk_oos_z2']>=90).sum())}/{TOPK}")
print(f"  por fitness (B1)        : mk_oos_z2 medio {top_fit['mk_oos_z2'].mean():5.1f} | "
      f"%Ret_96 {r96(top_fit):.0f}% | pasan mk_oos_z2>=90: {int((top_fit['mk_oos_z2']>=90).sum())}/{TOPK}")
print(f"  (pool entero: %Ret_96 {r96(R):.0f}% | mk_oos_z2 medio {R['mk_oos_z2'].mean():.1f})")

print("\n=== VEREDICTO B1 ===")
ok_order = rho_fit > rho_pfis and rho_fit > 0.1
ok_top = top_fit['mk_oos_z2'].mean() > top_pfis['mk_oos_z2'].mean()
print(f"  fitness predice Z2 mejor que pf_is (ambos solo-Z1): {ok_order} "
      f"(fit {rho_fit:+.3f} vs pf_is {rho_pfis:+.3f})")
print(f"  el top-por-fitness es más honesto en Z2 que el top-por-pf_is: {ok_top} "
      f"(mk_z2 {top_fit['mk_oos_z2'].mean():.1f} vs {top_pfis['mk_oos_z2'].mean():.1f})")
print(f"  -> B1 {'VALIDADO' if (ok_order and ok_top) else 'REVISAR'}")
R.to_csv("experimentos/validate_fitness_b1.csv", index=False)
print("CSV: experimentos/validate_fitness_b1.csv", flush=True)
