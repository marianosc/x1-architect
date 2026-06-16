# ##########################################################################
# SYSTEM: X1-ARCHITECT | B4 - INVESTIGAR los combos que "pasan" el barrido
# FILE: tools/b4_investigate.py
# ROL: Los 4 (activo,TF) que baten la tasa del azar en el monkey se someten al
#      MISMO juez que cerró XAUUSD H1: DSR deflactado por N. ¿Sobrevive el
#      Sharpe, o es ruido de pocos trades / multiplicidad? Reporta también
#      n_oos (un monkey con pocos trades es poco fiable) y % formulaico.
# USO: python tools/b4_investigate.py
# ##########################################################################
import os, sys, re, time
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch
from modules.formulaic import expand_formulaic, formulaic_vocabulary, is_formulaic
from modules.ga_miner import run_ga, geno_to_cand, geno_key

GAMMA = 0.5772156649015329
POP, GEN, N_EVOL, N_HOLDOUT, TOPK = 1000, 40, 500, 5000, 20
TOK = re.compile(r'\s*(?:>=|<=|>|<|\|)\s*')
COMBOS = [('GBPUSD', 'H1', 0.0002), ('EURGBP', 'H1', 0.0002),
          ('XAUUSD', 'H4', 1.0), ('EURGBP', 'H4', 0.0002)]


def psr(sr, sr0, T, sk, ku):
    d = np.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4.0 * sr * sr))
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(max(1, T - 1)) / d))


def investigate(sym, tf, fp):
    df = pd.read_parquet(rf'C:\temp\X1_FULL_{sym}_{tf}.parquet'); zone = df['Zone'].values
    z_is, z_oos = zone == 1, zone == 2
    z1s, z1e = int(np.argmax(z_is)), int(np.where(z_is)[0][-1] + 1)
    base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
    data = base.values.astype(np.float32); cm = {n: i for i, n in enumerate(base.columns)}
    ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}
    data, cm = expand_formulaic(data, cm, formulaic_vocabulary(cm))
    cfg = {'cooldown': 25, 'f_points': fp}
    R = run_ga(data, cm, ri, z1s, z1e, cfg, pop=POP, generations=GEN, n_monkeys=N_EVOL,
               seed=2026, log=lambda *_: None)
    close = data[:, cm['Close']].astype(np.float64)
    ret1 = np.zeros(len(close)); ret1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
    fr = fp / float(np.mean(close[z_oos]))
    winners, seen = [], []
    for g in R['winners']:
        tk = set(TOK.split(geno_to_cand(g)[0]))
        if all(len(tk & s) / (len(tk | s) + 1e-9) < 0.6 for s in seen):
            winners.append(g); seen.append(tk)
        if len(winners) >= TOPK: break
    recs, jobs = [], []
    for g in winners:
        rule, side, ex = geno_to_cand(g)
        try:
            sim = simulate(data, cm, ri, rule, ex, side, cooldown=25, friction_points=fp)
        except ValueError:
            continue
        r2 = sim['vector'][z_oos]; r2 = r2[r2 != 0]
        idx = np.where(sim['mask'])[0]; ent = idx[z_oos[idx]]
        if len(ent) < 5 or len(r2) < 10:
            continue
        pos = np.searchsorted(idx, ent); expo = int(max(1, round(float(np.mean(sim['durations'][pos])))))
        jobs.append(dict(ret_1=ret1[z_oos], n_trades=len(ent), exposure=expo,
                         strat_total=float(sim['vector'][z_oos].sum()), side=side,
                         n_monkeys=N_HOLDOUT, seed=4242, friction_per_trade=fr))
        recs.append(dict(rule=rule[:55], side=side, exit=ex, n_oos=len(r2),
                         sr=float(np.mean(r2) / (np.std(r2, ddof=1) + 1e-12)),
                         skew=float(stats.skew(r2)), kurt=float(stats.kurtosis(r2, fisher=False)),
                         form=any(is_formulaic(t) for t in TOK.split(rule))))
    mk = [m['pvalue'] * 100 for m in monkey_batch(jobs)]
    D = pd.DataFrame(recs); D['mk_oos_z2'] = np.round(mk, 1)
    N = R['n_unique']
    v_sr = float(D['sr'].var(ddof=1))
    sr0 = np.sqrt(v_sr) * ((1 - GAMMA) * stats.norm.ppf(1 - 1.0 / N) + GAMMA * stats.norm.ppf(1 - 1.0 / (N * np.e)))
    D['dsr'] = D.apply(lambda r: psr(r['sr'], sr0, r['n_oos'], r['skew'], r['kurt']), axis=1)
    D = D.sort_values('dsr', ascending=False).reset_index(drop=True)
    D.insert(0, 'tf', tf); D.insert(0, 'sym', sym)
    return dict(sym=sym, tf=tf, N=N, sr0=round(sr0, 4), n_oos_med=int(D['n_oos'].median()),
                max_mk=float(D['mk_oos_z2'].max()), pass90=int((D['mk_oos_z2'] >= 90).sum()),
                max_sr=round(float(D['sr'].max()), 4), best_dsr=round(float(D['dsr'].max()), 3),
                dsr_sig=int((D['dsr'] >= 0.95).sum()), pct_form=round(100 * D['form'].mean()), table=D)


print("=== B4 INVESTIGACIÓN: DSR deflactado de los combos que pasan el monkey ===", flush=True)
out, tables = [], []
for sym, tf, fp in COMBOS:
    t = time.time(); r = investigate(sym, tf, fp)
    tables.append(r.pop('table')); out.append(r)
    print(f"  [{sym} {tf}] {(time.time()-t)/60:.1f}min | N={r['N']:,} | n_oos med {r['n_oos_med']} | "
          f"máx mk {r['max_mk']:.0f} ({r['pass90']}/20) | SR0 {r['sr0']} | máx SR {r['max_sr']} | "
          f"DSR best {r['best_dsr']} ({r['dsr_sig']} sig) | %form {r['pct_form']:.0f}", flush=True)

T = pd.DataFrame(out)
pd.concat(tables).to_csv('experimentos/b4_investigate_winners.csv', index=False)
T.to_csv('experimentos/b4_investigate.csv', index=False)
print("\n=== RESUMEN ===")
print(T[['sym', 'tf', 'N', 'n_oos_med', 'max_mk', 'pass90', 'sr0', 'max_sr', 'best_dsr', 'dsr_sig']].to_string(index=False))
nsig = int((T['dsr_sig'] > 0).sum())
print(f"\nVEREDICTO: combos con DSR>=0.95 (edge deflactado real): {nsig}/{len(T)}")
if nsig == 0:
    print("  -> el monkey 'pasaba' por ruido de pocos trades/multiplicidad; el DSR deflactado MATA a todos")
    print("  -> consistente con XAUUSD H1: no hay edge que sobreviva N -> materia prima nueva")
else:
    print("  -> HAY candidato(s) con Sharpe deflactado significativo: investigar a fondo SIN coronar (robustez, MT5)")
print("CSV: experimentos/b4_investigate.csv", flush=True)
