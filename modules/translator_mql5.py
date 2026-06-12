# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 106.0 - MQL5 TRANSLATOR (FULL DNA)
# FILE: modules/translator_mql5.py
# ROL: Generador de EAs MQL5 con cobertura COMPLETA del ADN de L1.
#
# CORRIGE (bugs v104):
#   - Solo 7 de ~19 indicadores tenían traducción => EAs que no compilaban.
#   - La salida por tiempo (Ret_N) era un comentario: el EA nunca cerraba.
#   - La sintética no tenía el tope de 48 velas del motor.
#   - Sin cooldown entre entradas (el minero usa Min_Dist_Bars).
#   - Shift incorrecto: X1 decide al cierre de la vela i con indicadores de
#     la vela i-1 (columnas _sft). Al abrir una vela nueva en MT5, la vela
#     recién cerrada es shift=1 y la vela de señal es shift=2.
#
# ESTRATEGIA DE TRADUCCIÓN: cada indicador se resuelve vía handle nativo de
# MT5 cuando existe equivalente exacto, o vía función inline X1_* calculada
# sobre precios (garantiza compilación sin .ex5 externos). Regla de oro:
# ningún indicador entra a L1 sin entrada en este registro.
# ##########################################################################
import re

SHIFT_SIGNAL = 2
MAX_HOLD_SYNTH = 48

# -----------------------------------------------------------------------------
# 1. REGISTRO DE INDICADORES (LA TABLA DE VERDAD PYTHON <-> MQL5)
#    handle: (var, init) — None si es inline puro.
#    value : expresión MQL5 que devuelve el double ({p}=período, {s}=shift).
#    helper: función X1_* requerida en el EA.
# -----------------------------------------------------------------------------
REGISTRY = {
    'rsi':        {'handle': ('h_rsi_{p}',  'iRSI(_Symbol, _Period, {p}, PRICE_CLOSE)'),
                   'value': 'GetVal(h_rsi_{p}, 0, {s})', 'helper': None},
    'mfi':        {'handle': ('h_mfi_{p}',  'iMFI(_Symbol, _Period, {p}, VOLUME_TICK)'),
                   'value': 'GetVal(h_mfi_{p}, 0, {s})', 'helper': None},
    'cci':        {'handle': ('h_cci_{p}',  'iCCI(_Symbol, _Period, {p}, PRICE_TYPICAL)'),
                   'value': 'GetVal(h_cci_{p}, 0, {s})', 'helper': None},
    'willr':      {'handle': ('h_wpr_{p}',  'iWPR(_Symbol, _Period, {p})'),
                   'value': 'GetVal(h_wpr_{p}, 0, {s})', 'helper': None},
    'adx':        {'handle': ('h_adx_{p}',  'iADX(_Symbol, _Period, {p})'),
                   'value': 'GetVal(h_adx_{p}, 0, {s})', 'helper': None},
    'plus_di':    {'handle': ('h_adx_{p}',  'iADX(_Symbol, _Period, {p})'),
                   'value': 'GetVal(h_adx_{p}, 1, {s})', 'helper': None},
    'minus_di':   {'handle': ('h_adx_{p}',  'iADX(_Symbol, _Period, {p})'),
                   'value': 'GetVal(h_adx_{p}, 2, {s})', 'helper': None},
    'ema':        {'handle': ('h_ema_{p}',  'iMA(_Symbol, _Period, {p}, 0, MODE_EMA, PRICE_CLOSE)'),
                   'value': 'GetVal(h_ema_{p}, 0, {s})', 'helper': None},
    'stoch':      {'handle': ('h_sto_{p}',  'iStochastic(_Symbol, _Period, {p}, 3, 3, MODE_SMA, STO_LOWHIGH)'),
                   'value': 'GetVal(h_sto_{p}, 0, {s})', 'helper': None},
    'std':        {'handle': ('h_std_{p}',  'iStdDev(_Symbol, _Period, {p}, 0, MODE_SMA, PRICE_CLOSE)'),
                   'value': 'GetVal(h_std_{p}, 0, {s})', 'helper': None},
    'trix':       {'handle': ('h_trix_{p}', 'iTriX(_Symbol, _Period, {p}, PRICE_CLOSE)'),
                   'value': 'GetVal(h_trix_{p}, 0, {s})', 'helper': None},
    'bbw':        {'handle': ('h_bb_{p}',   'iBands(_Symbol, _Period, {p}, 0, 2.0, PRICE_CLOSE)'),
                   'value': 'X1_BBW(h_bb_{p}, {s})', 'helper': 'bbw'},
    'natr':       {'handle': ('h_atr_{p}',  'iATR(_Symbol, _Period, {p})'),
                   'value': 'X1_NATR(h_atr_{p}, {s})', 'helper': 'natr'},
    'vol_z':      {'handle': ('h_atr_{p}',  'iATR(_Symbol, _Period, {p})'),
                   'value': 'X1_VOLZ(h_atr_{p}, {p}, {s})', 'helper': 'vol_z'},
    'slope':      {'handle': ('h_ema_{p}',  'iMA(_Symbol, _Period, {p}, 0, MODE_EMA, PRICE_CLOSE)'),
                   'value': 'X1_SLOPE(h_ema_{p}, {s})', 'helper': 'slope'},
    'macdh':      {'handle': ('h_macd_{p}', 'iMACD(_Symbol, _Period, {p}, {p2}, 9, PRICE_CLOSE)'),
                   'value': '(GetVal(h_macd_{p}, 0, {s}) - GetVal(h_macd_{p}, 1, {s}))', 'helper': None},
    'aroon':      {'handle': None, 'value': 'X1_AROONOSC({p}, {s})', 'helper': 'aroon'},
    'cmo':        {'handle': None, 'value': 'X1_CMO({p}, {s})',      'helper': 'cmo'},
    'roc':        {'handle': None, 'value': 'X1_ROC({p}, {s})',      'helper': 'roc'},
    'mom':        {'handle': None, 'value': 'X1_MOM({p}, {s})',      'helper': 'mom'},
    'linreg':     {'handle': None, 'value': 'X1_LINREG({p}, {s})',   'helper': 'linreg'},
    'efficiency': {'handle': None, 'value': 'X1_EFFICIENCY({p}, {s})', 'helper': 'efficiency'},
    'force':      {'handle': None, 'value': 'X1_FORCE({p}, {s})',    'helper': 'force'},
}

