# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.920 - MASTER TOURNAMENT AUDITOR
# FILE: L3.py
# ROL: Auditor de Alta Fidelidad con Memoria Retroactiva y Diversidad.
# ESTRUCTURA: Shared Memory Ryzen 9 | Numba JIT | Jaccard Diversification.
# ##########################################################################
import os, sys, pandas as pd, numpy as np, warnings, json, time
from joblib import Parallel, delayed
from scipy import stats
from pathlib import Path
from numba import njit

# Desactivación de ruidos del kernel para el Ryzen 9
warnings.filterwarnings("ignore")
LOCAL_SSD_TEMP = "C:/temp"

# --- BLOQUE 1: MEMORIA COMPARTIDA (GLOBALES) ---
G_DF = None      # Matriz de precios y características
G_RET_1 = None   # Vector de retornos unarios (1 vela)
G_C_MAP = None   # Mapa de nombres de columnas a índices
G_RI_MAP = None  # Mapa de columnas de retorno futuro
G_ZONES = None   # Máscaras de Entrenamiento y OOS
G_CFG = None     # Configuración de la Constitución (fricción, trades)
G_FUSES = None   # Estado de los interruptores de seguridad del Dashboard

# --- BLOQUE 2: MOTORES MATEMÁTICOS TURBO ---

def calculate_ulcer_index_real(returns_vector):
    """Calcula el estrés acumulado de la curva (DD históricos)."""
    if len(returns_vector) < 5: return 99.0
    eq = np.cumsum(returns_vector)
    curve = 100.0 + (eq * 100.0)
    peaks = np.maximum.accumulate(curve)
    dds = (curve - peaks) / (peaks + 1e-9)
    return round(np.sqrt(np.mean(dds**2)) * 100.0, 3)

@njit(cache=True)
def numba_synthetic_engine(entry_indices, ret_1_v, side_mult):
    """Calcula el beneficio de salida lógica sin usar bucles de Python."""
    n = len(entry_indices)
    res = np.zeros(n)
    for i in range(n):
        idx = entry_indices[i]
        profit = 0.0
        # Simulación de Hold dinámico hasta 48 velas
        for b in range(1, 49):
            fut = idx + b
            if fut >= len(ret_1_v): break
            profit += ret_1_v[fut-1] * side_mult
        res[i] = profit
    return res

