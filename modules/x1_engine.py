# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 106.0 - MOTOR UNICO (FASE 1 SANEAMIENTO)
# FILE: modules/x1_engine.py
# ROL: Fuente única de verdad para señales, salidas y fricción.
#
# ANTES DE ESTE MODULO el intérprete de reglas vivía duplicado en 5 sitios
# (L2, L3, L5, backtest_engine, optimizer) con semánticas divergentes:
#   - L3 auditaba SINTETICA_REVERSE sin la rotura de regla bar-a-bar
#     (acumulaba 48 velas siempre) => auditaba una salida distinta a la minada.
#   - L3 y optimizer no aplicaban cooldown; L2 y app sí.
#   - backtest_engine soportaba >,<,== ; el resto solo >=,<=.
# Este módulo consolida la semántica CORRECTA (la del minero L2) y la expone
# para que todas las capas midan con el mismo metro.
#
# DEPENDENCIAS: numpy (obligatoria). numba OPCIONAL: si está instalada se
# compila JIT (blanca/Ryzen); si no, cae a NumPy/Python puro (notebook).
# ##########################################################################
import numpy as np

# --- NUMBA OPCIONAL (notebook no la tiene; blanca sí) ---
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

# Operadores soportados. El minero L2 solo emite '>=' y '<='; el resto se
# acepta por compatibilidad con reglas manuales (futuro Creador de Estrategias).
_OP_GE, _OP_LE, _OP_GT, _OP_LT, _OP_EQ = 0, 1, 2, 3, 4
_OP_MAP = {'>=': _OP_GE, '<=': _OP_LE, '>': _OP_GT, '<': _OP_LT, '==': _OP_EQ}

SYNTHETIC_EXIT = "SINTETICA_REVERSE"
MAX_HOLD_SYNTH = 48  # velas máximas de la salida sintética (idéntico a L2/L3/optimizer)


# -----------------------------------------------------------------------------
# 1. PARSER DE REGLAS (UNICO EN TODO EL SISTEMA)
# -----------------------------------------------------------------------------
def parse_rule(rule_str, col_map):
    """Convierte 'rsi_14_sft >= 70|ema_55_sft <= Close_sft' en tuplas numéricas.

    Devuelve lista de (col1_idx, op_id, col2_idx, valor):
      - col2_idx = -1 cuando el lado derecho es un literal numérico (en 'valor').
    Lanza ValueError ante regla malformada o columna inexistente: una regla
    ilegible debe FALLAR ruidosamente, no devolver señal vacía en silencio
    (el silencio fue lo que escondió las divergencias durante meses).
    """
    parsed = []
    for cond in str(rule_str).split('|'):
        cond = cond.strip()
        if not cond:
            continue
        # Detección de operador: los de 2 caracteres primero ('>=' antes que '>')
        op_found = None
        for op_txt in ('>=', '<=', '==', '>', '<'):
            if op_txt in cond:
                op_found = op_txt
                break
        if op_found is None:
            raise ValueError(f"Regla sin operador válido: '{cond}'")

        lhs, rhs = (p.strip() for p in cond.split(op_found, 1))
        if lhs not in col_map:
            raise ValueError(f"Columna desconocida en regla: '{lhs}'")
        c1 = col_map[lhs]

        if rhs in col_map:
            c2, val = col_map[rhs], 0.0
        else:
            try:
                c2, val = -1, float(rhs)
            except ValueError:
                raise ValueError(f"Lado derecho ilegible: '{rhs}'")
        parsed.append((c1, _OP_MAP[op_found], c2, np.float32(val)))

    if not parsed:
        raise ValueError(f"Regla vacía: '{rule_str}'")
    return parsed


def _compare(v1, op_id, v2):
    """Comparación vectorizada según op_id."""
    if op_id == _OP_GE: return v1 >= v2
    if op_id == _OP_LE: return v1 <= v2
    if op_id == _OP_GT: return v1 > v2
    if op_id == _OP_LT: return v1 < v2
    return v1 == v2


def signal_mask(data, rule, col_map=None):
    """Máscara booleana de entrada para una regla (string o ya parseada).

    `data` es la matriz float32 (filas=velas, columnas según col_map).
    """
    parsed = parse_rule(rule, col_map) if isinstance(rule, str) else rule
    mask = np.ones(data.shape[0], dtype=bool)
    for c1, op_id, c2, val in parsed:
        rhs = data[:, c2] if c2 != -1 else val
        mask &= _compare(data[:, c1], op_id, rhs)
    return mask


