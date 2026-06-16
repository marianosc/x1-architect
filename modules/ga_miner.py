# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 108.0 - MINERO EVOLUTIVO (B3)
# FILE: modules/ga_miner.py
# ROL: GA dirigido con WARM-START de hipótesis económicas. Reemplaza la tirada
#      uniforme de L2 (random = anti-edge probado). Fitness = fitness_population
#      (B1, CPCV K=6 sobre Z1, monkey-OOS Q25 beta-neutral). Z2 INTOCABLE
#      (holdout final, una sola medición fuera del GA).
#
# GENOTIPO: {conds:[(lhs,op,rhs),..1-3], side, exit}. lhs = token viejo o
#   formulaico (B2a); exit EVOLUCIONA. Islas TREND/MOM/VOL/CYCLE con migración.
#   Mutación incluye "promover un indicador a su versión formulaica" → los
#   operadores de B2a entran DIRIGIDOS por el GA, no a ciegas.
# ##########################################################################
import re
import time

import numpy as np

from modules.fitness_v108 import fitness_population
from modules.formulaic import (BASES, expand_formulaic, formulaic_vocabulary,
                               is_formulaic, parse_token)

EXITS = ['Ret_12', 'Ret_24', 'Ret_48', 'Ret_72', 'Ret_96', 'SINTETICA_REVERSE']
OPS = ['>=', '<=']
FAMILIES = {
    'TREND': ('ema', 'adx', 'slope', 'aroon', 'linreg', 'efficiency', 'macdh', 'trix', 'plus_di', 'minus_di'),
    'MOM':   ('rsi', 'cmo', 'roc', 'mfi', 'mom', 'force'),
    'VOL':   ('bbw', 'natr', 'std', 'vol_z'),
    'CYCLE': ('stoch', 'willr', 'cci'),
}
# Periodos formulaicos curados para mutación/promoción (tractable)
FORM_PERIODS = (8, 13, 21, 55)


# ----------------------------- GENOTIPO -----------------------------
def geno_key(g):
    conds = sorted(f"{l}{o}{r}" for l, o, r in g['conds'])
    return f"{'|'.join(conds)}@{g['side']}@{g['exit']}"


def geno_to_cand(g):
    rule = '|'.join(f"{l} {o} {r}" for l, o, r in g['conds'])
    return (rule, g['side'], g['exit'])


def _snap_period(fam, period, periods_avail):
    """Periodo disponible más cercano (la spec usa 14; la ADN tiene 13, etc.)."""
    cand = [p for (f, p) in periods_avail if f == fam]
    if not cand:
        return None
    return min(cand, key=lambda p: abs(p - period))


# ----------------------------- VOCABULARIO -----------------------------
class Vocab:
    def __init__(self, col_map, z1_slice, data):
        self.cm = col_map
        # columnas base disponibles por familia-keyword
        self.old = [c for c in col_map if c.endswith('_sft')
                    and c not in ('Close_sft', 'hour_sft', 'dow_sft')]
        self.ctx = [c for c in col_map if c == 'Close_sft' or c.startswith('ema')]
        # periodos disponibles por familia base formulaica
        self.periods = []
        for c in self.old:
            stem = c[:-4]
            m = re.match(r'^([a-z_]+?)_(\d+)$', stem)
            if m and m.group(1) in BASES:
                self.periods.append((m.group(1), int(m.group(2))))
        if 'close_sft' in (c.lower() for c in col_map):
            self.periods.append(('close', 0))
        # LHS por isla
        self.island_lhs = {}
        for isl, kws in FAMILIES.items():
            self.island_lhs[isl] = [c for c in self.old if any(k in c for k in kws)]
        # cuantiles Z1 por columna (para umbrales) — se rellena on-demand
        self._q = {}
        self._z1 = z1_slice
        self._data = data

    def closest_col(self, fam, period):
        """Columna `{fam}_{p}_sft` con el periodo más cercano disponible (la
        spec usa periodos que la ADN puede no tener: 14→13, etc.). None si no hay."""
        cand = []
        for c in self.cm:
            m = re.match(rf'^{fam}_(\d+)_sft$', c)
            if m:
                cand.append((abs(int(m.group(1)) - period), c))
        return min(cand)[1] if cand else None

    def quant(self, token):
        if token not in self._q:
            if token in self.cm:
                col = self._data[self._z1, self.cm[token]]
                self._q[token] = np.quantile(col, [0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95])
            else:
                self._q[token] = np.array([0.0])
        return self._q[token]

    def rand_lhs(self, isl, rng):
        return str(rng.choice(self.island_lhs[isl])) if self.island_lhs[isl] else str(rng.choice(self.old))

    def rand_rhs(self, lhs, rng):
        # 65% umbral numérico (cuantil del lhs), 35% token de contexto (relacional)
        if rng.random() < 0.35 and self.ctx:
            return str(rng.choice(self.ctx))
        return str(round(float(rng.choice(self.quant(lhs))), 4))

    def to_formulaic(self, lhs, rng):
        """Promueve un token base a su versión formulaica (si su familia ∈ BASES)."""
        tok = lhs[:-4] if lhs.endswith('_sft') else lhs
        m = re.match(r'^([a-z_]+?)_(\d+)$', tok)
        base = None
        if m and m.group(1) in BASES:
            base = tok
        elif tok == 'close':
            base = 'close'
        if base is None:
            return None
        op = rng.choice(['delta', 'slope', 'tsrank', 'distmax', 'distmin'])
        param = int(rng.choice([3, 5, 10])) if op in ('delta', 'slope') else int(rng.choice([20, 50, 100]))
        return f"{op}{param}_{base}_sft"


