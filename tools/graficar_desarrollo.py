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
blocks = [("B0\nmonkey paralelo", "hecho"), ("B1\nfitness CPCV", "hecho"),
          ("B2a\ngramática", "hecho*"), ("B3\nGA + warm-start", "hecho*"),
          ("B4\nDSR + barrido", "hecho*")]
for i, (lab, st) in enumerate(blocks):
    c = VERDE if st == "hecho" else (AMBAR if st.endswith("*") else "#d9d6cc")
    ax.add_patch(plt.Rectangle((i, 0), 0.9, 1, color=c))
    ax.text(i + 0.45, 0.5, lab, ha="center", va="center", fontsize=9,
            color="white" if st != "pend" else GRIS, fontweight="bold")
    if i < len(blocks) - 1:
        ax.annotate("", xy=(i + 1, 0.5), xytext=(i + 0.9, 0.5),
                    arrowprops=dict(arrowstyle="->", color=GRIS))
ax.text(1.55, 1.15, "* B2a construido y probado, pero el control dice que NO aporta aún (B2b en pausa)", color=AMBAR, fontsize=8)
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

# ── B1 tuning — el barrido: por qué Q25 (juez justo = EURGBP sin tendencia) ──
bcsv = os.path.join(ROOT, "experimentos", "barrido_b1.csv")
if os.path.exists(bcsv):
    B = pd.read_csv(bcsv)
    confs = ["pf_is(naive)", "n=1000,median", "n=1000,q25"]
    lab = ["pf_is\n(naive)", "fitness\nmediana", "fitness\nQ25 ✓"]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4))
    x = np.arange(len(confs)); w = 0.38
    for ax, metric, ylab, title in (
            (axL, 'top_long', '% horizonte largo en top-50  (más BAJO = mejor)',
             'De-sesgo de beta (Ret_72/96 en el top)'),
            (axR, 'rho', 'Spearman(métrica , honestidad Z2)',
             'Poder predictivo Z1→Z2')):
        for j, sym in enumerate(('XAUUSD', 'EURGBP')):
            vals = [float(B[(B.config == c) & (B.sym == sym)][metric].iloc[0]) for c in confs]
            cols = [AMBAR if sym == 'XAUUSD' else AZUL]
            bars = ax.bar(x + (j - 0.5) * w, vals, w,
                          color=(AMBAR if sym == 'XAUUSD' else AZUL),
                          label=f"{sym}{' (bull, beta)' if sym=='XAUUSD' else ' (sin tendencia, juez justo)'}")
            for b, v in zip(bars, vals):
                ax.text(b.get_x() + w / 2, v + (1 if metric == 'top_long' else 0.004),
                        f"{v:.0f}" if metric == 'top_long' else f"{v:.2f}", ha="center", fontsize=8)
        ax.set_xticks(x); ax.set_xticklabels(lab); ax.set_title(title, fontsize=10.5)
        ax.set_ylabel(ylab, fontsize=9); ax.legend(fontsize=8)
    fig.suptitle("B1 TUNING — Q25 elegido: en EURGBP (juez sin beta) la mediana NO de-sesga (64% largo) "
                 "y Q25 sí (14%)", fontsize=11.5, y=1.02)
    save(fig, "v108_b1_tuning.png")

