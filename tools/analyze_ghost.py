# ##########################################################################
# SYSTEM: X1-ARCHITECT | EXPERIMENTOS A3+A4+B1 (programa nocturno 2026-06-12)
# FILE: tools/analyze_ghost.py
# ROL: Analisis del parquet fantasma:
#   A3 - correlacion (Spearman) de metricas IS contra resultado OOS + deciles
#   A4 - sondas de frontera: matriz monkey_oos x min_pf (mapa, no cosecha)
#   B1 - metricas institucionales: t-stat OOS, PSR, DSR (Bailey/Lopez de
#        Prado, ajustada por ~1M de pruebas) y PBO por CSCV (8 bloques Z1)
# USO: python tools/analyze_ghost.py [ghost_parquet]
# ##########################################################################
import sys
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

GHOST = sys.argv[1] if len(sys.argv) > 1 else r"C:\temp\X1_GHOST_XAUUSD_H1_LONG_MOMENTUM.parquet"
N_TRIALS = 1_000_000  # pruebas de la granja (~1M por ciclo) para el DSR

COOLDOWN = 25  # Constitucion H1; expo > cooldown => el motor APILA posiciones

df = pd.read_parquet(GHOST)
ok = df[(df["err"] == "") & df["pf_oos"].notna() & df["monkey_oos"].notna()].copy()
ok["overlap_oos"] = ok["expo_oos"] / COOLDOWN
honest = ok[ok["expo_oos"] <= COOLDOWN].copy()  # sin solape: EA-implementable tal cual
print(f"# ANALISIS FANTASMA — {len(df):,} candidatos, {len(ok):,} con OOS medible, "
      f"{len(honest):,} SIN solape (expo<=cooldown)\n")

# ================== A2.5: EL ARTEFACTO DE SOLAPAMIENTO ==================
print("## A2.5 — ARTEFACTO: el monkey premia el apilamiento, no el timing\n")
print("El motor imputa Ret_N en cada entrada con cooldown 25: si N>25 simula una")
print("cartera PIRAMIDADA que el EA real (una posicion por vez) nunca ejecutara.")
print("El mono (busyUntil) no puede apilar => pvalue inflado con el solape:\n")
g = ok.groupby("Exit").agg(n=("monkey_oos", "size"),
                           mk_oos_mediana=("monkey_oos", "median"),
                           pct_pasa90=("monkey_oos", lambda s: 100 * np.mean(s >= 90)),
                           expo_med=("expo_oos", "median"))
print("| Exit | n | solape | mk_oos mediana | % pasa 90 |")
print("|---|---|---|---|---|")
for ex, row in g.sort_values("expo_med").iterrows():
    print(f"| {ex} | {row['n']:.0f} | {row['expo_med']/COOLDOWN:.1f}x | "
          f"{row['mk_oos_mediana']:.1f} | {row['pct_pasa90']:.1f}% |")
rho_ov, p_ov = stats.spearmanr(ok["overlap_oos"], ok["monkey_oos"])
print(f"\nSpearman solape vs monkey_oos: **{rho_ov:+.3f}** (p={p_ov:.1e}). "
      f"En los cohortes SIN solape la tasa de paso es ~10-13% = azar (el resultado honesto).\n")

# =========================== A3: CORRELACIONES ===========================
IS_FEATURES = ["PF_L2", "pf_is", "r2_is", "xs_is", "monkey_is", "trades_is",
               "expo_is", "stag", "n_conds", "beta_is", "oer"]
OOS_TARGETS = ["pf_oos", "monkey_oos", "profit_oos", "xs_oos"]

def spearman_table(pool, titulo, min_n=50):
    print(f"### {titulo} (n={len(pool):,})\n")
    print("| metrica IS | vs pf_oos | vs monkey_oos | vs profit_oos | vs xs_oos |")
    print("|---|---|---|---|---|")
    for f in IS_FEATURES:
        if f not in pool.columns: continue
        cells = []
        for t in OOS_TARGETS:
            sub = pool[[f, t]].dropna()
            if len(sub) < min_n:
                cells.append("n/d"); continue
            rho, p = stats.spearmanr(sub[f], sub[t])
            flag = "**" if (abs(rho) >= 0.05 and p < 1e-3) else ""
            cells.append(f"{flag}{rho:+.3f}{flag} (p={p:.1e})")
        print(f"| {f} | " + " | ".join(cells) + " |")
    print()


