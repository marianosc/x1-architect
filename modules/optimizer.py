# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.930 - BOLD IA OPTIMIZER (CONSOLIDATED)
# FILE: modules/optimizer.py
# ROL: IA de Selección con Netting Valiente y Visión Híbrida.
# ##########################################################################
import numpy as np
import pandas as pd
from scipy import stats
from modules.x1_engine import simulate

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
def get_strategy_vectors(market_data, col_map, ret_indices, rule_str, exit_label, side, r2, pf,
                         cooldown=24, friction_points=0.0):
    """v106: simulación delegada al Motor Único. La IA ahora ve EXACTAMENTE
    los mismos trades que el minero y el auditor (mismo cooldown) y puede
    componer sobre retornos netos de fricción (antes componía en bruto)."""
    try:
        sim = simulate(market_data, col_map, ret_indices, rule_str, exit_label, side,
                       cooldown=int(cooldown), friction_points=float(friction_points))
        if sim['n_trades'] < 8: return None
        final_vector = sim['vector'].astype(np.float32)
        return {
            'mask': sim['mask'], 'holding_mask': sim['holding_mask'], 'vector': final_vector,
            'health': calculate_internal_health(final_vector, r2, pf),
            'mdd_solo': get_max_drawdown_pct(final_vector)
        }
    except Exception: return None

# -----------------------------------------------------------------------------
# 3. ALGORITMO IA GREEDY (BOLD NETTING)
# -----------------------------------------------------------------------------
def run_greedy_selection(data_pack, strategies_df, max_items=5, max_corr=0.35, max_jac=0.35, max_mdd=3.0,
                         cooldown=24, friction_points=0.0):
    """v106: IA Valiente sobre el Motor Único (cooldown y fricción explícitos)."""
    m_values, c_map, r_indices, m_dates, c_list, m_zones, n_bars = data_pack
    pool = []

    # 1. Preparación de la Élite (Top 400 por Health)
# --- v104.935: DETECCIÓN AUTOMÁTICA DE COLUMNA DE RÁNKING ---
    sort_col = 'Health' if 'Health' in strategies_df.columns else 'Momentum'

    # Ordenamos por la columna detectada (Health o Momentum)
    for idx_s, row_s in strategies_df.sort_values(sort_col, ascending=False).head(400).iterrows():
        alpha = get_strategy_vectors(m_values, c_map, r_indices, row_s['Entry'], row_s['Exit'], row_s['Side'], row_s['R2'], row_s['PF'],
                                     cooldown=cooldown, friction_points=friction_points)
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