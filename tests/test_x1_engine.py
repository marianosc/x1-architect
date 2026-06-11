# ##########################################################################
# SYSTEM: X1-ARCHITECT | FASE 1 SANEAMIENTO
# FILE: tests/test_x1_engine.py
# ROL: Pruebas de equivalencia del Motor Único contra las 5 implementaciones
#      históricas, y demostración numérica de las divergencias que motivaron
#      la consolidación (bug sintética L3, cooldown desigual).
# USO: python tests/test_x1_engine.py   (no requiere pytest ni numba)
# ##########################################################################
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.x1_engine import (
    SYNTHETIC_EXIT, apply_cooldown, max_drawdown_pct, parse_rule,
    profit_factor, signal_mask, simulate, synthetic_exit,
)
from modules.backtest_engine import apply_time_filter, fast_signal_generator

RNG = np.random.default_rng(42)


# -----------------------------------------------------------------------------
# DATASET SINTETICO (mismas convenciones que el Parquet de L1)
# -----------------------------------------------------------------------------
def build_market(n=3000):
    close = 2000.0 * np.cumprod(1.0 + RNG.normal(0, 0.002, n))
    cols = {
        'Close': close,
        'Ret_12': np.zeros(n),
        'Ret_24': np.zeros(n),
        'rsi_14_sft': RNG.uniform(0, 100, n),
        'ema_55_sft': close * RNG.uniform(0.98, 1.02, n),
        'Close_sft': np.roll(close, 1),
    }
    for h in (12, 24):
        ret = np.zeros(n)
        ret[:-h] = (close[h:] - close[:-h]) / close[:-h]
        cols[f'Ret_{h}'] = ret
    names = list(cols.keys())
    data = np.column_stack([cols[k] for k in names]).astype(np.float32)
    col_map = {k: i for i, k in enumerate(names)}
    ret_indices = {k: i for i, k in enumerate(names) if k.startswith('Ret_')}
    return data, col_map, ret_indices


# -----------------------------------------------------------------------------
# REFERENCIAS HISTORICAS (copiadas literalmente de L2 y L3 para comparar)
# -----------------------------------------------------------------------------
def l2_synthetic_reference(data, entries, rule_str, col_map, ret_1, side_mult):
    """Bucle sintético del minero (L2.engine, líneas 84-96). LA SEMANTICA BUENA."""
    l_info = []
    for sub in rule_str.split('|'):
        p = sub.split()
        c1 = col_map[p[0]]
        c2 = col_map[p[2]] if p[2] in col_map else -1
        val = 0.0 if c2 != -1 else np.float32(p[2])
        op = 0 if p[1] == '>=' else 1
        l_info.append((c1, c2, op, val))

    profits = []
    for idx in entries:
        p_acum = 0.0
        for b in range(1, 49):
            fut = idx + b
            if fut >= data.shape[0]:
                break
            p_acum += ret_1[fut - 1] * side_mult
            valid = True
            for c1, c2, op, val in l_info:
                v1 = data[fut, c1]
                v2 = data[fut, c2] if c2 != -1 else val
                if op == 0 and not (v1 >= v2): valid = False; break
                if op == 1 and not (v1 <= v2): valid = False; break
            if not valid:
                break
        profits.append(p_acum)
    return np.array(profits)


def l3_synthetic_reference(entries, ret_1, side_mult):
    """numba_synthetic_engine del auditor (L3, líneas 38-51). EL BUG:
    acumula SIEMPRE 48 velas — jamás consulta la regla."""
    res = np.zeros(len(entries))
    for i, idx in enumerate(entries):
        profit = 0.0
        for b in range(1, 49):
            fut = idx + b
            if fut >= len(ret_1):
                break
            profit += ret_1[fut - 1] * side_mult
        res[i] = profit
    return res


# -----------------------------------------------------------------------------
# TESTS
# -----------------------------------------------------------------------------
def test_signal_equivalente_a_backtest_engine():
    """El motor único genera la MISMA máscara que fast_signal_generator."""
    data, col_map, _ = build_market()
    rules = [
        "rsi_14_sft >= 70",
        "rsi_14_sft <= 30|ema_55_sft >= Close_sft",
        "rsi_14_sft >= 40|rsi_14_sft <= 60|ema_55_sft <= Close_sft",
        "ema_55_sft > Close_sft",
        "rsi_14_sft < 25",
    ]
    for rule in rules:
        m_new = signal_mask(data, rule, col_map)
        m_old = fast_signal_generator(data, rule, col_map)
        assert np.array_equal(m_new, m_old), f"Divergencia de señal en: {rule}"
    print("OK  señal == backtest_engine.fast_signal_generator (5 reglas)")


def test_parser_falla_ruidosamente():
    """Regla rota debe lanzar ValueError, no devolver vacío en silencio."""
    _, col_map, _ = build_market(50)
    for bad in ("columna_fantasma >= 10", "rsi_14_sft >= abc", "sin_operador"):
        try:
            parse_rule(bad, col_map)
        except ValueError:
            continue
        raise AssertionError(f"No falló con regla ilegal: {bad}")
    print("OK  parser ruidoso ante reglas ilegales (3 casos)")


def test_cooldown_equivalente():
    """apply_cooldown == backtest_engine.apply_time_filter."""
    mask = RNG.random(2000) < 0.15
    for cd in (0, 5, 24, 100):
        a = apply_cooldown(mask.copy(), cd)
        b = apply_time_filter(mask.copy(), cd)
        assert np.array_equal(a, b), f"Cooldown divergente con cd={cd}"
    print("OK  cooldown == backtest_engine.apply_time_filter (4 valores)")


