# ##########################################################################
# SYSTEM: X1-ARCHITECT | TEST v108-B2a
# FILE: tests/test_formulaic.py
# ROL: Cada operador formulaico computa EXACTO (vs referencia numpy), es
#      determinista, respeta la propiedad del shift (op(x_sft)=op(x)_sft, base
#      de la paridad) y el factory expand_formulaic agrega columnas correctas.
# USO: python tests/test_formulaic.py
# ##########################################################################
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.formulaic import (
    compute_operator, expand_formulaic, formulaic_tokens_in_rules,
    formulaic_vocabulary, parse_token,
)

RNG = np.random.default_rng(2026)
X = np.cumsum(RNG.normal(0, 1, 3000)).astype(np.float64)  # serie con nivel y tendencia


# ---------------- referencias numpy ----------------
def ref_delta(x, K):
    o = np.zeros(len(x)); o[K:] = x[K:] - x[:-K]; return o


def ref_slope(x, K):
    o = np.zeros(len(x)); xs = np.arange(K)
    for t in range(K - 1, len(x)):
        o[t] = np.polyfit(xs, x[t - K + 1:t + 1], 1)[0]
    return o


def ref_tsrank(x, W):
    o = np.full(len(x), 0.5)
    for t in range(len(x)):
        lo = max(0, t - (W - 1))
        prev = x[lo:t]
        if len(prev):
            o[t] = np.mean(prev < x[t])
    return o


def ref_dist(x, W, is_max):
    o = np.zeros(len(x))
    for t in range(len(x)):
        lo = max(0, t - (W - 1))
        win = x[lo:t + 1]
        o[t] = x[t] - (win.max() if is_max else win.min())
    return o


def test_operadores_vs_numpy():
    cases = [('delta', 5, ref_delta(X, 5)), ('delta', 10, ref_delta(X, 10)),
             ('slope', 3, ref_slope(X, 3)), ('slope', 10, ref_slope(X, 10)),
             ('tsrank', 50, ref_tsrank(X, 50)), ('tsrank', 100, ref_tsrank(X, 100)),
             ('distmax', 20, ref_dist(X, 20, True)), ('distmin', 50, ref_dist(X, 50, False))]
    for op, p, ref in cases:
        got = compute_operator(op, X, p)
        assert np.allclose(got, ref, atol=1e-9), f"{op}{p} != referencia (maxdiff {np.abs(got-ref).max():.2e})"
    print(f"OK  {len(cases)} operadores == referencia numpy (delta/slope/tsrank/distmax/distmin)")


def test_determinismo():
    for op, p in (('slope', 5), ('tsrank', 100), ('distmin', 50)):
        a = compute_operator(op, X, p); b = compute_operator(op, X, p)
        assert np.array_equal(a, b), f"{op}{p} no determinista"
    print("OK  operadores deterministas (misma serie == misma salida)")


def test_propiedad_shift():
    """op(x_sft) == shift(op(x),1) en el interior — base de la paridad _sft."""
    x_sft = np.roll(X, 1); x_sft[0] = X[0]
    for op, p in (('delta', 5), ('slope', 3), ('tsrank', 50), ('distmax', 20)):
        op_x = compute_operator(op, X, p)
        op_xsft = compute_operator(op, x_sft, p)
        sh = np.roll(op_x, 1)
        # comparar lejos del borde (warmup) donde la igualdad es exacta
        lo = p + 2
        assert np.allclose(op_xsft[lo:], sh[lo:], atol=1e-9), f"shift roto en {op}{p}"
    print("OK  propiedad del shift: op(x_sft) = op(x)_sft (computar sobre _sft = versión _sft)")


def test_token_parsing_y_vocabulario():
    assert parse_token('delta5_rsi_13_sft') == ('delta', 5, 'rsi_13')
    assert parse_token('tsrank100_natr_55_sft') == ('tsrank', 100, 'natr_55')
    assert parse_token('rsi_13_sft') is None            # no formulaico
    assert parse_token('Close_sft') is None
    cmap = {'rsi_13_sft': 0, 'natr_55_sft': 1, 'adx_21_sft': 2, 'close_sft': 3, 'ema_55_sft': 4}
    vocab = formulaic_vocabulary(cmap)
    # 4 bases válidas (rsi,natr,adx,close; ema NO está en BASES) × (2 ops×3 K + 3 ops×3 W) = 4×15
    assert len(vocab) == 4 * 15, f"vocabulario inesperado: {len(vocab)}"
    assert 'delta3_rsi_13_sft' in vocab and 'tsrank100_close_sft' in vocab
    assert not any('ema' in t for t in vocab), "ema no es base formulaica"
    toks = formulaic_tokens_in_rules(['delta5_rsi_13_sft >= 0.5|rsi_21_sft <= 30'])
    assert toks == {'delta5_rsi_13_sft'}
    print(f"OK  parsing + vocabulario ({len(vocab)} tokens de 4 bases) + extracción de reglas")


def test_expand_factory():
    n = 500
    data = np.column_stack([np.arange(n, dtype=np.float32),          # Close (dummy)
                            RNG.normal(50, 10, n).astype(np.float32)])  # rsi_13_sft
    cmap = {'Close': 0, 'rsi_13_sft': 1}
    aug, c2 = expand_formulaic(data, cmap, ['delta3_rsi_13_sft', 'tsrank50_rsi_13_sft', 'rsi_13_sft'])
    assert 'delta3_rsi_13_sft' in c2 and 'tsrank50_rsi_13_sft' in c2
    assert aug.shape[1] == 4, "deberían agregarse 2 columnas (la base ya estaba)"
    ref = compute_operator('delta', data[:, 1], 3)
    assert np.allclose(aug[:, c2['delta3_rsi_13_sft']], ref.astype(np.float32), atol=1e-4)
    # idempotencia
    aug2, c3 = expand_formulaic(aug, c2, ['delta3_rsi_13_sft'])
    assert aug2.shape[1] == aug.shape[1], "no debe duplicar columnas ya presentes"
    # base ausente -> KeyError
    try:
        expand_formulaic(data, cmap, ['delta3_cci_99_sft'])
        raise AssertionError("debía lanzar KeyError por base ausente")
    except KeyError:
        pass
    print("OK  expand_formulaic: agrega correcto, idempotente, KeyError si falta la base")


if __name__ == '__main__':
    tests = [test_operadores_vs_numpy, test_determinismo, test_propiedad_shift,
             test_token_parsing_y_vocabulario, test_expand_factory]
    print(f"=== GRAMÁTICA FORMULAICA v108-B2a - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
