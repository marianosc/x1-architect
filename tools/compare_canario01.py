# Calibracion CANARIO01: x1_engine.simulate (referencia) vs Strategy Tester MT5.
# PRUEBA DE SINCRONIA POR PRECIO (veredicto notebook): el motor entra a Close[i],
# que en MT5 es el open de la vela i+1. Por eso el trade MT5 etiquetado en i+1
# debe rellenar a ~= Close[i] del motor (tolerancia: spread). Emparejamos por
# INDICE DE BARRA (no por aritmetica de horas, robusto a gaps de finde) y
# comparamos precios de fill. Tambien: friccion 1.0, divergencia residual y
# desglose del grupo +2 barras (gap finde / DST).
import csv, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules import x1_engine as eng

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARQUET = r"C:\temp\X1_FULL_XAUUSD_H1.parquet"
MT5_CSV = r"C:\Users\Pc\AppData\Roaming\MetaQuotes\Terminal\Common\Files\X1_TRUTH_CANARIO01.csv"
RULE = "rsi_13_sft <= 30|ema_55_sft >= Close_sft"
SIDE, EXIT = "LONG", "Ret_24"
LOTS, CONTRACT = 0.10, 100.0
Z2_START = np.datetime64("2023-06-05 00:00")
Z2_END = np.datetime64("2025-12-09 00:00")


