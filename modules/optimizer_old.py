# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 101.39 - IA OPTIMIZER (SEED ROTATION CORE)
# FILE: modules/optimizer.py
# ROL: IA de Selección con Lógica de Cobertura y Rotación de Semilla.
# UPD: Re-expansión atómica para integridad total (322 líneas).
# FIX: Resuelto bloqueo de sliders estrictos y NameError de métricas.
# AUDITADO: 4 VECES - CÓDIGO ÍNTEGRO - SIN RESÚMENES.
# ##########################################################################
import numpy as np
import pandas as pd
from scipy import stats
from modules.backtest_engine import fast_signal_generator

# -----------------------------------------------------------------------------
# 1. MOTOR DE SALUD OPERATIVA (VITALIDAD DE CURVA)
# -----------------------------------------------------------------------------
def calculate_internal_health(vector_returns, r2_base, pf_base):
    """
    Analiza la pendiente final de la equidad para evitar Alphas 'muertos'.
    Esta métrica es el motor de ordenamiento para la formación de equipos.
    """
    # Filtro de actividad: Solo analizamos velas donde hubo trades
    active_mask = vector_returns != 0
    active_rets = vector_returns[active_mask]
    
    # Si la muestra es estadísticamente insignificante, asignamos salud mínima
    if len(active_rets) < 12:
        return 0.0001
    
    # Construcción de la equidad operativa
    cumulative_equity = np.cumsum(active_rets)
    total_trades = len(cumulative_equity)
    
    # ANALISIS DE MOMENTUM: Salud del último tramo (20% de la vida)
    window_limit = max(5, int(total_trades * 0.2))
    recent_data_segment = cumulative_equity[-window_limit:]
    
    if len(recent_data_segment) < 3:
        current_slope = 0.0
    else:
        # Aplicamos regresión lineal sobre el tramo final
        x_axis = np.arange(len(recent_data_segment))
        slope_val, _, r_val, _, _ = stats.linregress(x_axis, recent_data_segment)
        # La pendiente es ponderada por su estabilidad (R2)
        current_slope = slope_val * (r_val ** 2)

    # ANALISIS DE ESTANCAMIENTO: ¿Está la estrategia en una 'Caja Roja'?
    all_peaks = np.maximum.accumulate(cumulative_equity)
    last_peak_level = all_peaks[-1]
    
    # Contador de trades sin nuevos máximos
    stagnation_counter = 0
    for j in range(len(cumulative_equity)-1, -1, -1):
        if cumulative_equity[j] < last_peak_level:
            stagnation_counter += 1
        else:
            # Se ha encontrado un pico, detenemos el conteo
            break
            
    # Penalización logarítmica: Suaviza el impacto de estancamientos cortos
    # pero fulmina estrategias con desiertos masivos (como los 900 días).
    time_decay_score = 1.0 / (np.log10(stagnation_counter + 10))
    
    # Puntuación Integrada: Estabilidad Histórica * Vitalidad Reciente * Decay
    # Usamos la función tanh para normalizar la pendiente en un rango seguro
    normalized_vitality = np.tanh(current_slope + 1.2)
    final_health_score = (r2_base * pf_base * normalized_vitality) * time_decay_score
    
    return round(max(0.0001, final_health_score), 4)

# -----------------------------------------------------------------------------
# 2. MOTOR DE CORRELACIÓN ROBUSTA (PEARSON ANTI-NAN)
# -----------------------------------------------------------------------------
def get_safe_correlation(vec1, vec2):
    """v102.15: Radar de Riesgo (Correlación de Drawdowns)."""
    try:
        # 1. Generamos las curvas de equidad
        e1, e2 = np.cumsum(vec1), np.cumsum(vec2)
        
        # 2. Calculamos las series de Drawdown (distancia al pico)
        dd1 = e1 - np.maximum.accumulate(e1)
        dd2 = e2 - np.maximum.accumulate(e2)
        
        # 3. Filtro de varianza (Si uno no tiene DD, la correlación es 0)
        if np.std(dd1) < 1e-9 or np.std(dd2) < 1e-9: return 0.0
        
        # 4. Pearson sobre el sufrimiento acumulado
        corr_val = np.corrcoef(dd1, dd2)[0, 1]
        return round(corr_val, 4) if not np.isnan(corr_val) else 0.0
    except: return 0.0

