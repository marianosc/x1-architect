# ##########################################################################
# SYSTEM: X1-ARCHITECT | B4 - DEFLATED SHARPE RATIO (cierre formal XAUUSD H1)
# FILE: tools/b4_dsr.py
# ROL: DSR (Bailey/López de Prado) de los ganadores de B3, deflactado por
#      N=47.928 individuos únicos evaluados. Mismo escepticismo: con tantas
#      pruebas, el mejor Sharpe OOS debe superar el MÁXIMO ESPERADO bajo el
#      azar. Esperado: no significativo (el binomial ya lo anticipó).
# USO: python tools/b4_dsr.py
# ##########################################################################
import os, sys, json
import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.formulaic import expand_formulaic, formulaic_vocabulary

GAMMA = 0.5772156649015329  # Euler-Mascheroni
PARQUET = r'C:\temp\X1_FULL_XAUUSD_H1.parquet'
N_TRIALS = json.load(open('experimentos/ga_b3_meta.json'))['n_unique']

df = pd.read_parquet(PARQUET); zone = df['Zone'].values
z_oos = zone == 2
base = df.drop(columns=['DateTime', 'Zone'], errors='ignore')
data = base.values.astype(np.float32)
cm = {n: i for i, n in enumerate(base.columns)}
ri = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}
data, cm = expand_formulaic(data, cm, formulaic_vocabulary(cm))

W = pd.read_csv('experimentos/ga_b3_winners.csv')
rows = []
for _, w in W.iterrows():
    try:
        sim = simulate(data, cm, ri, w['rule'], w['exit'], w['side'], cooldown=25, friction_points=1.0)
    except ValueError:
        continue
    r = sim['vector'][z_oos]; r = r[r != 0]          # retornos por trade en Z2 (holdout)
    if len(r) < 10:
        continue
    sr = float(np.mean(r) / (np.std(r, ddof=1) + 1e-12))     # Sharpe por trade
    rows.append(dict(rule=w['rule'][:60], mk=w['mk_oos_z2'], T=len(r), sr=sr,
                     skew=float(stats.skew(r)), kurt=float(stats.kurtosis(r, fisher=False))))
D = pd.DataFrame(rows)

# Var[SR] entre las pruebas (estimada con los ganadores; sesga bajo → conservadora)
v_sr = float(D['sr'].var(ddof=1))
sr0 = np.sqrt(v_sr) * ((1 - GAMMA) * stats.norm.ppf(1 - 1.0 / N_TRIALS)
                       + GAMMA * stats.norm.ppf(1 - 1.0 / (N_TRIALS * np.e)))


def psr(sr, sr_star, T, sk, ku):
    denom = np.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4.0 * sr * sr))
    return float(stats.norm.cdf((sr - sr_star) * np.sqrt(T - 1) / denom))


D['psr0'] = D.apply(lambda r: psr(r['sr'], 0.0, r['T'], r['skew'], r['kurt']), axis=1)
D['dsr'] = D.apply(lambda r: psr(r['sr'], sr0, r['T'], r['skew'], r['kurt']), axis=1)
D = D.sort_values('dsr', ascending=False).reset_index(drop=True)
D.to_csv('experimentos/b4_dsr.csv', index=False)

print(f"=== B4 — DSR de XAUUSD H1 (cierre formal) ===")
print(f"N pruebas (individuos únicos del GA): {N_TRIALS:,}")
print(f"SR0 (máximo Sharpe/trade esperado bajo azar con N={N_TRIALS:,}): {sr0:.4f}")
print(f"Var[SR] entre ganadores: {v_sr:.5f}\n")
print(D[['mk', 'T', 'sr', 'psr0', 'dsr']].head(8).to_string(index=False))
best = D.iloc[0]
n_sig = int((D['dsr'] >= 0.95).sum())
print(f"\nmejor DSR: {best['dsr']:.3f} (SR/trade {best['sr']:+.4f} vs SR0 {sr0:.4f}) | "
      f"ganadores con DSR>=0.95: {n_sig}/{len(D)}")
print(f"-> {'SIGNIFICATIVO' if n_sig > 0 else 'NO SIGNIFICATIVO'}: "
      f"{'algún ganador supera el azar deflactado' if n_sig>0 else 'ningún ganador supera el máximo esperado bajo azar con 48k pruebas'}")
print("CSV: experimentos/b4_dsr.csv")
