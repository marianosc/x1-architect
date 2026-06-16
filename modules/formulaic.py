# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 108.0 - GRAMÁTICA FORMULAICA (B2a)
# FILE: modules/formulaic.py
# ROL: Feature factory ON-DEMAND. Amplía el VOCABULARIO de tokens del minero
#      con operadores temporales sobre CUALQUIER indicador del ADN, sin tocar
#      el motor (que sigue comparando columnas) ni explotar el Parquet en L1.
#
# OPERADORES v1 (4):
#   delta_K(x)    = x[t] - x[t-K]
#   slope_K(x)    = pendiente OLS de x sobre K barras (como linreg, del indicador)
#   ts_rank_W(x)  = #{ x[t-i] < x[t], i=1..W-1 } / (W-1) ∈ [0,1]  (normaliza nivel)
#   dist_max_W(x) = x[t] - max(x[t-W+1..t])  ;  dist_min_W(x) = x[t] - min(...)
#
# TOKEN: {op}{param}_{base}_sft  — ej. delta5_rsi_13_sft, tsrank100_natr_55_sft.
#   El factory computa el operador SOBRE la columna `_sft` que ya está en el
#   Parquet ⇒ el resultado ES la versión `_sft` del operador (x_sft[t]=x[t-1]
#   ⇒ op(x_sft)=op(x)_sft). No hace falta la serie cruda; el motor lo compara
#   como una columna más. La paridad MQL5 (B2b) compone el helper sobre el
#   indicador base al mismo shift.
# ##########################################################################
import re

import numpy as np

try:
    from numba import njit
    NUMBA_ACTIVE = True
except ImportError:  # notebook sin numba
    NUMBA_ACTIVE = False
    def njit(*a, **k):
        if len(a) == 1 and callable(a[0]):
            return a[0]
        def wrap(f):
            return f
        return wrap

OPS = ('delta', 'slope', 'tsrank', 'distmax', 'distmin')
K_WINDOWS = (3, 5, 10)        # delta / slope
W_WINDOWS = (20, 50, 100)     # ts_rank / dist
BASES = ('rsi', 'natr', 'adx', 'cci', 'mom', 'close')
_TOKEN_RE = re.compile(r'^(delta|slope|tsrank|distmax|distmin)(\d+)_(.+)$')


# ---------------------------- KERNELS ----------------------------
@njit(cache=True, nogil=True)
def _delta(x, K):
    n = x.shape[0]; out = np.zeros(n)
    for t in range(K, n):
        out[t] = x[t] - x[t - K]
    return out


@njit(cache=True, nogil=True)
def _slope(x, K):
    n = x.shape[0]; out = np.zeros(n)
    im = (K - 1) / 2.0
    den = 0.0
    for i in range(K):
        den += (i - im) * (i - im)
    if den <= 0.0:
        return out
    for t in range(K - 1, n):
        sy = 0.0
        for i in range(K):
            sy += x[t - K + 1 + i]
        ym = sy / K
        sxy = 0.0
        for i in range(K):
            sxy += (i - im) * (x[t - K + 1 + i] - ym)
        out[t] = sxy / den
    return out


@njit(cache=True, nogil=True)
def _ts_rank(x, W):
    n = x.shape[0]; out = np.full(n, 0.5)
    for t in range(n):
        lo = t - (W - 1)
        if lo < 0:
            lo = 0
        cnt = 0; den = 0
        for j in range(lo, t):       # los W-1 (o los disponibles) bares previos
            den += 1
            if x[j] < x[t]:
                cnt += 1
        if den > 0:
            out[t] = cnt / den
    return out


@njit(cache=True, nogil=True)
def _dist_ext(x, W, is_max):
    n = x.shape[0]; out = np.zeros(n)
    for t in range(n):
        lo = t - (W - 1)
        if lo < 0:
            lo = 0
        ext = x[lo]
        for j in range(lo + 1, t + 1):
            if is_max:
                if x[j] > ext:
                    ext = x[j]
            else:
                if x[j] < ext:
                    ext = x[j]
        out[t] = x[t] - ext
    return out