# ----------------------------- WARM-START -----------------------------
def warm_seeds(vocab):
    """Las 3 hipótesis económicas (vieja + formulaica), LONG + espejo SHORT,
    con periodos snapeados a la ADN disponible (14→13, etc.)."""
    col = vocab.closest_col  # columna {fam}_{p}_sft más cercana disponible
    q90 = lambda tok: round(float(vocab.quant(tok)[-2]), 4) if tok and tok in vocab.cm else 0.9

    seeds = {}  # isla -> lista de genotipos LONG
    rsi40 = col('rsi', 14); rsi8 = col('rsi', 8); natr = col('natr', 14)
    ema200 = col('ema', 200); ema55 = col('ema', 55); ema21 = col('ema', 21); adx = col('adx', 14)
    H = {
        'TREND': [
            [(ema200, '<=', 'Close_sft'), (rsi40, '<=', '40')],                     # H1 pullback viejo
            [(f'slope10_{ema55[:-4]}_sft', '>=', '0'), (f'tsrank50_{rsi40[:-4]}_sft', '<=', '0.3')],  # H1 form
            [(adx, '>=', '25'), ('Close_sft', '>=', ema21)],                        # H3 breakout viejo
            [(f'distmax20_close_sft', '>=', '-2.0'), (f'delta5_{adx[:-4]}_sft', '>=', '0')],  # H3 form
        ],
        'VOL': [
            [(rsi8, '<=', '20'), (natr, '>=', q90(natr))],                          # H2 reversión vol viejo
            [(f'tsrank100_{natr[:-4]}_sft', '>=', '0.9'), (rsi8, '<=', '20')],      # H2 form
        ],
        'MOM': [
            [(adx, '>=', '25'), ('Close_sft', '>=', ema21)],                        # H3 (también MOM)
            [(f'delta5_{adx[:-4]}_sft', '>=', '0'), (rsi40, '<=', '50')],
        ],
        'CYCLE': [
            [(rsi8, '<=', '20')], [(rsi40, '<=', '40')],                            # cycle: arranca de RSI extremos
        ],
    }
    for isl, lst in H.items():
        gl = []
        for conds in lst:
            conds = [c for c in conds if c[0] is not None]
            if not conds:
                continue
            for side in ('LONG', 'SHORT'):
                for ex in ('Ret_24', 'SINTETICA_REVERSE'):
                    gl.append({'conds': [tuple(c) for c in conds], 'side': side, 'exit': ex})
        seeds[isl] = gl
    return seeds


# ----------------------------- OPERADORES GA -----------------------------
def rand_geno(isl, vocab, rng):
    nc = int(rng.choice([1, 2, 2, 3]))
    conds = []
    for _ in range(nc):
        lhs = vocab.rand_lhs(isl, rng)
        if rng.random() < 0.25:  # exploración formulaica
            f = vocab.to_formulaic(lhs, rng)
            if f:
                lhs = f
        conds.append((lhs, str(rng.choice(OPS)), vocab.rand_rhs(lhs, rng)))
    return {'conds': conds, 'side': str(rng.choice(['LONG', 'SHORT'])), 'exit': str(rng.choice(EXITS))}


def mutate(g, isl, vocab, rng):
    g = {'conds': [tuple(c) for c in g['conds']], 'side': g['side'], 'exit': g['exit']}
    r = rng.random()
    if r < 0.15 and len(g['conds']) < 3:                       # add cond
        lhs = vocab.rand_lhs(isl, rng)
        g['conds'].append((lhs, str(rng.choice(OPS)), vocab.rand_rhs(lhs, rng)))
    elif r < 0.27 and len(g['conds']) > 1:                     # del cond
        g['conds'].pop(int(rng.integers(len(g['conds']))))
    elif r < 0.42:                                             # cambiar exit
        g['exit'] = str(rng.choice(EXITS))
    elif r < 0.52:                                             # flip side
        g['side'] = 'SHORT' if g['side'] == 'LONG' else 'LONG'
    elif r < 0.72:                                             # mutar umbral/op de una cond
        i = int(rng.integers(len(g['conds']))); l, o, _ = g['conds'][i]
        g['conds'][i] = (l, str(rng.choice(OPS)), vocab.rand_rhs(l, rng))
    elif r < 0.86:                                             # cambiar indicador
        i = int(rng.integers(len(g['conds']))); lhs = vocab.rand_lhs(isl, rng)
        g['conds'][i] = (lhs, str(rng.choice(OPS)), vocab.rand_rhs(lhs, rng))
    else:                                                      # PROMOVER a formulaico
        i = int(rng.integers(len(g['conds']))); l, o, rr = g['conds'][i]
        f = vocab.to_formulaic(l, rng)
        if f:
            g['conds'][i] = (f, o, vocab.rand_rhs(f, rng))
    return g


