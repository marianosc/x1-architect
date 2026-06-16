# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 108.0 - FITNESS DEL MINERO (B1)
# FILE: modules/fitness_v108.py
# ROL: Fitness por candidato para el minero evolutivo v108. Mide CUÁNTO le
#      gana al azar en el OOS-interno de Z1, robusto, simple y NEUTRAL a la
#      beta de régimen. Z2 (2022-26) NO se toca: es el holdout final (B4).
#
# DISEÑO (spec NOTEBOOK 2026-06-15, aprobado por Mariano):
#   1. CPCV-purgado sobre Z1: K=6 bloques contiguos. Cada bloque es un
#      test-fold OOS-interno. Purging: se descartan las entradas a <= N velas
#      del borde derecho del bloque (su Ret_N se devengaría fuera del fold) +
#      embargo. El monkey necesita una secuencia CONTIGUA, así que el fold es
#      un bloque contiguo (combinatorio de tamaño 1; extensible a k_test>1).
#   2. Cascada por candidato:
#      a. pre-filtro barato (sin monkey): min_t por fold; y PF del candidato
#         en el fold <= 1.0 => fold = 0 (basura obvia, no gasta monkey).
#      b. supervivientes -> monkey REAL reducido (n=300-500) vía monkey_batch
#         (B0, paralelo nogil) en cada fold -> un mk_oos por fold.
#   3. fitness_core = MEDIANA de los mk_oos sobre folds válidos.
#   4. fitness = fitness_core - lambda * complejidad (nodos de la regla).
#   5. n escala: 300-500 en evolución; 5.000 en finalistas (B4).
#   6. Determinismo: semilla de monos derivada de la REGLA (crc32) -> el mismo
#      candidato da el mismo fitness sea cual sea su posición (el GA no
#      persigue ruido). Apoyado en el RNG thread-local de B0.
# ##########################################################################
import zlib

import numpy as np

from modules.x1_engine import simulate
from modules.x1_validators import monkey_batch


def cpcv_blocks(start, end, K=6):
    """K bloques contiguos [bs, be) que parten [start, end)."""
    edges = np.linspace(int(start), int(end), int(K) + 1).astype(np.int64)
    return [(int(edges[i]), int(edges[i + 1])) for i in range(int(K))]


def rule_complexity(rule):
    """Nodos de la regla = nº de condiciones (proxy de complejidad para la
    parsimonia). Con la gramática formulaica (B2) se contarán operadores."""
    return max(1, len([c for c in str(rule).split('|') if c.strip()]))


def _exit_purge_bars(exit_label, durations):
    """Velas a purgar del borde derecho: N para Ret_N; duración media (techo)
    para la sintética (su tenencia real)."""
    s = str(exit_label)
    if s != 'SINTETICA_REVERSE' and '_' in s:
        return int(s.split('_')[1])
    return int(max(1, np.ceil(float(np.mean(durations))))) if len(durations) else 1


def _rule_seed(base, rule, side, exit_label):
    """Semilla estable por candidato: misma regla -> mismos monos siempre."""
    key = f"{rule}|{side}|{exit_label}".encode("utf-8")
    return (int(base) + zlib.crc32(key)) & 0x7FFFFFFF


