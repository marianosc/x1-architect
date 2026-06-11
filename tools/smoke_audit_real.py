# ##########################################################################
# SYSTEM: X1-ARCHITECT | FASE 1+4 SANEAMIENTO
# FILE: tools/smoke_audit_real.py
# ROL: Smoke-test del auditor L3 v106 sobre DATOS REALES sin tocar disco.
#      Carga el Parquet de COSECHA/DATOS_MERCADO, inyecta los globales de
#      L3 a mano y pasa estrategias reales del MASTER por audit_worker.
# USO: python tools/smoke_audit_real.py [ruta_proyecto_Z] [n_estrategias] [n_monos]
#      En la notebook (sin numba) usar n_monos bajo (100-300).
#      En blanca (numba) aguanta el 5000 oficial.
# ##########################################################################
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import L3
from modules.x1_validators import NUMBA_ACTIVE

DEFAULT_Z = r"Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON"


def main():
    z_dir = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_Z
    n_strats = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    n_monos = int(sys.argv[3]) if len(sys.argv) > 3 else (5000 if NUMBA_ACTIVE else 200)

    parquet = os.path.join(z_dir, "COSECHA", "DATOS_MERCADO", "X1_FULL_XAUUSD_H1.parquet")
    master = os.path.join(z_dir, "COSECHA", "MASTER_XAUUSD_H1_SHORT_MOMENTUM.csv")

    print(f"numba: {'ACTIVA' if NUMBA_ACTIVE else 'NO (modo NumPy puro)'} | monos: {n_monos}")
    print(f"Mercado : {parquet}")
    df_f = pd.read_parquet(parquet)
    print(f"          {len(df_f):,} velas | columnas: {len(df_f.columns)} "
          f"| High/Low: {'SI' if 'High' in df_f.columns else 'NO (XS quedará NaN)'}")

    # --- Globales de L3 exactamente como los arma run_radar ---
    L3.G_ZONES = {'is': (df_f['Zone'] == 1).values, 'oos': (df_f['Zone'] == 2).values}
    close = df_f['Close'].values.astype(np.float64)
    ret1 = np.zeros(len(close))
    ret1[:-1] = (close[1:] - close[:-1]) / (close[:-1] + 1e-9)
    L3.G_RET_1 = ret1
    base = df_f.drop(columns=['DateTime', 'Zone'], errors='ignore')
    L3.G_DF = base.values.astype(np.float32)
    L3.G_C_MAP = {n: i for i, n in enumerate(base.columns)}
    L3.G_RI_MAP = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}

    assets = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "data", "assets.csv"))
    row_a = assets[assets['Symbol'] == 'XAUUSD'].iloc[0]
    L3.G_CFG = {
        "min_t": int(row_a['Min_Trades']), "min_pf": float(row_a['Min_PF']),
        "f_points": float(row_a['Slippage_Cost']) + float(row_a['Avg_Spread']) + float(row_a['Broker_Comm']),
        "Stag_Global": int(row_a['Stag_Global']),
        "cooldown": int(row_a['Min_Dist_Bars']),
        "monkey_train_min": float(row_a['Monkey_Train_Min']),
        "monkey_test_min": float(row_a['Monkey_Test_Min']),
        "monkey_n": n_monos,
    }
    # 'nogap' como argumento extra desactiva el fusible anti_gap para poder
    # ejercitar el camino del Monkey Test aunque el lote muera por estancamiento
    anti_gap = 'nogap' not in [a.lower() for a in sys.argv]
    L3.G_FUSES = {"anti_gap": anti_gap, "monkey_test": True}
    print(f"Constitución XAUUSD: cooldown={L3.G_CFG['cooldown']} | "
          f"fricción={L3.G_CFG['f_points']:.2f} pts | "
          f"monkey IS>={L3.G_CFG['monkey_train_min']:.0f}% OOS>={L3.G_CFG['monkey_test_min']:.0f}%\n")

    df_m = pd.read_csv(master)
    print(f"Estrategias reales: {master} ({len(df_m)} en disco, auditando {n_strats})\n")

    cols = ['Entry', 'Side', 'Exit', 'PF', 'R2', 'Stag_Active', 'Trades', 'OER',
            'UI', 'Health', 'Monkey', 'Monkey_OOS', 'XS_IS', 'XS_OOS']
    t0 = time.time()
    for _, r in df_m.head(n_strats).iterrows():
        row = [r['Entry'], r['Side'], r['Exit'], r['PF']]
        res, status = L3.audit_worker(row)
        regla = str(r['Entry'])[:58]
        if res is None:
            print(f"  [{status:<16}] {regla}")
        else:
            d = dict(zip(cols, res))
            print(f"  [{status:<16}] {regla}")
            print(f"     PF {d['PF']:.3f} | R2 {d['R2']:.3f} | trades {d['Trades']} | "
                  f"monkey IS {d['Monkey']:.1f}% OOS {d['Monkey_OOS']:.1f}% | "
                  f"XS {d['XS_IS']} / {d['XS_OOS']}")
    print(f"\nTiempo total: {time.time()-t0:.1f}s "
          f"({(time.time()-t0)/max(1,n_strats):.1f}s por estrategia)")


if __name__ == '__main__':
    main()
