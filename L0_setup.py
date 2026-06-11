# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 101.01 - TARGET ANALYZER (DYNAMIC ZONES)
# FILE: L0_setup.py
# ROL: Generador y Sincronizador de assets.csv con soporte de Zonificación.
# ADD: Pct_Hist, Pct_Train, Pct_OOS (Split 25/50/25 por defecto).
# AUDITADO: 4 VECES - INTEGRIDAD TOTAL - SIN RESÚMENES.
# ##########################################################################
import os
import pandas as pd
import glob
import sys
import re

# CONFIGURACIÓN DE RUTAS INSTITUCIONALES
DATA_DIR = "data"

def get_symbol_from_file(filename):
    """Extrae el símbolo limpio del nombre del archivo CSV."""
    try:
        base = os.path.basename(filename).upper()
        # Ignorar archivos internos del sistema X1
        if any(x in base for x in ["MASTER", "ASSETS", "FACTORY", "X1_", "L1", "L2", "L3", "INYECTOR"]):
            return None
        
        # Regex de captura de símbolo (3 a 15 caracteres alfanuméricos)
        match = re.search(r'([A-Z0-9]{3,15})', base)
        if match:
            clean = match.group(1)
            # Filtros de exclusión de palabras reservadas
            if clean in ["MASTER", "AUDIT", "TEST", "DATA", "BACKUP"]: return None
            return clean
        return None
    except Exception:
        return None

def analyze_targets():
    print(f"\n\033[96m[L0] INICIANDO ESCANEO DE ARQUITECTURA (v101.01)...\033[0m")
    
    current_dir = os.getcwd()
    target_data_path = os.path.join(current_dir, DATA_DIR)

    # 1. Validación de Infraestructura de Carpetas
    if not os.path.exists(target_data_path):
        try:
            os.makedirs(target_data_path, exist_ok=True)
            print(f"\033[93m[L0] Carpeta '{DATA_DIR}' creada satisfactoriamente.\033[0m")
        except Exception as e:
            print(f"\033[91m[ERROR CRÍTICO] No se pudo crear la carpeta de datos: {e}\033[0m")
            return
    
    # 2. Búsqueda de Fuentes (Data Sourcing)
    search_pattern = os.path.join(target_data_path, "*.csv")
    csv_files = glob.glob(search_pattern)
    parquet_files = glob.glob("C:/temp/*.parquet")
    
    found_symbols = set()
    
    # Escaneo de archivos físicos
    for f in csv_files:
        sym = get_symbol_from_file(f)
        if sym: found_symbols.add(sym)
            
    # Escaneo de parquets existentes para redundancia
    for f in parquet_files:
        base = os.path.basename(f)
        if "X1_FULL_" in base:
            sym = base.replace("X1_FULL_", "").replace(".parquet", "")
            found_symbols.add(sym)
    
    if not found_symbols:
        print(f"\033[91m[ERROR] No se detectó materia prima (CSV en {DATA_DIR}/). Operación abortada.\033[0m")
        return

# 3. Definición de la Estructura Maestra v102.66 (TCE Edition)
    columns_master = [
        "Symbol", "Min_Trades", "Min_PF", "Min_R2", 
        "Stag_H1", "Stag_M30", "Stag_M15", "Stag_H4", "Stag_Global",
        "Monkey_Train_Min", "Monkey_Test_Min",
        "Slippage_Cost", "Min_Dist_Bars",
        "MC_Reshuffle_Min", "MC_Skip_Min", "Min_OOS_PF",
        "Min_OOS_Efficiency", "Max_Ulcer", "Min_Expectancy",
        "Pct_Hist", "Pct_Train", "Pct_OOS",
        "Min_Exit_Bars", "Max_Exit_Bars", "WFA_Min_PF",
        "Avg_Spread", "Broker_Comm" # <--- NUEVAS VARIABLES DE FRICCIÓN REAL
    ]

    assets_path = os.path.join(target_data_path, "assets.csv")

    if os.path.exists(assets_path):
        print(f"[L0] Auditando y sincronizando assets.csv existente...")
        try:
            df = pd.read_csv(assets_path)
            # Inyección quirúrgica de nuevas columnas sin pérdida de datos de usuario
            for col in columns_master:
                if col not in df.columns:
                    df[col] = None
        except Exception as e:
            print(f"\033[91m[ERROR] El archivo assets.csv está corrupto o bloqueado: {e}\033[0m")
            return
    else:
        print(f"[L0] Generando matriz assets.csv desde cero...")
        df = pd.DataFrame(columns=columns_master)

# 4. VALORES POR DEFECTO v102.66 (Modelo ECN Institucional)
    DEFAULT_CONFIG = {
        "Min_Trades": 300,
        "Min_PF": 1.15,
        "Min_R2": 0.75,
        "Stag_H1": 150,
        "Stag_M30": 200,
        "Stag_M15": 300,
        "Stag_H4": 100,
        "Stag_Global": 15000,
        # v106: umbrales de la metodología Tomillero/Jaume (99% IS / 90% OOS)
        "Monkey_Train_Min": 99,
        "Monkey_Test_Min": 90,
        "Slippage_Cost": 0.1,
        "Min_Dist_Bars": 24,
        "MC_Reshuffle_Min": 1.05,
        "MC_Skip_Min": 1.02,
        "Min_OOS_PF": 1.10,
        "Min_OOS_Efficiency": 0.40,
        "Max_Ulcer": 5.0,
        "Min_Expectancy": 0.0002,
        "Pct_Hist": 25,
        "Pct_Train": 50,
        "Pct_OOS": 25,
        "Min_Exit_Bars": 1,
        "Max_Exit_Bars": 200,
        "WFA_Min_PF": 1.05,
        "Avg_Spread": 0.1,   # 0.2 Pips/Pts de spread medio
        "Broker_Comm": 0.1  # 0.3 Pips/Pts de comisión equivalente
    }

    # 5. Proceso de Actualización de Registros
    rows_updated = 0
    for sym in found_symbols:
        # Caso A: Símbolo Nuevo
        if sym not in df['Symbol'].values:
            new_entry = {"Symbol": sym}
            new_entry.update(DEFAULT_CONFIG)
            df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
            rows_updated += 1
            print(f" + Símbolo registrado: {sym}")
        else:
            # Caso B: Símbolo existente (Rellenar solo campos nuevos)
            idx_map = df[df['Symbol'] == sym].index[0]
            for key, val in DEFAULT_CONFIG.items():
                if key in df.columns:
                    if pd.isna(df.at[idx_map, key]):
                        df.at[idx_map, key] = val
                        rows_updated += 1

    # 6. Persistencia en Disco
    try:
        df.to_csv(assets_path, index=False)
        print(f"\n\033[92m[L0] ÉXITO: Sincronización v101.01 completada.")
        print(f"[L0] Assets actualizados: {len(df['Symbol'].unique())}")
        print(f"[L0] Cambios realizados en celdas: {rows_updated}\033[0m")
    except Exception as e:
        print(f"\033[91m[ERROR] No se pudo escribir el archivo: {e}\033[0m")

if __name__ == "__main__":
    analyze_targets()