def compute_operator(op, x, param):
    """Aplica un operador a una serie (float64). Devuelve float64."""
    x = np.ascontiguousarray(x, dtype=np.float64)
    if op == 'delta':   return _delta(x, int(param))
    if op == 'slope':   return _slope(x, int(param))
    if op == 'tsrank':  return _ts_rank(x, int(param))
    if op == 'distmax': return _dist_ext(x, int(param), True)
    if op == 'distmin': return _dist_ext(x, int(param), False)
    raise ValueError(f"operador formulaico desconocido: {op}")


# ---------------------------- TOKENS ----------------------------
def parse_token(token):
    """'delta5_rsi_13_sft' -> ('delta', 5, 'rsi_13'). None si no es formulaico."""
    name = token[:-4] if token.endswith('_sft') else token
    m = _TOKEN_RE.match(name)
    if not m:
        return None
    return m.group(1), int(m.group(2)), m.group(3)


def is_formulaic(token):
    return parse_token(token) is not None


def formulaic_tokens_in_rules(rules):
    """Extrae el set de tokens formulaicos referenciados por una lista de reglas."""
    found = set()
    for rule in rules:
        for cond in str(rule).split('|'):
            for op_txt in ('>=', '<=', '==', '>', '<'):
                if op_txt in cond:
                    for side in cond.split(op_txt, 1):
                        tok = side.strip()
                        if is_formulaic(tok):
                            found.add(tok)
                    break
    return found


def expand_formulaic(data, col_map, tokens):
    """Agrega a (data, col_map) SOLO las columnas formulaicas pedidas que falten.

    `tokens`: iterable de tokens `{op}{param}_{base}_sft`. Idempotente (ignora
    los ya presentes y los no-formulaicos). Devuelve (data_aug, col_map_aug).
    Lanza KeyError si la columna base de un token no existe.
    """
    cmap = dict(col_map)
    new_cols, new_names = [], []
    for tok in tokens:
        if tok in cmap or tok in new_names:
            continue
        p = parse_token(tok)
        if p is None:
            continue
        op, param, base = p
        base_sft = base + '_sft'
        if base_sft not in cmap:
            raise KeyError(f"token formulaico '{tok}': falta la columna base '{base_sft}'")
        y = compute_operator(op, data[:, cmap[base_sft]], param)
        new_cols.append(y.astype(np.float32))
        new_names.append(tok)
    if not new_cols:
        return data, col_map
    aug = np.column_stack([data] + new_cols)
    base_n = data.shape[1]
    for i, nm in enumerate(new_names):
        cmap[nm] = base_n + i
    return aug, cmap


def formulaic_vocabulary(col_map, bases=BASES, k_windows=K_WINDOWS, w_windows=W_WINDOWS):
    """Todos los tokens formulaicos válidos dadas las columnas base disponibles.

    Una base es válida por cada columna `{base}_<periodo>_sft` presente (close
    usa 'close' como prefijo de 'close_sft'). Devuelve lista de tokens `_sft`.
    """
    # columnas base disponibles por familia
    base_cols = {}
    for name in col_map:
        if not name.endswith('_sft'):
            continue
        stem = name[:-4]                       # ej. 'rsi_13' o 'close'
        fam = stem.split('_')[0]               # 'rsi' / 'close' / ...
        if fam in bases:
            base_cols.setdefault(fam, []).append(stem)
    toks = []
    for fam, stems in base_cols.items():
        for stem in stems:
            for op in ('delta', 'slope'):
                for k in k_windows:
                    toks.append(f"{op}{k}_{stem}_sft")
            for op in ('tsrank', 'distmax', 'distmin'):
                for w in w_windows:
                    toks.append(f"{op}{w}_{stem}_sft")
    return toks
