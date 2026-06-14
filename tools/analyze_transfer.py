# Analiza la transferencia IS->OOS de los sobrevivientes a PF>=1.25 (dump del waterfall
# de L3, X1_DUMP_TRANSFER). Reporta: distribución de pf_oos, Spearman rank(pf_is)<->
# rank(pf_oos), y la maldición del ganador (decil superior de pf_is vs el resto).
# USO: analyze_transfer.py <csv>
import sys
import numpy as np, pandas as pd
from scipy import stats

CSV = sys.argv[1] if len(sys.argv) > 1 else "C:/temp/transfer_xauusd_h1.csv"
df = pd.read_csv(CSV)
n = len(df)
print(f"=== TRANSFERENCIA IS->OOS | {CSV} | {n:,} candidatos (cruzan al gate del monkey) ===")
print(f"Por side: {df['side'].value_counts().to_dict()}")
print(f"Por exit: {df['exit'].value_counts().to_dict()}")

po = df['pf_oos'].values
pi = df['pf_is'].values
q = np.percentile(po, [25, 50, 75])
print(f"\n--- pf_oos (PF en Z2 fresca 2022-26) ---")
print(f"  mediana {q[1]:.3f} | Q1 {q[0]:.3f} | Q3 {q[2]:.3f} | media {np.mean(po):.3f}")
print(f"  %% pf_oos >= 1.25: {100*np.mean(po>=1.25):.1f}%  |  %% >= 1.0: {100*np.mean(po>=1.0):.1f}%")
print(f"  pf_is: mediana {np.median(pi):.3f} | Q1 {np.percentile(pi,25):.3f} | Q3 {np.percentile(pi,75):.3f}")

rho, pval = stats.spearmanr(pi, po)
print(f"\n--- Spearman rank(pf_is) <-> rank(pf_oos) ---")
print(f"  GLOBAL: rho = {rho:+.4f}  (p = {pval:.2e}, n={n:,})")
# Control del confound ENTRE-EXITS: el rho global puede ser espurio si Ret_96 tiene a la
# vez pf_is y pf_oos más altos (bull). Spearman DENTRO de cada exit (>=200 candidatos).
print(f"  Dentro de cada exit (saca el confound entre-horizontes):")
within = {}
for ex, sub in df.groupby('exit'):
    if len(sub) >= 200:
        r, p = stats.spearmanr(sub['pf_is'], sub['pf_oos'])
        within[ex] = (r, p, len(sub))
        print(f"    {ex:<20} n={len(sub):>5}  rho={r:+.4f}  (p={p:.2e})")
max_within = max((r for r, p, nn in within.values() if p < 0.01), default=0.0)

# Maldición del ganador: decil superior de pf_is vs el resto
dec = np.percentile(pi, 90)
top = po[pi >= dec]; rest = po[pi < dec]
print(f"\n--- Maldición del ganador (decil superior IS: pf_is >= {dec:.3f}) ---")
print(f"  decil TOP IS (n={len(top):,}): pf_oos mediana {np.median(top):.3f} | media {np.mean(top):.3f} | %>=1.0 {100*np.mean(top>=1.0):.1f}%")
print(f"  resto         (n={len(rest):,}): pf_oos mediana {np.median(rest):.3f} | media {np.mean(rest):.3f} | %>=1.0 {100*np.mean(rest>=1.0):.1f}%")
print(f"  delta mediana (top - resto): {np.median(top)-np.median(rest):+.3f}")

# Deciles de pf_is -> pf_oos medio (curva de transferencia)
print(f"\n--- Curva de transferencia: pf_oos por decil de pf_is ---")
df['dec_is'] = pd.qcut(df['pf_is'], 10, labels=False, duplicates='drop')
g = df.groupby('dec_is')['pf_oos'].agg(['median', 'mean', lambda x: 100*np.mean(x>=1.0)])
g.columns = ['pf_oos_med', 'pf_oos_mean', 'pct>=1.0']
print(g.round(3).to_string())

# VEREDICTO con los 3 criterios de NOTEBOOK (medianas/Spearman = robustos a outliers;
# el mean de pf_oos está dominado por PF≈inf de candidatos sin perdedores en OOS, se ignora).
# CAVEAT de régimen: mediana pf_oos > 1 NO prueba edge -> Z2 2022-26 es un bull del oro y el
# 99% del pool es LONG de horizonte largo (surfea la deriva). El juez es la TRANSFERENCIA.
print(f"\n=== VEREDICTO (criterios NOTEBOOK, robustos) ===")
wc = np.median(top) - np.median(rest)            # maldición del ganador (negativo = curse)
print(f"  Spearman GLOBAL {rho:+.4f} (rho^2={rho**2*100:.2f}% var) — pero DILUIDO entre-exits.")
print(f"  Spearman DENTRO de exit (máx sig.): {max_within:+.4f} (rho^2={max_within**2*100:.2f}% var)")
print(f"  Maldición del ganador (global): decil top {np.median(top):.3f} vs resto {np.median(rest):.3f} -> {wc:+.3f}")
print(f"  pf_oos mediana {np.median(po):.3f} (>1 pero CONFUNDIDO por el bull 2022-26: 99% LONG largo)")
if max_within >= 0.10:
    print(f"  -> Transferencia DÉBIL pero ROBUSTA dentro de horizontes largos (rho~{max_within:.2f}).")
    print(f"  -> NO es anti-edge limpio. Branch 2 de NOTEBOOK: monkey n=1000 sobre la COLA")
    print(f"     (top pf_is de Ret_72/Ret_96) para separar skill de exposición al bull.")
else:
    print(f"  -> SIN transferencia material + maldición del ganador -> ANTI-EDGE -> v108.1 gramática")
