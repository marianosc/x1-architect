# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.998 - MQL5 TRANSLATOR (FULL SYNC)
# FILE: modules/translator_mql5.py
# ROL: Traductor de Lógica y Extractor de Handles para MT5.
# ##########################################################################
import re

def translate_to_mql5(rule_str):
    """Traduce reglas X1 a lenguaje C++ de MetaTrader 5."""
    try:
        parts = rule_str.split('|')
        mql5_elements = []
        for p in parts:
            it = p.split()
            if len(it) < 3: continue
            
            left_raw = it[0].lower().replace('_sft', '')
            operator = it[1]
            right_raw = it[2].lower().replace('_sft', '')
            
            nums = re.findall(r'\d+', left_raw)
            period = nums[0] if nums else "14"
            
            # --- MAPEO DE INDICADORES (BUFFER 0, SHIFT 1) ---
            if 'rsi' in left_raw: l_code = f"GetVal(h_rsi_{period}, 0, 1)"
            elif 'ema' in left_raw: l_code = f"GetVal(h_ema_{period}, 0, 1)"
            elif 'linreg' in left_raw: l_code = f"GetVal(h_lr_{period}, 0, 1)"
            elif 'efficiency' in left_raw: l_code = f"GetVal(h_eff_{period}, 0, 1)"
            elif 'vol_z' in left_raw: l_code = f"GetVal(h_vz_{period}, 0, 1)"
            elif 'cci' in left_raw: l_code = f"GetVal(h_cci_{period}, 0, 1)"
            elif 'adx' in left_raw: l_code = f"GetVal(h_adx_{period}, 0, 1)"
            elif 'close' in left_raw: l_code = "iClose(_Symbol, _Period, 1)"
            else: l_code = left_raw
            
            # --- MAPEO DERECHO ---
            if 'ema' in right_raw:
                nums_r = re.findall(r'\d+', right_raw)
                p_r = nums_r[0] if nums_r else "100"
                r_code = f"GetVal(h_ema_{p_r}, 0, 1)"
            elif 'close' in right_raw: r_code = "iClose(_Symbol, _Period, 1)"
            else: r_code = right_raw
                
            mql5_elements.append(f"({l_code} {operator} {r_code})")
        return " && ".join(mql5_elements)
    except Exception as e: return f"/* ERR: {str(e)} */"

def get_required_handles(rule_str):
    """v104.998: Extrae indicadores necesarios para el Dashboard."""
    handles = set()
    # Detectamos patrones como rsi_14, ema_200, linreg_24...
    matches = re.findall(r'(\w+)_(\d+)', rule_str.lower())
    for name, per in matches:
        if name in ['rsi', 'ema', 'linreg', 'efficiency', 'vol_z', 'cci', 'adx']:
            handles.add((name, per))
    return handles

def generate_full_mql5_code(act_id, act_alpha):
    """Genera el código fuente íntegro (.mq5) sincronizado con el Auditor L3."""
    rule = act_alpha['Entry']
    side = act_alpha['Side']
    exit_type = act_alpha['Exit']
    mql5_logic = translate_to_mql5(rule)
    req_handles = get_required_handles(rule)
    
    code = f"""//+------------------------------------------------------------------+
//| X1-ARCHITECT REALITY CHECK | ID: {act_id}
//+------------------------------------------------------------------+
#include <Trade\\Trade.mqh>
CTrade trade;

// Handles de Indicadores
"""
    for name, per in req_handles: code += f"int h_{name}_{per};\n"
    
    code += f"""
int OnInit() {{
"""
    for name, per in req_handles:
        if name == 'rsi': code += f"   h_rsi_{per} = iRSI(_Symbol, _Period, {per}, PRICE_CLOSE);\n"
        elif name == 'ema': code += f"   h_ema_{per} = iMA(_Symbol, _Period, {per}, 0, MODE_EMA, PRICE_CLOSE);\n"
        # Los indicadores personalizados (linreg, etc) requieren el nombre del .ex5 en MQL5
        elif name == 'linreg': code += f"   h_lr_{per} = iCustom(_Symbol, _Period, \"Linear Regression\", {per});\n"
    
    code += f"""   return(INIT_SUCCEEDED);
}}

void OnDeinit(const int reason) {{
   if(MQLInfoInteger(MQL_TESTER)) {{
      int h = FileOpen(\"X1_TRUTH_{act_id}.csv\", FILE_WRITE|FILE_CSV|FILE_COMMON|FILE_ANSI);
      if(h != INVALID_HANDLE) {{
         FileWrite(h, \"Time\", \"Equity\");
         FileWrite(h, TimeToString(TimeCurrent()), AccountInfoDouble(ACCOUNT_EQUITY));
         FileClose(h);
      }}
   }}
}}

void OnTick() {{
   if(PositionsTotal() > 0) {{
"""
    if exit_type == "SINTETICA_REVERSE":
        code += f"      if(!({mql5_logic})) trade.PositionClose(PositionGetTicket(0));\n"
    
    code += f"""      return;
   }}
   if({mql5_logic}) {{
      trade.SetExpertMagicNumber({act_id});
      if(\"{side}\" == \"LONG\") trade.Buy(0.1); else trade.Sell(0.1);
   }}
}}

double GetVal(int handle, int buffer, int shift) {{
   double buf[]; 
   if(CopyBuffer(handle, buffer, shift, 1, buf) > 0) return buf[0];
   return 0;
}}
"""
    return code