# -----------------------------------------------------------------------------
# 2. COOLDOWN (FILTRO TEMPORAL DE ENTRADAS)
# -----------------------------------------------------------------------------
@njit(cache=True)
def apply_cooldown(mask, cooldown):
    """Mantiene una entrada solo si pasaron >= cooldown velas desde la anterior.

    Semántica idéntica a L2.numba_apply_time_filter y backtest_engine.apply_time_filter.
    cooldown <= 0 devuelve la máscara intacta.
    """
    if cooldown <= 0:
        return mask.copy()
    clean = np.zeros(mask.shape[0], dtype=np.bool_)
    last = -cooldown - 1
    for i in range(mask.shape[0]):
        if mask[i] and i >= last + cooldown:
            clean[i] = True
            last = i
    return clean


# -----------------------------------------------------------------------------
# 3. SALIDA SINTETICA (LA SEMANTICA CORRECTA: ROTURA DE REGLA BAR-A-BAR)
# -----------------------------------------------------------------------------
@njit(cache=True)
def _synthetic_core(data, entries, ret_1, side_mult, c1s, ops, c2s, vals, max_hold):
    """Por cada entrada acumula ret_1 mientras la regla siga viva (máx max_hold).

    Réplica exacta del bucle de L2.engine / optimizer.get_strategy_vectors:
    el retorno de la vela b se devenga ANTES de comprobar la regla en idx+b;
    si la regla se rompe ahí, el trade cierra incluyendo esa vela.
    Devuelve (profits, durations) alineados con `entries`.
    """
    n_rows = data.shape[0]
    n_conds = len(c1s)
    profits = np.zeros(len(entries))
    durations = np.zeros(len(entries), dtype=np.int64)

    for k in range(len(entries)):
        idx = entries[k]
        p_acum = 0.0
        dur = 0
        for b in range(1, max_hold + 1):
            fut = idx + b
            if fut >= n_rows:
                break
            p_acum += ret_1[fut - 1] * side_mult
            dur = b
            valid = True
            for c in range(n_conds):
                v1 = data[fut, c1s[c]]
                v2 = data[fut, c2s[c]] if c2s[c] != -1 else vals[c]
                op = ops[c]
                if op == 0:
                    if not (v1 >= v2): valid = False
                elif op == 1:
                    if not (v1 <= v2): valid = False
                elif op == 2:
                    if not (v1 > v2): valid = False
                elif op == 3:
                    if not (v1 < v2): valid = False
                else:
                    if not (v1 == v2): valid = False
                if not valid:
                    break
            if not valid:
                break
        profits[k] = p_acum
        durations[k] = dur
    return profits, durations


def synthetic_exit(data, entries, parsed_rule, ret_1, side_mult, max_hold=MAX_HOLD_SYNTH):
    """Wrapper que desempaqueta la regla parseada en arrays planos para numba."""
    c1s = np.array([p[0] for p in parsed_rule], dtype=np.int64)
    ops = np.array([p[1] for p in parsed_rule], dtype=np.int64)
    c2s = np.array([p[2] for p in parsed_rule], dtype=np.int64)
    vals = np.array([p[3] for p in parsed_rule], dtype=np.float32)
    return _synthetic_core(data, entries.astype(np.int64), ret_1, side_mult,
                           c1s, ops, c2s, vals, max_hold)