print("## A3 — Spearman IS -> OOS (la pregunta: ¿que metrica IS predice OOS?)\n")
spearman_table(ok, "Pool COMPLETO (contaminado por el gradiente de solape)")
spearman_table(honest, "Subset HONESTO sin solape (expo<=25: lo que el EA puede ejecutar)")
spearman_table(ok[ok["Exit"] == "Ret_96"], "Cohorte Ret_96 (solape ~constante 3.8x: timing a apalancamiento igual)")

print("\n### Deciles sobre el pool completo (media de pf_oos y % que pasaria monkey_oos>=90)\n")
for f in ["xs_is", "pf_is", "monkey_is", "r2_is"]:
    sub = ok[[f, "pf_oos", "monkey_oos"]].dropna()
    if len(sub) < 500: continue
    sub["dec"] = pd.qcut(sub[f], 10, labels=False, duplicates="drop")
    g = sub.groupby("dec").agg(n=("pf_oos", "size"), pf_oos=("pf_oos", "mean"),
                               mk90=("monkey_oos", lambda s: 100 * np.mean(s >= 90)))
    rng = sub.groupby("dec")[f].agg(["min", "max"])
    print(f"**{f}** (decil 0=bajo, 9=alto):")
    print("| decil | rango | n | pf_oos medio | % monkey_oos>=90 |")
    print("|---|---|---|---|---|")
    for d, row in g.iterrows():
        print(f"| {d} | {rng.loc[d,'min']:.3f}-{rng.loc[d,'max']:.3f} | {row['n']:.0f} "
              f"| {row['pf_oos']:.3f} | {row['mk90']:.1f}% |")
    print()

# =========================== A4: FRONTERA ===========================
print("\n## A4 — Sondas de frontera (mapa del terreno, NO cosecha; etiqueta FRONTERA)\n")
MIN_T_FRONTERA = int(sys.argv[2]) if len(sys.argv) > 2 else 300
for pool, tag in ((ok, "pool completo (CONTAMINADO por solape)"),
                  (honest, "subset honesto sin solape")):
    base_gates = (pool["trades_is"] >= MIN_T_FRONTERA) & (pool["stag"] <= 5000) & \
                 (pool["profit_z1z2"] > 0) & (pool["trades_oos"] >= 2) & (pool["monkey_is"] >= 99)
    print(f"### {tag} — cruzan gates fijos (trades>={MIN_T_FRONTERA}, stag<=5000, profit>0, mk_is>=99): "
          f"{int(base_gates.sum())} de {len(pool):,}\n")
    for xs_filter, xs_tag in ((None, "sin filtro XS"), (0.55, "con XS_IS>=0.55 (umbral candidato, Fase 2)")):
        g = base_gates if xs_filter is None else (base_gates & (pool["xs_is"] >= xs_filter))
        print(f"**{xs_tag}** (cruzan: {int(g.sum())})\n")
        print("| monkey_oos \\ min_pf | 1.25 | 1.15 | 1.05 |")
        print("|---|---|---|---|")
        for mk in (90, 80, 70, 60, 50):
            cells = []
            for pf in (1.25, 1.15, 1.05):
                n = int((g & (pool["pf_is"] >= pf) & (pool["monkey_oos"] >= mk)).sum())
                cells.append(str(n))
            print(f"| >={mk} | " + " | ".join(cells) + " |")
        print()

# =========================== B1: INSTITUCIONALES ===========================
print("\n## B1 — Metricas institucionales (columnas fantasma, no gates)\n")
b = ok[(ok["trades_oos"] >= 10) & (ok["oos_std"] > 0)].copy()
b["sr_oos"] = b["oos_mean"] / b["oos_std"]
b["tstat_oos"] = b["sr_oos"] * np.sqrt(b["trades_oos"])
# PSR contra SR*=0 (Bailey & Lopez de Prado 2012)
denom = np.sqrt(np.maximum(1e-12, 1 - b["oos_skew"] * b["sr_oos"] +
                           (b["oos_kurt"] - 1) / 4.0 * b["sr_oos"] ** 2))