def crossover(a, b, rng):
    pool = list(a['conds']) + list(b['conds'])
    k = int(rng.choice([1, 2, 2, 3]))
    k = min(k, len(pool))
    idx = rng.choice(len(pool), size=k, replace=False)
    conds = [tuple(pool[i]) for i in idx]
    return {'conds': conds, 'side': a['side'] if rng.random() < 0.5 else b['side'],
            'exit': a['exit'] if rng.random() < 0.5 else b['exit']}


# ----------------------------- MOTOR GA -----------------------------
def run_ga(data, col_map, ret_indices, z1_start, z1_end, cfg, *,
           pop=1000, islands=('TREND', 'MOM', 'VOL', 'CYCLE'), generations=40,
           n_monkeys=1000, elite_frac=0.10, mut_rate=0.25, tourn_k=3,
           migrate_every=10, random_frac=0.15, seed=2026, log=print):
    rng = np.random.default_rng(seed)
    vocab = Vocab(col_map, slice(z1_start, z1_end), data)
    seeds = warm_seeds(vocab)
    cache = {}              # geno_key -> fitness_core
    n_unique = [0]

    def evaluate(genos):
        """Evalúa (cacheado) una lista de genotipos. Batch de fitness_population."""
        todo, keys = [], []
        for g in genos:
            k = geno_key(g)
            if k not in cache:
                cache[k] = None
                todo.append(g); keys.append(k)
        if todo:
            cands = [geno_to_cand(g) for g in todo]
            res = fitness_population(cands, data, col_map, ret_indices, z1_start, z1_end,
                                     cfg, n_monkeys=n_monkeys)
            for k, r in zip(keys, res):
                cache[k] = r['fitness']
            n_unique[0] += len(todo)
        return [cache[geno_key(g)] for g in genos]

    # init poblaciones por isla: semillas + variantes + random
    P = {}
    for isl in islands:
        base = list(seeds.get(isl, []))
        pobl = list(base)
        while len(pobl) < pop * (1 - random_frac):
            pobl.append(mutate(rng.choice(base) if base else rand_geno(isl, vocab, rng), isl, vocab, rng))
        while len(pobl) < pop:
            pobl.append(rand_geno(isl, vocab, rng))
        P[isl] = pobl[:pop]

    best_hist = []
    n_elite = max(1, int(pop * elite_frac))
    for gen in range(generations):
        gen_best = {}
        for isl in islands:
            fits = evaluate(P[isl])
            order = np.argsort(fits)[::-1]
            P[isl] = [P[isl][i] for i in order]; fits = [fits[i] for i in order]
            gen_best[isl] = fits[0]
            # nueva generación: elitismo + torneo/crossover/mutación
            nxt = P[isl][:n_elite]
            while len(nxt) < pop:
                a = P[isl][min(rng.integers(0, len(P[isl]), tourn_k))]
                b = P[isl][min(rng.integers(0, len(P[isl]), tourn_k))]
                child = crossover(a, b, rng)
                if rng.random() < mut_rate:
                    child = mutate(child, isl, vocab, rng)
                nxt.append(child)
            P[isl] = nxt
        best_hist.append(max(gen_best.values()))
        log(f"  gen {gen:02d} | best {max(gen_best.values()):.1f} "
            f"({', '.join(f'{k}:{v:.0f}' for k,v in gen_best.items())}) | únicos {n_unique[0]}")
        # migración
        if migrate_every and (gen + 1) % migrate_every == 0 and len(islands) > 1:
            tops = {isl: P[isl][0] for isl in islands}
            il = list(islands)
            for i, isl in enumerate(il):
                P[isl][-1] = tops[il[(i + 1) % len(il)]]

    # evaluar las poblaciones finales (la última gen creó hijos sin evaluar)
    for isl in islands:
        evaluate(P[isl])
    # cosecha: top diversos por fitness sobre toda la población final
    allg = [(geno_key(g), g) for isl in islands for g in P[isl]]
    seen, uniq = set(), []
    for k, g in allg:
        if k not in seen:
            seen.add(k); uniq.append(g)
    uniq.sort(key=lambda g: cache[geno_key(g)], reverse=True)
    return dict(winners=uniq, cache=cache, n_unique=n_unique[0], best_hist=best_hist, vocab=vocab)