# -----------------------------------------------------------------------------
# BLOQUE 3: EL VERDUGO (AUDIT_WORKER)
# -----------------------------------------------------------------------------
def audit_worker(s_row):
    """Procesa una sola estrategia aplicando el guantelete de sinceridad."""
    d_f, ret_1, c_map, ri, zones, cfg, fuses = G_DF, G_RET_1, G_C_MAP, G_RI_MAP, G_ZONES, G_CFG, G_FUSES
    
    try:
        rule, side, exit_l, _ = s_row
        side_mult = 1.0 if side == "LONG" else -1.0
        
        # A. GENERACIÓN DE SEÑAL
        mask_e = np.ones(d_f.shape[0], dtype=bool)
        for sub in rule.split('|'):
            p = sub.split()
            v1 = d_f[:, c_map[p[0]]]
            v2 = d_f[:, c_map[p[2]]] if p[2] in c_map else np.float32(p[2])
            if p[1] == '>=': mask_e &= (v1 >= v2)
            elif p[1] == '<=': mask_e &= (v1 <= v2)
        
        idx_e = np.where(mask_e)[0]
        if len(idx_e) < 20: return None, "FAIL_TRADES"

        # B. CÁLCULO DE RETORNOS (HÍBRIDO + FRICCIÓN)
        r_all = np.zeros(d_f.shape[0])
        if exit_l == "SINTETICA_REVERSE":
            r_all[idx_e] = numba_synthetic_engine(idx_e, ret_1, side_mult)
        elif exit_l in ri:
            r_all[idx_e] = d_f[idx_e, ri[exit_l]] * side_mult
        else: return None, "ERR_EXIT"

        # Descuento de fricción normalizado por el precio de entrada
        prices_in = d_f[idx_e, c_map['Close_sft']]
        r_all[idx_e] -= cfg['f_points'] / (prices_in + 1e-9)

        # C. FILTRO DE ESTANCAMIENTO (PEAK-TO-PRESENT)
        eq_global = np.cumsum(r_all)
        peaks = np.maximum.accumulate(eq_global)
        peak_hits = np.where(np.diff(peaks, prepend=-1e-9) > 0)[0]
        
        if len(peak_hits) > 0:
            # Hueco entre picos históricos
            gap_internal = np.max(np.diff(peak_hits)) if len(peak_hits) > 1 else 0
            # Hueco desde el último pico hasta el presente (Sinceridad Total)
            gap_to_now = (len(r_all) - 1) - peak_hits[-1]
            max_stag_real = int(max(gap_internal, gap_to_now))
        else: max_stag_real = len(r_all)

        if fuses.get("anti_gap", True) and max_stag_real > cfg['Stag_Global']:
            return None, "FAIL_GAP"

        # D. FILTROS DE ACTIVIDAD Y RENTABILIDAD
        r_is = r_all[zones['is']][r_all[zones['is']] != 0]
        r_oos = r_all[zones['oos']][r_all[zones['oos']] != 0]

        if len(r_oos) < 2: return None, "FAIL_OOS_EMPTY" # Muerte súbita inactivos
        if len(r_is) < cfg['min_t']: return None, "FAIL_TRADES"
        
        pf_is = np.sum(r_is[r_is > 0]) / (abs(np.sum(r_is[r_is < 0])) + 1e-9)
        if pf_is < cfg['min_pf']: return None, "FAIL_PF_NET"
        
        # El balance final de la vida entera debe ser positivo
        profit_total = np.sum(r_all)
        if profit_total <= 0: return None, "FAIL_NEG_PROFIT"

        # E. CÁLCULO DE SALUD (RANKING HEALTH)
        eq_is_curve = np.cumsum(r_is)
        _, _, r_v, _, _ = stats.linregress(np.arange(len(eq_is_curve)), eq_is_curve)
        r2_real = max(0.0, float(r_v**2))
        
        m_is = np.mean(r_is)
        oer = max(0.0, min((np.mean(r_oos) / m_is) if abs(m_is) > 1e-9 else 0.0, 2.0))
        
        # Puntuación final que integra Beneficio, Estabilidad y Sinceridad
        health = (profit_total * r2_real * (oer + 0.1)) / (np.log10(max_stag_real + 10))

        return [rule, side, exit_l, round(float(pf_is), 3), round(r2_real, 4), max_stag_real, len(r_is), round(float(oer), 4), round(float(profit_total), 4), round(float(health), 4), 100.0], "PASS"
    except: return None, "ERR"

