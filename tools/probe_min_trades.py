# Valida el Min_Trades DINÁMICO de L3 (v108) sobre el terreno fresco: replica
# EXACTO la fórmula de audit_worker usando el motor real para las duraciones.
#   spacing   = max(cooldown, mean(durations del candidato))
#   min_t_req = max(30, int(0.25 * velas_IS / spacing))
# Reporta min_t_req por horizonte de salida. Esperado NOTEBOOK: ~414 para Ret_24.
import os, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from modules.x1_engine import simulate, SYNTHETIC_EXIT

SYM, TF = (sys.argv[1] if len(sys.argv) > 1 else "XAUUSD"), (sys.argv[2] if len(sys.argv) > 2 else "H1")
COOLDOWN = 25
F_POINTS = 1.0  # XAUUSD calibrada

df = pd.read_parquet(Path("C:/temp") / f"X1_FULL_{SYM}_{TF}.parquet")
velas_is = int((df['Zone'] == 1).sum())
df_m = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
G = df_m.values.astype(np.float32)
c_map = {n: i for i, n in enumerate(df_m.columns)}
ri = {n: i for i, n in enumerate(df_m.columns) if 'Ret_' in n}

# Regla LONG permisiva y representativa (dip de momentum, dispara seguido).
RULE = "rsi_13_sft <= 55"
EXITS = ["Ret_12", "Ret_24", "Ret_48", "Ret_72", "Ret_96", SYNTHETIC_EXIT]

print(f"=== Min_Trades DINÁMICO | {SYM}@{TF} | velas_IS(Z1)={velas_is:,} | cooldown={COOLDOWN} | regla='{RULE}' ===")
print(f"{'Exit':<18}{'n_trades':>9}{'dur_media':>11}{'spacing':>9}{'min_t_req':>11}")
for ex in EXITS:
    sim = simulate(G, c_map, ri, RULE, ex, "LONG", cooldown=COOLDOWN, friction_points=F_POINTS)
    durs = sim['durations']
    dur_mean = float(np.mean(durs)) if len(durs) else COOLDOWN
    spacing = max(COOLDOWN, dur_mean)
    min_t_req = max(30, int(0.25 * velas_is / spacing))
    print(f"{ex:<18}{sim['n_trades']:>9}{dur_mean:>11.1f}{spacing:>9.1f}{min_t_req:>11}")
