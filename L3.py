# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 106.0 - MASTER TOURNAMENT AUDITOR
# FILE: L3.py
# ROL: Auditor de Alta Fidelidad con Memoria Retroactiva y Diversidad.
# UPD v106 (SANEAMIENTO):
#   - Simulación delegada al Motor Único (x1_engine.simulate): se corrige el
#     bug histórico de la salida sintética (antes se auditaba a 48 velas fijas
#     sin rotura de regla) y se aplica el MISMO cooldown que el minero
#     (Min_Dist_Bars de assets.csv; antes L3 auditaba sin cooldown).
#   - Fusible monkey_test IMPLEMENTADO (antes existía solo en la UI):
#     bootstrap data-driven de Marc Cortázar, umbrales Monkey_Train_Min (IS)
#     y Monkey_Test_Min (OOS) de assets.csv. Último gate del embudo.
#   - Excursion Score (Tomillero): columnas XS_IS / XS_OOS como telemetría
#     de calidad de entrada (requiere High/Low en el Parquet; si no están,
#     quedan en NaN sin matar a nadie).
# ##########################################################################
import os, sys, pandas as pd, numpy as np, warnings, json, time
from joblib import Parallel, delayed
from scipy import stats
from pathlib import Path

from modules.x1_engine import simulate
from modules.x1_validators import monkey_test, excursion_score

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

