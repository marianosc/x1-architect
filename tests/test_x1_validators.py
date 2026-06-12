# ##########################################################################
# SYSTEM: X1-ARCHITECT | FASE 4 SANEAMIENTO
# FILE: tests/test_x1_validators.py
# ROL: Sanidad estadística del Monkey Test y exactitud del Excursion Score.
# USO: python tests/test_x1_validators.py   (no requiere pytest ni numba)
# ##########################################################################
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.x1_validators import (
    excursion_score, monkey_test, rolling_forward_returns,
)

RNG = np.random.default_rng(7)
N_MONKEYS_TEST = 1000  # suficiente para sanidad; en blanca (numba) van 5000


# -----------------------------------------------------------------------------
# MONKEY TEST
# -----------------------------------------------------------------------------
def test_monos_copian_la_cadencia():
    """Con la corrección de cadencia los monos operan ~ los mismos trades."""
    ret_1 = RNG.normal(0, 0.002, 4000)
    res = monkey_test(ret_1, n_trades=120, exposure=24, strat_total=0.0,
                      n_monkeys=N_MONKEYS_TEST, correct_cadence=True)
    assert 120 * 0.85 < res['monkey_trades'] < 120 * 1.15, \
        f"Cadencia rota: {res['monkey_trades']:.1f} monos-trades vs 120 reales"
    # Modo fiel a la herramienta original (sin corrección): cadencia menor
    res_raw = monkey_test(ret_1, n_trades=120, exposure=24, strat_total=0.0,
                          n_monkeys=N_MONKEYS_TEST, correct_cadence=False)
    assert res_raw['monkey_trades'] < res['monkey_trades'], \
        "Sin corrección la cadencia debería ser menor (modo Marc original)"
    print(f"OK  cadencia: estrategia 120 trades | monos corregidos "
          f"{res['monkey_trades']:.1f} | monos modo original {res_raw['monkey_trades']:.1f}")


def test_beta_captura_la_tendencia():
    """En mercado alcista los monos LONG ganan (beta>0) y los SHORT pierden."""
    ret_1 = RNG.normal(0.0008, 0.002, 4000)  # deriva alcista clara
    res_long = monkey_test(ret_1, 100, 24, 0.0, side='LONG', n_monkeys=N_MONKEYS_TEST)
    res_short = monkey_test(ret_1, 100, 24, 0.0, side='SHORT', n_monkeys=N_MONKEYS_TEST)
    assert res_long['beta'] > 0, "Beta LONG debería ser positiva en mercado alcista"
    assert res_short['beta'] < 0, "Beta SHORT debería ser negativa en mercado alcista"
    print(f"OK  beta: LONG {res_long['beta']:+.4f} / SHORT {res_short['beta']:+.4f} "
          f"en mercado con deriva alcista")


def test_estrategia_sin_edge_no_pasa_el_99():
    """Una estrategia que ES un mono (entradas al azar) no debe lucir élite."""
    ret_1 = RNG.normal(0, 0.002, 4000)  # sin deriva
    exposure, n_trades = 24, 80
    fwd = rolling_forward_returns(ret_1, exposure)
    entries = np.sort(RNG.choice(len(ret_1) - exposure, n_trades, replace=False))
    strat_total = float(fwd[entries].sum())
    res = monkey_test(ret_1, n_trades, exposure, strat_total, n_monkeys=N_MONKEYS_TEST)
    assert 0.02 < res['pvalue'] < 0.98, \
        f"Un mono disfrazado obtuvo p-value extremo: {res['pvalue']}"
    print(f"OK  mono disfrazado de estrategia: p-value {res['pvalue']:.3f} "
          f"(no supera el umbral 0.99)")


