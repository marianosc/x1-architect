# ##########################################################################
# SYSTEM: X1-ARCHITECT | BARRIDO MULTI-ACTIVO/TF (B4)
# FILE: tools/run_barrido_b4.py
# ROL: Correr el GA (mismas semillas + config) sobre cada (activo, TF) y medir
#      el holdout Z2 con el mismo escepticismo de multiplicidad (binomial vs
#      azar 10%). Veredicto: ¿ALGÚN (activo,TF) supera el azar con margen?
#      ⚠️ El barrido en sí tiene multiplicidad (~7 corridas): "pasó alguna" NO
#      alcanza; se reporta el binomial por celda y se juzga con escepticismo.
# USO: python tools/run_barrido_b4.py
# ##########################################################################
import os, sys, time, re, json
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch
from modules.formulaic import expand_formulaic, formulaic_vocabulary, is_formulaic
from modules.ga_miner import run_ga, geno_to_cand, geno_key

POP, GEN, N_EVOL, N_HOLDOUT, TOPK = 1000, 40, 500, 5000, 20
COMBOS = [  # (symbol, tf_label, f_points)
    ('XAUUSD', 'H1', 1.0), ('EURUSD', 'H1', 0.0001), ('GBPUSD', 'H1', 0.0002),
    ('USDJPY', 'H1', 0.015), ('EURGBP', 'H1', 0.0002),
    ('XAUUSD', 'H4', 1.0), ('EURGBP', 'H4', 0.0002),
]
LONG_TOK = re.compile(r'\s*(?:>=|<=|>|<|\|)\s*')


def run_one(sym, tf, fp):
    parquet = rf'C:\temp\X1_FULL_{sym}_{tf}.parquet'
    if not os.path.exists(parquet):
        print(f"  ! {sym} {tf}: falta {parquet} — salteado", flush=True)
        return None
    df = pd.read_parquet(parquet); zone = df['Zone'].values
    z_is, z_oos = zone == 1, zone == 2
    if z_is.sum() < 2000 or z_oos.sum() < 500:
        print(f"  ! {sym} {tf}: zonas chicas (Z1 {z_is.sum()}, Z2 {z_oos.sum()}) — salteado", flush=True)
        return None
    z1s, z1e = int(np.argmax(z_is)), int(np.where(z_is)[0][-1] + 1)
    base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
    data = base.values.astype(np.float32)
    cm = {n: i for i, n in enumerate(base.columns)}
    ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}
    data, cm = expand_formulaic(data, cm, formulaic_vocabulary(cm))
    cfg = {'cooldown': 25, 'f_points': fp}
    t = time.time()
    R = run_ga(data, cm, ri, z1s, z1e, cfg, pop=POP, generations=GEN, n_monkeys=N_EVOL,
               seed=2026, log=lambda *_: None)
    # top-K diversos
    close = data[:, cm['Close']].astype(np.float64)
    ret1 = np.zeros(len(close)); ret1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
    fr = fp / float(np.mean(close[z_oos]))
    winners, seen = [], []
    for g in R['winners']:
        tk = set(LONG_TOK.split(geno_to_cand(g)[0]))
        if all(len(tk & s) / (len(tk | s) + 1e-9) < 0.6 for s in seen):
            winners.append(g); seen.append(tk)
        if len(winners) >= TOPK:
            break
    jobs, fits = [], []
    for g in winners:
        rule, side, ex = geno_to_cand(g)
        try:
            sim = simulate(data, cm, ri, rule, ex, side, cooldown=25, friction_points=fp)
        except ValueError:
            continue
        idx = np.where(sim['mask'])[0]; ent = idx[z_oos[idx]]
        if len(ent) >= 5:
            pos = np.searchsorted(idx, ent); expo = int(max(1, round(float(np.mean(sim['durations'][pos])))))
            jobs.append(dict(ret_1=ret1[z_oos], n_trades=len(ent), exposure=expo,
                             strat_total=float(sim['vector'][z_oos].sum()), side=side,
                             n_monkeys=N_HOLDOUT, seed=4242, friction_per_trade=fr))
            fits.append(R['cache'][geno_key(g)])
    mk = np.array([r['pvalue'] * 100 for r in monkey_batch(jobs)]) if jobs else np.array([0.0])
    n90 = int((mk >= 90).sum())
    pbin = stats.binomtest(n90, len(mk), 0.10, alternative='greater').pvalue
    print(f"  [{sym} {tf}] {(time.time()-t)/60:.1f}min | mejor fitZ1 {max(R['best_hist']):.0f} | "
          f"únicos {R['n_unique']:,} | holdout: máx mk_z2 {mk.max():.1f}, pasan {n90}/{len(mk)}, "
          f"binomial p={pbin:.3f}", flush=True)
    return dict(sym=sym, tf=tf, best_fit_z1=round(max(R['best_hist']), 1), n_unique=R['n_unique'],
                max_mk_z2=round(float(mk.max()), 1), pass90=n90, n_top=len(mk),
                binomial_p=round(float(pbin), 3))


print(f"=== BARRIDO MULTI-ACTIVO/TF (B4) | {len(COMBOS)} corridas GA ===", flush=True)
rows = []
for sym, tf, fp in COMBOS:
    r = run_one(sym, tf, fp)
    if r:
        rows.append(r)
        pd.DataFrame(rows).to_csv('experimentos/barrido_b4.csv', index=False)  # checkpoint

T = pd.DataFrame(rows)
print("\n=== TABLA BARRIDO B4 ===")
print(T.to_string(index=False))
any_edge = ((T['binomial_p'] <= 0.05) & (T['max_mk_z2'] >= 90)).any()
print(f"\n=== VEREDICTO ===")
print(f"  corridas con tasa de pase > azar (binomial p<=0.05): {int((T['binomial_p']<=0.05).sum())}/{len(T)}")
print(f"  -> {'ALGUNA supera el azar: investigar ESE caso a fondo (no coronar)' if any_edge else 'NINGUNA supera el azar -> el metodo con indicadores tecnicos no da edge en mercados liquidos -> materia prima nueva'}")
print("CSV: experimentos/barrido_b4.csv", flush=True)
