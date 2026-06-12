# Genera los PNG numerados de docs/graficos/ para la bitacora visual
# (docs/bitacora.html). Cada grafico documenta un hito/desafio real del
# proyecto con los datos de verdad (calibracion, muro FAIL_GAP, embudo,
# tiempos). Re-correr tras cada hito nuevo y agregar la card en el HTML.
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from modules import x1_engine as eng

OUT = os.path.join(ROOT, "docs", "graficos")
os.makedirs(OUT, exist_ok=True)

VERDE, ROJO, AMBAR, GRIS, AZUL = "#1D9E75", "#E24B4A", "#BA7517", "#5F5E5A", "#2D6CA2"
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "figure.facecolor": "white", "axes.grid": True,
                     "grid.alpha": 0.25, "grid.linewidth": 0.6})

PARQUET = r"C:\temp\X1_FULL_XAUUSD_H1.parquet"
CALIB = os.path.join(ROOT, "CANARIO01_calibracion.csv")
MT5_CSV = r"C:\Users\Pc\AppData\Roaming\MetaQuotes\Terminal\Common\Files\X1_TRUTH_CANARIO01.csv"

df = pd.read_parquet(PARQUET)
dt = pd.to_datetime(df["DateTime"]).reset_index(drop=True)
zone = df["Zone"].values
base = df.drop(columns=["DateTime", "Zone"], errors="ignore")
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if "Ret_" in n}


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"OK  {name}")


# ── 01: esquema de zonas del Parquet y el cambio de criterio (opcion b) ──
fig, ax = plt.subplots(figsize=(10, 3.2))
spans = [(0, "Zona 0 — 'Hist'\n2015-11 → 2018-05\n14.882 velas", "#d9d6cc"),
         (1, "Zona 1 — IS (tribunal del minero)\n2018-05 → 2023-06\n29.766 velas", "#bfe3d5"),
         (2, "Zona 2 — OOS (tribunal final)\n2023-06 → 2025-12\n14.883 velas", "#f5d9a8")]
x0 = 0
for z, label, color in spans:
    w = (zone == z).sum()
    ax.barh(0, w, left=x0, height=0.55, color=color, edgecolor="#999")
    ax.text(x0 + w / 2, 0, label, ha="center", va="center", fontsize=9.5)
    x0 += w
z1s = int(np.argmax(zone == 1))
ax.axvline(z1s, color=ROJO, lw=2.5)
ax.annotate("z1_start: desde aquí se juzga\nestancamiento y profit (v106.1)",
            xy=(z1s, 0.32), xytext=(z1s + 1500, 0.62), color=ROJO, fontsize=10,
            arrowprops=dict(arrowstyle="->", color=ROJO))
ax.text(z1s / 2, -0.45, "contexto: alimenta indicadores,\npero NO ejecuta a nadie",
        ha="center", fontsize=9, color=GRIS, style="italic")
ax.set_xlim(0, len(zone)); ax.set_ylim(-0.7, 0.85)
ax.axis("off")
ax.set_title("Zonas del Parquet XAUUSD H1 (59.531 velas) — Zona 0 = contexto, no tribunal (veredicto ciclo 1)")
save(fig, "01_esquema_zonas_z1start.png")

# ── 02: la prueba decisiva de la calibracion: fill MT5 vs Close[i] ──
cal = pd.read_csv(CALIB)
d1 = cal[(cal["offset"] == 1) & (cal["gap_h"] <= 1.5)]["dprice"].dropna().values
fig, ax = plt.subplots(figsize=(8.5, 4.2))
ax.hist(d1, bins=24, color=VERDE, edgecolor="white", alpha=0.9)
ax.axvline(0, color=GRIS, lw=1, ls="--")
ax.axvline(d1.mean(), color=ROJO, lw=2)
ax.annotate(f"media +{d1.mean():.3f} pts\n= medio-spread del ask",
            xy=(d1.mean(), ax.get_ylim()[1] * 0.82), xytext=(0.26, ax.get_ylim()[1] * 0.74),
            color=ROJO, fontsize=10, arrowprops=dict(arrowstyle="->", color=ROJO))
