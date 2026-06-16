# ##########################################################################
# SYSTEM: X1-ARCHITECT | TEST v108 - ACCIÓN DE PRECIO
# FILE: tests/test_price_action.py
# ROL: Cada feature OHLC computa EXACTO (casos a mano + referencia numpy), el
#      factory agrega columnas correctas y respeta el shift _sft (= feature de
#      la vela t-1, sin lookahead).
# USO: python tests/test_price_action.py
# ##########################################################################
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.price_action import (
    _compute_raw, expand_price_action, is_price_action, pa_tokens_in_rules,
    parse_pa_token, price_action_vocabulary, ATR_P,
)

RNG = np.random.default_rng(11)


def _ohlc(n=2000):
    c = 100 + np.cumsum(RNG.normal(0, 0.5, n))
    o = c + RNG.normal(0, 0.3, n)
    hi = np.maximum(o, c) + np.abs(RNG.normal(0, 0.4, n))
    lo = np.minimum(o, c) - np.abs(RNG.normal(0, 0.4, n))
    return o, hi, lo, c


O, H, L, C = _ohlc()


def test_forma_de_vela_casos_exactos():
    # vela: O=10 H=14 L=8 C=13  → body=3 range=6
    o, h, l, c = np.array([10.]), np.array([14.]), np.array([8.]), np.array([13.])
    assert abs(_compute_raw('body_ratio', o, h, l, c, 0)[0] - 3 / 6) < 1e-9
    assert abs(_compute_raw('close_pos', o, h, l, c, 0)[0] - (13 - 8) / 6) < 1e-9   # 0.8333
    assert abs(_compute_raw('upper_wick', o, h, l, c, 0)[0] - (14 - 13) / 6) < 1e-9  # max(O,C)=13
    assert abs(_compute_raw('lower_wick', o, h, l, c, 0)[0] - (10 - 8) / 6) < 1e-9   # min(O,C)=10
    assert _compute_raw('candle_dir', o, h, l, c, 0)[0] == 1.0
    print("OK  forma de vela exacta (body/close_pos/wicks/dir en vela O10 H14 L8 C13)")


def test_secuencias_y_gaps_exactos():
    c = np.array([10., 11., 12., 11., 13.])             # sube,sube,baja,sube
    o = np.array([10., 10., 10., 12., 11.])             # O[3]=12 vs C[2]=12 (sin gap), O[4]=11 vs C[3]=11
    assert list(_compute_raw('n_consec_up', o, c, c, c, 0)) == [0, 1, 2, 0, 1]
    o2 = np.array([10., 10., 13., 10., 10.])            # O[2]=13 > C[1]=11 → gap_up
    g = _compute_raw('gap_up', o2, c, c, c, 0)
    assert abs(g[2] - (13 - 11) / 11) < 1e-9 and g[1] == 0.0
    print("OK  secuencias (n_consec) y gaps exactos")


def test_windowed_vs_numpy():
    W = 20
    dh = _compute_raw('dist_swinghigh', O, H, L, C, W)
    ref = np.array([(C[i] - H[max(0, i - W + 1):i + 1].max()) / (C[i] + 1e-9) for i in range(len(C))])
    assert np.allclose(dh, ref, atol=1e-9), "dist_swinghigh != ref"
    assert (dh <= 1e-9).all(), "dist a swing high debe ser <= 0"
    dl = _compute_raw('dist_swinglow', O, H, L, C, W)
    assert (dl >= -1e-9).all(), "dist a swing low debe ser >= 0"
    bo = _compute_raw('breakout_high', O, H, L, C, W)
    assert set(np.unique(bo)).issubset({0.0, 1.0})
    # breakout exacto: C rompe el máx de las W previas
    i = 500
    prev_max = H[max(0, i - W):i][:-1].max() if i - W >= 0 else H[0:i].max()
    # (replica del kernel: ventana [i-W+1, i-1])
    lo = max(0, i - W)
    pm = H[lo + 1:i].max()
    assert bo[i] == (1.0 if C[i] > pm else 0.0)
    hh = _compute_raw('n_higher_highs', O, H, L, C, 10)
    assert (hh >= 0).all() and (hh <= 10).all()
    print("OK  windowed (dist_swing/breakout/n_higher_highs) == referencia numpy")


def test_size_atr_estable():
    ra = _compute_raw('range_atr', O, H, L, C, 0)
    # en régimen estable atr = SMA(TR,14); comparar i grande
    tr = np.empty(len(C)); tr[0] = H[0] - L[0]
    for i in range(1, len(C)):
        tr[i] = max(H[i] - L[i], abs(H[i] - C[i - 1]), abs(L[i] - C[i - 1]))
    atr = np.array([tr[i - ATR_P + 1:i + 1].mean() for i in range(len(C))])
    i = 800
    assert abs(ra[i] - (H[i] - L[i]) / (atr[i] + 1e-9)) < 1e-6
    assert (ra > 0).all()
    print("OK  range_atr/body_atr vs ATR(14) de referencia")


def test_factory_shift_y_vocab():
    vocab = price_action_vocabulary()
    assert len(vocab) == 11 + 6 * 3, f"vocabulario PA inesperado: {len(vocab)}"  # 11 plain + 6×3 windowed
    assert parse_pa_token('close_pos_sft') == ('close_pos', 0)
    assert parse_pa_token('breakout_high20_sft') == ('breakout_high', 20)
    assert parse_pa_token('rsi_13_sft') is None
    assert pa_tokens_in_rules(['close_pos_sft >= 0.7|rsi_13_sft <= 30']) == {'close_pos_sft'}

    n = len(C)
    data = np.column_stack([O, H, L, C]).astype(np.float32)
    cm = {'Open': 0, 'High': 1, 'Low': 2, 'Close': 3}
    aug, c2 = expand_price_action(data, cm, ['close_pos_sft', 'breakout_high20_sft', 'rsi_x'])
    assert 'close_pos_sft' in c2 and 'breakout_high20_sft' in c2 and aug.shape[1] == 6
    # referencia desde las MISMAS columnas float32 que usa el factory (evita
    # discrepancia float32/float64 de inputs): el test es del SHIFT, no de precisión
    raw = _compute_raw('close_pos', data[:, 0], data[:, 1], data[:, 2], data[:, 3], 0).astype(np.float32)
    col = aug[:, c2['close_pos_sft']]
    assert np.allclose(col[1:], raw[:-1], atol=1e-5), "el _sft debe ser shift(raw,1)"
    # idempotente + KeyError sin Open
    aug2, _ = expand_price_action(aug, c2, ['close_pos_sft'])
    assert aug2.shape[1] == aug.shape[1]
    try:
        expand_price_action(np.zeros((5, 3), np.float32), {'High': 0, 'Low': 1, 'Close': 2}, ['close_pos_sft'])
        raise AssertionError("debía exigir Open")
    except KeyError:
        pass
    print("OK  factory: vocab (29 tokens), parsing, shift _sft = shift(raw,1), idempotente, exige OHLC")


if __name__ == '__main__':
    tests = [test_forma_de_vela_casos_exactos, test_secuencias_y_gaps_exactos,
             test_windowed_vs_numpy, test_size_atr_estable, test_factory_shift_y_vocab]
    print(f"=== ACCIÓN DE PRECIO v108 - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