# -----------------------------------------------------------------------------
# BLOQUE 3: EL VERDUGO (AUDIT_WORKER)
# -----------------------------------------------------------------------------
def audit_worker(s_row):
    """Procesa una sola estrategia aplicando el guantelete de sinceridad."""
    d_f, ret_1, c_map, ri, zones, cfg, fuses = G_DF, G_RET_1, G_C_MAP, G_RI_MAP, G_ZONES, G_CFG, G_FUSES

    try:
        rule, side, exit_l, _ = s_row

        # A+B. SIMULACIÓN CON EL MOTOR ÚNICO (señal + cooldown + salida + fricción)
        # Mismo cooldown que el minero: el auditor mide el MISMO conjunto de trades.
        try:
            sim = simulate(d_f, c_map, ri, rule, exit_l, side,
                           cooldown=cfg['cooldown'], friction_points=cfg['f_points'])
        except ValueError:
            return None, "ERR_EXIT"

        idx_e = np.where(sim['mask'])[0]
        if len(idx_e) < 20: return None, "FAIL_TRADES"
        r_all = sim['vector']
        durations = sim['durations']

        # C. FILTRO DE ESTANCAMIENTO (PEAK-TO-PRESENT)
        # v106.1 (veredicto notebook, ciclo 1): Zona 0 = contexto ("Hist"),
        # NO tribunal. El minero selecciona por PF solo en Zona 1, así que
        # estancamiento y profit total se juzgan desde z1_start; juzgar la
        # historia completa hacía que FAIL_GAP ejecutara al 99.999% por no
        # ganar en un régimen (2015-2018) en el que nadie fue seleccionado.
        # Las señales/indicadores siguen calculándose sobre toda la historia.
        z1s = int(cfg.get('z1_start', 0))
        r_judge = r_all[z1s:]
        eq_global = np.cumsum(r_judge)
        peaks = np.maximum.accumulate(eq_global)
        peak_hits = np.where(np.diff(peaks, prepend=-1e-9) > 0)[0]

        if len(peak_hits) > 0:
            # Hueco entre picos históricos
            gap_internal = np.max(np.diff(peak_hits)) if len(peak_hits) > 1 else 0
            # Hueco desde el último pico hasta el presente (Sinceridad Total)
            gap_to_now = (len(r_judge) - 1) - peak_hits[-1]
            max_stag_real = int(max(gap_internal, gap_to_now))
        else: max_stag_real = len(r_judge)

        if fuses.get("anti_gap", True) and max_stag_real > cfg['Stag_Global']:
            return None, "FAIL_GAP"

        # D. FILTROS DE ACTIVIDAD Y RENTABILIDAD
        r_is = r_all[zones['is']][r_all[zones['is']] != 0]
        r_oos = r_all[zones['oos']][r_all[zones['oos']] != 0]

        if len(r_oos) < 2: return None, "FAIL_OOS_EMPTY" # Muerte súbita inactivos
        if len(r_is) < cfg['min_t']: return None, "FAIL_TRADES"
        
        pf_is = np.sum(r_is[r_is > 0]) / (abs(np.sum(r_is[r_is < 0])) + 1e-9)
        if pf_is < cfg['min_pf']: return None, "FAIL_PF_NET"
        
        # El balance final debe ser positivo (desde Zona 1: Z0 es contexto)
        profit_total = np.sum(r_judge)
        if profit_total <= 0: return None, "FAIL_NEG_PROFIT"

        # E. CÁLCULO DE SALUD (RANKING HEALTH)
        eq_is_curve = np.cumsum(r_is)
        _, _, r_v, _, _ = stats.linregress(np.arange(len(eq_is_curve)), eq_is_curve)
        r2_real = max(0.0, float(r_v**2))

        m_is = np.mean(r_is)
        oer = max(0.0, min((np.mean(r_oos) / m_is) if abs(m_is) > 1e-9 else 0.0, 2.0))

        # Puntuación final que integra Beneficio, Estabilidad y Sinceridad
        health = (profit_total * r2_real * (oer + 0.1)) / (np.log10(max_stag_real + 10))

        # F. MONKEY TEST (FUSIBLE REAL v106 - ÚLTIMO GATE, METODOLOGÍA TOMILLERO)
        # Los monos copian cadencia, exposición y dirección de la estrategia
        # sobre la secuencia real de la zona. Umbrales: IS 99% / OOS 90%.
        z_is = zones['is'].values if hasattr(zones['is'], 'values') else zones['is']
        z_oos = zones['oos'].values if hasattr(zones['oos'], 'values') else zones['oos']
        monkey_is_pct, monkey_oos_pct = -1.0, -1.0  # -1 = no evaluado (fusible OFF)

        if fuses.get("monkey_test", True):
            close_all = d_f[:, c_map['Close']]
            for z_mask, thresh_key, fail_label, attr in (
                    (z_is, 'monkey_train_min', "FAIL_MONKEY_IS", 'is'),
                    (z_oos, 'monkey_test_min', "FAIL_MONKEY_OOS", 'oos')):
                entries_z = idx_e[z_mask[idx_e]]
                if len(entries_z) < 1:
                    continue
                pos = np.searchsorted(idx_e, entries_z)
                expo_z = int(max(1, round(float(np.mean(durations[pos])))))
                strat_total_z = float(r_all[z_mask].sum())
                # v106.2: los monos pagan el MISMO peaje normalizado que la
                # estrategia paga via simulate() (la estrategia llega NETA;
                # sin esto los monos cobraban bruto = pelea injusta).
                friction_z = float(cfg['f_points']) / float(np.mean(close_all[z_mask]))
                res_mk = monkey_test(ret_1[z_mask], len(entries_z), expo_z,
                                     strat_total_z, side,
                                     n_monkeys=cfg.get('monkey_n', 5000),
                                     seed=cfg.get('monkey_seed', 12345),
                                     friction_per_trade=friction_z)
                pct = res_mk['pvalue'] * 100.0
                if attr == 'is': monkey_is_pct = pct
                else: monkey_oos_pct = pct
                if pct < cfg[thresh_key]:
                    return None, fail_label

        # G. EXCURSION SCORE (TELEMETRÍA DE CALIDAD DE ENTRADA - NO MATA)
        xs_is, xs_oos = np.nan, np.nan
        if 'High' in c_map and 'Low' in c_map:
            high_v, low_v = d_f[:, c_map['High']], d_f[:, c_map['Low']]
            close_v = d_f[:, c_map['Close']]
            for z_mask, attr in ((z_is, 'is'), (z_oos, 'oos')):
                entries_z = idx_e[z_mask[idx_e]]
                if len(entries_z) < 1:
                    continue
                pos = np.searchsorted(idx_e, entries_z)
                xs_val, _ = excursion_score(high_v, low_v, close_v,
                                            entries_z, durations[pos], side)
                if attr == 'is': xs_is = round(xs_val, 4)
                else: xs_oos = round(xs_val, 4)

        return [rule, side, exit_l, round(float(pf_is), 3), round(r2_real, 4),
                max_stag_real, len(r_is), round(float(oer), 4),
                round(float(profit_total), 4), round(float(health), 4),
                round(monkey_is_pct, 1), round(monkey_oos_pct, 1),
                xs_is, xs_oos], "PASS"
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
    def _cfg_val(key, default):
        v = row_a.get(key, default)
        return default if pd.isna(v) else v

    G_CFG = {"min_t": int(_cfg_val('Min_Trades', 300)),
             "min_pf": float(_cfg_val('Min_PF', 1.15)),
             "f_points": float(_cfg_val('Slippage_Cost', 0.1)) + float(_cfg_val('Avg_Spread', 0.1)) + float(_cfg_val('Broker_Comm', 0.1)),
             "Stag_Global": int(_cfg_val('Stag_Global', 5000)),
             # v106: cooldown unificado con el minero + umbrales monkey (Tomillero 99/90)
             "cooldown": int(_cfg_val('Min_Dist_Bars', 24)),
             "monkey_train_min": float(_cfg_val('Monkey_Train_Min', 99)),
             "monkey_test_min": float(_cfg_val('Monkey_Test_Min', 90)),
             "monkey_n": 5000,
             # v106.1: primer índice de Zona 1 — desde aquí se juzga el
             # estancamiento y el profit (Zona 0 = contexto, no tribunal)
             "z1_start": int(np.argmax(df_f['Zone'].values == 1)) if (df_f['Zone'] == 1).any() else 0}

    # Overrides de Constitución por variable de entorno (marco de experimentos
    # nocturnos, R3): un cambio por corrida, sin editar assets.csv jamás.
    for k, env in (("min_t", "X1_MIN_TRADES"), ("min_pf", "X1_MIN_PF"),
                   ("Stag_Global", "X1_STAG_GLOBAL"), ("cooldown", "X1_COOLDOWN"),
                   ("monkey_train_min", "X1_MONKEY_TRAIN_MIN"),
                   ("monkey_test_min", "X1_MONKEY_TEST_MIN"),
                   ("monkey_n", "X1_MONKEY_N"), ("f_points", "X1_F_POINTS")):
        if os.environ.get(env):
            G_CFG[k] = type(G_CFG[k])(float(os.environ[env]))
            print(f"\033[93m[L3] OVERRIDE {env}: {k} = {G_CFG[k]}\033[0m")
    
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
    stats_map = {k: 0 for k in ["FAIL_TRADES", "FAIL_PF_NET", "FAIL_GAP", "FAIL_OOS_EMPTY", "FAIL_NEG_PROFIT", "FAIL_MONKEY_IS", "FAIL_MONKEY_OOS", "ERR", "ERR_EXIT", "PASS"]}
    for _, s in out: stats_map[s] = stats_map.get(s, 0) + 1

    # 6. RE-RANKING Y FILTRO JACCARD (DIVERSIDAD)
    final_elite = []
    if passed_batch:
        df_all = pd.DataFrame(passed_batch, columns=['Entry','Side','Exit','PF','R2','Stag_Active','Trades','OER','UI','Health','Monkey','Monkey_OOS','XS_IS','XS_OOS'])
        df_all = df_all.sort_values(by=['Health', 'PF'], ascending=False)

        seen_tokens = []
        for _, row in df_all.iterrows():
            if len(final_elite) >= 500: break
            tks = set(str(row['Entry']).lower().replace('|',' ').replace('_sft','').split())
            if not any((len(tks.intersection(s))/(len(tks.union(s))+1e-9)) > 0.75 for s in seen_tokens):
                final_elite.append(row); seen_tokens.append(tks)

        pd.DataFrame(final_elite).to_csv(out_csv, index=False)

    # Telemetría para el Commander: SIEMPRE se escribe, aun en cosecha cero
    # (la autopsia de mortalidad es un dato válido que no debe perderse).
    with open(COSECHA / f"AUDIT_{sym}_{side}_{fam}.json", 'w') as fj:
        json.dump({"total": len(raw_df), "qualified": len(passed_batch),
                   "harvested": len(final_elite), "details": stats_map}, fj)

    if raw_p.exists(): raw_p.unlink()
    print(f"\033[92m[L3] CICLO FINALIZADO. Élite de {len(final_elite)} Alphas actualizada.\033[0m")

if __name__ == '__main__': run_radar()