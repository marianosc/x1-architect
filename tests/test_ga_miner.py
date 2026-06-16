# ##########################################################################
# SYSTEM: X1-ARCHITECT | TEST v108-B3
# FILE: tests/test_ga_miner.py
# ROL: El GA produce genotipos válidos, es determinista, y MEJORA el fitness
#      (elitismo ⇒ mejor no-decreciente; encuentra una regla con edge plantado).
#      Z2 nunca entra al fitness (fitness_population usa solo z1_start..z1_end).
# USO: python tests/test_ga_miner.py
# ##########################################################################
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.ga_miner import (Vocab, crossover, geno_key, geno_to_cand, mutate,
                              rand_geno, run_ga, warm_seeds)

RNG = np.random.default_rng(3)


def _market():
    """Mercado sintético con columnas base y un EDGE plantado en rsi_13<=30."""
    N, Z1S, Z1E, Z2E = 40000, 8000, 32000, 40000
    zone = np.zeros(N, dtype=np.int64); zone[Z1S:Z1E] = 1; zone[Z1E:Z2E] = 2
    rsi13 = RNG.uniform(0, 100, N).astype(np.float32)
    ret1 = RNG.normal(0, 0.001, N)
    sig = np.where(rsi13 <= 30)[0]
    ret1[np.clip(sig + 1, 0, N - 1)] += 0.01            # edge: sube tras rsi<=30
    close = (100.0 * np.cumprod(1 + ret1)).astype(np.float64)
    cols = {'Close': close, 'Close_sft': np.roll(close, 1),
            'rsi_13_sft': rsi13, 'ema_55_sft': close * RNG.uniform(0.98, 1.02, N),
            'adx_13_sft': RNG.uniform(0, 50, N), 'natr_13_sft': RNG.uniform(0, 3, N),
            'cci_13_sft': RNG.uniform(-200, 200, N), 'mom_13_sft': RNG.normal(0, 1, N),
            'stoch_13_sft': RNG.uniform(0, 100, N), 'willr_13_sft': RNG.uniform(-100, 0, N),
            'bbw_13_sft': RNG.uniform(0, 0.1, N)}
    for h in (12, 24, 48, 72, 96):
        r = np.zeros(N); r[:-h] = (close[h:] - close[:-h]) / close[:-h]; cols[f'Ret_{h}'] = r
    names = list(cols)
    data = np.column_stack([cols[k] for k in names]).astype(np.float32)
    cm = {k: i for i, k in enumerate(names)}
    ri = {k: i for i, k in enumerate(names) if k.startswith('Ret_')}
    return data, cm, ri, Z1S, Z1E


DATA, CM, RI, Z1S, Z1E = _market()
VOC = Vocab(CM, slice(Z1S, Z1E), DATA)
CFG = {'cooldown': 25, 'f_points': 0.0}


def test_geno_roundtrip_y_operadores():
    g = rand_geno('MOM', VOC, RNG)
    assert 1 <= len(g['conds']) <= 3 and g['side'] in ('LONG', 'SHORT') and g['exit']
    rule, side, ex = geno_to_cand(g)
    assert '|'.join(f"{l} {o} {r}" for l, o, r in g['conds']) == rule
    for _ in range(50):
        m = mutate(g, 'MOM', VOC, RNG)
        assert 1 <= len(m['conds']) <= 3, "mutación rompió el nº de condiciones"
        c = crossover(g, m, RNG)
        assert 1 <= len(c['conds']) <= 3
    print("OK  genotipo válido: rand/mutate/crossover mantienen 1-3 condiciones")


def test_warm_seeds_resuelven():
    seeds = warm_seeds(VOC)
    assert set(seeds) >= {'TREND', 'MOM', 'VOL', 'CYCLE'}
    n = sum(len(v) for v in seeds.values())
    assert n >= 12, f"pocas semillas: {n}"
    # cada semilla LONG tiene su espejo SHORT
    for isl, gl in seeds.items():
        sides = {g['side'] for g in gl}
        assert sides == {'LONG', 'SHORT'} or not gl
    print(f"OK  warm-start: {n} semillas (LONG+SHORT) en 4 islas, periodos snapeados")


def test_determinismo():
    r1 = run_ga(DATA, CM, RI, Z1S, Z1E, CFG, pop=40, islands=('MOM',), generations=3,
                n_monkeys=100, seed=7, log=lambda *_: None)
    r2 = run_ga(DATA, CM, RI, Z1S, Z1E, CFG, pop=40, islands=('MOM',), generations=3,
                n_monkeys=100, seed=7, log=lambda *_: None)
    assert r1['best_hist'] == r2['best_hist'], "GA no determinista con misma semilla"
    assert r1['n_unique'] == r2['n_unique']
    print(f"OK  determinismo: misma semilla ⇒ mismo best_hist y nº únicos ({r1['n_unique']})")


def test_ga_mejora_con_edge():
    r = run_ga(DATA, CM, RI, Z1S, Z1E, CFG, pop=60, islands=('MOM', 'CYCLE'), generations=6,
               n_monkeys=200, seed=11, log=lambda *_: None)
    bh = r['best_hist']
    assert all(bh[i + 1] >= bh[i] - 1e-9 for i in range(len(bh) - 1)), f"elitismo roto: {bh}"
    assert bh[-1] > 0, f"el GA no encontró ningún candidato con fitness>0: {bh[-1]}"
    assert r['n_unique'] > 0 and len(r['winners']) > 0
    print(f"OK  el GA mejora con edge plantado: best {bh[0]:.0f}→{bh[-1]:.0f}, "
          f"{r['n_unique']} únicos evaluados")


if __name__ == '__main__':
    tests = [test_geno_roundtrip_y_operadores, test_warm_seeds_resuelven,
             test_determinismo, test_ga_mejora_con_edge]
    print(f"=== MINERO EVOLUTIVO v108-B3 - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