@njit(cache=True)
def _synthetic_single_core(data, mask, ret_1, side_mult, c1s, ops, c2s, vals,
                           max_hold, cooldown):
    """Caminata busy-until de POSICION UNICA para la salida sintética.

    v107 (opción B aprobada): una entrada aceptada bloquea nuevas entradas
    hasta su cierre REAL (duración dinámica por rotura de regla). La vela de
    cierre también consume la oportunidad (el EA hace `return` tras
    PositionClose), así que la siguiente entrada es >= cierre + 1 y además
    respeta el cooldown desde la última entrada.
    """
    n_rows = data.shape[0]
    n_conds = len(c1s)
    entries_buf = np.empty(n_rows, dtype=np.int64)
    profits_buf = np.empty(n_rows, dtype=np.float64)
    dur_buf = np.empty(n_rows, dtype=np.int64)
    k = 0
    busy_until = -1
    last_entry = -cooldown - 1
    for i in range(n_rows):
        if i <= busy_until or not mask[i]:
            continue
        if i - last_entry < cooldown:
            continue
        p_acum = 0.0
        dur = 0
        for b in range(1, max_hold + 1):
            fut = i + b
            if fut >= n_rows:
                break
            p_acum += ret_1[fut - 1] * side_mult
            dur = b
            valid = True
            for c in range(n_conds):
                v1 = data[fut, c1s[c]]
                v2 = data[fut, c2s[c]] if c2s[c] != -1 else vals[c]
                op = ops[c]
                if op == 0:
                    if not (v1 >= v2): valid = False
                elif op == 1:
                    if not (v1 <= v2): valid = False
                elif op == 2:
                    if not (v1 > v2): valid = False
                elif op == 3:
                    if not (v1 < v2): valid = False
                else:
                    if not (v1 == v2): valid = False
                if not valid:
                    break
            if not valid:
                break
        entries_buf[k] = i
        profits_buf[k] = p_acum
        dur_buf[k] = dur
        k += 1
        busy_until = i + dur
        last_entry = i
    return entries_buf[:k], profits_buf[:k], dur_buf[:k]


def synthetic_exit_single(data, mask, parsed_rule, ret_1, side_mult, cooldown,
                          max_hold=MAX_HOLD_SYNTH):
    """Sintética de posición única sobre la máscara CRUDA (sin cooldown previo).

    Devuelve (entries, profits, durations) de las entradas ACEPTADAS por la
    caminata busy-until. Es la semántica del EA real (una posición por vez).
    """
    c1s = np.array([p[0] for p in parsed_rule], dtype=np.int64)
    ops = np.array([p[1] for p in parsed_rule], dtype=np.int64)
    c2s = np.array([p[2] for p in parsed_rule], dtype=np.int64)
    vals = np.array([p[3] for p in parsed_rule], dtype=np.float32)
    return _synthetic_single_core(data, mask, ret_1, side_mult,
                                  c1s, ops, c2s, vals, max_hold, int(cooldown))


