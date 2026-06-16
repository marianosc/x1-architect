# ##########################################################################
# SYSTEM: X1-ARCHITECT | B1 TUNING (barrido + validación cruzada EURGBP)
# FILE: tools/barrido_b1.py
# ROL: Cerrar la config del fitness v108. Barre n∈{400,1000}×agg∈{mediana,Q25}
#      sobre XAUUSD (Z2 bull, sesgado a beta) Y EURGBP (sin tendencia = JUEZ
#      JUSTO del fitness beta-neutral, spec NOTEBOOK).
#      Juez: (a) Spearman(fitness, mk_oos_z2) global, (b) de-sesgo de beta
#      (% horizonte largo en el top-50), (c) coherencia en EURGBP.
# USO: python tools/barrido_b1.py [n_sample]
# ##########################################################################
import os, sys, time, json
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch
from modules.fitness_v108 import fitness_population

N_SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
N_TRUTH = 1000
LONG_HORIZON = {'Ret_72', 'Ret_96'}   # los exits "beta" (deriva larga)
SYMBOLS = {
    'XAUUSD': dict(parquet=r'C:\temp\X1_FULL_XAUUSD_H1.parquet', f_points=1.0,
                   pools=[r'C:\temp\X1_RAW_XAUUSD_LONG_MOMENTUM.parquet',
                          r'C:\temp\X1_RAW_XAUUSD_LONG_TREND.parquet']),
    'EURGBP': dict(parquet=r'C:\temp\X1_FULL_EURGBP_H1.parquet', f_points=0.0002,
                   pools=[r'C:\temp\X1_RAW_EURGBP_LONG_MOMENTUM.parquet',
                          r'C:\temp\X1_RAW_EURGBP_LONG_TREND.parquet']),
}
CONFIGS = [(400, 'median'), (1000, 'median'), (400, 'q25'), (1000, 'q25')]


def load_symbol(sym, spec):
    df = pd.read_parquet(spec['parquet'])
    zone = df['Zone'].values
    z_is, z_oos = zone == 1, zone == 2
    z1s, z1e = int(np.argmax(z_is)), int(np.where(z_is)[0][-1] + 1)
    base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
    data = base.values.astype(np.float32)
    cm = {n: i for i, n in enumerate(base.columns)}
    ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}
    close = data[:, cm['Close']].astype(np.float64)
    ret1 = np.zeros(len(close)); ret1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
    pool = pd.concat([pd.read_parquet(p) for p in spec['pools']], ignore_index=True)
    pool = pool.sample(n=min(N_SAMPLE, len(pool)), random_state=42).reset_index(drop=True)
    cands = list(zip(pool['Entry'], pool['Side'], pool['Exit']))
    fp = spec['f_points']; fr_oos = fp / float(np.mean(close[z_oos]))
    # verdad Z2 (solo validación) + pf_is
    pf_is = np.full(len(cands), np.nan); jobs, tags = [], []
    for ci, (rule, side, ex) in enumerate(cands):
        try:
            sim = simulate(data, cm, ri, rule, ex, side, cooldown=25, friction_points=fp)
        except ValueError:
            continue
        idx = np.where(sim['mask'])[0]; r_all = sim['vector']
        r_i = r_all[z_is][r_all[z_is] != 0]
        if len(r_i) >= 2:
            pf_is[ci] = r_i[r_i > 0].sum() / (abs(r_i[r_i < 0].sum()) + 1e-9)
        ent = idx[z_oos[idx]]
        if len(ent) >= 5:
            pos = np.searchsorted(idx, ent); expo = int(max(1, round(float(np.mean(sim['durations'][pos])))))
            jobs.append(dict(ret_1=ret1[z_oos], n_trades=len(ent), exposure=expo,
                             strat_total=float(r_all[z_oos].sum()), side=side,
                             n_monkeys=N_TRUTH, seed=777 + ci, friction_per_trade=fr_oos))
            tags.append(ci)
    mk = np.full(len(cands), np.nan)
    for ci, r in zip(tags, monkey_batch(jobs)):
        mk[ci] = r['pvalue'] * 100.0
    return dict(data=data, cm=cm, ri=ri, z1s=z1s, z1e=z1e, cfg={'cooldown': 25, 'f_points': fp},
                cands=cands, exits=pool['Exit'].values, pf_is=pf_is, mk=mk)


print(f"Cargando símbolos (pool {N_SAMPLE}/símbolo, verdad Z2 n={N_TRUTH})...", flush=True)
S = {}
for sym, spec in SYMBOLS.items():
    t = time.time(); S[sym] = load_symbol(sym, spec)
    print(f"  {sym}: {len(S[sym]['cands'])} cands en {time.time()-t:.0f}s", flush=True)


def metrics(sym, fitness_core):
    d = S[sym]
    R = pd.DataFrame({'exit': d['exits'], 'fit': fitness_core, 'pf_is': d['pf_is'], 'mk': d['mk']})
    R = R[R['mk'].notna() & R['pf_is'].notna()].reset_index(drop=True)
    rho = stats.spearmanr(R['fit'], R['mk'])[0]
    top = R.nlargest(50, 'fit')
    longp = 100 * top['exit'].isin(LONG_HORIZON).mean()
    return dict(rho=rho, top_mk=float(top['mk'].mean()), top_long=float(longp),
                pool_long=100 * R['exit'].isin(LONG_HORIZON).mean())


rows = []
# baseline pf_is (referencia naive, una vez por símbolo)
for sym in SYMBOLS:
    d = S[sym]; R = pd.DataFrame({'exit': d['exits'], 'pf_is': d['pf_is'], 'mk': d['mk']}).dropna()
    rho = stats.spearmanr(R['pf_is'], R['mk'])[0]; top = R.nlargest(50, 'pf_is')
    rows.append(dict(config='pf_is(naive)', sym=sym, rho=round(rho, 3),
                     top_mk=round(float(top['mk'].mean()), 1),
                     top_long=round(100 * top['exit'].isin(LONG_HORIZON).mean(), 0)))

for n, agg in CONFIGS:
    for sym in SYMBOLS:
        d = S[sym]
        fit = fitness_population(d['cands'], d['data'], d['cm'], d['ri'], d['z1s'], d['z1e'],
                                 d['cfg'], n_monkeys=n, agg=agg)
        m = metrics(sym, np.array([f['fitness_core'] for f in fit]))
        rows.append(dict(config=f'n={n},{agg}', sym=sym, rho=round(m['rho'], 3),
                         top_mk=round(m['top_mk'], 1), top_long=round(m['top_long'], 0)))
        print(f"  {sym} n={n} {agg}: Spearman {m['rho']:+.3f} | top50 mk_z2 {m['top_mk']:.1f} | "
              f"top50 %largo {m['top_long']:.0f}% (pool {m['pool_long']:.0f}%)", flush=True)

T = pd.DataFrame(rows)
T.to_csv("experimentos/barrido_b1.csv", index=False)
print("\n=== TABLA (juez: Spearman global + de-sesgo beta [top %largo BAJO] + coherencia EURGBP) ===")
piv = T.pivot(index='config', columns='sym', values=['rho', 'top_long'])
print(piv.to_string())
print("\nCSV: experimentos/barrido_b1.csv")