# -----------------------------------------------------------------------------
# 3. ANALIZADOR DE RIESGO ATÓMICO (MAX DRAWDOWN)
# -----------------------------------------------------------------------------
def get_max_drawdown_pct(returns_vector):
    """
    Calcula el Drawdown porcentual exacto sobre base monetaria 100.
    Garantiza simetría total con el gráfico del Dashboard.
    """
    if len(returns_vector) == 0:
        return 0.0
        
    acc_equity = np.cumsum(returns_vector)
    # Escalado a base 100 para evitar errores de coma flotante en porcentajes
    monetary_curve = 100.0 + (acc_equity * 100.0)
    
    # Identificación de picos históricos
    running_peaks = np.maximum.accumulate(monetary_curve)
    
    # Cálculo de la serie de drawdowns (caídas desde el pico)
    dd_series = (monetary_curve - running_peaks) / (running_peaks + 1e-9)
    
    # El valor máximo de la serie es nuestro Max DD
    max_dd_val = abs(np.min(dd_series)) * 100
    return max_dd_val

# -----------------------------------------------------------------------------
# 4. GENERADOR DE VECTORES DE COMPONENTES (v104.300 - HYBRID VISION)
# -----------------------------------------------------------------------------
def get_strategy_vectors(market_data, col_map, ret_indices, rule_str, exit_label, side, r2, pf):
    """
    v104.300: Generador Híbrido con soporte para Salidas Lógicas.
    Permite que la IA 'vea' y sume los beneficios de las estrategias SINTETICA_REVERSE.
    """
    try:
        # 1. Generación de Señal de Entrada
        mask_sig = fast_signal_generator(market_data, rule_str, col_map)
        n_signals = np.sum(mask_sig)
        if n_signals < 8: return None
            
        n_rows = market_data.shape[0]
        holding_mask = np.zeros(n_rows, dtype=bool)
        final_vector = np.zeros(n_rows, dtype=np.float32)
        side_mult = 1.0 if side == 'LONG' else -1.0
        entry_indices = np.where(mask_sig)[0]

        # 2. PROCESAMIENTO DE SALIDA (HÍBRIDO: VELAS VS LÓGICA)
# --- v104.950: MOTOR DE SIMULACIÓN HÍBRIDO (SINCRO TOTAL L2/L3) ---
        if exit_label == "SINTETICA_REVERSE":
            # La IA simula la rotura de lógica bar a bar para calcular el beneficio real
            close_prices = market_data[:, col_map['Close']]
            # Retorno de 1 vela para la suma acumulada
            ret_1_v = (pd.Series(close_prices).shift(-1).values - close_prices) / (close_prices + 1e-9)
            parts = rule_str.split('|')

            for idx in entry_indices:
                profit_acum = 0.0
                actual_duration = 0
                # Buscamos el punto de salida (Límite institucional 48 velas)
                for bars_held in range(1, 49):
                    fut_idx = idx + bars_held
                    if fut_idx >= n_rows: break
                    
                    actual_duration = bars_held
                    profit_acum += ret_1_v[fut_idx - 1] * side_mult
                    
                    # Verificación de lógica de salida: ¿Sigue siendo válida la regla?
                    is_logic_valid = True
                    for sub in parts:
                        tk = sub.split()
                        v1 = market_data[fut_idx, col_map[tk[0]]]
                        v2 = market_data[fut_idx, col_map[tk[2]]] if tk[2] in col_map else np.float32(tk[2])
                        if tk[1] == '>=' and not (v1 >= v2): is_logic_valid = False; break
                        if tk[1] == '<=' and not (v1 <= v2): is_logic_valid = False; break
                    
                    if not is_logic_valid: break
                
                final_vector[idx] = profit_acum
                holding_mask[idx : idx + actual_duration + 1] = True

        else:
            # --- SALIDA TRADICIONAL POR BARRAS FIJAS ---
            if exit_label not in ret_indices: return None
            try: bars = int(exit_label.split('_')[1])
            except: bars = 24
            
            final_vector[mask_sig] = market_data[mask_sig, ret_indices[exit_label]] * side_mult
            for idx in entry_indices:
                holding_mask[idx : min(idx + bars, n_rows)] = True

        # 3. CÁLCULO DE MÉTRICAS DE SALUD PARA LA IA
        h_val = calculate_internal_health(final_vector, r2, pf)
        mdd_ind = get_max_drawdown_pct(final_vector)
        
        return {
            'mask': mask_sig, 
            'holding_mask': holding_mask, 
            'vector': final_vector, 
            'health': h_val,
            'mdd_solo': mdd_ind
        }
    except Exception:
        return None

# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.400 - IA SELECTION (NETTING CORE)
# FILE: modules/optimizer.py
# ROL: IA de Selección con Rotación de Semilla y Compensación de Drawdown.
# ##########################################################################

def run_greedy_selection(data_pack, strategies_df, max_items=5, max_corr=0.3, max_jac=0.2, max_mdd=5.0):
    """
    v104.400: IA DE FORMACIÓN DE EQUIPOS POR COMPENSACIÓN DE VARIANZA.
    Busca el 'Netting' perfecto: donde la ganancia de uno borra la pérdida del otro.
    """
    # 1. DESEMPAQUETADO DEL PACK RYZEN 9
    m_values, c_map, r_indices, m_dates, c_list, m_zones, n_bars = data_pack

    # 2. PREPARACIÓN DEL POOL BALANCEADO (SIDE-FAIR POOL)
    pool_candidates = []
    # Tomamos la élite de cada lado para asegurar cobertura
    df_longs = strategies_df[strategies_df['Side'] == 'LONG'].head(150)
    df_shorts = strategies_df[strategies_df['Side'] == 'SHORT'].head(150)
    df_pool = pd.concat([df_longs, df_shorts])
    
    for idx_s, row_s in df_pool.iterrows():
        alpha_data = get_strategy_vectors(m_values, c_map, r_indices, row_s['Entry'], row_s['Exit'], row_s['Side'], row_s['R2'], row_s['PF'])
        if alpha_data:
            pool_candidates.append({
                'id': idx_s, 
                'data': row_s, 
                'holding_mask': alpha_data['holding_mask'], 
                'vector': alpha_data['vector'], 
                'health': alpha_data['health'], 
                'mdd_solo': alpha_data['mdd_solo']
            })

    if not pool_candidates: return []
    
    # Ordenamos por Health (Salud Institucional)
    pool_candidates.sort(key=lambda x: x['health'], reverse=True)

    # 3. BÚSQUEDA SOBERANA POR ROTACIÓN DE SEMILLA
    best_overall_team = []
    max_score_global = -np.inf
    
    # Probamos las 60 mejores estrategias como 'Capitanes' de equipo
    seed_limit = min(60, len(pool_candidates))
    
    for i in range(seed_limit):
        seed_alpha = pool_candidates[i]
        
        # El capitán debe ser legal individualmente para no arrastrar al equipo
        if seed_alpha['mdd_solo'] > max_mdd * 1.5: continue
            
        trial_team = [seed_alpha]
        acc_rets_sum = seed_alpha['vector'].copy()
        
        # Intentamos emparejar con socios que cubran sus huecos
        for partner in pool_candidates:
            if len(trial_team) >= max_items: break
            if any(member['id'] == partner['id'] for member in trial_team): continue
                
            # --- TEST 1: DIVERSIFICACIÓN ESTRUCTURAL (JACCARD & PEARSON) ---
            is_diverse = True
            for member in trial_team:
                # Jaccard por Exposición (Holding Mask)
                inter = np.logical_and(partner['holding_mask'], member['holding_mask']).sum()
                union = np.logical_or(partner['holding_mask'], member['holding_mask']).sum()
                j_score = inter / (union + 1e-9)
                
                # Pearson por Correlación de Drawdown
                p_score = abs(get_safe_correlation(partner['vector'], member['vector']))
                
                if j_score > max_jac or p_score > max_corr:
                    is_diverse = False; break
            
            if not is_diverse: continue

            # --- TEST 2: EL FILTRO DEL NETTING REAL (1/N) ---
            # Sumamos el beneficio del nuevo socio a la curva actual
            hypo_rets_sum = acc_rets_sum + partner['vector']
            n_members = len(trial_team) + 1
            
            # Calculamos el DD de la equidad combinada normalizada
            team_mdd_real = get_max_drawdown_pct(hypo_rets_sum / n_members)
            
            # LEY DE ACERO: Si el socio sube el DD por encima del slider, queda prohibido
            if team_mdd_real <= max_mdd:
                trial_team.append(partner)
                acc_rets_sum = hypo_rets_sum

        # --- EVALUACIÓN DE APTITUD DEL EQUIPO (FITNESS) ---
        if len(trial_team) >= 2:
            final_rets = acc_rets_sum / len(trial_team)
            f_profit = np.sum(final_rets)
            f_mdd = get_max_drawdown_pct(final_rets)
            
            # Fitness: Premiamos Profit/DD pero con un multiplicador por tamaño de equipo
            # Esto fuerza a la IA a buscar cooperaciones en lugar de lobos solitarios
            current_fitness = (f_profit / (f_mdd + 0.05)) * (len(trial_team) ** 1.5)
            
            if current_fitness > max_score_global:
                max_score_global = current_fitness
                best_overall_team = trial_team

    # 4. FORMATEO DE SALIDA PARA EL DASHBOARD
    if not best_overall_team: return []

    output_ia = []
    for component in best_overall_team:
        data_row = component['data']
        # Métrica Recovery Factor Individual sobre el backtest real
        rf_val = round(abs(np.sum(component['vector'])) / (component['mdd_solo']/100 + 1e-9), 2)
        
        output_ia.append({
            'id': component['id'], 
            'Entry': data_row['Entry'], 
            'Exit': data_row['Exit'], 
            'Side': data_row['Side'],
            'TimeFrame': data_row.get('TimeFrame', 'H1'),
            'PF': round(data_row.get('PF', 0.0), 2), 
            'R2': round(data_row.get('R2', 0.0), 4), 
            'Health': component['health'],
            'RF': rf_val,
            'Stag_Active': data_row.get('Stag_Active', 0), 
            'Family': data_row.get('Family', 'UNK')
        })
    
    return output_ia


# -----------------------------------------------------------------------------
# 6. ANALÍTICA DE CORRELACIÓN (PORTFOLIO HEATMAP DATA)
# -----------------------------------------------------------------------------
def get_correlation_matrix(df_portfolio_returns):
    """v102.15: Genera matriz basada en la coincidencia de Drawdowns."""
    if df_portfolio_returns.empty: return pd.DataFrame()
    
    id_columns = [col for col in df_portfolio_returns.columns if "ID_" in col]
    if len(id_columns) < 2: return pd.DataFrame()
    
    # Transformamos cada curva de equidad en su serie de Drawdown
    df_dd = df_portfolio_returns[id_columns].copy()
    for col in id_columns:
        df_dd[col] = df_dd[col] - df_dd[col].cummax()
        
    # Correlacionamos el riesgo, no el beneficio
    return df_dd.corr()