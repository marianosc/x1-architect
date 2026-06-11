# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 106.0 - BACKTEST ENGINE (MOTOR UNICO)
# FILE: modules/backtest_engine.py
# ROL: Métricas de riesgo + adaptador del dashboard sobre el Motor Único.
# UPD v106: señal, cooldown y simulación delegadas a x1_engine. Se conservan
#           las firmas públicas (fast_signal_generator, apply_time_filter,
#           X1_Compute_Engine) para no romper app.py/optimizer/L5.
# ##########################################################################
import numpy as np
import pandas as pd

from modules.x1_engine import signal_mask, apply_cooldown, simulate

# -----------------------------------------------------------------------------
# 1. GENERADOR DE SEÑALES (WRAPPER LEGACY SOBRE EL MOTOR ÚNICO)
# -----------------------------------------------------------------------------
def fast_signal_generator(data_np, rule_str, col_map):
    """Interpreta reglas lógicas y las transforma en máscaras booleanas.

    v106: delega en x1_engine.signal_mask. Conserva el contrato histórico del
    dashboard: ante regla ilegible devuelve máscara vacía (sin lanzar).
    """
    try:
        return signal_mask(data_np, str(rule_str), col_map)
    except Exception:
        return np.zeros(data_np.shape[0], dtype=bool)

# -----------------------------------------------------------------------------
# 2. FILTRO TEMPORAL (WRAPPER LEGACY)
# -----------------------------------------------------------------------------
def apply_time_filter(mask, cooldown):
    return apply_cooldown(np.asarray(mask, dtype=bool), int(cooldown))

# -----------------------------------------------------------------------------
# 3. MÉTRICAS DE RIESGO (RESTORED & AUDITED)
# -----------------------------------------------------------------------------
def calculate_drawdown(equity_values, initial_capital):
    acc_val = initial_capital + np.array(equity_values)
    peaks = np.maximum.accumulate(acc_val)
    dd_money = acc_val - peaks
    dd_pct = (dd_money / (peaks + 1e-9)) * 100
    return dd_money, np.min(dd_money), np.min(dd_pct)

def calculate_sortino(returns):
    """Ratio Sortino anualizado basado en volatilidad negativa."""
    active_rets = returns[returns != 0]
    if len(active_rets) < 5: return 0.0
    downside = active_rets[active_rets < 0]
    if len(downside) < 2: return 0.0
    # Anualización estándar para H1 (252 días * 24 horas)
    return (np.mean(active_rets) / (np.std(downside) + 1e-9)) * np.sqrt(252 * 24)

def calculate_ulcer_index(equity_values):
    if len(equity_values) < 2: return 0.0
    curve = 100.0 + (equity_values * 100.0) 
    peaks = np.maximum.accumulate(curve)
    dd_pct = (curve - peaks) / (peaks + 1e-9)
    return round(np.sqrt(np.mean(dd_pct ** 2)) * 100.0, 3)

def get_dual_stagnation(equity_curve, entry_mask, mining_start_idx=0):
    res = {"global_val": 0, "global_start": 0, "global_end": 0, "active_val": 0, "active_start": 0, "active_end": 0}
    if len(equity_curve) < 2 or entry_mask is None or not np.any(entry_mask): return res
    idx_g = np.where(entry_mask == True)[0]
    first_g = idx_g[0]
    p_g = np.maximum.accumulate(equity_curve[first_g:] - equity_curve[first_g])
    h_g = np.where(np.diff(p_g, prepend=-1e-9) > 0)[0]
    if len(h_g) >= 2:
        g_g = np.diff(h_g); m_g = np.argmax(g_g)
        res["global_val"], res["global_start"], res["global_end"] = int(g_g[m_g]), first_g + h_g[m_g], first_g + h_g[m_g+1]
    if mining_start_idx < len(equity_curve):
        p_a = np.maximum.accumulate(equity_curve[mining_start_idx:] - equity_curve[mining_start_idx])
        h_a = np.where(np.diff(p_a, prepend=-1e-9) > 0)[0]
        if len(h_a) >= 2:
            g_a = np.diff(h_a); m_a = np.argmax(g_a)
            res["active_val"], res["active_start"], res["active_end"] = int(g_a[m_a]), mining_start_idx + h_a[m_a], mining_start_idx + h_a[m_a+1]
    return res

# -----------------------------------------------------------------------------
# 4. MOTOR ATÓMICO (HYBRID SYNC)
# -----------------------------------------------------------------------------
def X1_Compute_Engine(data_pack, strategies_list, total_friction=1.0):
    """v106: cada estrategia se simula con el Motor Único — el dashboard ve
    exactamente las mismas cifras que el minero y el auditor."""
    data_values, col_map, ret_indices, dates, _, _, _ = data_pack
    n_rows = data_values.shape[0]

    individual_equities = {}
    total_returns_vector = np.zeros(n_rows)
    all_entry_masks = np.zeros(n_rows, dtype=bool)

    for strat in strategies_list:
        try:
            sim = simulate(data_values, col_map, ret_indices, strat['Entry'],
                           strat['Exit'], strat['Side'],
                           cooldown=int(strat.get('Cooldown', 24)),
                           friction_points=float(total_friction))
        except ValueError:
            continue
        if sim['n_trades'] == 0: continue

        all_entry_masks |= sim['mask']
        total_returns_vector += sim['vector']
        uid = strat.get('id', 'UNK')
        individual_equities[f"ID_{uid}"] = np.cumsum(sim['vector'])

    n_strats = len(strategies_list)
    df_res = pd.DataFrame(individual_equities, index=dates)
    df_res['Portfolio'] = np.cumsum(total_returns_vector) / (n_strats if n_strats > 0 else 1)
    df_res['Entry_Signal'] = all_entry_masks
    return df_res