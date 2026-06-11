# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 100.62 - SQX TRANSLATOR (STABLE)
# FILE: modules/translator.py
# ##########################################################################
import re

def translate_to_sqx(rule_str):
    """
    Convierte reglas lógicas de nuestro sistema a pseudocódigo de StrategyQuant.
    Soporta traducción de indicadores técnicos, operadores y desplazamientos.
    
    Ejemplo de entrada: "rsi_14_sft <= 30|Close_sft >= ema_200_sft"
    Ejemplo de salida: "(RSI(Close, 14)[1] <= 30) AND (Close[1] >= EMA(Close, 200)[1])"
    """
    try:
        # 1. Separar las condiciones unidas por nuestro PIPE '|' (AND lógico)
        parts = rule_str.split('|')
        res_elements = []
        
        for p in parts:
            it = p.split()
            if len(it) < 3: 
                continue
            
            # 2. Extraer componentes: IZQUIERDA, OPERADOR, DERECHA
            # Limpiamos el sufijo '_sft' que usamos para evitar Look-Ahead bias
            left_raw = it[0].lower().replace('_sft', '')
            operator = it[1]
            right_raw = it[2].lower().replace('_sft', '')
            
            # 3. Extraer el periodo numérico del indicador (ej: rsi_14 -> 14)
            # Se realiza fuera de la f-string para garantizar compatibilidad con versiones de Python < 3.12
            num_list = re.findall(r'\d+', left_raw)
            period = num_list[0] if num_list else "14"
            
            # 4. Mapeo de traducción para el lado IZQUIERDO (Indicadores principales)
            if 'rsi' in left_raw: 
                l_sqx = "RSI(Close, " + period + ")[1]"
            elif 'mfi' in left_raw: 
                l_sqx = "MoneyFlowIndex(" + period + ")[1]"
            elif 'cci' in left_raw: 
                l_sqx = "CCI(" + period + ")[1]"
            elif 'bbw' in left_raw: 
                # Suponemos desviación estándar 2.0 por defecto
                l_sqx = "BBWidth(Close, " + period + ", 2.0)[1]"
            elif 'bbp' in left_raw: 
                l_sqx = "BBPercent(Close, " + period + ", 2.0)[1]"
            elif 'ema' in left_raw: 
                l_sqx = "EMA(Close, " + period + ")[1]"
            elif 'adx' in left_raw: 
                l_sqx = "ADX(" + period + ")[1]"
            elif 'willr' in left_raw: 
                l_sqx = "WilliamsPercentR(" + period + ")[1]"
            elif 'aroon' in left_raw:
                l_sqx = "AroonOscillator(" + period + ")[1]"
            elif 'stoch' in left_raw: 
                # Traducción estándar para la línea K del Estocástico
                l_sqx = "StochK(" + period + ", 3, 3)[1]"
            elif 'close' in left_raw: 
                l_sqx = "Close[1]"
            else: 
                # Si no es un indicador conocido, pasamos el token limpio
                l_sqx = left_raw
            
            # 5. Mapeo de traducción para el lado DERECHO (Comparador)
            if 'ema' in right_raw:
                # Si comparamos contra otra media móvil (ej: Close > EMA)
                num_r_list = re.findall(r'\d+', right_raw)
                period_r = num_r_list[0] if num_r_list else "100"
                r_sqx = "EMA(Close, " + period_r + ")[1]"
            elif 'close' in right_raw:
                r_sqx = "Close[1]"
            else:
                # Si es un valor numérico fijo (ej: 30, 70, 0)
                r_sqx = right_raw
            
            # 6. Ensamblaje de la pieza de lógica individual
            res_elements.append("(" + l_sqx + " " + operator + " " + r_sqx + ")")
            
        # Unimos todas las piezas con el operador AND de SQX
        return " AND ".join(res_elements)

    except Exception as e:
        # En caso de fallo en el parseo, devolvemos un flag de error identificable
        return "ERR_TRANS_LOGIC: " + str(e)

def get_sqx_header(symbol, timeframe):
    """Genera el encabezado informativo para el snippet de SQX."""
    return "--- X1-ARCHITECT SQX EXPORT | " + str(symbol) + " @ " + str(timeframe) + " ---\n"