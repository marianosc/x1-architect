# ##########################################################################
# SYSTEM: X1-ARCHITECT | CONTROL B2a (¿aporta la gramática formulaica?)
# FILE: tools/control_b2a.py
# ROL: Comparar fitness B1 (n=1000, Q25) de un pool con VOCABULARIO AMPLIADO
#      (reglas con ≥1 operador formulaico) vs un pool de GRAMÁTICA VIEJA (solo
#      indicadores crudos), en XAUUSD (bull) y EURGBP (juez beta-neutral).
#      ¿Aparecen candidatos con mejor fitness/transferencia? ¿Los ganadores
#      USAN los operadores nuevos?
# USO: python tools/control_b2a.py [M_pool]
# ##########################################################################
import os, sys, time
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch
from modules.fitness_v108 import fitness_population
from modules.formulaic import expand_formulaic, is_formulaic, formulaic_vocabulary

M = int(sys.argv[1]) if len(sys.argv) > 1 else 1200
N_FIT, N_TRUTH = 1000, 1000
EXITS = ['Ret_24', 'Ret_48', 'Ret_96', 'SINTETICA_REVERSE']
PERIODS = [13, 21, 55]            # subconjunto representativo (tractable)
SYMS = {'XAUUSD': (r'C:\temp\X1_FULL_XAUUSD_H1.parquet', 1.0),
        'EURGBP': (r'C:\temp\X1_FULL_EURGBP_H1.parquet', 0.0002)}
RNG = np.random.default_rng(2026)


def gen_rule(pool, quant):
    """Genera una regla muestreando tokens UNIFORME del pool dado (sin forzar):
    así los operadores formulaicos COMPITEN de igual a igual con los viejos."""
    nconds = int(RNG.choice([1, 2, 2, 3]))
    conds = []
    for _ in range(nconds):
        tok = str(RNG.choice(pool))
        op = '>=' if RNG.random() < 0.5 else '<='
        thr = round(float(RNG.choice(quant[tok])), 4)
        conds.append(f"{tok} {op} {thr}")
    return "|".join(conds)


def best_exit(data, cm, ri, rule, fp, z_is):
    best, bex = -1e9, EXITS[0]
    for ex in EXITS:
        try:
            sim = simulate(data, cm, ri, rule, ex, 'LONG', cooldown=25, friction_points=fp)
        except ValueError:
            continue
        r = sim['vector'][z_is]; r = r[r != 0]
        if len(r) < 20:
            continue
        pf = r[r > 0].sum() / (abs(r[r < 0].sum()) + 1e-9)
        if pf > best:
            best, bex = pf, ex
    return bex