# ── B2a — ¿aporta la gramática formulaica? (control orgánico) ──
ccsv = os.path.join(ROOT, "experimentos", "control_b2a.csv")
if os.path.exists(ccsv):
    C = pd.read_csv(ccsv)
    syms = ['XAUUSD', 'EURGBP']
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4))
    # izq: más señales activas (viejo vs mixto)
    x = np.arange(len(syms)); w = 0.38
    vie = [int(C[(C.sym == s) & (C.vocab == 'VIEJA')]['activos'].iloc[0]) for s in syms]
    mix = [int(C[(C.sym == s) & (C.vocab == 'MIXTA')]['activos'].iloc[0]) for s in syms]
    axL.bar(x - w / 2, vie, w, color=GRIS, label="gramática vieja")
    axL.bar(x + w / 2, mix, w, color=VERDE, label="+ formulaica")
    for i, (a, b) in enumerate(zip(vie, mix)):
        axL.text(i - w / 2, a + 4, str(a), ha="center", fontsize=9)
        axL.text(i + w / 2, b + 4, str(b), ha="center", fontsize=9, color=VERDE)
    axL.set_xticks(x); axL.set_xticklabels(syms); axL.set_ylabel("candidatos activos (operan en ≥3 folds)")
    axL.set_title("Los operadores SÍ crean más señales tradeables", fontsize=10.5); axL.legend(fontsize=8)
    # der: pero la transferencia honesta NO mejora (organico CON-form vs SOLO-viejo)
    fm = [float(C[(C.sym == s) & (C.vocab == 'MIXTA')]['form_mk'].iloc[0]) for s in syms]
    om = [float(C[(C.sym == s) & (C.vocab == 'MIXTA')]['old_mk'].iloc[0]) for s in syms]
    axR.bar(x - w / 2, om, w, color=GRIS, label="candidatos SOLO-viejo")
    axR.bar(x + w / 2, fm, w, color=ROJO, label="candidatos CON-formulaico")
    for i, (a, b) in enumerate(zip(om, fm)):
        axR.text(i - w / 2, a + 0.6, f"{a:.0f}", ha="center", fontsize=9)
        axR.text(i + w / 2, b + 0.6, f"{b:.0f}", ha="center", fontsize=9, color=ROJO)
    axR.axhline(50, color=GRIS, ls=":", lw=1)
    axR.set_xticks(x); axR.set_xticklabels(syms); axR.set_ylabel("mk_z2 honesto medio (activos)")
    axR.set_title("...pero NO transfieren mejor (EURGBP: peor)", fontsize=10.5); axR.legend(fontsize=8)
    fig.suptitle("B2a — control orgánico: la gramática formulaica NO aporta (todavía). Más señales, "
                 "no mejor edge OOS → B2b en pausa", fontsize=11, y=1.02)
    save(fig, "v108_b2a_control.png")

# ── B3 — GA: convergencia Z1 vs el holdout Z2 honesto (multiplicidad) ──
import json as _json
gmeta = os.path.join(ROOT, "experimentos", "ga_b3_meta.json")
gwin = os.path.join(ROOT, "experimentos", "ga_b3_winners.csv")
if os.path.exists(gmeta) and os.path.exists(gwin):
    meta = _json.load(open(gmeta)); W = pd.read_csv(gwin).sort_values("mk_oos_z2", ascending=False)
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11, 4.4))
    bh = meta["best_hist"]
    axL.plot(range(len(bh)), bh, color=AZUL, lw=2, marker='o', ms=3)
    axL.set_xlabel("generación"); axL.set_ylabel("mejor fitness Z1 (B1, monkey-OOS Q25)")
    axL.set_title(f"El GA SÍ optimiza Z1: {bh[0]:.0f}→{bh[-1]:.0f}\n{meta['n_unique']:,} individuos únicos evaluados")
    axL.set_ylim(0, 100)
    mk = W["mk_oos_z2"].values
    x = np.arange(len(mk))
    axR.bar(x, mk, color=[VERDE if v >= 90 else GRIS for v in mk])
    axR.axhline(90, color=ROJO, ls="--", lw=1.5); axR.text(0.3, 91.5, "gate real mk_oos 90", color=ROJO, fontsize=9)
    n90 = int((mk >= 90).sum())
    axR.set_xlabel("top-20 ganadores (por fitness Z1)"); axR.set_ylabel("mk_oos en HOLDOUT Z2 (n=5000)")
    axR.set_title(f"...pero NO transfiere a Z2: {n90}/20 pasa (azar ~2/20)\nbinomial p=0,88 → dentro del ruido de 48k pruebas")
    axR.set_ylim(0, 100)
    fig.suptitle("B3 — minero evolutivo (GA + warm-start): optimiza Z1 pero el holdout Z2 no supera el azar "
                 "(multiplicidad) → DSR (B4) decide", fontsize=10.5, y=1.02)
    save(fig, "v108_b3_ga.png")

