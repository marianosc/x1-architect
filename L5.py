# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 101.08 - THE SILO UNIFIER (IDENTITY SYNC)
# FILE: L5.py
# ROL: Fusión de silos y eliminación de clones mediante Jaccard.
# FIX: Sincronización de carga de Parquet con identidad de Timeframe.
# AUDITADO: 4 VECES - INTEGRIDAD TOTAL - SIN RESÚMENES.
# ##########################################################################
import pandas as pd
import numpy as np
import os
import glob
import sys
import warnings
from joblib import Parallel, delayed

warnings.filterwarnings("ignore")

# --- CONFIGURACIÓN DE RUTAS ---
LOCAL_TEMP = "C:/temp"
current_dir = os.getcwd()

# Ruta de salida para el Cerebro (Nube/Persistencia)
if "Z:" in current_dir or "Google Drive" in current_dir:
    CLOUD_BASE = os.path.join(current_dir, "COSECHA")
else:
    CLOUD_BASE = os.path.join(current_dir, "COSECHA")

def log(msg, color="\033[94m"): 
    print(f"{color}[L5] {msg}\033[0m")
    sys.stdout.flush()

def get_signal_vector(data, rule, col_map):
    """Transforma una regla lógica en un vector booleano (0/1) para Jaccard."""
    try:
        parts = rule.split('|')
        mask = np.ones(data.shape[0], dtype=bool)
        for sub in parts:
            tokens = sub.split()
            if len(tokens) < 3: continue
            # tokens[0]=Ind1, tokens[1]=Op, tokens[2]=Ind2 o Valor
            c1 = data[:, col_map[tokens[0]]]
            c2 = data[:, col_map[tokens[2]]] if tokens[2] in col_map else np.float32(tokens[2])
            if tokens[1] == '>=': mask &= (c1 >= c2)
            elif tokens[1] == '<=': mask &= (c1 <= c2)
        return mask.astype(np.int8)
    except Exception: 
        return np.zeros(data.shape[0], dtype=np.int8)

def run_cleaner():
    try:
        # v101.08: Exigimos Símbolo y Timeframe
        if len(sys.argv) < 3:
            log("Error: Argumentos insuficientes (Symbol, Timeframe).", "\033[91m")
            return
            
        sym_arg = sys.argv[1].upper()
        tf_arg = sys.argv[2].upper()
        
        log(f"Iniciando Unificación: {sym_arg} @ {tf_arg}")
        
        # 1. CARGA DE MATERIA PRIMA (SINCRONIZADA)
        parquet_name = f"X1_FULL_{sym_arg}_{tf_arg}.parquet"
        parquet_path = os.path.join(LOCAL_TEMP, parquet_name)
        
        if not os.path.exists(parquet_path):
            log(f"FALLO CRÍTICO: No existe {parquet_name} en C:/temp.", "\033[91m")
            return

        df_market = pd.read_parquet(parquet_path)
        # Usamos solo la Zona 1 (Mining) para el cálculo de similitud estructural
        if 'Zone' in df_market.columns:
            df_market = df_market[df_market['Zone'] == 1]
        
        df_market = df_market.drop(columns=['DateTime', 'Zone'], errors='ignore')
        data_np = df_market.values.astype(np.float32)
        col_map = {n: i for i, n in enumerate(df_market.columns)}
        
        # 2. IDENTIFICACIÓN DE SILOS (Filtro por TF)
        # Buscamos MASTER_EURUSD_H1_*.csv
        search_pattern = os.path.join(CLOUD_BASE, f"MASTER_{sym_arg}_{tf_arg}_*.csv")
        master_files = [f for f in glob.glob(search_pattern) if "_CLEAN" not in f and "INYECTOR" not in f]
        
        if not master_files:
            log(f"No se encontraron silos para {sym_arg} @ {tf_arg}.", "\033[93m")
            return
            
        all_silo_alphas = []
        for f_path in master_files:
            try:
                df_silo = pd.read_csv(f_path)
                if not df_silo.empty:
                    # Cuota de Élite: Tomamos los mejores 50 diamantes de cada familia por R2
                    all_silo_alphas.append(df_silo.sort_values('R2', ascending=False).head(50))
            except Exception: continue
        
        if not all_silo_alphas:
            log("Todos los silos están vacíos.", "\033[93m")
            return
        
        # 3. FUSIÓN Y DE-DUPLICACIÓN LÓGICA
        full_pool = pd.concat(all_silo_alphas).drop_duplicates(subset=['Entry']).sort_values('R2', ascending=False)
        log(f"Candidatos únicos pre-limpieza: {len(full_pool)}")
        
        # 4. FILTRADO JACCARD (Eliminación de Clones Estructurales)
        rules_list = full_pool['Entry'].tolist()
        # Generación paralela de vectores de señal
        vectors = Parallel(n_jobs=32, backend='loky')(delayed(get_signal_vector)(data_np, r, col_map) for r in rules_list)
        
        keep_indices = []
        kept_vectors = []
        
        for i in range(len(vectors)):
            v_current = vectors[i]
            is_clone = False
            
            for v_saved in kept_vectors:
                # Índice de Jaccard: Intersección / Unión
                intersection = np.logical_and(v_current, v_saved).sum()
                union = np.logical_or(v_current, v_saved).sum()
                similarity = intersection / union if union > 0 else 0
                
                if similarity > 0.85: # Umbral de tolerancia de clonación
                    is_clone = True
                    break
            
            if not is_clone:
                keep_indices.append(full_pool.index[i])
                kept_vectors.append(v_current)
        
        # 5. GENERACIÓN DE MASTER CLEAN (LA COSECHA FINAL)
        final_clean_df = full_pool.loc[keep_indices]
        output_filename = f"MASTER_{sym_arg}_{tf_arg}_CLEAN.csv"
        final_clean_df.to_csv(os.path.join(CLOUD_BASE, output_filename), index=False)
        
        log(f"ÉXITO: {output_filename} generado con {len(final_clean_df)} diamantes únicos.", "\033[92m")

    except Exception as e: 
        log(f"ERR L5: {e}", "\033[91m")

if __name__ == "__main__": 
    run_cleaner()