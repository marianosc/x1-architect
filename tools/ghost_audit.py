# ##########################################################################
# SYSTEM: X1-ARCHITECT | EXPERIMENTO A2 (programa nocturno 2026-06-12)
# FILE: tools/ghost_audit.py
# ROL: MODO FANTASMA - audita una muestra de candidatos SIN matar a nadie.
#      Donde L3 ejecuta (early-return en el primer gate que falla), el
#      fantasma CAPTURA todos los valores de todos los gates por candidato
#      y los vuelca a un parquet para el analisis correlacional IS->OOS.
# USO: python tools/ghost_audit.py [n_sample] [n_monkeys] [raw] [full] [out]
#      Antes hay que generar el pool: python L2.py XAUUSD LONG MOMENTUM H1
#      (ghost NO borra el RAW, a diferencia de L3).
# ##########################################################################
import os, sys, time
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy import stats

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from modules.x1_engine import simulate
from modules.x1_validators import monkey_test, excursion_score

N_SAMPLE = int(sys.argv[1]) if len(sys.argv) > 1 else 20000
N_MONKEYS = int(sys.argv[2]) if len(sys.argv) > 2 else 1000  # fantasma: 1000 alcanza
RAW = sys.argv[3] if len(sys.argv) > 3 else r"C:\temp\X1_RAW_XAUUSD_LONG_MOMENTUM.parquet"
FULL = sys.argv[4] if len(sys.argv) > 4 else r"C:\temp\X1_FULL_XAUUSD_H1.parquet"
OUT = sys.argv[5] if len(sys.argv) > 5 else r"C:\temp\X1_GHOST_XAUUSD_H1_LONG_MOMENTUM.parquet"
COOLDOWN, FRICTION = 25, 1.0  # Constitucion oficial XAUUSD H1
N_BLOCKS_Z1 = 8               # para PBO/CSCV (B1)


