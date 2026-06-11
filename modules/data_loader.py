# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.300 - DATA LOADER (MASTER SINC)
# FILE: modules/data_loader.py
# ROL: Cargador Maestro Local SSD con Blindaje de Reintento y Purga de Clones.
# ##########################################################################
import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import hashlib
import time
from pathlib import Path
from scipy import stats

# -----------------------------------------------------------------------------
# CONFIGURACIÓN DE INFRAESTRUCTURA (RYZEN 9 LOCAL-FIRST)
# -----------------------------------------------------------------------------
TEMP_DIR_LDR = Path("C:/temp")
DATA_DIR_LDR = Path("data")

# Localización absoluta del sistema para evitar colisiones de rutas
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COSECHA_DIR_LDR = Path(BASE_DIR) / "COSECHA"

# Asegurar infraestructura al arranque
if not COSECHA_DIR_LDR.exists():
    os.makedirs(COSECHA_DIR_LDR, exist_ok=True)

def generate_x1_uid(rule_text):
    """Genera firma genética MD5 inmutable de 8 caracteres."""
    if not rule_text: return "00000000"
    normalized_dna = " ".join(str(rule_text).strip().split())
    return hashlib.md5(normalized_dna.encode('utf-8')).hexdigest()[:8].upper()

# -----------------------------------------------------------------------------
# 1. DESCUBRIMIENTO DE ACTIVOS (RETRY SHIELD)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=10)
def get_available_assets():
    """Escaneo resiliente de activos en SSD Local."""
    found_assets = set()
    path_assets_csv = DATA_DIR_LDR / "assets.csv"
    
    # Escudo de reintento: previene errores si el archivo está siendo escrito
    for _ in range(5):
        try:
            if path_assets_csv.exists():
                df_assets = pd.read_csv(path_assets_csv)
                if 'Symbol' in df_assets.columns:
                    symbols = df_assets['Symbol'].dropna().unique()
                    for s in symbols: found_assets.add(str(s).strip().upper())
                break
        except: time.sleep(0.2)

    if TEMP_DIR_LDR.exists():
        for p_file in TEMP_DIR_LDR.glob("X1_FULL_*.parquet"):
            parts = p_file.name.upper().split('_')
            if len(parts) >= 3: found_assets.add(parts[2])

    reserved = ["ASSETS", "MASTER", "TEMP", "BACKUP", "X1", "FULL", "FACTORY", "INYECTOR", "CLEAN", "AUDIT"]
    return sorted([a for a in found_assets if a not in reserved])

# -----------------------------------------------------------------------------
# 2. CARGA DE TELEMETRÍA (JSON AUDIT LOGS)
# -----------------------------------------------------------------------------
@st.cache_data(ttl=2)
def load_audit_stats(symbol_code):
    """Extrae telemetría sincronizada desde la carpeta local COSECHA."""
    clean_sym = symbol_code.split('_')[0].upper()
    audit_files = list(COSECHA_DIR_LDR.glob(f"AUDIT_{clean_sym}*.json"))
    telemetry = []
    
    for f in audit_files:
        try:
            with open(f, 'r') as j:
                data = json.load(j)
                parts = f.stem.split('_') # [AUDIT, SYMBOL, SIDE, FAMILY]
                if len(parts) >= 4:
                    data['side'], data['family'] = parts[2], parts[3]
                    telemetry.append(data)
        except: continue
    return telemetry

# -----------------------------------------------------------------------------
# 3. LÓGICA DE SALUD (MÉTRICA SOBERANA)
# -----------------------------------------------------------------------------
def calculate_quick_momentum(df_row_alpha):
    """Calcula la vitalidad de la estrategia para el Optimizer."""
    try:
        val_r2 = float(df_row_alpha.get('R2', 0))
        val_stag = float(df_row_alpha.get('Stag_Active', 15000))
        val_pf = float(df_row_alpha.get('PF', 1.0))
        # Ley X1: R2 * PF castigado logarítmicamente por el estancamiento
        return round((val_r2 * val_pf) / (np.log10(val_stag + 10)), 4)
    except: return 0.0