ax.set_xlabel("fill del EA − Close[i] del motor (puntos)")
ax.set_ylabel("trades")
ax.set_title("La sincronía probada por PRECIO: el EA rellena al open de la vela i+1 ≈ Close[i] + spread/2\n"
             f"({len(d1)} pares contiguos, 100% dentro de ±0.5 pt — el offset +1 NO era un bug)")
save(fig, "02_calibracion_fill_vs_close.png")

# ── 03: equity motor vs MT5 (los 107 pares sincronizados) ──
RULE = "rsi_13_sft <= 30|ema_55_sft >= Close_sft"
res = eng.simulate(data, cm, ri, RULE, "Ret_24", "LONG", cooldown=25, friction_points=1.0)
mt = pd.read_csv(MT5_CSV, sep="\t")
mt["entry_time"] = pd.to_datetime(mt["entry_time"], format="%Y.%m.%d %H:%M")
pares = cal[(cal["offset"] == 1) & (cal["gap_h"] <= 1.5)].copy()
pares["mt5_entry"] = pd.to_datetime(pares["mt5_entry"])
eng_net, mt_net, fechas = [], [], []
for tr in pares.itertuples():
    i = int(tr.eng_bar)
    eng_net.append(float(res["vector"][i]))
    row = mt[mt["entry_time"] == tr.mt5_entry].iloc[0]
    mt_net.append(row["profit"] / (row["entry_price"] * 100.0 * 0.10))
    fechas.append(dt[i])
eng_eq = np.cumsum(eng_net) * 100
mt_eq = np.cumsum(mt_net) * 100
fig, ax = plt.subplots(figsize=(9.5, 4.4))
ax.plot(fechas, eng_eq, color=AZUL, lw=2, label="x1_engine.simulate (fricción 1.0)")
ax.plot(fechas, mt_eq, color=AMBAR, lw=1.6, ls="--", label="Strategy Tester Darwinex (real)")
ax.set_ylabel("equity acumulada (%) — base aditiva")
ax.legend(loc="lower left")
ax.set_title("Calibración cerrada: motor vs MT5 sobre los 107 pares sincronizados (CANARIO01, Zona 2)\n"
             f"divergencia residual final: {mt_eq[-1] - eng_eq[-1]:+.3f} pts% (objetivo < 0.5)")
ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
save(fig, "03_calibracion_equity_motor_vs_mt5.png")

# ── 04: el muro FAIL_GAP del ciclo 1 ──
MASTER = r"Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON\COSECHA\MASTER_XAUUSD_H1_SHORT_MOMENTUM.csv"
r = pd.read_csv(MASTER).iloc[1]  # la regla con gap 22.046 (tiene picos visibles)
sim = eng.simulate(data, cm, ri, r["Entry"], r["Exit"], r["Side"], cooldown=25, friction_points=1.0)
eq = np.cumsum(sim["vector"]) * 100
peaks = np.maximum.accumulate(eq)
hits = np.where(np.diff(peaks, prepend=-1e-9) > 0)[0]
gaps = np.diff(hits); k = int(np.argmax(gaps))
fig, ax = plt.subplots(figsize=(10, 4.6))
for z, c in ((0, "#eceae2"), (1, "#e2f1ea"), (2, "#f8ecd4")):
    idx = np.where(zone == z)[0]
    ax.axvspan(dt[idx[0]], dt[idx[-1]], color=c, zorder=0)
ax.plot(dt, eq, color=AZUL, lw=1.1, label="equity (fricción 1.0)")
ax.plot(dt, peaks, color=VERDE, lw=1.0, ls=":", label="máximo histórico (peaks)")
ax.axvspan(dt[hits[k]], dt[hits[k + 1]], color=ROJO, alpha=0.18)
ax.annotate(f"{int(gaps[k]):,} velas sin máximo nuevo\n(umbral Stag_Global = 5.000)".replace(",", "."),
            xy=(dt[hits[k] + int(gaps[k] / 2)], peaks[hits[k]]),
            xytext=(dt[hits[k] + int(gaps[k] / 2) + 4000], peaks[hits[k]] - (eq.max() - eq.min()) * 0.38),
            ha="center", color=ROJO, fontsize=10,
            bbox=dict(boxstyle="round", fc="white", ec=ROJO, alpha=0.9),
            arrowprops=dict(arrowstyle="->", color=ROJO))
