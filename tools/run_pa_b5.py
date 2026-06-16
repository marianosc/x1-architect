# ##########################################################################
# SYSTEM: X1-ARCHITECT | RUN price action (materia prima nueva)
# FILE: tools/run_pa_b5.py
# ROL: GA minando SOLO con features de ACCIÓN DE PRECIO (geometría OHLC) sobre
#      XAUUSD H1 y H4 → funnel completo (holdout Z2 + monkey n=5000 + DSR
#      deflactado por N). ¿La geometría del precio tiene edge que los
#      osciladores promediaban y perdían? El DSR decide.
# USO: python tools/run_pa_b5.py [pop] [gen] [n_evol]
# ##########################################################################
import os, sys, re, time
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch
from modules.price_action import expand_price_action, price_action_vocabulary, is_price_action
from modules.ga_miner import run_ga, geno_to_cand, geno_key

GAMMA = 0.5772156649015329
POP = int(sys.argv[1]) if len(sys.argv) > 1 else 1000
GEN = int(sys.argv[2]) if len(sys.argv) > 2 else 40
N_EVOL = int(sys.argv[3]) if len(sys.argv) > 3 else 500
N_HOLDOUT, TOPK = 5000, 20
COMBOS = [('XAUUSD', 'H1', 1.0), ('XAUUSD', 'H4', 1.0)]
TOK = re.compile(r'\s*(?:>=|<=|>|<|\|)\s*')


def pa_seeds():
    H = {
        'TREND': [[('breakout_high20_sft', '>=', '1')],
                  [('close_pos_sft', '>=', '0.7'), ('n_higher_highs20_sft', '>=', '12')]],
        'MOM':   [[('close_pos_sft', '>=', '0.8')],
                  [('n_consec_up_sft', '>=', '3')]],
        'VOL':   [[('range_atr_sft', '>=', '1.5')],
                  [('body_atr_sft', '>=', '1.0'), ('close_pos_sft', '>=', '0.7')]],
        'CYCLE': [[('lower_wick_sft', '>=', '0.5')],
                  [('dist_swinglow20_sft', '<=', '0.01'), ('close_pos_sft', '>=', '0.6')]],
    }
    seeds = {}
    for isl, lst in H.items():
        gl = []
        for conds in lst:
            for side in ('LONG', 'SHORT'):
                for ex in ('Ret_24', 'SINTETICA_REVERSE'):
                    gl.append({'conds': [tuple(c) for c in conds], 'side': side, 'exit': ex})
        seeds[isl] = gl
    return seeds


def psr(sr, sr0, T, sk, ku):
    d = np.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4.0 * sr * sr))
    return float(stats.norm.cdf((sr - sr0) * np.sqrt(max(1, T - 1)) / d))


def run_combo(sym, tf, fp):
    df = pd.read_parquet(rf'C:\temp\X1_FULL_{sym}_{tf}.parquet'); zone = df['Zone'].values
    z_is, z_oos = zone == 1, zone == 2
    z1s, z1e = int(np.argmax(z_is)), int(np.where(z_is)[0][-1] + 1)
    base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
    data = base.values.astype(np.float32); cm = {n: i for i, n in enumerate(base.columns)}
    ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}
    pa_vocab = price_action_vocabulary()
    data, cm = expand_price_action(data, cm, pa_vocab)
    cfg = {'cooldown': 25, 'f_points': fp}
    R = run_ga(data, cm, ri, z1s, z1e, cfg, pop=POP, generations=GEN, n_monkeys=N_EVOL,
               seed=2026, log=lambda *_: None,
               extra_lhs=pa_vocab, replace_lhs=True, seeds_override=pa_seeds())
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
        recs.append(dict(sym=sym, tf=tf, rule=rule[:60], side=side, exit=ex, n_oos=len(r2),
                         fit=R['cache'][geno_key(g)],
                         sr=float(np.mean(r2) / (np.std(r2, ddof=1) + 1e-12)),
                         skew=float(stats.skew(r2)), kurt=float(stats.kurtosis(r2, fisher=False)),
                         pa=any(is_price_action(t) for t in TOK.split(rule))))
    mk = [m['pvalue'] * 100 for m in monkey_batch(jobs)]
    D = pd.DataFrame(recs); D['mk_oos_z2'] = np.round(mk, 1)
    N = R['n_unique']; v = float(D['sr'].var(ddof=1))
    sr0 = np.sqrt(v) * ((1 - GAMMA) * stats.norm.ppf(1 - 1.0 / N) + GAMMA * stats.norm.ppf(1 - 1.0 / (N * np.e)))
    D['dsr'] = D.apply(lambda r: psr(r['sr'], sr0, r['n_oos'], r['skew'], r['kurt']), axis=1)
    D = D.sort_values('dsr', ascending=False).reset_index(drop=True)
    nb = int((D['mk_oos_z2'] >= 90).sum())
    pbin = stats.binomtest(nb, len(D), 0.10, alternative='greater').pvalue
    return D, dict(sym=sym, tf=tf, best_fit=round(max(R['best_hist']), 1), n_unique=N,
                   n_oos_med=int(D['n_oos'].median()), max_mk=float(D['mk_oos_z2'].max()),
                   pass90=nb, n_top=len(D), binom_p=round(pbin, 3), sr0=round(sr0, 4),
                   max_sr=round(float(D['sr'].max()), 4), best_dsr=round(float(D['dsr'].max()), 3),
                   dsr_sig=int((D['dsr'] >= 0.95).sum()), pct_pa=round(100 * D['pa'].mean()))


print("=== PRICE ACTION (materia prima nueva) — GA solo-OHLC-geométrico + funnel + DSR ===", flush=True)
rows, tables = [], []
for sym, tf, fp in COMBOS:
    t = time.time(); D, r = run_combo(sym, tf, fp)
    tables.append(D); rows.append(r)
    print(f"  [{sym} {tf}] {(time.time()-t)/60:.1f}min | fitZ1 {r['best_fit']:.0f} | N={r['n_unique']:,} | "
          f"n_oos {r['n_oos_med']} | máx mk {r['max_mk']:.0f} ({r['pass90']}/{r['n_top']}, p={r['binom_p']}) | "
          f"SR0 {r['sr0']} máxSR {r['max_sr']} | DSR best {r['best_dsr']} ({r['dsr_sig']} sig) | %PA {r['pct_pa']:.0f}", flush=True)

T = pd.DataFrame(rows); pd.concat(tables).to_csv('experimentos/pa_winners.csv', index=False)
T.to_csv('experimentos/pa_b5.csv', index=False)
print("\n=== TABLA PRICE ACTION ===")
print(T[['sym', 'tf', 'best_fit', 'n_unique', 'n_oos_med', 'max_mk', 'pass90', 'binom_p', 'sr0', 'max_sr', 'best_dsr', 'dsr_sig']].to_string(index=False))
nsig = int((T['dsr_sig'] > 0).sum())
print(f"\n=== VEREDICTO ===  combos con DSR>=0.95: {nsig}/{len(T)}")
if nsig == 0:
    print("  -> price action TAMPOCO supera el DSR: el edge no está en el OHLC (ni osciladores ni geometría)")
    print("  -> siguiente vía: features exógenas (macro del oro) / cartera de débiles / destilar Vault")
else:
    print("  -> ¡price action SÍ supera el DSR en algún combo! verificar robustez antes de coronar")
print("CSV: experimentos/pa_b5.csv", flush=True)