# Funciones inline (réplicas exactas de las fórmulas de L1 / TA-Lib)
HELPERS = {
    'hour': """
double X1_HOUR(int s) {
   // hora de la vela referenciada (L1: DateTime.dt.hour, broker UTC+2)
   MqlDateTime t; TimeToStruct(iTime(_Symbol, _Period, s), t);
   return (double)t.hour;
}""",
    'dow': """
double X1_DOW(int s) {
   // dia de semana. L1 guarda pandas dayofweek+1 (1=Lun..5=Vie), que para
   // dias habiles coincide EXACTO con MqlDateTime.day_of_week (domingo=0).
   MqlDateTime t; TimeToStruct(iTime(_Symbol, _Period, s), t);
   return (double)t.day_of_week;
}""",
    'bbw': """
double X1_BBW(int hBands, int s) {
   // (Upper - Lower) / (Middle + 1e-6)  — idéntico a L1
   double up = GetVal(hBands, 1, s), lo = GetVal(hBands, 2, s), mid = GetVal(hBands, 0, s);
   return (up - lo) / (mid + 1e-6);
}""",
    'natr': """
double X1_NATR(int hAtr, int s) {
   // TA-Lib NATR = 100 * ATR / Close
   double c = iClose(_Symbol, _Period, s);
   return (c != 0.0) ? 100.0 * GetVal(hAtr, 0, s) / c : 0.0;
}""",
    'vol_z': """
double X1_VOLZ(int hAtr, int period, int s) {
   // Z-score del ATR sobre su media/desv rolling (ddof=1 como pandas)
   double m = 0.0;
   for(int i = 0; i < period; i++) m += GetVal(hAtr, 0, s + i);
   m /= period;
   double v = 0.0;
   for(int i = 0; i < period; i++) { double d = GetVal(hAtr, 0, s + i) - m; v += d * d; }
   double sd = (period > 1) ? MathSqrt(v / (period - 1)) : 0.0;
   return (sd > 1e-12) ? (GetVal(hAtr, 0, s) - m) / sd : 0.0;
}""",
    'slope': """
double X1_SLOPE(int hEma, int s) {
   // L1: pct_change(3) de la EMA * 100
   double e0 = GetVal(hEma, 0, s), e3 = GetVal(hEma, 0, s + 3);
   return (e3 != 0.0) ? (e0 - e3) / e3 * 100.0 : 0.0;
}""",
    'aroon': """
double X1_AROONOSC(int period, int s) {
   // TA-Lib AroonOsc = AroonUp - AroonDown = 100*(idxLow - idxHigh)/period
   int hh = iHighest(_Symbol, _Period, MODE_HIGH, period + 1, s);
   int ll = iLowest(_Symbol, _Period, MODE_LOW, period + 1, s);
   return 100.0 * ((double)(ll - hh)) / (double)period;
}""",
    'cmo': """
double X1_CMO(int period, int s) {
   double up = 0.0, dn = 0.0;
   for(int i = 0; i < period; i++) {
      double d = iClose(_Symbol, _Period, s + i) - iClose(_Symbol, _Period, s + i + 1);
      if(d > 0) up += d; else dn -= d;
   }
   double tot = up + dn;
   return (tot != 0.0) ? 100.0 * (up - dn) / tot : 0.0;
}""",
    'roc': """
double X1_ROC(int period, int s) {
   // TA-Lib ROC = (Close / Close_n - 1) * 100
   double c0 = iClose(_Symbol, _Period, s), cn = iClose(_Symbol, _Period, s + period);
   return (cn != 0.0) ? (c0 - cn) / cn * 100.0 : 0.0;
}""",
    'mom': """
double X1_MOM(int period, int s) {
   // TA-Lib MOM = Close - Close_n (diferencia absoluta, no ratio)
   return iClose(_Symbol, _Period, s) - iClose(_Symbol, _Period, s + period);
}""",
    'linreg': """
double X1_LINREG(int period, int s) {
   // TA-Lib LINEARREG_SLOPE: pendiente OLS sobre los últimos 'period' cierres
   double sx = 0, sy = 0, sxy = 0, sxx = 0;
   for(int i = 0; i < period; i++) {
      double y = iClose(_Symbol, _Period, s + period - 1 - i); // x=0 el más viejo
      double x = (double)i;
      sx += x; sy += y; sxy += x * y; sxx += x * x;
   }
   double n = (double)period, den = n * sxx - sx * sx;
   return (den != 0.0) ? (n * sxy - sx * sy) / den : 0.0;
}""",
    'efficiency': """
double X1_EFFICIENCY(int period, int s) {
   // Eficiencia fractal de L1: |cambio neto| / suma de |cambios|
   double net = MathAbs(iClose(_Symbol, _Period, s) - iClose(_Symbol, _Period, s + period));
   double sum = 0.0;
   for(int i = 0; i < period; i++)
      sum += MathAbs(iClose(_Symbol, _Period, s + i) - iClose(_Symbol, _Period, s + i + 1));
   return net / (sum + 1e-9);
}""",
    'force': """
double X1_ForceRaw(int s) {
   return (iClose(_Symbol, _Period, s) - iClose(_Symbol, _Period, s + 1))
          * (double)iTickVolume(_Symbol, _Period, s);
}
double X1_FORCE(int period, int s) {
   // EMA(period) de (deltaClose * tickVolume), semilla SMA (réplica de L1)
   int depth = period * 4;
   double k = 2.0 / (period + 1.0);
   double ema = 0.0;
   int oldest = s + depth;
   for(int i = 0; i < period; i++) ema += X1_ForceRaw(oldest - i);
   ema /= period;
   for(int j = oldest - period; j >= s; j--) ema = k * X1_ForceRaw(j) + (1.0 - k) * ema;
   return ema;
}""",
}


