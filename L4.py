# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 100.62 - STANDALONE BRIDGE (FULL ENGINE)
# FILE: L4.py
# ##########################################################################
import pandas as pd
import glob
import os
import re
import sys

# Definimos la ubicación de la cosecha
current_dir = os.getcwd()
CLOUD_BASE = os.path.join(current_dir, "COSECHA")

def log(msg, color="\033[96m"): 
    print(color + "[L4] " + str(msg) + "\033[0m")
    sys.stdout.flush()

# -----------------------------------------------------------------------------
# MOTOR DE TRADUCCIÓN STANDALONE (AUDITADO)
# -----------------------------------------------------------------------------
def translate_to_sqx_standalone(rule_str):
    """
    Motor de transpilación lógica. 
    Convierte la sintaxis de minería Python en sintaxis de bloque para AlgoWizard.
    """
    try:
        # Separamos las condiciones unidas por el PIPE '|'
        parts = rule_str.split('|')
        logic_res = []
        
        for p in parts:
            items = p.split()
            if len(items) < 3: 
                continue
            
            # Limpiamos los tokens (nombres de columnas y operadores)
            # Removemos '_sft' que es nuestro indicador de shift(1)
            left_raw = items[0].lower().replace('_sft', '')
            operator = items[1]
            right_raw = items[2].lower().replace('_sft', '')
            
            # Extraer el periodo numérico (ej: rsi_14 -> 14)
            # Lo hacemos con regex fuera de f-strings para compatibilidad total
            nums = re.findall(r'\d+', left_raw)
            period = nums[0] if nums else "14"
            
            # --- DICCIONARIO DE TRADUCCIÓN DE INDICADORES ---
            if 'rsi' in left_raw: 
                left_sqx = "RSI(Close, " + period + ")[1]"
            elif 'mfi' in left_raw: 
                left_sqx = "MoneyFlowIndex(" + period + ")[1]"
            elif 'cci' in left_raw: 
                left_sqx = "CCI(" + period + ")[1]"
            elif 'bbw' in left_raw: 
                left_sqx = "BBWidth(Close, " + period + ", 2.0)[1]"
            elif 'bbp' in left_raw: 
                left_sqx = "BBPercent(Close, " + period + ", 2.0)[1]"
            elif 'ema' in left_raw: 
                left_sqx = "EMA(Close, " + period + ")[1]"
            elif 'adx' in left_raw: 
                left_sqx = "ADX(" + period + ")[1]"
            elif 'willr' in left_raw: 
                left_sqx = "WilliamsPercentR(" + period + ")[1]"
            elif 'aroon' in left_raw:
                left_sqx = "AroonOscillator(" + period + ")[1]"
            elif 'stoch' in left_raw: 
                left_sqx = "StochK(" + period + ", 3, 3)[1]"
            elif 'cmo' in left_raw:
                left_sqx = "CMO(Close, " + period + ")[1]"
            elif 'roc' in left_raw:
                left_sqx = "ROC(Close, " + period + ")[1]"
            elif 'close' in left_raw: 
                left_sqx = "Close[1]"
            else: 
                left_sqx = left_raw
            
            # --- TRADUCCIÓN DEL LADO DERECHO ---
            if 'ema' in right_raw:
                nums_r = re.findall(r'\d+', right_raw)
                period_r = nums_r[0] if nums_r else "100"
                right_sqx = "EMA(Close, " + period_r + ")[1]"
            elif 'close' in right_raw:
                right_sqx = "Close[1]"
            else:
                right_sqx = right_raw
            
            # Construimos el bloque lógico individual
            logic_res.append("(" + left_sqx + " " + operator + " " + right_sqx + ")")
            
        # Unimos todo con el operador AND de SQX
        return " AND ".join(logic_res)

    except Exception as e:
        return "ERROR_IN_TRANSLATION: " + str(e)

# -----------------------------------------------------------------------------
# PROCESADOR DE ARCHIVOS (BRIDGE EXECUTION)
# -----------------------------------------------------------------------------
def run_bridge():
    log("Iniciando generación de inyectores masivos...")
    
    # Buscamos todos los archivos MASTER unificados (CLEAN)
    # Ejemplo: MASTER_XAUUSD_H1_CLEAN.csv
    pattern = os.path.join(CLOUD_BASE, "MASTER_*_CLEAN.csv")
    files = glob.glob(pattern)
    
    if not files:
        # Si no hay CLEAN, buscamos los masters de silos individuales como fallback
        log("No se encontraron archivos CLEAN. Buscando Masters de Silos...", "\033[93m")
        pattern = os.path.join(CLOUD_BASE, "MASTER_*.csv")
        files = [f for f in glob.glob(pattern) if "_CLEAN" not in f and "INYECTOR" not in f]

    if not files:
        log("No se encontraron archivos válidos en COSECHA para exportar.", "\033[91m")
        return

    for f_path in files:
        try:
            # Cargamos el archivo de diamantes
            df = pd.read_csv(f_path)
            if df.empty:
                continue
                
            asset_label = os.path.basename(f_path).replace('.csv', '')
            output_path = os.path.join(CLOUD_BASE, "INYECTOR_" + asset_label + ".txt")
            
            # Sincronización de Columnas (Aseguramos que existan R2 y PF)
            # Ordenamos por estabilidad R2 para poner los mejores arriba en el TXT
            sort_col = 'R2' if 'R2' in df.columns else df.columns[3]
            df = df.sort_values(sort_col, ascending=False)
            
            # Columnas de telemetría (Sincronizadas con L3 V100.62)
            mc_col = 'MC_Ratio' if 'MC_Ratio' in df.columns else 'MC'
            stag_col = 'Max_Stagnation' if 'Max_Stagnation' in df.columns else 'Stag'
            
            with open(output_path, 'w') as f_out:
                f_out.write("##########################################################################\n")
                f_out.write(" X1-ARCHITECT SQX INJECTOR | VERSION: 100.62 | ASSET: " + asset_label + "\n")
                f_out.write("##########################################################################\n\n")
                
                for i, row in df.iterrows():
                    # Traducir la regla a pseudocódigo
                    sqx_logic = translate_to_sqx_standalone(str(row['Entry']))
                    
                    if "ERROR" in sqx_logic: 
                        continue
                    
                    # Extraer métricas de la fila
                    val_pf = row['PF'] if 'PF' in df.columns else "N/A"
                    val_r2 = row['R2'] if 'R2' in df.columns else "N/A"
                    val_mc = row[mc_col] if mc_col in df.columns else "N/A"
                    val_stag = row[stag_col] if stag_col in df.columns else "N/A"
                    
                    # Escribir bloque de estrategia
                    f_out.write("RANK: " + str(i) + " | R2: " + str(val_r2) + " | PF: " + str(val_pf) + " | MC: " + str(val_mc) + "\n")
                    f_out.write("STAGNATION: " + str(val_stag) + " bars\n")
                    f_out.write("ENTRY LOGIC:\n")
                    f_out.write(sqx_logic + "\n")
                    f_out.write("EXIT RULE: " + str(row['Exit']).replace('Ret_', 'Close trade after ') + " candles\n")
                    f_out.write("-" * 80 + "\n")
            
            log("ÉXITO: Generado INYECTOR_" + asset_label + ".txt", "\033[92m")
            
        except Exception as e:
            log("ERROR procesando " + f_path + ": " + str(e), "\033[91m")

if __name__ == "__main__":
    try:
        run_bridge()
    except KeyboardInterrupt:
        log("Proceso cancelado por el usuario.")