def ghost_chunk(data, rows, c_map, ri_map, z_is, z_oos, z1s, n_monkeys):
    """Procesa un chunk de candidatos capturando TODO (sin early returns)."""
    close_all = data[:, c_map['Close']]
    fr_is = FRICTION / float(np.mean(close_all[z_is]))
    fr_oos = FRICTION / float(np.mean(close_all[z_oos]))
    close64 = close_all.astype(np.float64)
    ret_1 = np.zeros(len(close64))
    ret_1[:-1] = (close64[1:] - close64[:-1]) / (close64[:-1] + 1e-9)
    # bordes de los 8 bloques de Z1 (indices absolutos) para PBO
    z1_idx = np.where(z_is)[0]
    blocks = np.array_split(z1_idx, N_BLOCKS_Z1)
    has_hl = 'High' in c_map and 'Low' in c_map

    out = []
    for rule, side, exit_l, pf_l2 in rows:
        rec = {"Entry": rule, "Side": side, "Exit": exit_l, "PF_L2": float(pf_l2),
               "n_conds": len(str(rule).split('|'))}
        try:
            sim = simulate(data, c_map, ri_map, rule, exit_l, side,
                           cooldown=COOLDOWN, friction_points=FRICTION)
        except ValueError:
            rec["err"] = "EXIT"; out.append(rec); continue
        r_all = sim['vector']; durations = sim['durations']
        idx_e = np.where(sim['mask'])[0]
        rec["trades_total"] = int(len(idx_e))
        if len(idx_e) < 5:
            rec["err"] = "SIN_TRADES"; out.append(rec); continue
        rec["err"] = ""

        # --- estancamiento (criterio v106.1: desde z1_start) ---
        r_judge = r_all[z1s:]
        eq = np.cumsum(r_judge); peaks = np.maximum.accumulate(eq)
        hits = np.where(np.diff(peaks, prepend=-1e-9) > 0)[0]
        if len(hits) > 0:
            g_int = np.max(np.diff(hits)) if len(hits) > 1 else 0
            rec["stag"] = int(max(g_int, len(r_judge) - 1 - hits[-1]))
        else:
            rec["stag"] = len(r_judge)
        rec["profit_z1z2"] = float(np.sum(r_judge))

        # --- metricas IS / OOS ---
        r_is = r_all[z_is][r_all[z_is] != 0]
        r_oos = r_all[z_oos][r_all[z_oos] != 0]
        rec["trades_is"], rec["trades_oos"] = int(len(r_is)), int(len(r_oos))
        rec["pf_is"] = float(np.sum(r_is[r_is > 0]) / (abs(np.sum(r_is[r_is < 0])) + 1e-9)) if len(r_is) else np.nan
        rec["pf_oos"] = float(np.sum(r_oos[r_oos > 0]) / (abs(np.sum(r_oos[r_oos < 0])) + 1e-9)) if len(r_oos) else np.nan
        rec["profit_oos"] = float(r_oos.sum()) if len(r_oos) else np.nan
        if len(r_is) >= 3:
            _, _, r_v, _, _ = stats.linregress(np.arange(len(r_is)), np.cumsum(r_is))
            rec["r2_is"] = max(0.0, float(r_v ** 2))
        else:
            rec["r2_is"] = np.nan
        m_is = np.mean(r_is) if len(r_is) else np.nan
        rec["oer"] = float(max(0.0, min((np.mean(r_oos) / m_is) if (len(r_oos) and abs(m_is) > 1e-9) else 0.0, 2.0)))

        # momentos OOS por trade (para PSR/DSR/t-stat en B1)
        if len(r_oos) >= 2:
            rec["oos_mean"] = float(np.mean(r_oos)); rec["oos_std"] = float(np.std(r_oos, ddof=1))
            rec["oos_skew"] = float(stats.skew(r_oos)); rec["oos_kurt"] = float(stats.kurtosis(r_oos, fisher=False))
        else:
            rec["oos_mean"] = rec["oos_std"] = rec["oos_skew"] = rec["oos_kurt"] = np.nan

        # --- monkey IS y OOS (friccion justa, SIEMPRE se computa) ---
        for z_mask, fr, tag in ((z_is, fr_is, "is"), (z_oos, fr_oos, "oos")):
            entries_z = idx_e[z_mask[idx_e]]
            if len(entries_z) < 1:
                rec[f"monkey_{tag}"] = np.nan; rec[f"expo_{tag}"] = np.nan; continue
            pos = np.searchsorted(idx_e, entries_z)
            expo = int(max(1, round(float(np.mean(durations[pos])))))
            rec[f"expo_{tag}"] = expo
            res = monkey_test(ret_1[z_mask], len(entries_z), expo,
                              float(r_all[z_mask].sum()), side,
                              n_monkeys=n_monkeys, seed=12345, friction_per_trade=fr)
            rec[f"monkey_{tag}"] = round(res['pvalue'] * 100.0, 2)
            rec[f"beta_{tag}"] = res['beta']

        # --- excursion score ---
        rec["xs_is"] = rec["xs_oos"] = np.nan
        if has_hl:
            hi, lo, cl = data[:, c_map['High']], data[:, c_map['Low']], data[:, c_map['Close']]
            for z_mask, tag in ((z_is, "is"), (z_oos, "oos")):
                entries_z = idx_e[z_mask[idx_e]]
                if len(entries_z) < 1: continue
                pos = np.searchsorted(idx_e, entries_z)
                xs, _ = excursion_score(hi, lo, cl, entries_z, durations[pos], side)
                rec[f"xs_{tag}"] = round(xs, 4)

        # --- profit por bloque de Z1 (8 bloques, para PBO/CSCV) ---
        for b, bidx in enumerate(blocks):
            rec[f"z1_blk{b}"] = float(r_all[bidx].sum())
        out.append(rec)
    return out


def main():
    t0 = time.time()
    df_f = pd.read_parquet(FULL)
    zone = df_f['Zone'].values
    z_is, z_oos = zone == 1, zone == 2
    z1s = int(np.argmax(z_is))
    base = df_f.drop(columns=['DateTime', 'Zone'], errors='ignore')
    data = base.values.astype(np.float32)
    c_map = {n: i for i, n in enumerate(base.columns)}
    ri_map = {n: i for i, n in enumerate(base.columns) if 'Ret_' in n}

    raw = pd.read_parquet(RAW)
    n = min(N_SAMPLE, len(raw))
    sample = raw.sample(n=n, random_state=42).values
    print(f"[GHOST] pool {len(raw):,} candidatos | muestra {n:,} | monos {N_MONKEYS}")

    chunks = np.array_split(sample, 32)
    res = Parallel(n_jobs=32, backend='loky')(
        delayed(ghost_chunk)(data, ck, c_map, ri_map, z_is, z_oos, z1s, N_MONKEYS)
        for ck in chunks)
    rows = [r for sub in res for r in sub]
    out = pd.DataFrame(rows)
    out.to_parquet(OUT)
    ok = out[out["err"] == ""]
    print(f"[GHOST] {len(out):,} filas ({len(ok):,} con metricas completas) "
          f"-> {OUT} en {time.time()-t0:.0f}s")


if __name__ == '__main__':
    main()