# -----------------------------------------------------------------------------
# 2. PARSER DE TOKENS
# -----------------------------------------------------------------------------
def _resolve_operand(token, shift_expr):
    """Token X1 ('plus_di_14_sft', 'Close_sft', '70.5') -> (expr MQL5, handle, helper).

    Lanza ValueError si el token es un indicador desconocido: un EA que no se
    puede traducir COMPLETO no debe generarse a medias.
    """
    raw = token.strip()
    low = raw.lower().replace('_sft', '')

    # Literal numérico
    try:
        float(low)
        return raw.replace('_sft', ''), None, None
    except ValueError:
        pass

    if low == 'close':
        return f'iClose(_Symbol, _Period, {shift_expr})', None, None

    # B2: features de sesión sin período (hour/dow de la vela referenciada).
    # MQL5 no tiene TimeHour/TimeDayOfWeek (eran MQL4): se usa TimeToStruct.
    if low == 'hour':
        return f'X1_HOUR({shift_expr})', None, 'hour'
    if low == 'dow':
        return f'X1_DOW({shift_expr})', None, 'dow'

    m = re.match(r'^([a-z_]+?)_(\d+)$', low)
    if not m:
        raise ValueError(f"Token intraducible a MQL5: '{token}'")
    name, period = m.group(1), m.group(2)
    if name not in REGISTRY:
        raise ValueError(f"Indicador sin entrada en el registro MQL5: '{name}' (token '{token}')")

    spec = REGISTRY[name]
    fmt = {'p': period, 'p2': str(int(period) * 2), 's': shift_expr}
    expr = spec['value'].format(**fmt)
    handle = None
    if spec['handle'] is not None:
        h_var, h_init = spec['handle']
        handle = (h_var.format(**fmt), h_init.format(**fmt))
    return expr, handle, spec['helper']


