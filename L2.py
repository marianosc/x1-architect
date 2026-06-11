# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.800 - PURE GENETICS
# FILE: L2.py
# ##########################################################################
import os, sys, pandas as pd, numpy as np, random, time, json, shutil
from joblib import Parallel, delayed
from tqdm import tqdm
from pathlib import Path
from numba import njit

@njit(cache=True)
def numba_apply_time_filter(mask, cooldown):
    idx = np.where(mask)[0]
    if len(idx) == 0: return mask
    clean = np.zeros(mask.shape, dtype=np.bool_)
    last = -cooldown - 1
    for i in idx:
        if i >= last + cooldown:
            clean[i] = True; last = i
    return clean

@njit(cache=True)
def numba_calc_pf_dynamic(returns, cost_vector):
    pos_sum = 0.0; neg_sum = 0.0
    for i in range(len(returns)):
        r_net = returns[i] - cost_vector[i]
        if r_net > 0: pos_sum += r_net
        else: neg_sum += r_net
    return pos_sum / (abs(neg_sum) + 1e-9)

LOCAL_TEMP = "C:/temp"
DATA_DIR = "data"

def log(msg): 
    print(f"\033[94m[L2] {msg}\033[0m")
    sys.stdout.flush()

def load_mining_params(sym):
    p = {"cooldown": 24, "min_exit": 1, "max_exit": 200, "f_points": 0.3}
    try:
        df_a = pd.read_csv(os.path.join(DATA_DIR, "assets.csv"))
        row = df_a[df_a['Symbol'].str.contains(sym.split('_')[0])].iloc[0]
        p["f_points"] = float(row.get('Slippage_Cost', 0.1)) + float(row.get('Avg_Spread', 0.1)) + float(row.get('Broker_Comm', 0.1))
    except: pass
    return p

def engine(data, rules, col_map, ret_indices, side, params):
    res = []
    f_points = params["f_points"]
    side_mult = 1.0 if side == "LONG" else -1.0
    close_prices = data[:, col_map['Close']]
    ret_1_v = (pd.Series(close_prices).shift(-1) - close_prices).values / (close_prices + 1e-9)
    
    exit_options = [(n, data[:, i] * side_mult) for n, i in ret_indices.items() if params["min_exit"] <= int(n.split('_')[1]) <= params["max_exit"]]

    for rule in rules:
        try:
            parts = rule.split('|'); mask_e = np.ones(data.shape[0], dtype=np.bool_)
            l_info = []
            for sub in parts:
                p = sub.split()
                c1_idx = col_map[p[0]]
                c2_idx = col_map[p[2]] if p[2] in col_map else -1
                val_c = 0.0 if c2_idx != -1 else np.float32(p[2])
                op_id = 0 if p[1] == '>=' else 1
                l_info.append((c1_idx, c2_idx, op_id, val_c))
                if c2_idx != -1: mask_e &= (data[:, c1_idx] >= data[:, c2_idx]) if op_id == 0 else (data[:, c1_idx] <= data[:, c2_idx])
                else: mask_e &= (data[:, c1_idx] >= val_c) if op_id == 0 else (data[:, c1_idx] <= val_c)
            
            mask_e = numba_apply_time_filter(mask_e, params["cooldown"])
            if np.sum(mask_e) < 200: continue
            
            e_idx = np.where(mask_e)[0]
            cost_vec = f_points / data[e_idx, col_map['Close_sft']]
            best_pf, best_exit = 0.0, ""

            # 1. Velas Fijas
            for h_name, h_rets in exit_options:
                pf = numba_calc_pf_dynamic(h_rets[mask_e], cost_vec)
                if pf > best_pf: best_pf, best_exit = pf, h_name

            # 2. Sintética
            trade_rets_syn = []
            for idx in e_idx:
                p_acum = 0.0
                for b in range(1, 49):
                    fut = idx + b
                    if fut >= data.shape[0]: break
                    p_acum += ret_1_v[fut-1] * side_mult
                    valid = True
                    for c1, c2, op, val in l_info:
                        v1 = data[fut, c1]; v2 = data[fut, c2] if c2 != -1 else val
                        if op == 0 and not (v1 >= v2): valid = False; break
                        if op == 1 and not (v1 <= v2): valid = False; break
                    if not valid: break
                trade_rets_syn.append(p_acum)
            
            pf_syn = numba_calc_pf_dynamic(np.array(trade_rets_syn), cost_vec)
            if pf_syn > best_pf: best_pf, best_exit = pf_syn, "SINTETICA_REVERSE"

            if best_pf > 1.05:
                res.append([rule, side, best_exit, round(best_pf, 3)])
        except: continue
    return res