ax.text(dt[3000], eq.min(), "Zona 0", fontsize=9, color=GRIS)
ax.text(dt[z1s + 3000], eq.min(), "Zona 1 (IS)", fontsize=9, color=GRIS)
ax.text(dt[int(np.argmax(zone == 2)) + 3000], eq.min(), "Zona 2 (OOS)", fontsize=9, color=GRIS)
ax.set_ylabel("equity (%)")
ax.legend(loc="upper left")
ax.set_title("El muro FAIL_GAP del ciclo 1: con fricción 1.0 las equity pasan >5.000 velas sin máximos nuevos\n"
             "(regla real del MASTER v105 — el 99,9998% de 1.05M candidatos murió aquí)")
save(fig, "04_muro_failgap_ciclo1.png")

# ── 05: el embudo, ciclo 1 vs ciclo 2 (datos de los AUDIT json) ──
etapas = ["Candidatos\n(L2)", "Cruzan\nFAIL_GAP", "Cruzan\nTRADES/PF", "Llegan al\nMONKEY", "PASS\n(cosecha)"]
c1 = [1050495, 2, 0, 0, 0]
c2 = [1050122, 375, 209, 209, 0]
x = np.arange(len(etapas)); w = 0.38
fig, ax = plt.subplots(figsize=(9.5, 4.6))
b1 = ax.bar(x - w / 2, np.maximum(c1, 0.6), w, color="#c9c6ba", label="Ciclo 1 (gap sobre toda la historia)")
b2 = ax.bar(x + w / 2, np.maximum(c2, 0.6), w, color=VERDE, label="Ciclo 2 (Zona 0 = contexto)")
ax.set_yscale("log"); ax.set_ylim(0.5, 4e6)
def fmt(v):
    return f"{v/1e6:.2f}M" if v >= 1e6 else f"{v:,}".replace(",", ".")
for bars, vals in ((b1, c1), (b2, c2)):
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() * 1.25,
                fmt(v), ha="center", fontsize=9,
                fontweight="bold" if v else "normal")
ax.set_xticks(x, etapas)
ax.set_ylabel("candidatos (escala log)")
ax.legend()
ax.set_title("El embudo respira: 375 candidatos cruzan el gap en el ciclo 2 (vs 2) y el monkey ejecuta por primera vez\n"
             "verdugo final: FAIL_MONKEY_OOS (166/166 finalistas muertos en el listón 90%) — cosecha 0 = dato válido")
save(fig, "05_embudo_ciclo1_vs_ciclo2.png")

# ── 06: tiempos por capa y el costo real del monkey ──
silos = ["L MOM", "L TREND", "L VOL", "L CYCLE", "S MOM", "S TREND", "S VOL", "S CYCLE"]
l2 = [20.7, 20.9, 20.6, 20.8, 20.2, 20.5, 20.3, 20.3]
l3c1 = [35.7, 33.7, 37.9, 32.6, 6.2, 6.9, 5.6, 4.9]
l3c2 = [67.9, 35.9, 34.0, 40.6, 6.4, 6.7, 5.8, 4.8]
x = np.arange(len(silos)); w = 0.27
fig, ax = plt.subplots(figsize=(9.5, 4.4))
ax.bar(x - w, l2, w, color="#c9c6ba", label="L2 minería (500k hipótesis)")
ax.bar(x, l3c1, w, color=AZUL, label="L3 ciclo 1 (monkey nunca corre)")
ax.bar(x + w, l3c2, w, color=AMBAR, label="L3 ciclo 2 (monkey ejecuta)")
ax.annotate("+32 s = JIT del kernel del monkey\n(primera vez, queda cacheado)",
            xy=(0 + w, 67.9), xytext=(1.6, 55), fontsize=9, color=AMBAR,
            bbox=dict(boxstyle="round", fc="white", ec=AMBAR, alpha=0.9),
            arrowprops=dict(arrowstyle="->", color=AMBAR))
ax.set_xticks(x, silos)
ax.set_ylabel("segundos")
ax.legend(loc="upper right")
ax.set_title("Tiempos por silo (Ryzen 9 9950X3D, 32 procesos, numba): ciclo completo ~6 min\n"
             "monkey a 5.000 monos ≈ 20-80 ms por llamada — NO es cuello de botella")
save(fig, "06_tiempos_capas_monkey.png")

print("\nListo: PNGs en docs/graficos/")