b["psr_oos"] = stats.norm.cdf(b["sr_oos"] * np.sqrt(b["trades_oos"] - 1) / denom)
# DSR: PSR contra SR0 = max esperado de N_TRIALS pruebas sin edge
gamma = 0.5772156649
v_sr = float(b["sr_oos"].var())
sr0 = np.sqrt(v_sr) * ((1 - gamma) * stats.norm.ppf(1 - 1 / N_TRIALS) +
                       gamma * stats.norm.ppf(1 - 1 / (N_TRIALS * np.e)))
b["dsr"] = stats.norm.cdf((b["sr_oos"] - sr0) * np.sqrt(b["trades_oos"] - 1) / denom)
print(f"(n={len(b):,} con >=10 trades OOS | V[SR] del pool={v_sr:.5f} | "
      f"SR0 con N={N_TRIALS:.0e} pruebas = {sr0:.3f} por trade)\n")
print("| metrica | media | p95 | max | n>umbral |")
print("|---|---|---|---|---|")
print(f"| t-stat OOS | {b['tstat_oos'].mean():+.2f} | {b['tstat_oos'].quantile(0.95):+.2f} "
      f"| {b['tstat_oos'].max():+.2f} | {int((b['tstat_oos'] >= 2).sum())} con t>=2 |")
print(f"| PSR OOS | {b['psr_oos'].mean():.3f} | {b['psr_oos'].quantile(0.95):.3f} "
      f"| {b['psr_oos'].max():.3f} | {int((b['psr_oos'] >= 0.95).sum())} con PSR>=0.95 |")
print(f"| DSR (N=1M) | {b['dsr'].mean():.3f} | {b['dsr'].quantile(0.95):.3f} "
      f"| {b['dsr'].max():.3f} | {int((b['dsr'] >= 0.95).sum())} con DSR>=0.95 |")

print("\n### ¿Separan mejor que las nuestras? (Spearman contra pf_oos y monkey_oos)\n")
print("| metrica institucional (IS-side: t-stat de r_is no disponible; se usa OOS-honesto: correlacion entre metricas) |")
for m in ("tstat_oos", "psr_oos", "dsr"):
    rho1, p1 = stats.spearmanr(b[m], b["pf_oos"])
    rho2, p2 = stats.spearmanr(b[m], b["monkey_oos"])
    print(f"- {m}: vs pf_oos {rho1:+.3f} (p={p1:.1e}) | vs monkey_oos {rho2:+.3f} (p={p2:.1e})")

# PBO por CSCV sobre los 8 bloques de Z1
blk_cols = [c for c in df.columns if c.startswith("z1_blk")]
if len(blk_cols) == 8:
    M = ok[blk_cols].values  # n_strats x 8 bloques (profit por bloque)
    n_s = len(M)
    lambdas = []
    for tr_idx in combinations(range(8), 4):
        te_idx = [i for i in range(8) if i not in tr_idx]
        tr_perf = M[:, tr_idx].sum(axis=1)
        te_perf = M[:, te_idx].sum(axis=1)
        best = int(np.argmax(tr_perf))
        # rank relativo del campeon IS en el universo OOS
        omega = (stats.rankdata(te_perf)[best]) / (n_s + 1)
        lambdas.append(np.log(omega / (1 - omega)))
    lambdas = np.array(lambdas)
    pbo = float(np.mean(lambdas < 0))
    print(f"\n### PBO (CSCV, 8 bloques Z1, C(8,4)={len(lambdas)} particiones, "
          f"{n_s:,} estrategias)\n")
    print(f"**PBO = {pbo:.2f}** (probabilidad de que el campeon in-sample quede bajo la "
          f"mediana out-of-sample; >0.5 = seleccion = ruido puro; lambda medio "
          f"{lambdas.mean():+.2f})")