# ── B4 — barrido multi-activo/TF: el monkey "pasa" pero el DSR deflactado mata ──
bcsv = os.path.join(ROOT, "experimentos", "barrido_b4.csv")
icsv = os.path.join(ROOT, "experimentos", "b4_investigate.csv")
if os.path.exists(bcsv) and os.path.exists(icsv):
    B = pd.read_csv(bcsv); I = pd.read_csv(icsv)
    B["lbl"] = B["sym"] + " " + B["tf"]; B["passpct"] = 100 * B["pass90"] / B["n_top"]
    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.5, 4.6))
    cols = [VERDE if p <= 0.05 else GRIS for p in B["binomial_p"]]
    bars = axL.bar(B["lbl"], B["passpct"], color=cols)
    axL.axhline(10, color=ROJO, ls="--", lw=1.5); axL.text(0.1, 12, "azar ~10%", color=ROJO, fontsize=9)
    for b, p, n in zip(bars, B["passpct"], B["pass90"]):
        axL.text(b.get_x() + b.get_width() / 2, p + 1.5, f"{int(n)}", ha="center", fontsize=8)
    axL.set_ylabel("% del top-20 que pasa el monkey OOS (>=90)")
    axL.set_title("JUEZ 1 — el monkey: 4/7 combos 'baten el azar'\n(verde = binomial p<=0,05) ¿hay edge?")
    axL.tick_params(axis='x', rotation=35, labelsize=8)
    il = I["sym"] + " " + I["tf"]
    axR.bar(il, I["best_dsr"], color=AMBAR)
    axR.axhline(0.95, color=ROJO, ls="--", lw=1.5); axR.text(0.1, 0.90, "umbral DSR 0,95", color=ROJO, fontsize=9)
    for i, (v, no) in enumerate(zip(I["best_dsr"], I["n_oos_med"])):
        axR.text(i, v + 0.02, f"{v:.2f}\n({no} tr)", ha="center", fontsize=8)
    axR.set_ylim(0, 1.0); axR.set_ylabel("mejor DSR (Sharpe deflactado por N)")
    axR.set_title("JUEZ 2 — el DSR (deflactado por ~40k pruebas): 0/4\nel 'edge' era ruido de pocos trades")
    axR.tick_params(axis='x', rotation=20, labelsize=8)
    fig.suptitle("B4 — barrido multi-activo/TF: el monkey marca 4 combos pero el DSR deflactado los MATA a todos "
                 "→ no hay edge que sobreviva N", fontsize=10.5, y=1.02)
    save(fig, "v108_b4_barrido.png")

# ── B5 — price action vs el DSR + capstone: TODA la materia prima OHLC ──
pacsv = os.path.join(ROOT, "experimentos", "pa_b5.csv")
b4icsv = os.path.join(ROOT, "experimentos", "b4_investigate.csv")
if os.path.exists(pacsv) and os.path.exists(b4icsv):
    PA = pd.read_csv(pacsv); B4 = pd.read_csv(b4icsv)
    items = [("XAUUSD H1\ntécnico", 0.031, GRIS)]            # B4 DSR XAUUSD H1
    for _, r in B4.iterrows():
        items.append((f"{r['sym']} {r['tf']}\ntécnico", float(r['best_dsr']), GRIS))
    for _, r in PA.iterrows():
        items.append((f"{r['sym']} {r['tf']}\nprice action", float(r['best_dsr']), AZUL))
    items.sort(key=lambda x: x[1])
    labels = [a for a, _, _ in items]; vals = [b for _, b, _ in items]; cols = [c for _, _, c in items]
    fig, ax = plt.subplots(figsize=(11, 4.6))
    bars = ax.bar(range(len(items)), vals, color=cols)
    ax.axhline(0.95, color=ROJO, ls="--", lw=2); ax.text(0.1, 0.90, "umbral DSR 0,95 (edge real)", color=ROJO, fontsize=10)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8.5)
    ax.set_xticks(range(len(items))); ax.set_xticklabels(labels, fontsize=8)
    ax.set_ylim(0, 1.0); ax.set_ylabel("mejor DSR (Sharpe deflactado por ~30-48k pruebas)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=GRIS, label="indicadores técnicos (B0-B4)"),
                       Patch(color=AZUL, label="acción de precio / geometría (B5)")], loc="upper left", fontsize=9)
    ax.set_title("v108 — la materia prima OHLC, AGOTADA: ningún activo/TF/método supera el DSR\n"
                 "ni osciladores (gris) ni geometría del precio (azul) → el edge NO está en el OHLC",
                 fontsize=11)
    save(fig, "v108_b5_priceaction.png")

print("\nListo: PNGs en docs/desarrollo/")
