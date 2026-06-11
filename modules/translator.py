# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 106.0 - SQX TRANSLATOR (FULL DNA)
# FILE: modules/translator.py
# ROL: Pseudocódigo AlgoWizard/SQX para TODO el ADN de L1 (registro único).
# NOTA: MT5 es el juez de verdad del sistema; este export SQX es material
#       de apoyo. Los indicadores sin bloque nativo SQX se emiten como
#       pseudocódigo X1_* con comentario para recreación manual.
# ##########################################################################
import re

# Plantillas por indicador ({p}=período). [1] = vela cerrada anterior (_sft).
SQX_TEMPLATES = {
    'rsi':        "RSI(Close, {p})[1]",
    'mfi':        "MoneyFlowIndex({p})[1]",
    'cci':        "CCI({p})[1]",
    'willr':      "WilliamsPercentR({p})[1]",
    'adx':        "ADX({p})[1]",
    'aroon':      "AroonOscillator({p})[1]",
    'plus_di':    "ADX_DIPlus({p})[1]",
    'minus_di':   "ADX_DIMinus({p})[1]",
    'ema':        "EMA(Close, {p})[1]",
    'stoch':      "StochK({p}, 3, 3)[1]",
    'std':        "StdDev(Close, {p})[1]",
    'bbw':        "BBWidth(Close, {p}, 2.0)[1]",
    'bbp':        "BBPercent(Close, {p}, 2.0)[1]",
    'cmo':        "CMO(Close, {p})[1]",
    'roc':        "ROC(Close, {p})[1]",
    'mom':        "Momentum(Close, {p})[1]",
    'trix':       "TRIX(Close, {p})[1]",
    'macdh':      "MACDHistogram({p}, {p2}, 9)[1]",
    'natr':       "(ATR({p})[1] / Close[1] * 100)",
    'linreg':     "LinRegSlope(Close, {p})[1]",
    'slope':      "PercentChange(EMA(Close, {p}), 3)[1] /* pendiente EMA x100 */",
    'efficiency': "X1_Efficiency({p})[1] /* |neto|/suma|cambios| - recrear manual */",
    'vol_z':      "X1_VolZ(ATR({p}), {p})[1] /* z-score del ATR - recrear manual */",
    'force':      "ForceIndex({p})[1]",
}


def _sqx_operand(token):
    raw = str(token).strip()
    low = raw.lower().replace('_sft', '')
    try:
        float(low)
        return low
    except ValueError:
        pass
    if low == 'close':
        return "Close[1]"
    m = re.match(r'^([a-z_]+?)_(\d+)$', low)
    if not m:
        return raw  # token desconocido: se pasa limpio
    name, period = m.group(1), m.group(2)
    tpl = SQX_TEMPLATES.get(name)
    if tpl is None:
        return f"X1_{name}({period})[1] /* sin bloque SQX - recrear manual */"
    return tpl.format(p=period, p2=str(int(period) * 2))


def translate_to_sqx(rule_str):
    """Convierte reglas X1 a pseudocódigo de StrategyQuant.

    Ejemplo: "rsi_14_sft <= 30|Close_sft >= ema_200_sft"
          -> "(RSI(Close, 14)[1] <= 30) AND (Close[1] >= EMA(Close, 200)[1])"
    """
    try:
        elements = []
        for cond in str(rule_str).split('|'):
            cond = cond.strip()
            if not cond:
                continue
            op = next((o for o in ('>=', '<=', '==', '>', '<') if o in cond), None)
            if op is None:
                continue
            lhs, rhs = (t.strip() for t in cond.split(op, 1))
            elements.append(f"({_sqx_operand(lhs)} {op} {_sqx_operand(rhs)})")
        return " AND ".join(elements)
    except Exception as e:
        return "ERR_TRANS_LOGIC: " + str(e)


def get_sqx_header(symbol, timeframe):
    """Genera el encabezado informativo para el snippet de SQX."""
    return "--- X1-ARCHITECT SQX EXPORT | " + str(symbol) + " @ " + str(timeframe) + " ---\n"