def run_factory():
    try:
        random.seed(time.time()); sym, side, fam, tf_label = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
        m_params = load_mining_params(sym)
        df_mining = pd.read_parquet(os.path.join(LOCAL_TEMP, f"X1_FULL_{sym.upper()}_{tf_label.upper()}.parquet"))
        df_mining = df_mining[df_mining['Zone'] == 1]
        
        stats_map = {col: [round(x, 6) for x in df_mining[col].quantile([0.1, 0.25, 0.5, 0.75, 0.9]).values.tolist()] for col in df_mining.columns if '_sft' in col}
        data_np = df_mining.drop(columns=['DateTime','Zone'], errors='ignore').values.astype(np.float32)
        cols_list = df_mining.drop(columns=['DateTime','Zone'], errors='ignore').columns.tolist()
        c_map = {n: i for i, n in enumerate(cols_list)}; ri_map = {c: i for i, c in enumerate(cols_list) if 'Ret_' in c}
        
        all_indicators = [c for c in cols_list if '_sft' in c]
        DNA_FAMILIES = {
            "TREND": [c for c in all_indicators if any(x in c for x in ['ema', 'adx', 'slope', 'aroon', 'linreg', 'efficiency'])],
            "MOMENTUM": [c for c in all_indicators if any(x in c for x in ['rsi', 'cmo', 'roc', 'mfi'])],
            "VOLATILITY": [c for c in all_indicators if any(x in c for x in ['bbw', 'natr', 'std', 'vol_z'])],
            "CYCLE": [c for c in all_indicators if any(x in c for x in ['stoch', 'willr', 'cci'])]
        }
        
        pool = DNA_FAMILIES.get(fam.upper(), all_indicators)
        ctx_pool = [c for c in all_indicators if 'close' in c.lower() or 'ema' in c]
        if fam.upper() in ["MOMENTUM", "VOLATILITY", "CYCLE"]:
            pool = [c for c in pool if not any(x in c for x in ['ema', 'linreg', 'slope', 'adx'])]
            ctx_pool = [c for c in all_indicators if 'close' in c.lower()]

        total_hypo, chunk_sz, final_pool = 500000, 5000, []
        log(f"🚀 Cosecha v104.800 | {side}-{fam.upper()}")

        for _ in tqdm(range(0, total_hypo, chunk_sz)):
            rules_chunk = []
            for _ in range(chunk_sz):
                n_parts = random.choice([1, 2, 2, 3]); parts = []
                for _ in range(n_parts):
                    i1 = random.choice(pool); op = random.choice(['>=','<='])
                    val = random.choice(stats_map[i1]) if random.random() > 0.4 else random.choice(ctx_pool) if random.random() > 0.5 else str(round(random.uniform(-10,10),2))
                    parts.append(f"{i1} {op} {val}")
                rules_chunk.append("|".join(parts))
            
            out = Parallel(n_jobs=32, backend='loky')(delayed(engine)(data_np, ck, c_map, ri_map, side, m_params) for ck in np.array_split(rules_chunk, 32))
            for s_list in out: 
                if s_list: final_pool.extend(s_list)
        
        pd.DataFrame(final_pool, columns=['Entry','Side','Exit','PF']).to_parquet(os.path.join(LOCAL_TEMP, f"X1_RAW_{sym}_{side}_{fam}.parquet"))
        log(f"✅ Silo {fam} terminado. {len(final_pool)} Alphas.")
    except Exception as e: log(f"CRASH L2: {e}")

if __name__ == '__main__': run_factory()