def test_sintetica_replica_al_minero():
    """La salida sintética del motor único == bucle de L2 (la semántica buena)."""
    data, col_map, _ = build_market()
    rule = "rsi_14_sft >= 45|ema_55_sft <= Close_sft"
    for side_mult, side in ((1.0, 'LONG'), (-1.0, 'SHORT')):
        mask = signal_mask(data, rule, col_map)
        entries = np.where(mask)[0][:200]
        close = data[:, col_map['Close']].astype(np.float64)
        ret_1 = np.zeros(len(close))
        ret_1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)

        ref = l2_synthetic_reference(data, entries, rule, col_map, ret_1, side_mult)
        new, _ = synthetic_exit(data, entries, parse_rule(rule, col_map), ret_1, side_mult)
        assert np.allclose(ref, new, atol=1e-10), f"Sintética != L2 en {side}"
    print("OK  sintética == referencia L2 (LONG y SHORT, 200 trades)")


def test_demostracion_bug_l3():
    """DEMOSTRACION DEL HALLAZGO: el auditor L3 evaluaba OTRA salida sintética.

    Con una regla que se rompe rápido, L3 (48 velas siempre) difiere del
    minero L2 (rotura bar-a-bar). El motor único coincide con L2, no con L3.
    """
    data, col_map, _ = build_market()
    # Regla viva solo cuando rsi >= 45: en datos uniformes se rompe enseguida
    rule = "rsi_14_sft >= 45"
    mask = signal_mask(data, rule, col_map)
    entries = np.where(mask)[0][:300]
    close = data[:, col_map['Close']].astype(np.float64)
    ret_1 = np.zeros(len(close))
    ret_1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)

    ref_l2 = l2_synthetic_reference(data, entries, rule, col_map, ret_1, 1.0)
    ref_l3 = l3_synthetic_reference(entries, ret_1, 1.0)
    new, durations = synthetic_exit(data, entries, parse_rule(rule, col_map), ret_1, 1.0)

    assert np.allclose(new, ref_l2, atol=1e-10), "El motor debe replicar a L2"
    assert not np.allclose(ref_l3, ref_l2, atol=1e-6), \
        "Se esperaba divergencia L3 vs L2 (si esto falla, el bug no existiría)"

    diff = np.abs(ref_l3 - ref_l2)
    pf_l2 = profit_factor(ref_l2)
    pf_l3 = profit_factor(ref_l3)
    print("OK  BUG L3 DEMOSTRADO:")
    print(f"      trades comparados        : {len(entries)}")
    print(f"      duración media real (L2) : {durations.mean():.1f} velas "
          f"(L3 asumía 48 siempre)")
    print(f"      divergencia media |L3-L2|: {diff.mean():.6f} por trade")
    print(f"      PF según minero L2       : {pf_l2:.3f}")
    print(f"      PF según auditor L3      : {pf_l3:.3f}  <-- medía otra cosa")


def test_demostracion_cooldown_desigual():
    """DEMOSTRACION DEL HALLAZGO: L2 minaba con cooldown 24, L3 auditaba sin él.

    Mismo dataset, misma regla: el conjunto de trades difiere entre capas.
    El motor único exige el cooldown como parámetro explícito.
    """
    data, col_map, ret_idx = build_market()
    rule = "rsi_14_sft >= 30"  # señal densa
    sim_l2 = simulate(data, col_map, ret_idx, rule, 'Ret_24', 'LONG', cooldown=24)
    sim_l3 = simulate(data, col_map, ret_idx, rule, 'Ret_24', 'LONG', cooldown=0)
    assert sim_l3['n_trades'] > sim_l2['n_trades'], "Se esperaba más trades sin cooldown"
    print("OK  COOLDOWN DESIGUAL DEMOSTRADO:")
    print(f"      trades con cooldown 24 (como minaba L2) : {sim_l2['n_trades']}")
    print(f"      trades sin cooldown (como auditaba L3)  : {sim_l3['n_trades']}")


def test_salida_fija_y_friccion_como_l3():
    """Salida fija + fricción del motor == cálculo del auditor (L3 audit_worker)."""
    data, col_map, ret_idx = build_market()
    rule = "rsi_14_sft >= 55|ema_55_sft <= Close_sft"
    f_points = 0.3
    sim = simulate(data, col_map, ret_idx, rule, 'Ret_24', 'SHORT',
                   cooldown=0, friction_points=f_points)

    # Réplica literal de L3 (sin cooldown, fricción por precio de entrada)
    mask = fast_signal_generator(data, rule, col_map)
    idx_e = np.where(mask)[0]
    r_all = np.zeros(data.shape[0])
    r_all[idx_e] = data[idx_e, ret_idx['Ret_24']] * -1.0
    prices_in = data[idx_e, col_map['Close_sft']]
    r_all[idx_e] -= f_points / (prices_in + 1e-9)

    assert np.allclose(sim['vector'], r_all, atol=1e-9), "Vector neto != L3"
    assert sim['n_trades'] == len(idx_e)
    print(f"OK  salida fija + fricción == L3 ({len(idx_e)} trades, {f_points} pts)")


def test_metricas_basicas():
    """PF y MDD con valores de control calculados a mano."""
    assert abs(profit_factor(np.array([0.02, -0.01, 0.03, -0.01, 0.0])) - 2.5) < 1e-6
    # Curva 100 -> 110 -> 99: DD = 11/110 = 10%
    assert abs(max_drawdown_pct(np.array([0.10, -0.11])) - 10.0) < 1e-6
    print("OK  métricas PF y MDD contra valores de control")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    print(f"=== MOTOR UNICO X1 - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