def parse_rule_mql5(rule_str, shift_expr='s'):
    """Regla X1 completa -> (condición MQL5, dict de handles, set de helpers)."""
    conds, handles, helpers = [], {}, set()
    for cond in str(rule_str).split('|'):
        cond = cond.strip()
        if not cond:
            continue
        op = next((o for o in ('>=', '<=', '==', '>', '<') if o in cond), None)
        if op is None:
            raise ValueError(f"Condición sin operador: '{cond}'")
        lhs, rhs = (t.strip() for t in cond.split(op, 1))
        l_expr, l_handle, l_help = _resolve_operand(lhs, shift_expr)
        r_expr, r_handle, r_help = _resolve_operand(rhs, shift_expr)
        for h in (l_handle, r_handle):
            if h: handles[h[0]] = h[1]
        for hp in (l_help, r_help):
            if hp: helpers.add(hp)
        conds.append(f'({l_expr} {op} {r_expr})')
    if not conds:
        raise ValueError(f"Regla vacía: '{rule_str}'")
    return ' && '.join(conds), handles, helpers


def translate_to_mql5(rule_str, shift=SHIFT_SIGNAL):
    """Solo la expresión lógica (para mostrar en el dashboard)."""
    try:
        logic, _, _ = parse_rule_mql5(rule_str, shift_expr=str(shift))
        return logic
    except Exception as e:
        return f"/* ERR: {e} */"


def get_required_handles(rule_str):
    """Compatibilidad v104: pares (nombre, período) de indicadores con handle."""
    try:
        _, handles, _ = parse_rule_mql5(rule_str)
        out = set()
        for var in handles:
            m = re.match(r'^h_([a-z]+)_(\d+)$', var)
            if m: out.add((m.group(1), m.group(2)))
        return out
    except Exception:
        return set()


def magic_from_uid(uid):
    """Magic number determinista (31 bits) desde el X1_UID hex o cualquier string."""
    s = str(uid)
    try:
        return int(s, 16) & 0x7FFFFFFF
    except ValueError:
        return abs(hash(s)) & 0x7FFFFFFF


