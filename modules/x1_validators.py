# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 106.0 - VALIDADORES (FASE 4 SANEAMIENTO)
# FILE: modules/x1_validators.py
# ROL: Monkey Test (bootstrap data-driven) y Excursion Score (MFE/MAE).
#
# MONKEY TEST - port fiel del motor de Marc Cortázar (monkey_test_5.html,
# metodología Tomillero/Jaume/Antolí): cada mono recorre la secuencia REAL
# del histórico vela a vela; entra con p = trades/velas, mantiene la misma
# exposición media que la estrategia y cierra por tiempo. Preserva
# autocorrelación, colas gordas y clústeres de volatilidad (no es un
# Montecarlo paramétrico). P-value = % de monos que la estrategia supera.
# Umbrales de la metodología: 99% en IS (train) / 90% en OOS (test).
#
# EXCURSION SCORE (XS) - port del snippet SQX de Alan Tomillero
# (ExcursionScore.java): XS_trade = |MFE| / (|MFE| + |MAE|), media en [0,1].
# 0.50 = sin edge de entrada, >=0.55 = edge, >=0.60 = fuerte. Mide la calidad
# de la ENTRADA con independencia de la salida; su caída en OOS/live delata
# alpha decay antes de que lo muestre el P&L.
#
# Estos validadores implementan los fusibles 'monkey_test' (muerto en L3
# v104.920) y la métrica nueva XS. Numba opcional, igual que x1_engine.
# ##########################################################################
import os
from concurrent.futures import ThreadPoolExecutor

import numpy as np

try:
    from numba import njit
    NUMBA_ACTIVE = True
except ImportError:
    NUMBA_ACTIVE = False
    def njit(*args, **kwargs):
        if len(args) == 1 and callable(args[0]):
            return args[0]
        def wrap(func):
            return func
        return wrap

N_MONKEYS_DEFAULT = 5000  # mismo número que la herramienta de Marc


# -----------------------------------------------------------------------------
# 1. MONKEY TEST
# -----------------------------------------------------------------------------
def rolling_forward_returns(ret_1, exposure):
    """fwd[i] = suma de ret_1 en la ventana [i, i+exposure) - retorno de un
    trade que entra en i y cierra por tiempo a las `exposure` velas.

    Equivalente al pre-cálculo `forwardRet` del HTML de Marc. Para salidas
    fijas Ret_N de X1 esto coincide (aprox. compuesto vs simple) con la
    columna Ret_N; se recalcula aquí para que los monos y la estrategia
    midan EXACTAMENTE igual.
    """
    n = len(ret_1)
    fwd = np.zeros(n, dtype=np.float64)
    cum = np.concatenate(([0.0], np.cumsum(ret_1)))
    top = np.minimum(np.arange(n) + exposure, n)
    fwd = cum[top] - cum[np.arange(n)]
    return fwd


@njit(cache=True, nogil=True)
def _monkey_core(fwd, prob_entry, exposure, n_monkeys, seed, friction):
    """Bucle de monos fiel al motor de Marc: Bernoulli vela a vela + busyUntil.

    `friction` (retorno fraccional por trade) se descuenta en CADA entrada del
    mono, igual que simulate() se lo descuenta a la estrategia.

    v108-B0: nogil=True → bajo backend `threading` este kernel LIBERA el GIL,
    así varias llamadas (un candidato cada una) corren en paralelo de verdad
    compartiendo los arrays en memoria (sin pickle/disco como haría loky).
    DETERMINISMO: se re-siembra `np.random.seed(seed)` al inicio de CADA llamada
    y el estado np.random de Numba es THREAD-LOCAL, así que la secuencia de cada
    llamada es independiente del resto de threads y del orden → idéntico al
    serial (verificado en tests/test_monkey_parity.py).
    """
    np.random.seed(seed)
    n = fwd.shape[0]
    finals = np.zeros(n_monkeys)
    trade_counts = np.zeros(n_monkeys, dtype=np.int64)
    for m in range(n_monkeys):
        equity = 0.0
        busy_until = -1
        n_tr = 0
        for i in range(n):
            if i > busy_until:
                if np.random.random() <= prob_entry:
                    equity += fwd[i] - friction
                    busy_until = i + exposure - 1
                    n_tr += 1
        finals[m] = equity
        trade_counts[m] = n_tr
    return finals, trade_counts


