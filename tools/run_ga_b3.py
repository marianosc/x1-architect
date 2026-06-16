# ##########################################################################
# SYSTEM: X1-ARCHITECT | RUN B3 (primera corrida del minero evolutivo)
# FILE: tools/run_ga_b3.py
# ROL: Correr el GA (warm-start + fitness B1) sobre XAUUSD H1 y medir el
#      veredicto: ¿algún ganador supera, en el HOLDOUT Z2 + monkey OOS (UNA
#      sola medición), el techo de la gramática vieja random?
# USO: python tools/run_ga_b3.py [pop] [generations] [n_evol]
# ##########################################################################
import os, sys, time, json
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch
from modules.formulaic import expand_formulaic, formulaic_vocabulary, is_formulaic
from modules.ga_miner import run_ga, geno_to_cand, geno_key

POP = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
GEN = int(sys.argv[2]) if len(sys.argv) > 2 else 40
N_EVOL = int(sys.argv[3]) if len(sys.argv) > 3 else 500     # B1: evolución 300-500
N_HOLDOUT = 5000                                            # B1: finalistas 5000
CFG = {'cooldown': 25, 'f_points': 1.0}
PARQUET = r'C:\temp\X1_FULL_XAUUSD_H1.parquet'
TOPK = 20

t0 = time.time()
df = pd.read_parquet(PARQUET); zone = df['Zone'].values
z_is, z_oos = zone == 1, zone == 2
z1s, z1e = int(np.argmax(z_is)), int(np.where(z_is)[0][-1] + 1)
base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}
print(f"[B3] XAUUSD H1 | Z1 [{z1s},{z1e}) {z1e-z1s} velas | Z2 holdout {int(z_oos.sum())} velas", flush=True)

# pre-expandir TODO el vocabulario formulaico (una vez) → el GA no re-expande
vocab_form = formulaic_vocabulary(cm)
data, cm = expand_formulaic(data, cm, vocab_form)
print(f"[B3] vocabulario formulaico pre-expandido: +{len(vocab_form)} columnas "
      f"({data.shape[1]} totales) en {time.time()-t0:.0f}s", flush=True)

# ---------------- GA (Z2 JAMÁS entra al fitness) ----------------
print(f"[B3] GA: pop {POP} × 4 islas × {GEN} gen | fitness B1 n={N_EVOL} Q25 | warm-start 3 hipótesis", flush=True)
tg = time.time()
R = run_ga(data, cm, ri, z1s, z1e, CFG, pop=POP, generations=GEN, n_monkeys=N_EVOL, seed=2026)
print(f"[B3] GA terminado en {(time.time()-tg)/60:.1f} min | {R['n_unique']:,} individuos ÚNICOS evaluados", flush=True)

# top-K diversos (Jaccard de tokens < 0.6)
def toks(rule):
    import re
    return set(re.split(r'\s*(?:>=|<=|>|<|\|)\s*', rule))
winners, seen_tok = [], []
for g in R['winners']:
    rule = geno_to_cand(g)[0]; tk = toks(rule)
    if all(len(tk & s) / (len(tk | s) + 1e-9) < 0.6 for s in seen_tok):
        winners.append(g); seen_tok.append(tk)
    if len(winners) >= TOPK:
        break

# ---------------- HOLDOUT Z2 (UNA sola medición) ----------------
close = data[:, cm['Close']].astype(np.float64)
ret1 = np.zeros(len(close)); ret1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
fr = CFG['f_points'] / float(np.mean(close[z_oos]))
jobs, meta = [], []
for g in winners:
    rule, side, ex = geno_to_cand(g)
    try:
        sim = simulate(data, cm, ri, rule, ex, side, cooldown=25, friction_points=CFG['f_points'])
    except ValueError:
        continue
    idx = np.where(sim['mask'])[0]; ent = idx[z_oos[idx]]
    pf_is = 0.0
    r_i = sim['vector'][z_is]; r_i = r_i[r_i != 0]
    if len(r_i) >= 2:
        pf_is = r_i[r_i > 0].sum() / (abs(r_i[r_i < 0].sum()) + 1e-9)
    if len(ent) >= 5:
        pos = np.searchsorted(idx, ent); expo = int(max(1, round(float(np.mean(sim['durations'][pos])))))
        jobs.append(dict(ret_1=ret1[z_oos], n_trades=len(ent), exposure=expo,
                         strat_total=float(sim['vector'][z_oos].sum()), side=side,
                         n_monkeys=N_HOLDOUT, seed=4242, friction_per_trade=fr))
        meta.append(dict(rule=rule, side=side, exit=ex, fit=R['cache'][geno_key(g)],
                         pf_is=round(float(pf_is), 3), n_oos=int(len(ent)),
                         form=any(is_formulaic(t) for t in toks(rule))))
res = monkey_batch(jobs)
for m, r in zip(meta, res):
    m['mk_oos_z2'] = round(r['pvalue'] * 100.0, 1)

W = pd.DataFrame(meta).sort_values('mk_oos_z2', ascending=False).reset_index(drop=True)
W.to_csv('experimentos/ga_b3_winners.csv', index=False)
json.dump({'best_hist': R['best_hist'], 'n_unique': R['n_unique'], 'pop': POP, 'gen': GEN,
           'n_evol': N_EVOL}, open('experimentos/ga_b3_meta.json', 'w'))

print(f"\n=== VEREDICTO B3 (XAUUSD H1) ===")
print(f"  mejor fitness Z1 (B1): {max(R['best_hist']):.1f}")
print(f"  individuos únicos evaluados: {R['n_unique']:,}  (= N para el DSR de B4)")
print(f"  HOLDOUT Z2 (monkey OOS n={N_HOLDOUT}, UNA medición) de los top-{len(W)} diversos:")
print(W[['mk_oos_z2', 'fit', 'pf_is', 'n_oos', 'side', 'exit', 'form', 'rule']].head(12).to_string(index=False))
n90 = int((W['mk_oos_z2'] >= 90).sum())
print(f"\n  ganadores que pasan mk_oos_z2>=90 (gate real): {n90}/{len(W)} | máx mk_oos_z2 {W['mk_oos_z2'].max():.1f}")
print(f"  TECHO gramática vieja random (control B2a, ref): top-50 mk_z2 ~58-60, máx individual ~89")
print(f"  -> {'HAY edge: el GA supera el techo random' if W['mk_oos_z2'].max() >= 90 else 'sin edge claro: ningún ganador pasa el gate 90 en Z2'}")
print(f"\n[B3] total {(time.time()-t0)/60:.1f} min. CSV: experimentos/ga_b3_winners.csv", flush=True)