def fitness_population(cands, data, col_map, ret_indices, z1_start, z1_end, cfg,
                      K=6, n_monkeys=400, lam=0.0, seed=12345, embargo_frac=0.1,
                      min_t_fold=None, n_threads=None, agg='q25'):
    # agg DEFAULT='q25' (B1 tuning cerrado 2026-06-16): el barrido validó Q25
    # contra EURGBP (juez sin tendencia): de-sesga la beta en el top (14% largo
    # vs 54-64% de la mediana) y mejora la coherencia (Spearman +0.09 vs +0.04).
    # La mediana favorecía el horizonte largo en mercados laterales. Ver
    # tools/barrido_b1.py y experimentos/barrido_b1.csv.
    """Fitness v108 para una POBLACIÓN de candidatos (batched, B0-paralelo).

    cands: iterable de (rule, side, exit_label).
    cfg  : dict con 'cooldown', 'f_points' (como L3.G_CFG).
    Devuelve lista de dicts (mismo orden) con: rule/side/exit, complexity,
    fold_mk (lista K, NaN si fold inválido), n_valid, fitness_core, fitness.
    """
    blocks = cpcv_blocks(z1_start, z1_end, K)
    close = data[:, col_map['Close']].astype(np.float64)
    ret_1 = np.zeros(len(close))
    ret_1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
    f_points = float(cfg['f_points'])
    cooldown = int(cfg['cooldown'])
    velas_block = (int(z1_end) - int(z1_start)) / float(K)
    if min_t_fold is None:
        # piso laxo: el pre-filtro fuerte (min_t global) es del GA; acá solo
        # exigimos lo mínimo para que el monkey de un fold sea significativo.
        min_t_fold = max(5, int(0.10 * velas_block / max(cooldown, 1)))

    per = [{'rule': r, 'side': s, 'exit': e, 'complexity': rule_complexity(r),
            'fold_mk': [np.nan] * K, 'n_valid': 0, 'reason': ''} for r, s, e in cands]
    jobs, tags = [], []
    for ci, (rule, side, exit_l) in enumerate(cands):
        try:
            sim = simulate(data, col_map, ret_indices, rule, exit_l, side,
                           cooldown=cooldown, friction_points=f_points)
        except ValueError:
            per[ci]['reason'] = 'ERR_EXIT'
            continue
        idx_e = np.where(sim['mask'])[0]
        r_all = sim['vector']
        durs = sim['durations']
        if len(idx_e) == 0:
            per[ci]['reason'] = 'SIN_TRADES'
            continue
        N = _exit_purge_bars(exit_l, durs)
        emb = max(1, int(embargo_frac * N))
        cseed = _rule_seed(seed, rule, side, exit_l)
        for fi, (bs, be) in enumerate(blocks):
            hi = be - N - emb  # purga del borde derecho (Ret_N + embargo)
            sel = (idx_e >= bs) & (idx_e < hi)
            ent = idx_e[sel]
            if len(ent) < min_t_fold:
                continue  # fold inválido -> NaN
            rv = r_all[ent]
            pf = rv[rv > 0].sum() / (abs(rv[rv < 0].sum()) + 1e-9)
            if pf <= 1.0:
                per[ci]['fold_mk'][fi] = 0.0  # cheap reject: ni gasta monkey
                continue
            pos = np.searchsorted(idx_e, ent)
            expo = int(max(1, round(float(np.mean(durs[pos])))))
            jobs.append(dict(ret_1=ret_1[bs:be], n_trades=int(len(ent)), exposure=expo,
                             strat_total=float(rv.sum()), side=side, n_monkeys=int(n_monkeys),
                             seed=cseed + fi, friction_per_trade=f_points / float(np.mean(close[bs:be]))))
            tags.append((ci, fi))

    results = monkey_batch(jobs, n_threads=n_threads) if jobs else []
    for (ci, fi), res in zip(tags, results):
        per[ci]['fold_mk'][fi] = res['pvalue'] * 100.0

    for rec in per:
        mk = np.array([m for m in rec['fold_mk'] if not np.isnan(m)])
        rec['n_valid'] = int(len(mk))
        # Exige operar consistentemente en Z1: con < K/2 folds válidos, fitness 0.
        if len(mk) < (K // 2):
            core = 0.0
        elif agg == 'q25':           # más exigencia de consistencia (peor cuartil)
            core = float(np.percentile(mk, 25))
        else:                        # 'median' (default)
            core = float(np.median(mk))
        rec['fitness_core'] = core
        rec['fitness'] = core - float(lam) * rec['complexity']
    return per


def fitness_v108(rule, side, exit_label, data, col_map, ret_indices,
                 z1_start, z1_end, cfg, **kw):
    """Atajo para UN candidato (tests/inspección). Ver fitness_population."""
    return fitness_population([(rule, side, exit_label)], data, col_map, ret_indices,
                              z1_start, z1_end, cfg, **kw)[0]
