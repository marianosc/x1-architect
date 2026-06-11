# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.930 - BOLD IA OPTIMIZER (CONSOLIDATED)
# FILE: modules/optimizer.py
# ROL: IA de Selección con Netting Valiente y Visión Híbrida.
# ##########################################################################
import numpy as np
import pandas as pd
from scipy import stats
from modules.backtest_engine import fast_signal_generator

# -----------------------------------------------------------------------------
# 1. ANALÍTICA DE RIESGO Y SALUD
# -----------------------------------------------------------------------------
def get_max_drawdown_pct(returns_vector):
    """Calcula el DD porcentual exacto sobre base monetaria 100."""
    if len(returns_vector) == 0: return 0.0
    acc_equity = np.cumsum(returns_vector)
    monetary_curve = 100.0 + (acc_equity * 100.0)
    peaks = np.maximum.accumulate(monetary_curve)
    dd_series = (monetary_curve - peaks) / (peaks + 1e-9)
    return abs(np.min(dd_series)) * 100

def get_safe_correlation(vec1, vec2):
    """Mide la confluencia de Drawdowns (Pearson Anti-NaN)."""
    try:
        e1, e2 = np.cumsum(vec1), np.cumsum(vec2)
        dd1, dd2 = e1 - np.maximum.accumulate(e1), e2 - np.maximum.accumulate(e2)
        if np.std(dd1) < 1e-9 or np.std(dd2) < 1e-9: return 0.0
        corr = np.corrcoef(dd1, dd2)[0, 1]
        return round(corr, 4) if not np.isnan(corr) else 0.0
    except: return 0.0

def calculate_internal_health(vector_returns, r2_base, pf_base):
    """Calcula la vitalidad basada en estabilidad y estancamiento reciente."""
    active_rets = vector_returns[vector_returns != 0]
    if len(active_rets) < 12: return 0.0001
    eq = np.cumsum(active_rets)
    last_peak = np.maximum.accumulate(eq)[-1]
    stagnation = 0
    for j in range(len(eq)-1, -1, -1):
        if eq[j] < last_peak: stagnation += 1
        else: break
    # Vitalidad = (Estabilidad IS) / Penalización Logarítmica del Silencio
    return round((r2_base * pf_base) / (np.log10(stagnation + 10)), 4)

# -----------------------------------------------------------------------------
# 2. GENERADOR DE VECTORES HÍBRIDO (CURA DE CEGUERA IA)
# -----------------------------------------------------------------------------
def get_strategy_vectors(market_data, col_map, ret_indices, rule_str, exit_label, side, r2, pf):
    """Simula el beneficio real sincronizado con L2/L3."""
    try:
        mask_sig = fast_signal_generator(market_data, rule_str, col_map)
        if np.sum(mask_sig) < 8: return None
            
        n_rows, side_mult = market_data.shape[0], (1.0 if side == 'LONG' else -1.0)
        holding_mask, final_vector = np.zeros(n_rows, dtype=bool), np.zeros(n_rows, dtype=np.float32)
        entry_indices = np.where(mask_sig)[0]

        if exit_label == "SINTETICA_REVERSE":
            # --- SIMULACIÓN SINTÉTICA (SINCRO TOTAL) ---
            close = market_data[:, col_map['Close']]
            ret_1_v = (pd.Series(close).shift(-1).values - close) / (close + 1e-9)
            parts = rule_str.split('|')
            for idx in entry_indices:
                profit_acum, duration = 0.0, 0
                for b in range(1, 49):
                    fut = idx + b
                    if fut >= n_rows: break
                    duration, profit_acum = b, profit_acum + (ret_1_v[fut-1] * side_mult)
                    # Rotura de lógica bar-a-bar
                    valid = True
                    for sub in parts:
                        tk = sub.split()
                        v1 = market_data[fut, col_map[tk[0]]]
                        v2 = market_data[fut, col_map[tk[2]]] if tk[2] in col_map else np.float32(tk[2])
                        if (tk[1] == '>=' and v1 < v2) or (tk[1] == '<=' and v1 > v2):
                            valid = False; break
                    if not valid: break
                final_vector[idx], holding_mask[idx : idx + duration + 1] = profit_acum, True
        else:
            # --- SALIDA TRADICIONAL POR TIEMPO ---
            if exit_label not in ret_indices: return None
            bars = int(exit_label.split('_')[1]) if '_' in exit_label else 24
            final_vector[mask_sig] = market_data[mask_sig, ret_indices[exit_label]] * side_mult
            for idx in entry_indices: holding_mask[idx : min(idx + bars, n_rows)] = True

        return {
            'mask': mask_sig, 'holding_mask': holding_mask, 'vector': final_vector, 
            'health': calculate_internal_health(final_vector, r2, pf),
            'mdd_solo': get_max_drawdown_pct(final_vector)
        }
    except: return None

