# Genera los PNG del log visual de desarrollo (docs/desarrollo.html).
# Cada avance numérico deja su gráfico acá. Re-correr tras cada bloque.
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "desarrollo")
os.makedirs(OUT, exist_ok=True)
VERDE, ROJO, AMBAR, GRIS, AZUL = "#1D9E75", "#E24B4A", "#BA7517", "#5F5E5A", "#2D6CA2"
plt.rcParams.update({"font.family": "Segoe UI", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": "white",
                     "axes.grid": True, "grid.alpha": 0.25})


def save(fig, name):
    fig.savefig(os.path.join(OUT, name), dpi=130, bbox_inches="tight"); plt.close(fig)
    print("OK", name)


# ── v108 — línea de tiempo de bloques del minero ──
fig, ax = plt.subplots(figsize=(10, 2.4))
blocks = [("B0\nmonkey paralelo", "hecho"), ("B1\nfitness CPCV", "hecho*"),
          ("B2\ngramática", "pend"), ("B3\nGA + warm-start", "pend"),
          ("B4\nDSR + holdout + MT5", "pend")]
for i, (lab, st) in enumerate(blocks):
    c = VERDE if st == "hecho" else (AMBAR if st.endswith("*") else "#d9d6cc")
    ax.add_patch(plt.Rectangle((i, 0), 0.9, 1, color=c))
    ax.text(i + 0.45, 0.5, lab, ha="center", va="center", fontsize=9,
            color="white" if st != "pend" else GRIS, fontweight="bold")
    if i < len(blocks) - 1:
        ax.annotate("", xy=(i + 1, 0.5), xytext=(i + 0.9, 0.5),
                    arrowprops=dict(arrowstyle="->", color=GRIS))
ax.text(1.45, 1.15, "* mecanismo OK, tuning a decidir por NOTEBOOK", color=AMBAR, fontsize=8.5)
ax.set_xlim(-0.1, 5); ax.set_ylim(-0.1, 1.4); ax.axis("off")
ax.set_title("Minero evolutivo v108 — rumbo Python puro (opción C)", fontsize=12)
save(fig, "v108_timeline.png")

# ── B0 — speedup del monkey paralelo ──
th = [1, 8, 16, 32]; sp = [1.0, 7.9, 14.0, 15.9]
fig, ax = plt.subplots(figsize=(7.5, 4.2))
bars = ax.bar([str(t) for t in th], sp, color=[GRIS, AZUL, AZUL, VERDE])
for b, s in zip(bars, sp):
    ax.text(b.get_x() + b.get_width() / 2, s + 0.3, f"{s:.1f}×", ha="center", fontweight="bold")
ax.set_xlabel("threads"); ax.set_ylabel("speedup vs serial")
ax.set_title("B0 — Monkey paralelo (nogil + monkey_batch), paridad BIT-IDÉNTICA\n"
             "los 10.931×2 jobs: de ~5,5 h serial a ~14 min (15,9× en 32 cores)")
ax.annotate("paridad serial==paralelo\nverificada (test 4/4)", xy=(3, 15.9),
            xytext=(1.4, 13), fontsize=9, color=VERDE,
            bbox=dict(boxstyle="round", fc="white", ec=VERDE),
            arrowprops=dict(arrowstyle="->", color=VERDE))
save(fig, "v108_b0_speedup.png")

# ── B1 — Spearman: quién predice la honestidad Z2 (mk_oos_z2) ──
labels = ["pf_is\n(naive minero)", "fitness B1\n(mediana)", "fitness B1\n(Q25)", "pf_oos\n(ve Z2, ref)"]
rho = [0.168, 0.202, 0.192, 0.790]
cols = [GRIS, VERDE, "#7FBF9B", "#c9c6ba"]
fig, ax = plt.subplots(figsize=(8.5, 4.4))
bars = ax.bar(labels, rho, color=cols)
for b, r in zip(bars, rho):
    ax.text(b.get_x() + b.get_width() / 2, r + 0.012, f"+{r:.3f}", ha="center", fontweight="bold")
ax.axhline(0.168, color=GRIS, ls="--", lw=1)
ax.text(2.6, 0.18, "el fitness solo-Z1 supera al naive solo-Z1", color=VERDE, fontsize=9)
ax.set_ylabel("Spearman(métrica solo-Z1 , mk_oos_z2 honesto)")
ax.set_ylim(0, 0.88)
ax.set_title("B1 — ¿Qué métrica de Z1 predice la honestidad en Z2 (2022-26)?\n"
             "pf_oos no cuenta (ve Z2 directo); la pelea justa es pf_is vs fitness, ambos solo-Z1")
save(fig, "v108_b1_spearman.png")

# ── B1 — composición del top-50: el fitness de-sesga el horizonte beta ──
grp = ["pool entero", "top-50 por pf_is", "top-50 por fitness"]
pct96 = [80, 58, 38]; mkz2 = [42.5, 58.2, 47.0]
x = np.arange(len(grp)); w = 0.38
fig, ax = plt.subplots(figsize=(8.5, 4.4))
ax2 = ax.twinx()
b1 = ax.bar(x - w / 2, pct96, w, color=AMBAR, label="% Ret_96 (horizonte beta)")
b2 = ax2.bar(x + w / 2, mkz2, w, color=AZUL, label="mk_oos_z2 medio (honestidad)")
for b, v in zip(b1, pct96): ax.text(b.get_x() + w / 2, v + 1, f"{v}%", ha="center", color=AMBAR, fontweight="bold")
for b, v in zip(b2, mkz2): ax2.text(b.get_x() + w / 2, v + 1, f"{v:.0f}", ha="center", color=AZUL, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(grp)
ax.set_ylabel("% Ret_96", color=AMBAR); ax2.set_ylabel("mk_oos_z2 medio", color=AZUL)
ax.set_ylim(0, 95); ax2.set_ylim(0, 70)
ax.set_title("B1 — el fitness de-sesga la beta (Ret_96: 80%→38%) pero su top NO afina aún\n"
             "(el top por pf_is sigue con mejor mk_oos_z2: 58 vs 47 — pendiente de tuning)")
save(fig, "v108_b1_top50.png")

# ── B1 — scatter fitness vs honestidad Z2 (desde el CSV real) ──
csv = os.path.join(ROOT, "experimentos", "validate_fitness_b1.csv")
if os.path.exists(csv):
    R = pd.read_csv(csv)
    fig, ax = plt.subplots(figsize=(8.5, 5))
    is96 = R["exit"] == "Ret_96"
    ax.scatter(R.loc[~is96, "fitness"], R.loc[~is96, "mk_oos_z2"], s=8, alpha=0.4,
               color=VERDE, label="otros exits")
    ax.scatter(R.loc[is96, "fitness"], R.loc[is96, "mk_oos_z2"], s=8, alpha=0.3,
               color=AMBAR, label="Ret_96 (beta largo)")
    ax.axhline(90, color=ROJO, ls="--", lw=1); ax.text(2, 91.5, "listón mk_oos 90", color=ROJO, fontsize=8.5)
    ax.set_xlabel("fitness B1 (mediana mk_oos por fold, solo Z1)")
    ax.set_ylabel("mk_oos_z2 honesto (verdad OOS, n=1000)")
    ax.legend(loc="upper left", fontsize=9)
    ax.set_title(f"B1 — fitness (Z1) vs honestidad (Z2) sobre {len(R):,} candidatos frescos\n"
                 "tendencia positiva real (Spearman +0,20) pero ruidosa: hay señal débil, no oro")
    save(fig, "v108_b1_scatter.png")

print("\nListo: PNGs en docs/desarrollo/")