def run_symbol(sym):
    parquet, fp = SYMS[sym]
    df = pd.read_parquet(parquet); zone = df['Zone'].values
    z_is, z_oos = zone == 1, zone == 2
    z1s, z1e = int(np.argmax(z_is)), int(np.where(z_is)[0][-1] + 1)
    base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
    data = base.values.astype(np.float32)
    cm = {n: i for i, n in enumerate(base.columns)}
    ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}

    # vocabularios
    vocab_old = [c for c in base.columns if c.endswith('_sft')
                 and c not in ('Close_sft', 'hour_sft', 'dow_sft')]
    form_all = formulaic_vocabulary(cm)
    vocab_form = [t for t in form_all if any(f"_{p}_sft" in t for p in PERIODS) or 'close_sft' in t]
    data, cm = expand_formulaic(data, cm, vocab_form)   # materializa las formulaicas

    # cuantiles Z1 por columna usada en reglas
    allcols = vocab_old + vocab_form
    q = {}
    for c in allcols:
        col = data[z1s:z1e, cm[c]]
        q[c] = np.quantile(col, [0.1, 0.25, 0.5, 0.75, 0.9])

    close = data[:, cm['Close']].astype(np.float64)
    ret1 = np.zeros(len(close)); ret1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
    fp_oos = fp / float(np.mean(close[z_oos]))
    vocab_all = vocab_old + vocab_form
    out = {}
    for tag, pool in (('VIEJA', vocab_old), ('MIXTA', vocab_all)):
        rules = [gen_rule(pool, q) for _ in range(M)]
        cands = [(r, 'LONG', best_exit(data, cm, ri, r, fp, z_is)) for r in rules]
        fit = fitness_population(cands, data, cm, ri, z1s, z1e,
                                 {'cooldown': 25, 'f_points': fp}, n_monkeys=N_FIT)
        # verdad Z2 (monkey honesto por candidato)
        jobs, tags = [], []
        for ci, (rule, side, ex) in enumerate(cands):
            try:
                sim = simulate(data, cm, ri, rule, ex, side, cooldown=25, friction_points=fp)
            except ValueError:
                continue
            idx = np.where(sim['mask'])[0]; ent = idx[z_oos[idx]]
            if len(ent) >= 5:
                pos = np.searchsorted(idx, ent); expo = int(max(1, round(float(np.mean(sim['durations'][pos])))))
                jobs.append(dict(ret_1=ret1[z_oos], n_trades=len(ent), exposure=expo,
                                 strat_total=float(sim['vector'][z_oos].sum()), side=side,
                                 n_monkeys=N_TRUTH, seed=777 + ci, friction_per_trade=fp_oos))
                tags.append(ci)
        mk = np.full(len(cands), np.nan)
        for ci, r in zip(tags, monkey_batch(jobs)):
            mk[ci] = r['pvalue'] * 100.0
        R = pd.DataFrame({'rule': [c[0] for c in cands], 'exit': [c[2] for c in cands],
                          'fit': [f['fitness_core'] for f in fit], 'mk': mk})
        R = R[R['mk'].notna()].reset_index(drop=True)
        R['form'] = R['rule'].apply(lambda s: any(is_formulaic(t.strip())
                                                   for c in s.split('|') for t in
                                                   __import__('re').split(r'>=|<=|>|<', c)))
        top = R.nlargest(50, 'fit')
        act = R[R['fit'] > 0]
        af, ao = act[act['form']], act[~act['form']]
        out[tag] = dict(n=len(R), activos=int(len(act)),
                        fit_p90=float(R['fit'].quantile(0.90)), fit_max=float(R['fit'].max()),
                        top_mk=float(top['mk'].mean()),
                        rho=float(stats.spearmanr(R['fit'], R['mk'])[0]),
                        pct_form_act=float(100 * act['form'].mean()),
                        top_form=float(100 * top['form'].mean()),
                        # PRUEBA ORGÁNICA: ¿los candidatos CON formulaico rinden mejor?
                        form_fit=float(af['fit'].mean()) if len(af) else float('nan'),
                        old_fit=float(ao['fit'].mean()) if len(ao) else float('nan'),
                        form_mk=float(af['mk'].mean()) if len(af) else float('nan'),
                        old_mk=float(ao['mk'].mean()) if len(ao) else float('nan'))
        o = out[tag]
        print(f"  [{sym}/{tag}] activos {o['activos']} | fit p90 {o['fit_p90']:.0f} max {o['fit_max']:.0f} "
              f"| top50 mk_z2 {o['top_mk']:.1f} | rho {o['rho']:+.3f} | "
              f"top50 %form {o['top_form']:.0f}% (pool act {o['pct_form_act']:.0f}%)", flush=True)
        if tag == 'MIXTA':
            print(f"     ORGÁNICO (activos): fitness CON-form {o['form_fit']:.1f} vs SOLO-viejo {o['old_fit']:.1f} "
                  f"| mk_z2 CON-form {o['form_mk']:.1f} vs SOLO-viejo {o['old_mk']:.1f}", flush=True)
    return out


rows = []
for sym in SYMS:
    t = time.time(); print(f"== {sym} ==", flush=True)
    o = run_symbol(sym)
    for tag in ('VIEJA', 'MIXTA'):
        rows.append(dict(sym=sym, vocab=tag, **o[tag]))
    print(f"  ({time.time()-t:.0f}s)", flush=True)

T = pd.DataFrame(rows)
T.to_csv("experimentos/control_b2a.csv", index=False)
print("\n=== CONTROL B2a (¿aporta el vocabulario ampliado?) ===")
print(T.to_string(index=False))
print("\nLectura: AMPLIADA aporta si tiene MÁS fit>=90 / mejor top_mk / mejor rho, "
      "y si top50 %formulaico es ALTO (los ganadores usan los operadores nuevos).")
print("CSV: experimentos/control_b2a.csv")
