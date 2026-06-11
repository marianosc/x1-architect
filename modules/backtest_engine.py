# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.355 - BACKTEST ENGINE (RESTORED)
# FILE: modules/backtest_engine.py
# ROL: Núcleo matemático con soporte para Salidas Sintéticas y Sortino.
# ##########################################################################
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# 1. GENERADOR DE SEÑALES VECTORIZADO
# -----------------------------------------------------------------------------
def fast_signal_generator(data_np, rule_str, col_map):
    """Interpreta reglas lógicas y las transforma en máscaras booleanas."""
    try:
        conditions = str(rule_str).split('|')
        rows = data_np.shape[0]
        master_mask = np.ones(rows, dtype=bool)
        
        for cond in conditions:
            cond = cond.strip()
            if not cond: continue
            
            operator = None
            if '>=' in cond: operator = '>='
            elif '<=' in cond: operator = '<='
            elif '==' in cond: operator = '=='
            elif '>' in cond: operator = '>'
            elif '<' in cond: operator = '<'
            
            if not operator: continue
            
            parts = cond.split(operator)
            left_token = parts[0].strip()
            right_token = parts[1].strip()
            
            if left_token in col_map:
                val_left = data_np[:, col_map[left_token]]
            else: return np.zeros(rows, dtype=bool)

            if right_token in col_map:
                val_right = data_np[:, col_map[right_token]]
            else:
                try: val_right = float(right_token)
                except ValueError: return np.zeros(rows, dtype=bool)

            if operator == '>=': mask = val_left >= val_right
            elif operator == '<=': mask = val_left <= val_right
            elif operator == '>': mask = val_left > val_right
            elif operator == '<': mask = val_left < val_right
            elif operator == '==': mask = val_left == val_right
            master_mask &= mask
        return master_mask
    except Exception: return np.zeros(data_np.shape[0], dtype=bool)

# -----------------------------------------------------------------------------
# 2. FILTRO TEMPORAL
# -----------------------------------------------------------------------------
def apply_time_filter(mask, cooldown):
    if cooldown <= 0: return mask
    indices = np.where(mask)[0]
    if len(indices) == 0: return mask
    clean_mask = np.zeros_like(mask, dtype=bool)
    last_idx = -cooldown - 1
    for idx in indices:
        if idx >= last_idx + cooldown:
            clean_mask[idx] = True
            last_idx = idx
    return clean_mask

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
    data_values, col_map, ret_indices, dates, _, _, _ = data_pack
    n_rows = data_values.shape[0]
    close_prices = data_values[:, col_map['Close']]
    ret_1_v = (pd.Series(close_prices).shift(-1).values - close_prices) / (close_prices + 1e-9)
    
    individual_equities = {}
    total_returns_vector = np.zeros(n_rows)
    all_entry_masks = np.zeros(n_rows, dtype=bool)
    
    for strat in strategies_list:
        mask = fast_signal_generator(data_values, strat['Entry'], col_map)
        mask = apply_time_filter(mask, int(strat.get('Cooldown', 24)))
        if np.sum(mask) == 0: continue
        all_entry_masks |= mask
        
        side_mult = 1.0 if strat['Side'] == 'LONG' else -1.0
        r_net_final = np.zeros(n_rows)
        entry_indices = np.where(mask)[0]

        if strat['Exit'] == "SINTETICA_REVERSE":
            parts = strat['Entry'].split('|')
            for idx in entry_indices:
                p_acum = 0.0
                for bars in range(1, 49):
                    fut = idx + bars
                    if fut >= n_rows: break
                    p_acum += ret_1_v[fut - 1] * side_mult
                    valid = True
                    for sub in parts:
                        tk = sub.split()
                        v1 = data_values[fut, col_map[tk[0]]]
                        v2 = data_values[fut, col_map[tk[2]]] if tk[2] in col_map else float(tk[2])
                        if tk[1] == '>=' and not (v1 >= v2): valid = False; break
                        if tk[1] == '<=' and not (v1 <= v2): valid = False; break
                    if not valid: break
                r_net_final[idx] = p_acum
        else:
            if strat['Exit'] in ret_indices:
                r_net_final[mask] = data_values[mask, ret_indices[strat['Exit']]] * side_mult
            else: continue

        # Fricción Dinámica (ECN Realismo)
        prices_in = data_values[mask, col_map['Close_sft']]
        r_net_final[mask] -= total_friction / (prices_in + 1e-9)
        
        total_returns_vector += r_net_final
        uid = strat.get('id', 'UNK')
        individual_equities[f"ID_{uid}"] = np.cumsum(r_net_final)
        
    n_strats = len(strategies_list)
    df_res = pd.DataFrame(individual_equities, index=dates)
    df_res['Portfolio'] = np.cumsum(total_returns_vector) / (n_strats if n_strats > 0 else 1)
    df_res['Entry_Signal'] = all_entry_masks
    return df_res