def load_xauusd_cfg():
    with open(os.path.join(ROOT, "data", "assets.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["Symbol"] == "XAUUSD":
                fr = float(r["Slippage_Cost"]) + float(r["Avg_Spread"]) + float(r["Broker_Comm"])
                return int(float(r["Min_Dist_Bars"])), fr
    return 25, 1.0


COOLDOWN, FRICTION = load_xauusd_cfg()

# ----------------- LADO MOTOR -----------------
df = pd.read_parquet(PARQUET)
dt = pd.to_datetime(df["DateTime"]).reset_index(drop=True)
idx_of = {t: i for i, t in enumerate(dt)}
base = df.drop(columns=["DateTime", "Zone"], errors="ignore")
data = base.values.astype(np.float32)
col_map = {n: i for i, n in enumerate(base.columns)}
ret_indices = {n: i for i, n in enumerate(base.columns) if "Ret_" in n}
CLOSE = col_map["Close"]
RET24 = ret_indices[EXIT]

res = eng.simulate(data, col_map, ret_indices, RULE, EXIT, SIDE,
                   cooldown=COOLDOWN, friction_points=FRICTION)
in_z2 = (dt.values >= Z2_START) & (dt.values < Z2_END)
eng_entries = [i for i in np.where(res["mask"])[0] if in_z2[i]]
eng_set = set(eng_entries)
print(f"Config XAUUSD: cooldown={COOLDOWN} | friccion={FRICTION:.2f} pts")
print(f"MOTOR: {len(eng_entries)} entradas en Zona 2")

# ----------------- LADO MT5 -----------------
mt = pd.read_csv(MT5_CSV, sep="\t")
mt["entry_time"] = pd.to_datetime(mt["entry_time"], format="%Y.%m.%d %H:%M")
mt["exit_time"] = pd.to_datetime(mt["exit_time"], format="%Y.%m.%d %H:%M")
print(f"MT5  : {len(mt)} trades\n")

# MT5 entry_time fuera del grid del Parquet -> sintoma de desfase de huso (DST)
not_in_grid = [t for t in mt["entry_time"] if t not in idx_of]
print(f"MT5 entry_time NO presentes en el grid del Parquet (UTC+2 fijo): "
      f"{len(not_in_grid)} -> {[str(x) for x in not_in_grid[:3]]}")

# ----------------- PRUEBA DE SINCRONIA POR PRECIO -----------------
# Para cada trade MT5 (entra en barra j) buscamos su socio motor escaneando
# hacia atras j-1, j-2, ... (sincronia perfecta => socio en j-1, offset 1).
rows = []
for tr in mt.itertuples():
    j = idx_of.get(tr.entry_time)
    if j is None:
        rows.append((tr.entry_time, None, None, None, None, None)); continue
    partner, offset = None, None
    for k in range(1, 6):
        if j - k in eng_set:
            partner, offset = j - k, k
            break
    if partner is None:
        rows.append((tr.entry_time, None, None, None, None, None)); continue
    close_p = float(data[partner, CLOSE])              # Close[i] del motor
    dprice = float(tr.entry_price) - close_p           # fill - Close[i]
    # gap real (h) entre la barra del motor y la del fill MT5 (>offset*1h => finde)
    gap_h = (dt[j] - dt[partner]).total_seconds() / 3600.0
    rows.append((tr.entry_time, partner, offset, dprice, gap_h, close_p))

cmp = pd.DataFrame(rows, columns=["mt5_entry", "eng_bar", "offset", "dprice", "gap_h", "close_prev"])
mok = cmp[cmp["offset"] == 1].copy()           # sincronia perfecta (barras contiguas)
off2 = cmp[cmp["offset"] >= 2].copy()           # desfasados (candidatos a gap finde)
orphan = cmp[cmp["offset"].isna()].copy()
print(f"\n--- SINCRONIA POR INDICE DE BARRA (motor[j-1] <-> MT5[j]) ---")
print(f"offset 1 (contiguo, sincronia perfecta) : {len(mok)}/{len(mt)} ({100*len(mok)/len(mt):.1f}%)")
print(f"offset >=2 (desfasado)                  : {len(off2)}")
print(f"sin socio motor (boundary)              : {len(orphan)} -> {[str(x) for x in orphan['mt5_entry'][:4]]}")

# offset 1 se subdivide: contiguo (gap<=1h, spread puro) vs finde (Vie->Lun)
contig = mok[mok["gap_h"] <= 1.5]
wknd1 = mok[mok["gap_h"] > 1.5]
d = contig["dprice"].values
print(f"\n--- PRECIOS DE FILL vs Close[i] del motor (offset 1) ---")
print(f"contiguas (gap<=1h): {len(contig)} | offset1 con gap finde: {len(wknd1)}")
print(f"  delta fill-Close[i] (contiguas): media {d.mean():+.3f} | mediana {np.median(d):+.3f} "
      f"| std {d.std():.3f} | min {d.min():+.2f} | max {d.max():+.2f} pts")
for tol in (0.5, 1.0, 2.0):
    print(f"  |delta| <= {tol} pt : {100*np.mean(np.abs(d) <= tol):.1f}% de las contiguas")

# ----------------- CLASIFICACION offset>=2 y offset1-finde: gap de finde + DST -----------------
def is_weekend_jump(eng_bar, j):
    # algun salto >1h entre la barra del motor y la del fill => finde/feriado
    return any((dt[k + 1] - dt[k]).total_seconds() > 3600 * 1.5
               for k in range(eng_bar, j))

print(f"\n--- GRUPO DESFASADO (offset>=2 o offset1 con salto) : gap de finde / DST ---")
wk_explained = 0
desfase = pd.concat([off2, wknd1])
for tr in desfase.sort_values("mt5_entry").itertuples():
    j = idx_of[tr.mt5_entry]
    eb = int(tr.eng_bar)
    wknd = is_weekend_jump(eb, j)
    wk_explained += int(wknd)
    dow_e = dt[eb].day_name()[:3]; dow_m = dt[j].day_name()[:3]
    seas = "verano" if 4 <= tr.mt5_entry.month <= 10 else "invierno"
    tag = "FINDE/feriado" if wknd else "sin gap (revisar)"
    print(f"  motor {dt[eb]} ({dow_e}) -> MT5 {tr.mt5_entry} ({dow_m}) | "
          f"off {int(tr.offset)} | salto {tr.gap_h:.0f}h | delta {tr.dprice:+.2f} pts | {seas} | {tag}")
print(f"\noffset 1 con DST de verano (broker UTC+3): n/a -> MT5 ya cae en grid UTC+2 "
      f"({len(not_in_grid)} fuera de grid) => sin desfase DST en los datos")

# MATCH DE PRECIO sobre TODOS los emparejados (fill ~= Close[i] del motor):
allm = cmp[cmp["offset"].notna()]
price_within1 = int(np.sum(np.abs(allm["dprice"].values) <= 1.0))
print(f"\n% MATCH DE PRECIO (|fill - Close[i]| <= 1 pt) sobre emparejados: "
      f"{100*price_within1/len(mt):.1f}% ({price_within1}/{len(mt)})")
print(f"  excepciones (>1pt): "
      f"{[f'{r.mt5_entry.date()}:{r.dprice:+.1f}' for r in allm[np.abs(allm['dprice'])>1].itertuples()]}")
print(f"  -> son gap overnight/finde o jitter de umbral RSI(13) (TA-Lib vs iRSI) en barra volatil")
print(f"boundary no evaluable: {len(orphan)} (inicio/fin del rango del tester)")

# ----------------- P&L / EQUITY RESIDUAL (solo pares offset 1 contiguos) -----------------
eng_net, mt_net, eng_gross, mt_gross = [], [], [], []
for tr in contig.itertuples():
    i = int(tr.eng_bar)
    eng_gross.append(float(data[i, RET24]))
    eng_net.append(float(res["vector"][i]))
    row = mt[mt["entry_time"] == tr.mt5_entry].iloc[0]
    mt_gross.append((row["exit_price"] - row["entry_price"]) / row["entry_price"])
    mt_net.append(row["profit"] / (row["entry_price"] * CONTRACT * LOTS))
eng_net, mt_net = np.array(eng_net), np.array(mt_net)
eng_gross, mt_gross = np.array(eng_gross), np.array(mt_gross)
print(f"\n--- EQUITY (sobre {len(contig)} pares offset-1 contiguos, base aditiva %) ---")
print(f"GROSS  motor {eng_gross.sum()*100:+.3f}%  | MT5 {mt_gross.sum()*100:+.3f}%  "
      f"| dif {(mt_gross.sum()-eng_gross.sum())*100:+.3f} pts")
print(f"NETO   motor {eng_net.sum()*100:+.3f}%  | MT5 {mt_net.sum()*100:+.3f}%  "
      f"| DIVERGENCIA RESIDUAL {(mt_net.sum()-eng_net.sum())*100:+.3f} pts%")
print(f"MT5 profit USD total (0.10 lote): {mt['profit'].sum():+.2f} USD")

out = cmp.copy()
out.to_csv(os.path.join(ROOT, "CANARIO01_calibracion.csv"), index=False)
print("\nVolcado: CANARIO01_calibracion.csv")