# -----------------------------------------------------------------------------
# 3. ALGORITMO IA GREEDY (BOLD NETTING)
# -----------------------------------------------------------------------------
def run_greedy_selection(data_pack, strategies_df, max_items=5, max_corr=0.35, max_jac=0.35, max_mdd=3.0):
    """v104.930: IA Valiente. El Netting es el único juez del equipo."""
    m_values, c_map, r_indices, m_dates, c_list, m_zones, n_bars = data_pack
    pool = []
    
    # 1. Preparación de la Élite (Top 400 por Health)
# --- v104.935: DETECCIÓN AUTOMÁTICA DE COLUMNA DE RÁNKING ---
    sort_col = 'Health' if 'Health' in strategies_df.columns else 'Momentum'
    
    # Ordenamos por la columna detectada (Health o Momentum)
    for idx_s, row_s in strategies_df.sort_values(sort_col, ascending=False).head(400).iterrows():
        alpha = get_strategy_vectors(m_values, c_map, r_indices, row_s['Entry'], row_s['Exit'], row_s['Side'], row_s['R2'], row_s['PF'])
        if alpha: pool.append({'id': idx_s, 'data': row_s, **alpha})

    if not pool: return []
    best_overall_team, max_team_fitness = [], -np.inf

    # 2. BÚSQUEDA POR SEMILLAS (100 Intentos de Capitanes)
    for i in range(min(100, len(pool))):
        seed = pool[i]
        # RELAJACIÓN v104.930: Un bot de 20% DD puede ser el capitán si el equipo lo cura.
        if seed['mdd_solo'] > 25.0: continue 
        
        current_team, acc_rets = [seed], seed['vector'].copy()
        
        for partner in pool:
            if len(current_team) >= max_items: break
            if any(m['id'] == partner['id'] for m in current_team): continue
            
            # --- FILTRO 1: DIVERSIDAD (Jaccard + Pearson) ---
            if any((np.logical_and(partner['holding_mask'], m['holding_mask']).sum() / (np.logical_or(partner['holding_mask'], m['holding_mask']).sum() + 1e-9)) > max_jac or abs(get_safe_correlation(partner['vector'], m['vector'])) > max_corr for m in current_team):
                continue

            # --- FILTRO 2: EL PODER DEL NETTING (1/N) ---
            hypo_team_rets = (acc_rets + partner['vector']) / (len(current_team) + 1)
            # Solo entra si el equipo unido respeta el slider del usuario (ej. 3% o 10%)
            if get_max_drawdown_pct(hypo_team_rets) <= max_mdd:
                current_team.append(partner)
                acc_rets += partner['vector']

        # 3. EVALUACIÓN DE APTITUD (Fitness Score)
        if len(current_team) >= 2:
            final_rets = acc_rets / len(current_team)
            # Fitness = (Profit / DD + Epsilon) * Coeficiente de Cooperación
            fitness = (np.sum(final_rets) / (get_max_drawdown_pct(final_rets) + 0.05)) * len(current_team)
            if fitness > max_team_fitness:
                max_team_fitness, best_overall_team = fitness, current_team

    return [{**c['data'].to_dict(), 'id': c['id'], 'Health': c['health']} for c in best_overall_team]

def get_correlation_matrix(df_p):
    if df_p.empty: return pd.DataFrame()
    id_cols = [c for c in df_p.columns if "ID_" in c]
    if len(id_cols) < 2: return pd.DataFrame()
    df_dd = df_p[id_cols].copy()
    for c in id_cols: df_dd[c] = df_dd[c] - df_dd[c].cummax()
    return df_dd.corr()