def monkey_test(ret_1, n_trades, exposure, strat_total, side='LONG',
                n_monkeys=N_MONKEYS_DEFAULT, seed=12345, correct_cadence=True,
                friction_per_trade=0.0):
    """Ejecuta el Monkey Test sobre una zona del histórico.

    Args:
      ret_1       : retornos vela-a-vela de la ZONA evaluada (IS u OOS),
                    en la orientación del activo (sin ajustar por side).
      n_trades    : trades reales de la estrategia EN ESA ZONA.
      exposure    : exposición media en velas (duración del trade).
      strat_total : retorno total neto de la estrategia EN ESA ZONA.
      side        : 'LONG'/'SHORT' - los monos copian la dirección.
      n_monkeys   : tiradas (5000 = herramienta original de Marc).
      seed        : reproducibilidad del veredicto.
      correct_cadence: la herramienta original usa p = trades/velas, pero el
                    busyUntil consume ~exposure velas de oportunidad por trade,
                    así que los monos terminan operando MENOS que la estrategia
                    (test más blando). Con True se ajusta
                    p = trades / (velas - trades*(exposure-1)) para que la
                    cadencia esperada coincida con la real (test más justo
                    y más exigente).
      friction_per_trade: peaje por trade de los monos, en retorno fraccional
                    (p.ej. f_points / precio_medio_de_la_zona). La herramienta
                    original de Marc compara la estrategia NETA de fricción
                    contra monos BRUTOS: ese sesgo castiga a las estrategias
                    reales (deben superar al azar Y pagar el spread que los
                    monos no pagan). Con friction_per_trade > 0 cada entrada
                    del mono paga el mismo peaje normalizado que la estrategia
                    paga vía simulate(), y la pelea es justa. 0.0 = comporta-
                    miento original (sesgado), conservado para regresión.

    Returns dict:
      pvalue          : fracción de monos que la estrategia supera [0,1]
      beta            : retorno medio de los monos (lo que regala el mercado
                        con esa cadencia y dirección, sin estrategia)
      monkey_win_pct  : fracción de monos que acabaron en positivo
      monkey_trades   : media de trades por mono (control de cadencia)
      prob_entry      : p usada
    """
    ret = np.ascontiguousarray(ret_1, dtype=np.float64)
    if str(side).upper() != 'LONG':
        ret = -ret
    n = len(ret)
    if n < 10 or n_trades < 1:
        return {'pvalue': 0.0, 'beta': 0.0, 'monkey_win_pct': 0.0,
                'monkey_trades': 0.0, 'prob_entry': 0.0}

    exposure = int(max(1, min(exposure, n - 1)))
    if correct_cadence:
        free_bars = n - n_trades * (exposure - 1)
        prob_entry = min(1.0, n_trades / max(1.0, float(free_bars)))
    else:
        prob_entry = min(1.0, n_trades / n)
    fwd = rolling_forward_returns(ret, exposure)

    finals, counts = _monkey_core(fwd, prob_entry, exposure, int(n_monkeys), int(seed),
                                  float(friction_per_trade))

    return {
        'pvalue': float(np.mean(strat_total > finals)),
        'beta': float(finals.mean()),
        'monkey_win_pct': float(np.mean(finals > 0)),
        'monkey_trades': float(counts.mean()),
        'prob_entry': float(prob_entry),
    }


def monkey_batch(jobs, n_threads=None):
    """Corre una lista de monkey_test EN PARALELO (v108-B0).

    `jobs`: lista de dicts con los kwargs de monkey_test (ret_1, n_trades,
    exposure, strat_total, side, n_monkeys, seed, friction_per_trade, ...).
    Devuelve la lista de resultados EN EL MISMO ORDEN que `jobs`.

    Paraleliza con threads: como `_monkey_core` es `nogil=True`, las llamadas
    liberan el GIL y corren de verdad en paralelo (a diferencia de un njit
    normal, que lo retiene y serializa). Sin pickle ni disco — los arrays se
    comparten en memoria, evitando el crash de loky con el G_DF de 162 MB.

    DETERMINISTA: cada job re-siembra su propio estado (RNG thread-local de
    Numba), así que el resultado es IDÉNTICO al serial sea cual sea el número
    de threads o el orden de ejecución (ver tests/test_monkey_parity.py).
    """
    if n_threads is None:
        n_threads = max(1, min(32, (os.cpu_count() or 4)))
    if n_threads == 1 or len(jobs) <= 1:
        return [monkey_test(**j) for j in jobs]
    with ThreadPoolExecutor(max_workers=n_threads) as ex:
        return list(ex.map(lambda j: monkey_test(**j), jobs))


# -----------------------------------------------------------------------------
# 2. EXCURSION SCORE (XS)
# -----------------------------------------------------------------------------
@njit(cache=True)
def _xs_core(high, low, entry_prices, entries, durations, side_mult):
    """XS por trade sobre la ventana de tenencia [idx+1, idx+dur]."""
    n_rows = high.shape[0]
    out = np.full(len(entries), np.nan)
    for k in range(len(entries)):
        idx = entries[k]
        dur = durations[k]
        lo_i = idx + 1
        hi_i = min(idx + dur, n_rows - 1)
        if hi_i < lo_i:
            continue
        h_max = high[lo_i]
        l_min = low[lo_i]
        for j in range(lo_i + 1, hi_i + 1):
            if high[j] > h_max: h_max = high[j]
            if low[j] < l_min: l_min = low[j]
        entry = entry_prices[k]
        if side_mult > 0:
            mfe = h_max - entry
            mae = entry - l_min
        else:
            mfe = entry - l_min
            mae = h_max - entry
        if mfe < 0.0: mfe = 0.0
        if mae < 0.0: mae = 0.0
        denom = mfe + mae
        if denom > 0.0:
            out[k] = mfe / denom
    return out


def excursion_score(high, low, close, entries, durations, side):
    """Excursion Score medio de un conjunto de trades (Tomillero).

    XS_trade = |MFE| / (|MFE| + |MAE|), excursiones medidas desde el precio
    de entrada (Close de la vela de señal) sobre High/Low de las velas en
    posición. Media en [0,1]; NaN por trade sin recorrido se excluye
    (mismo criterio que el snippet Java: denom > 0).

    Returns: (xs_mean, xs_por_trade)
    """
    entries = np.asarray(entries, dtype=np.int64)
    durations = np.asarray(durations, dtype=np.int64)
    if len(entries) == 0:
        return 0.0, np.zeros(0)
    side_mult = 1.0 if str(side).upper() == 'LONG' else -1.0
    entry_prices = np.asarray(close, dtype=np.float64)[entries]
    xs = _xs_core(np.asarray(high, dtype=np.float64),
                  np.asarray(low, dtype=np.float64),
                  entry_prices, entries, durations, side_mult)
    valid = xs[~np.isnan(xs)]
    return (float(valid.mean()) if valid.size else 0.0), xs