def test_estrategia_con_edge_real_pasa():
    """Una estrategia con ventaja inyectada debe superar al 99% de los monos."""
    n = 4000
    ret_1 = RNG.normal(0, 0.002, n)
    exposure, n_trades = 3, 60
    # Inyectar edge: tras cada vela de entrada, 3 velas de +0.8%
    entries = np.sort(RNG.choice(np.arange(0, n - 10, 10), n_trades, replace=False))
    for idx in entries:
        ret_1[idx: idx + exposure] = 0.008
    fwd = rolling_forward_returns(ret_1, exposure)
    strat_total = float(fwd[entries].sum())
    res = monkey_test(ret_1, n_trades, exposure, strat_total, n_monkeys=N_MONKEYS_TEST)
    assert res['pvalue'] >= 0.99, f"Edge real no detectado: p-value {res['pvalue']}"
    print(f"OK  edge inyectado detectado: p-value {res['pvalue']:.3f} >= 0.99")


def test_friccion_baja_la_beta_de_los_monos():
    """(a) Con friction_per_trade>0 la beta baja exactamente trades*friccion.

    Mismo seed => mismas entradas Bernoulli => la unica diferencia entre los
    dos universos de monos es el peaje: beta_0 - beta_f == monkey_trades * f.
    """
    ret_1 = RNG.normal(0, 0.002, 4000)
    f = 0.0004  # ~1.0 pt sobre precio 2500 (peaje XAUUSD normalizado)
    r0 = monkey_test(ret_1, 100, 24, 0.0, n_monkeys=N_MONKEYS_TEST, seed=99)
    rf = monkey_test(ret_1, 100, 24, 0.0, n_monkeys=N_MONKEYS_TEST, seed=99,
                     friction_per_trade=f)
    esperado = rf['monkey_trades'] * f
    assert np.isclose(r0['beta'] - rf['beta'], esperado, rtol=1e-9), \
        f"beta_0-beta_f={r0['beta']-rf['beta']:.6f} != trades*f={esperado:.6f}"
    print(f"OK  friccion de monos: beta {r0['beta']:+.5f} -> {rf['beta']:+.5f} "
          f"(caida = {rf['monkey_trades']:.0f} trades x {f} exacta)")


def test_estrategia_neta_vs_monos_con_friccion_es_justa():
    """(b) Sin edge y con friccion en AMBOS lados, el p-value vuelve a ~uniforme.

    Antes (monos brutos) una estrategia-mono que pagaba spread real quedaba
    castigada con p-value bajo: el sesgo de la herramienta original.
    """
    ret_1 = RNG.normal(0, 0.002, 4000)  # sin deriva
    exposure, n_trades, f = 24, 80, 0.0004
    fwd = rolling_forward_returns(ret_1, exposure)
    entries = np.sort(RNG.choice(len(ret_1) - exposure, n_trades, replace=False))
    strat_neta = float(fwd[entries].sum()) - n_trades * f  # paga su peaje
    res_justa = monkey_test(ret_1, n_trades, exposure, strat_neta,
                            n_monkeys=N_MONKEYS_TEST, friction_per_trade=f)
    res_sesgada = monkey_test(ret_1, n_trades, exposure, strat_neta,
                              n_monkeys=N_MONKEYS_TEST, friction_per_trade=0.0)
    assert 0.02 < res_justa['pvalue'] < 0.98, \
        f"Pelea justa deberia dar p-value no extremo: {res_justa['pvalue']}"
    assert res_sesgada['pvalue'] <= res_justa['pvalue'], \
        "El modo sesgado (monos brutos) deberia castigar a la estrategia neta"
    print(f"OK  pelea justa: p-value {res_justa['pvalue']:.3f} (~uniforme) | "
          f"modo sesgado la castigaba: {res_sesgada['pvalue']:.3f}")


def test_friccion_cero_reproduce_comportamiento_original():
    """(c) Regresion: friction_per_trade=0 == llamada sin el parametro."""
    ret_1 = RNG.normal(0.0003, 0.002, 4000)
    a = monkey_test(ret_1, 90, 12, 0.05, n_monkeys=N_MONKEYS_TEST, seed=7)
    b = monkey_test(ret_1, 90, 12, 0.05, n_monkeys=N_MONKEYS_TEST, seed=7,
                    friction_per_trade=0.0)
    for k in ('pvalue', 'beta', 'monkey_win_pct', 'monkey_trades', 'prob_entry'):
        assert a[k] == b[k], f"Regresion rota en '{k}': {a[k]} != {b[k]}"
    print(f"OK  regresion: friction_per_trade=0 identico al original "
          f"(pvalue {a['pvalue']:.3f}, beta {a['beta']:+.5f})")


