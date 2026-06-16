# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 108.0 - ACCIÓN DE PRECIO (materia prima nueva)
# FILE: modules/price_action.py
# ROL: Features OHLC-GEOMÉTRICAS que los osciladores PROMEDIAN Y PIERDEN
#      (forma de vela, tamaño vs ATR, estructura de swings, rupturas,
#      secuencias). Factory on-demand como `formulaic`; el motor las compara
#      como columnas. Cada feature es función de OHLC → traducible a MQL5
#      (iOpen/iHigh/iLow/iClose) — gate de oro antes de cosechar.
#
# SHIFT (_sft): la feature se computa sobre el OHLC CRUDO y se desplaza 1 vela
#   ⇒ el token `{feat}_sft[t]` = feature de la vela t-1 (decisión en t con
#   info de t-1, sin lookahead), igual que el resto del ADN.
#
# TOKENS: no-ventana `{name}_sft` (close_pos, body_ratio, candle_dir,
#   upper_wick, lower_wick, range_atr, body_atr, gap_up, gap_down,
#   n_consec_up, n_consec_down); con-ventana `{name}{W}_sft` (dist_swinghigh,
#   dist_swinglow, n_higher_highs, n_lower_lows, breakout_high, breakout_low).
# ##########################################################################
import re

import numpy as np

try:
    from numba import njit
    NUMBA_ACTIVE = True
except ImportError:
    NUMBA_ACTIVE = False
    def njit(*a, **k):
        if len(a) == 1 and callable(a[0]):
            return a[0]
        def wrap(f):
            return f
        return wrap

EPS = 1e-9
ATR_P = 14
PA_WINDOWS = (10, 20, 50)
PLAIN = ('body_ratio', 'close_pos', 'upper_wick', 'lower_wick', 'candle_dir',
         'range_atr', 'body_atr', 'gap_up', 'gap_down', 'n_consec_up', 'n_consec_down')
WINDOWED = ('dist_swinghigh', 'dist_swinglow', 'n_higher_highs', 'n_lower_lows',
            'breakout_high', 'breakout_low')
_TOKEN_RE = re.compile(r'^(' + '|'.join(WINDOWED) + r')(\d+)$')


# ----------------------------- KERNELS (sobre OHLC crudo) -----------------------------
@njit(cache=True, nogil=True)
def _atr(H, L, C, P):
    n = C.shape[0]; tr = np.empty(n); atr = np.zeros(n)
    tr[0] = H[0] - L[0]
    for i in range(1, n):
        a = H[i] - L[i]; b = abs(H[i] - C[i - 1]); c = abs(L[i] - C[i - 1])
        tr[i] = a if (a >= b and a >= c) else (b if b >= c else c)
    s = 0.0
    for i in range(n):
        s += tr[i]
        if i >= P:
            s -= tr[i - P]
        atr[i] = s / P if i >= P - 1 else (tr[i] if i == 0 else s / (i + 1))
    return atr


@njit(cache=True, nogil=True)
def _candle(O, H, L, C, kind):
    n = C.shape[0]; out = np.zeros(n)
    for i in range(n):
        rng = H[i] - L[i]
        if kind == 0:        # body_ratio
            out[i] = abs(C[i] - O[i]) / (rng + EPS)
        elif kind == 1:      # close_pos
            out[i] = (C[i] - L[i]) / (rng + EPS)
        elif kind == 2:      # upper_wick
            mx = O[i] if O[i] > C[i] else C[i]
            out[i] = (H[i] - mx) / (rng + EPS)
        elif kind == 3:      # lower_wick
            mn = O[i] if O[i] < C[i] else C[i]
            out[i] = (mn - L[i]) / (rng + EPS)
        else:                # candle_dir
            out[i] = 1.0 if C[i] > O[i] else (-1.0 if C[i] < O[i] else 0.0)
    return out


@njit(cache=True, nogil=True)
def _size_atr(O, H, L, C, body):
    atr = _atr(H, L, C, ATR_P); n = C.shape[0]; out = np.zeros(n)
    for i in range(n):
        num = abs(C[i] - O[i]) if body else (H[i] - L[i])
        out[i] = num / (atr[i] + EPS)
    return out


@njit(cache=True, nogil=True)
def _gap(O, C, up):
    n = C.shape[0]; out = np.zeros(n)
    for i in range(1, n):
        g = (O[i] - C[i - 1]) / (C[i - 1] + EPS)
        out[i] = (g if g > 0 else 0.0) if up else (-g if g < 0 else 0.0)
    return out


@njit(cache=True, nogil=True)
def _consec(C, up):
    n = C.shape[0]; out = np.zeros(n); run = 0
    for i in range(1, n):
        adv = C[i] > C[i - 1] if up else C[i] < C[i - 1]
        run = run + 1 if adv else 0
        out[i] = run
    return out


@njit(cache=True, nogil=True)
def _dist_swing(H, L, C, W, is_high):
    n = C.shape[0]; out = np.zeros(n)
    for i in range(n):
        lo = i - W + 1
        if lo < 0:
            lo = 0
        ext = H[lo] if is_high else L[lo]
        for j in range(lo + 1, i + 1):
            if is_high:
                if H[j] > ext:
                    ext = H[j]
            else:
                if L[j] < ext:
                    ext = L[j]
        out[i] = (C[i] - ext) / (C[i] + EPS)
    return out