# -----------------------------------------------------------------------------
# BLOQUE 4: MOTOR DE ORQUESTACIÓN (RUN_RADAR)
# -----------------------------------------------------------------------------
def run_radar():
    global G_DF, G_RET_1, G_C_MAP, G_RI_MAP, G_ZONES, G_CFG, G_FUSES
    if len(sys.argv) < 5: return
    sym, tf_l, side, fam = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    
    ROOT = Path(os.getcwd()); COSECHA = ROOT / "COSECHA"; DATA = ROOT / "data"
    raw_p = Path(LOCAL_SSD_TEMP) / f"X1_RAW_{sym}_{side}_{fam}.parquet"
    if not raw_p.exists(): return
    
    # 1. CARGA DE MATRICES
    df_f = pd.read_parquet(Path(LOCAL_SSD_TEMP) / f"X1_FULL_{sym.upper()}_{tf_l.upper()}.parquet")
    G_ZONES = {'is': df_f['Zone']==1, 'oos': df_f['Zone']==2}
    G_RET_1 = (df_f['Close'].shift(-1).values - df_f['Close'].values) / (df_f['Close'].values + 1e-9)
    G_DF = df_f.drop(columns=['DateTime','Zone'], errors='ignore').values.astype(np.float32)
    G_C_MAP = {n: i for i, n in enumerate(df_f.drop(columns=['DateTime','Zone'], errors='ignore').columns)}
    G_RI_MAP = {n: i for i, n in enumerate(df_f.drop(columns=['DateTime','Zone'], errors='ignore').columns) if 'Ret_' in n}

    # 2. CARGA DE CONFIGURACIÓN
    df_a = pd.read_csv(DATA / "assets.csv").dropna(subset=['Symbol'])
    row_a = df_a[df_a['Symbol'].str.contains(str(sym).split('_')[0].upper(), na=False)].iloc[0]
    G_CFG = {"min_t": int(row_a.get('Min_Trades', 300)), "min_pf": float(row_a.get('Min_PF', 1.15)), "f_points": float(row_a.get('Slippage_Cost', 0.1)) + float(row_a.get('Avg_Spread', 0.1)) + float(row_a.get('Broker_Comm', 0.1)), "Stag_Global": int(row_a.get('Stag_Global', 5000))}
    
    try:
        with open(DATA / "audit_config.json", 'r') as f: G_FUSES = json.load(f)
    except: G_FUSES = {"anti_gap": True, "oos_neg_slope": True}

    # 3. RE-AUDITORÍA RETROACTIVA (FUSIÓN DE MEMORIA)
    out_csv = COSECHA / f"MASTER_{sym}_{tf_l}_{side}_{fam}.csv"
    raw_df = pd.read_parquet(raw_p)
    if out_csv.exists():
        try:
            df_old = pd.read_csv(out_csv)[['Entry', 'Side', 'Exit', 'PF']]
            raw_df = pd.concat([df_old, raw_df]).drop_duplicates(subset=['Entry'], keep='last')
            print(f"\033[93m[L3] RE-AUDITORÍA: Procesando {len(df_old)} históricos contra leyes v104.920\033[0m")
        except: pass

    # 4. EJECUCIÓN PARALELA RYZEN 9
    print(f"\033[94m[L3] Auditando {len(raw_df):,} candidatos | Fricción: {G_CFG['f_points']} pts\033[0m")
    out = Parallel(n_jobs=32, backend='loky')(delayed(audit_worker)(row) for row in raw_df.values)

    # 5. CONSOLIDACIÓN DE RESULTADOS (STATS MAP)
    passed_batch = [r for r, s in out if s == "PASS"]
    stats_map = {k: 0 for k in ["FAIL_TRADES", "FAIL_PF_NET", "FAIL_GAP", "FAIL_OOS_EMPTY", "FAIL_NEG_PROFIT", "ERR", "ERR_EXIT", "PASS"]}
    for _, s in out: stats_map[s] = stats_map.get(s, 0) + 1

    # 6. RE-RANKING Y FILTRO JACCARD (DIVERSIDAD)
    if passed_batch:
        df_all = pd.DataFrame(passed_batch, columns=['Entry','Side','Exit','PF','R2','Stag_Active','Trades','OER','UI','Health','Monkey'])
        df_all = df_all.sort_values(by=['Health', 'PF'], ascending=False)
        
        final_elite, seen_tokens = [], []
        for _, row in df_all.iterrows():
            if len(final_elite) >= 500: break
            tks = set(str(row['Entry']).lower().replace('|',' ').replace('_sft','').split())
            if not any((len(tks.intersection(s))/(len(tks.union(s))+1e-9)) > 0.75 for s in seen_tokens):
                final_elite.append(row); seen_tokens.append(tks)
        
        pd.DataFrame(final_elite).to_csv(out_csv, index=False)
        
        # Telemetría para el Commander
        with open(COSECHA / f"AUDIT_{sym}_{side}_{fam}.json", 'w') as fj:
            json.dump({"total": len(raw_df), "qualified": len(passed_batch), "harvested": len(final_elite), "details": stats_map}, fj)

    if raw_p.exists(): raw_p.unlink()
    print(f"\033[92m[L3] CICLO FINALIZADO. Élite de {len(final_elite) if passed_batch else 0} Alphas actualizada.\033[0m")

if __name__ == '__main__': run_radar()