# -----------------------------------------------------------------------------
# 4. SIMULADOR UNICO (LO QUE TODAS LAS CAPAS DEBEN LLAMAR)
# -----------------------------------------------------------------------------
def simulate(data, col_map, ret_indices, entry_rule, exit_label, side,
             cooldown=0, friction_points=0.0, max_hold=MAX_HOLD_SYNTH,
             close_sft_col='Close_sft', single_position=True):
    """Simula una estrategia completa y devuelve sus vectores canónicos.

    Convenciones (idénticas en minado, auditoría, optimizer y dashboard):
      - El beneficio de cada trade se imputa a la VELA DE ENTRADA (vector[idx]).
      - La fricción se descuenta por trade: friction_points / Close_sft[entrada].
      - side: 'LONG' (+1) o 'SHORT' (-1).
      - exit_label: 'Ret_N' (salida fija a N velas) o SYNTHETIC_EXIT.
      - cooldown: velas mínimas entre entradas (0 = sin filtro). DEBE ser el
        mismo valor en todas las capas; la divergencia histórica L2(24)/L3(0)
        hacía que el auditor midiera otro conjunto de trades.
      - single_position (v107, DEFAULT True — opción B aprobada por Mariano):
        UNA posición por vez, la semántica del EA real. Antes el motor
        imputaba Ret_N en cada entrada con solo el cooldown de espaciado:
        con N > cooldown eso simula una cartera PIRAMIDADA inejecutable, y
        el monkey (busyUntil) no puede replicarla — el experimento A2.5
        (2026-06-12) mostró que el p-value OOS escalaba con el solape
        (Ret_12: 10% de paso = azar; Ret_96: 94% = apalancamiento).
        * Fijas Ret_N: equivale EXACTO a espaciado >= max(cooldown, N+1)
          (la vela de cierre consume la oportunidad: el EA hace `return`
          tras PositionClose; verificado en la calibración del canario,
          donde Ret_24 + cooldown 25 da espaciado 25, idéntico a MT5).
        * Sintética: caminata busy-until con duración dinámica
          (_synthetic_single_core).
        single_position=False conserva la semántica vieja (investigación /
        regresión / comparación con cosechas históricas).

    Devuelve dict:
      mask          : entradas efectivas (bool, n_velas)
      vector        : retorno neto por vela de entrada (float64, n_velas)
      holding_mask  : velas con posición abierta (bool) — para Jaccard
      durations     : duración por trade (solo sintética; fijas = N constante)
      n_trades      : entradas efectivas
    """
    n_rows = data.shape[0]
    side_mult = 1.0 if str(side).upper() == 'LONG' else -1.0

    parsed = parse_rule(entry_rule, col_map)
    mask_raw = signal_mask(data, parsed)

    vector = np.zeros(n_rows, dtype=np.float64)
    holding = np.zeros(n_rows, dtype=bool)

    if exit_label == SYNTHETIC_EXIT:
        close = data[:, col_map['Close']].astype(np.float64)
        # ret_1[i] = retorno de close[i] a close[i+1] (última vela queda 0)
        ret_1 = np.zeros(n_rows, dtype=np.float64)
        ret_1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
        if single_position:
            entries, profits, durations = synthetic_exit_single(
                data, mask_raw, parsed, ret_1, side_mult, int(cooldown), max_hold)
            mask = np.zeros(n_rows, dtype=bool)
            mask[entries] = True
        else:
            mask = apply_cooldown(mask_raw, int(cooldown))
            entries = np.where(mask)[0]
            profits, durations = (synthetic_exit(data, entries, parsed, ret_1,
                                                 side_mult, max_hold)
                                  if len(entries) else (np.zeros(0), np.zeros(0, dtype=np.int64)))
        if len(entries) == 0:
            return {'mask': mask, 'vector': vector, 'holding_mask': holding,
                    'durations': np.zeros(0, dtype=np.int64), 'n_trades': 0}
        vector[entries] = profits
        for k, idx in enumerate(entries):
            holding[idx: idx + durations[k] + 1] = True
    else:
        if exit_label not in ret_indices:
            raise ValueError(f"Salida desconocida: '{exit_label}'")
        bars = int(str(exit_label).split('_')[1]) if '_' in str(exit_label) else 24
        spacing = max(int(cooldown), bars + 1) if single_position else int(cooldown)
        mask = apply_cooldown(mask_raw, spacing)
        entries = np.where(mask)[0]
        if len(entries) == 0:
            return {'mask': mask, 'vector': vector, 'holding_mask': holding,
                    'durations': np.zeros(0, dtype=np.int64), 'n_trades': 0}
        vector[entries] = data[entries, ret_indices[exit_label]] * side_mult
        durations = np.full(len(entries), bars, dtype=np.int64)
        for idx in entries:
            holding[idx: min(idx + bars, n_rows)] = True

    # Fricción normalizada por precio de entrada (convención L3/app)
    if friction_points and friction_points > 0:
        prices_in = data[entries, col_map[close_sft_col]].astype(np.float64)
        vector[entries] -= friction_points / (prices_in + 1e-9)

    return {'mask': mask, 'vector': vector, 'holding_mask': holding,
            'durations': durations, 'n_trades': int(len(entries))}


# -----------------------------------------------------------------------------
# 5. METRICAS BASICAS SOBRE EL VECTOR CANONICO
# -----------------------------------------------------------------------------
def profit_factor(trade_returns):
    """PF sobre retornos por trade (ya netos de fricción)."""
    r = np.asarray(trade_returns, dtype=np.float64)
    r = r[r != 0]
    if r.size == 0:
        return 0.0
    pos = r[r > 0].sum()
    neg = abs(r[r < 0].sum())
    return float(pos / (neg + 1e-9))


def max_drawdown_pct(returns_vector):
    """DD porcentual máximo sobre base monetaria 100 (idéntico a optimizer)."""
    r = np.asarray(returns_vector, dtype=np.float64)
    if r.size == 0:
        return 0.0
    curve = 100.0 + np.cumsum(r) * 100.0
    peaks = np.maximum.accumulate(curve)
    dd = (curve - peaks) / (peaks + 1e-9)
    return float(abs(dd.min()) * 100.0)
