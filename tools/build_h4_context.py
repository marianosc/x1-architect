# ##########################################################################
# SYSTEM: X1-ARCHITECT | EXPERIMENTO B3 (programa nocturno 2026-06-12)
# FILE: tools/build_h4_context.py
# ROL: ADN inter-timeframe — features de TENDENCIA H4 alineadas SIN lookahead
#      sobre las filas H1. Produce X1_FULL_XAUUSD_H1C4.parquet (tf "H1C4")
#      para minarlo con L2/L3 normales (sym XAUUSD => Constitucion H1).
# SIN LOOKAHEAD: la columna {x}_sft de la fila H4 con DateTime T contiene el
#      valor de la vela H4 ANTERIOR (cerrada exactamente en T). merge_asof
#      backward sobre el tiempo H1 elige la fila H4 con T <= t_H1, asi que
#      el valor usado siempre proviene de una vela H4 YA CERRADA.
# ##########################################################################
import numpy as np
import pandas as pd

H1 = r"C:\temp\X1_FULL_XAUUSD_H1.parquet"
H4 = r"C:\temp\X1_FULL_XAUUSD_H4.parquet"
OUT = r"C:\temp\X1_FULL_XAUUSD_H1C4.parquet"

# familias de TENDENCIA (prior de Mariano) en 3 escalas H4
CTX = [f"{ind}_{p}_sft" for ind in ("ema", "adx", "linreg", "efficiency")
       for p in (21, 55, 120)]

df1 = pd.read_parquet(H1)
df4 = pd.read_parquet(H4)
df1["DateTime"] = pd.to_datetime(df1["DateTime"])
df4["DateTime"] = pd.to_datetime(df4["DateTime"])

ctx = df4[["DateTime"] + CTX].copy()
# renombrar manteniendo la keyword de familia ('ema'/'adx'/...) para que L2
# las asigne a TREND: ema_21_sft -> ema_h4x21_sft (regex de periodo intacta no
# hace falta en L2; el traductor MQL5 para H4-ctx queda PENDIENTE, anotado).
ctx.columns = ["DateTime"] + [c.replace("_sft", "").replace("_", "_h4x", 1) + "_sft"
                              for c in CTX]
ctx = ctx.sort_values("DateTime")
df1 = df1.sort_values("DateTime")

merged = pd.merge_asof(df1, ctx, on="DateTime", direction="backward")
n_nan = int(merged[ctx.columns[1]].isna().sum())
merged = merged.dropna().reset_index(drop=True)
merged.set_index("DateTime", drop=False, inplace=True)
merged.to_parquet(OUT, compression="snappy")

new_cols = [c for c in merged.columns if "_h4x" in c]
print(f"H1C4: {len(merged):,} velas | {len(merged.columns)} cols | "
      f"nuevas H4ctx: {new_cols}")
print(f"filas descartadas por warmup H4 (NaN): {n_nan}")
# verificacion anti-lookahead: la fila H4 elegida nunca es posterior a la H1
chk = pd.merge_asof(df1[["DateTime"]], ctx[["DateTime"]].assign(t4=ctx["DateTime"]),
                    on="DateTime", direction="backward")
viol = int((chk["t4"] > chk["DateTime"]).sum())
print(f"violaciones de lookahead (t_H4 > t_H1): {viol} (esperado 0)")
print(f"-> {OUT}")