@njit(cache=True, nogil=True)
def _count_struct(H, L, W, higher):
    n = H.shape[0]; out = np.zeros(n)
    for i in range(n):
        lo = i - W + 1
        if lo < 1:
            lo = 1
        cnt = 0
        for j in range(lo, i + 1):
            if higher:
                if H[j] > H[j - 1]:
                    cnt += 1
            else:
                if L[j] < L[j - 1]:
                    cnt += 1
        out[i] = cnt
    return out


@njit(cache=True, nogil=True)
def _breakout(H, L, C, W, is_high):
    n = C.shape[0]; out = np.zeros(n)
    for i in range(n):
        lo = i - W
        if lo < 0:
            lo = 0
        if i == 0:
            continue
        ext = H[lo] if is_high else L[lo]
        for j in range(lo + 1, i):                # ventana PREVIA (excluye la actual)
            if is_high:
                if H[j] > ext:
                    ext = H[j]
            else:
                if L[j] < ext:
                    ext = L[j]
        out[i] = 1.0 if ((C[i] > ext) if is_high else (C[i] < ext)) else 0.0
    return out


# ----------------------------- DESPACHO + FACTORY -----------------------------
def _compute_raw(name, O, H, L, C, W):
    O = np.ascontiguousarray(O, np.float64); H = np.ascontiguousarray(H, np.float64)
    L = np.ascontiguousarray(L, np.float64); C = np.ascontiguousarray(C, np.float64)
    if name == 'body_ratio':  return _candle(O, H, L, C, 0)
    if name == 'close_pos':   return _candle(O, H, L, C, 1)
    if name == 'upper_wick':  return _candle(O, H, L, C, 2)
    if name == 'lower_wick':  return _candle(O, H, L, C, 3)
    if name == 'candle_dir':  return _candle(O, H, L, C, 4)
    if name == 'range_atr':   return _size_atr(O, H, L, C, False)
    if name == 'body_atr':    return _size_atr(O, H, L, C, True)
    if name == 'gap_up':      return _gap(O, C, True)
    if name == 'gap_down':    return _gap(O, C, False)
    if name == 'n_consec_up': return _consec(C, True)
    if name == 'n_consec_down': return _consec(C, False)
    if name == 'dist_swinghigh': return _dist_swing(H, L, C, W, True)
    if name == 'dist_swinglow':  return _dist_swing(H, L, C, W, False)
    if name == 'n_higher_highs': return _count_struct(H, L, W, True)
    if name == 'n_lower_lows':   return _count_struct(H, L, W, False)
    if name == 'breakout_high':  return _breakout(H, L, C, W, True)
    if name == 'breakout_low':   return _breakout(H, L, C, W, False)
    raise ValueError(f"feature de price action desconocida: {name}")


def parse_pa_token(token):
    """'close_pos_sft'->('close_pos',0); 'breakout_high20_sft'->('breakout_high',20). None si no es PA."""
    name = token[:-4] if token.endswith('_sft') else token
    if name in PLAIN:
        return name, 0
    m = _TOKEN_RE.match(name)
    if m:
        return m.group(1), int(m.group(2))
    return None


def is_price_action(token):
    return parse_pa_token(token) is not None


def pa_tokens_in_rules(rules):
    found = set()
    for rule in rules:
        for cond in str(rule).split('|'):
            for op in ('>=', '<=', '==', '>', '<'):
                if op in cond:
                    for s in cond.split(op, 1):
                        if is_price_action(s.strip()):
                            found.add(s.strip())
                    break
    return found


def price_action_vocabulary():
    toks = [f"{n}_sft" for n in PLAIN]
    for n in WINDOWED:
        toks += [f"{n}{w}_sft" for w in PA_WINDOWS]
    return toks


def expand_price_action(data, col_map, tokens, ohlc=('Open', 'High', 'Low', 'Close')):
    """Agrega a (data, col_map) las columnas de price action pedidas (faltantes).
    Requiere las 4 columnas OHLC crudas en col_map. Idempotente."""
    for c in ohlc:
        if c not in col_map:
            raise KeyError(f"price action requiere la columna cruda '{c}' en el Parquet")
    O, H, L, C = (data[:, col_map[c]] for c in ohlc)
    cmap = dict(col_map); new_cols, new_names = [], []
    for tok in tokens:
        if tok in cmap or tok in new_names:
            continue
        p = parse_pa_token(tok)
        if p is None:
            continue
        name, W = p
        raw = _compute_raw(name, O, H, L, C, W)
        sft = np.empty_like(raw); sft[1:] = raw[:-1]; sft[0] = raw[0]   # _sft = shift 1
        new_cols.append(sft.astype(np.float32)); new_names.append(tok)
    if not new_cols:
        return data, col_map
    aug = np.column_stack([data] + new_cols)
    for i, nm in enumerate(new_names):
        cmap[nm] = data.shape[1] + i
    return aug, cmap