def test_forward_returns_exactos():
    """fwd[i] debe ser la suma exacta de la ventana, incluso en el borde final."""
    ret = np.array([0.01, 0.02, 0.03, 0.04])
    fwd = rolling_forward_returns(ret, 2)
    esperado = np.array([0.03, 0.05, 0.07, 0.04])  # última ventana truncada
    assert np.allclose(fwd, esperado), f"fwd incorrecto: {fwd}"
    print("OK  rolling_forward_returns exacto (incluye borde final truncado)")


# -----------------------------------------------------------------------------
# EXCURSION SCORE
# -----------------------------------------------------------------------------
def _candles(closes, spread=0.0):
    """High/Low sintéticos: vela plana alrededor del cierre."""
    c = np.asarray(closes, dtype=np.float64)
    return c + spread, c - spread, c


def test_xs_entrada_perfecta():
    """Si tras entrar el precio solo sube (LONG), XS = 1."""
    high, low, close = _candles([100, 101, 102, 103, 104])
    xs_mean, _ = excursion_score(high, low, close, entries=[0], durations=[4], side='LONG')
    assert abs(xs_mean - 1.0) < 1e-9, f"XS esperado 1.0, obtenido {xs_mean}"
    print("OK  XS=1.000 con entrada perfecta LONG (sin excursión adversa)")


def test_xs_entrada_desastrosa():
    """Si tras entrar el precio solo cae (LONG), XS = 0."""
    high, low, close = _candles([100, 99, 98, 97, 96])
    xs_mean, _ = excursion_score(high, low, close, entries=[0], durations=[4], side='LONG')
    assert abs(xs_mean) < 1e-9, f"XS esperado 0.0, obtenido {xs_mean}"
    print("OK  XS=0.000 con entrada desastrosa LONG (solo excursión adversa)")


def test_xs_simetrico_es_medio():
    """Excursión favorable == adversa => XS = 0.5 (sin edge de entrada)."""
    # Sube a 102 y baja a 98: MFE=2, MAE=2 desde entrada 100
    high, low, close = _candles([100, 102, 98, 100])
    xs_mean, _ = excursion_score(high, low, close, entries=[0], durations=[3], side='LONG')
    assert abs(xs_mean - 0.5) < 1e-9, f"XS esperado 0.5, obtenido {xs_mean}"
    print("OK  XS=0.500 con excursiones simétricas (sin edge)")


def test_xs_short_es_espejo():
    """El mismo recorrido valorado en SHORT invierte MFE/MAE."""
    high, low, close = _candles([100, 103, 99, 100])  # MFE_long=3, MAE_long=1
    xs_long, _ = excursion_score(high, low, close, [0], [3], 'LONG')
    xs_short, _ = excursion_score(high, low, close, [0], [3], 'SHORT')
    assert abs(xs_long - 0.75) < 1e-9
    assert abs(xs_short - 0.25) < 1e-9
    assert abs((xs_long + xs_short) - 1.0) < 1e-9, "LONG y SHORT deben ser espejo"
    print(f"OK  espejo LONG/SHORT: XS {xs_long:.2f} vs {xs_short:.2f} (suman 1)")


def test_xs_umbral_java():
    """Coherencia con el snippet de Alan: media de varios trades, [0,1]."""
    high, low, close = _candles([100, 101, 102, 103, 100, 102, 98, 100, 100, 99, 98, 100])
    xs_mean, xs = excursion_score(high, low, close,
                                  entries=[0, 4, 8], durations=[3, 3, 3], side='LONG')
    assert 0.0 <= xs_mean <= 1.0
    assert len(xs) == 3
    print(f"OK  XS medio de 3 trades = {xs_mean:.3f} (por trade: "
          f"{', '.join(f'{v:.2f}' for v in xs)})")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    print(f"=== VALIDADORES X1 (Monkey + XS) - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