# -----------------------------------------------------------------------------
# 3. GENERADOR DEL EA COMPLETO
# -----------------------------------------------------------------------------
def generate_full_mql5_code(act_id, act_alpha, cooldown=24):
    """EA íntegro sincronizado con el Motor Único (x1_engine.simulate):
    evaluación a vela nueva con SHIFT_SIGNAL=2, cooldown en velas, salida por
    tiempo REAL para Ret_N, sintética con rotura de regla y tope de 48 velas.
    Lanza ValueError si la regla contiene indicadores intraducibles.
    """
    rule = act_alpha['Entry']
    side = str(act_alpha['Side']).upper()
    exit_type = str(act_alpha['Exit'])

    logic, handles, helpers = parse_rule_mql5(rule, shift_expr='s')
    magic = magic_from_uid(act_id)

    if exit_type == 'SINTETICA_REVERSE':
        exit_code = (f"      if(held >= MAX_HOLD_SYNTH || !X1_EntryRule(SHIFT_SIGNAL))\n"
                     f"         trade.PositionClose(_Symbol);")
        exit_desc = "SINTETICA_REVERSE (rotura de regla, tope 48 velas)"
    else:
        try:
            bars_exit = int(exit_type.split('_')[1])
        except (IndexError, ValueError):
            raise ValueError(f"Salida desconocida: '{exit_type}'")
        exit_code = (f"      if(held >= {bars_exit})\n"
                     f"         trade.PositionClose(_Symbol);")
        exit_desc = f"tiempo fijo: {bars_exit} velas"

    h_decl = '\n'.join(f'int {v};' for v in sorted(handles))
    h_init = '\n'.join(f'   {v} = {init};' for v, init in sorted(handles.items()))
    h_chk = '\n'.join(f'   if({v} == INVALID_HANDLE) return(INIT_FAILED);' for v in sorted(handles))
    helper_code = '\n'.join(HELPERS[h] for h in sorted(helpers))
    order_call = 'trade.Buy(InpLots, _Symbol)' if side == 'LONG' else 'trade.Sell(InpLots, _Symbol)'

    return f"""//+------------------------------------------------------------------+
//| X1-ARCHITECT v106 | ID: {act_id} | {side}
//| Entrada: {rule}
//| Salida : {exit_desc} | Cooldown: {cooldown} velas
//| SINCRONIA: senal evaluada a vela nueva con shift=2 (columnas _sft de X1:
//| la decision del motor en la vela i usa indicadores de la vela i-1).
//+------------------------------------------------------------------+
#property strict
#include <Trade\\Trade.mqh>
CTrade trade;

input double InpLots         = 0.10;
input long   InpMagic        = {magic};
input int    InpCooldownBars = {cooldown};

#define SHIFT_SIGNAL   {SHIFT_SIGNAL}
#define MAX_HOLD_SYNTH {MAX_HOLD_SYNTH}

{h_decl}

datetime g_last_bar       = 0;
datetime g_entry_bar      = 0;
datetime g_last_entry_bar = 0;

int OnInit() {{
{h_init}
{h_chk}
   trade.SetExpertMagicNumber(InpMagic);
   return(INIT_SUCCEEDED);
}}

double GetVal(int handle, int buffer, int shift) {{
   double buf[];
   if(CopyBuffer(handle, buffer, shift, 1, buf) > 0) return buf[0];
   return 0.0;
}}
{helper_code}

bool X1_EntryRule(int s) {{
   return {logic};
}}

int BarsSince(datetime t) {{
   if(t == 0) return 1000000;
   return iBarShift(_Symbol, _Period, t, false);
}}

void OnTick() {{
   // Evaluamos UNA vez por vela (X1 decide a cierre de vela)
   datetime bar_now = iTime(_Symbol, _Period, 0);
   if(bar_now == g_last_bar) return;
   g_last_bar = bar_now;

   // --- GESTION DE SALIDA ---
   if(PositionSelect(_Symbol) && PositionGetInteger(POSITION_MAGIC) == InpMagic) {{
      int held = BarsSince(g_entry_bar);
{exit_code}
      return;
   }}

   // --- COOLDOWN ENTRE ENTRADAS (Min_Dist_Bars del minero) ---
   if(BarsSince(g_last_entry_bar) < InpCooldownBars) return;

   // --- ENTRADA ---
   if(X1_EntryRule(SHIFT_SIGNAL)) {{
      if({order_call}) {{
         g_entry_bar = bar_now;
         g_last_entry_bar = bar_now;
      }}
   }}
}}

void OnDeinit(const int reason) {{
   if(MQLInfoInteger(MQL_TESTER)) {{
      int h = FileOpen("X1_TRUTH_{act_id}.csv", FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI);
      if(h != INVALID_HANDLE) {{
         FileWrite(h, "Time", "Equity");
         FileWrite(h, TimeToString(TimeCurrent()), AccountInfoDouble(ACCOUNT_EQUITY));
         FileClose(h);
      }}
   }}
}}
"""