# -----------------------------------------------------------------------------
# 4. CARGA DE ESTRATEGIAS (DASHBOARD CORE)
# -----------------------------------------------------------------------------
def load_strategies(symbol_search, timeframe_filter=None):
    """Cargador Único con Purga de Fenotipo e Inyección de Identidad."""
    clean_sym = symbol_search.split('_')[0].upper()
    cols_mandat = ['X1_UID','Side','TimeFrame','Stag_Active','R2','OER','UI','Expectancy','Trades','Family','Entry','Exit','PF','Momentum']
    
    files = list(COSECHA_DIR_LDR.glob(f"MASTER_{clean_sym}*.csv"))
    if not files: return pd.DataFrame(columns=cols_mandat)
        
    accumulator = []
    for f in files:
        if any(x in f.name for x in ["_CLEAN", "INYECTOR"]): continue
        try:
            df_t = pd.read_csv(f)
            if df_t.empty: continue
            
            # Recuperamos Metadatos desde el Nombre del Archivo [MASTER, SYMBOL, TF, SIDE, FAMILY]
            parts = f.stem.split('_')
            df_t['Side'] = parts[3] if len(parts) >= 4 else "UNK"
            df_t['Family'] = parts[4] if len(parts) >= 5 else "MIXED"
            df_t['TimeFrame'] = parts[2] if len(parts) >= 3 else "H1"
            
            # Si no hay columna Exit, es un Alpha de la vieja guardia (Velas fijas)
            if 'Exit' not in df_t.columns:
                df_t['Exit'] = "Ret_24" # Default
            
            if timeframe_filter and str(df_t['TimeFrame'].iloc[0]) != str(timeframe_filter):
                continue
            accumulator.append(df_t)
        except: continue
            
    if not accumulator: return pd.DataFrame(columns=cols_mandat)
    
    # Fusión y Limpieza de Tipos
    df_merged = pd.concat(accumulator, ignore_index=True)
    for col in ['PF', 'R2', 'Trades', 'Stag_Active', 'OER', 'UI']:
        if col in df_merged.columns:
            df_merged[col] = pd.to_numeric(df_merged[col], errors='coerce').fillna(0)
    
    # --- PURGA DE FENOTIPO (Anti-Clones por comportamiento) ---
    df_merged['pf_m'] = df_merged['PF'].round(3)
    df_merged['r2_m'] = df_merged['R2'].round(3)
    df_merged = df_merged.drop_duplicates(subset=['pf_m', 'r2_m', 'Trades', 'Side'], keep='first')
    df_merged = df_merged.drop(columns=['pf_m', 'r2_m'])
    
    # Inyección de Salud y Firma Genética
    df_merged['Momentum'] = df_merged.apply(calculate_quick_momentum, axis=1)
    df_merged['X1_UID'] = df_merged['Entry'].apply(generate_x1_uid)
    
    # Filtrado final de columnas
    available_cols = [c for c in cols_mandat if c in df_merged.columns]
    return df_merged[available_cols].set_index('X1_UID', drop=False)

# -----------------------------------------------------------------------------
# 5. MOTOR DE DATOS DE MERCADO (PARQUET ENGINE RYZEN OPT)
# -----------------------------------------------------------------------------
@st.cache_resource(show_spinner="🚓 Policía de Datos validando integridad Parquet...")
def load_market_data_engine(symbol_query, timeframe_query):
    """Carga ultra-veloz de Parquet desde SSD local con escudo de reintento."""
    filename = f"X1_FULL_{str(symbol_query).upper()}_{str(timeframe_query).upper()}.parquet"
    path_parquet = TEMP_DIR_LDR / filename
    
    if not path_parquet.exists(): return None
        
    for _ in range(5):
        try:
            df = pd.read_parquet(path_parquet)
            if 'DateTime' in df.columns:
                df.index = pd.to_datetime(df['DateTime'])
                df = df.drop(columns=['DateTime'])
            
            z_array = df['Zone'].values.astype(np.int8) if 'Zone' in df.columns else None
            if 'Zone' in df.columns: df = df.drop(columns=['Zone'])
                
            map_cols = {n: i for i, n in enumerate(df.columns)}
            map_rets = {n: i for i, n in enumerate(df.columns) if 'Ret_' in n}
            
            return (df.values.astype(np.float32), map_cols, map_rets, df.index, df.columns.tolist(), z_array, len(df))
        except:
            time.sleep(0.5) # Espera si el archivo está bloqueado por L1
            continue
    return None

# -----------------------------------------------------------------------------
# 6. ANALÍTICA DE PRODUCCIÓN PARA PULSE.PY
# -----------------------------------------------------------------------------
@st.cache_data(ttl=5)
def get_farm_analytics():
    """Consolidador de telemetría para el visor Pulse."""
    audit_files = list(COSECHA_DIR_LDR.glob("AUDIT_*.json"))
    if not audit_files: return pd.DataFrame()
    
    all_stats = []
    for f in audit_files:
        try:
            with open(f, 'r') as file:
                data = json.load(file)
                parts = f.stem.split('_') 
                if len(parts) >= 4:
                    data['symbol'], data['side'], data['family'] = parts[1], parts[2], parts[3]
                    all_stats.append(data)
        except: continue
    return pd.DataFrame(all_stats)