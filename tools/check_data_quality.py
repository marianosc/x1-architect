#!/usr/bin/env python
"""
check_data_quality.py - Gate de calidad para data M1 (Dukascopy) antes de minar.

Veredicto por archivo: PASS / WARN / FAIL.
  FAIL : data inusable (no monotona, duplicados, OHLC invalido, sin columnas).
  WARN : usable pero a vigilar (cobertura baja, DST, volumen anomalo, costuras moderadas).
  PASS : limpia.

Mejora central vs la curacion one-off: distingue los gaps de fin de semana / sesion
(saltos LEGITIMOS de apertura) de las COSTURAS intra-sesion, que son la firma del defecto
que pudrio al EURUSD viejo (81 saltos>1%/anio por CSV concatenado con bases distintas).

Umbrales aprobados por Mariano (2026-06-13). Ajustar las constantes de abajo si cambia el criterio.

Uso:
    python tools/check_data_quality.py                       # glob por defecto en DATA_DIR
    python tools/check_data_quality.py ruta1.csv ruta2.csv   # archivos puntuales
    python tools/check_data_quality.py --data-dir "D:\\x" --glob "*dukas*.csv"
"""
import argparse
import gc
import glob
import os
import sys

import numpy as np
import pandas as pd

DATA_DIR_DEFAULT = r"Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON\data"
GLOB_DEFAULT = "*dukas*.csv"

# --- umbrales ---
JUMP_PCT = 1.0             # % de |retorno| que cuenta como salto
GAP_MIN_FOR_REOPEN = 60    # min: por encima, la barra es apertura post-gap -> salto legitimo
SEAM_WARN_PER_YEAR = 10    # costuras intra-sesion/anio -> WARN
SEAM_FAIL_PER_YEAR = 40    # costuras intra-sesion/anio -> FAIL
COVERAGE_WARN_FRAC = 0.50  # anio interior con < 50% de la mediana de filas/anio -> WARN
DST_REOPEN_GAP_MIN = 120   # min: gap que delimita apertura de semana para el test de DST
VOL_SCALE_WARN = 1e6       # mediana de volumen por encima -> escala anomala (informativo)

TIME_COL_CANDIDATES = ["DateTime", "Date", "Timestamp", "Time"]
DATE_FORMAT = "%Y%m%d %H:%M:%S.%f"
SUMMER = [5, 6, 7, 8, 9]
WINTER = [11, 12, 1, 2, 3]


def _load(path):
    cols = list(pd.read_csv(path, nrows=0).columns)
    tcol = next((c for c in TIME_COL_CANDIDATES if c in cols), None)
    missing = [c for c in ["Open", "High", "Low", "Close"] if c not in cols]
    use = [c for c in [tcol, "Open", "High", "Low", "Close", "Volume"] if c in cols]
    df = pd.read_csv(path, usecols=use)
    return df, tcol, missing, cols


def _parse_time(s):
    try:
        return pd.to_datetime(s, format=DATE_FORMAT)
    except (ValueError, TypeError):
        return pd.to_datetime(s, errors="coerce")


def _mode_hour(hours):
    if len(hours) == 0:
        return None
    vals, cts = np.unique(hours, return_counts=True)
    return int(vals[np.argmax(cts)])


def check_file(path):
    name = os.path.basename(path)
    findings = []  # (nivel, mensaje)
    print("=" * 78)
    print("ARCHIVO:", name, f"({os.path.getsize(path) / 1e6:.1f} MB)")

    df, tcol, missing, cols = _load(path)
    if missing or tcol is None:
        msg = f"faltan columnas {missing}" + ("" if tcol else " + sin columna de tiempo")
        print("  columnas:", cols)
        print("  VEREDICTO: FAIL -", msg)
        del df
        gc.collect()
        return "FAIL", [("FAIL", msg)]

    dt = _parse_time(df[tcol])
    n = len(df)
    nat = int(dt.isna().sum())
    print(f"  filas: {n:,} | rango: {dt.min()} -> {dt.max()}")
    if nat:
        findings.append(("FAIL", f"{nat} timestamps no parseables"))

    # --- temporal ---
    if not bool(dt.is_monotonic_increasing):
        findings.append(("FAIL", "timestamps no monotonos crecientes"))
    dups = int(dt.duplicated().sum())
    if dups:
        findings.append(("FAIL", f"{dups} timestamps duplicados"))

    # --- OHLC sanidad ---
    o = df["Open"].to_numpy(float)
    h = df["High"].to_numpy(float)
    lo = df["Low"].to_numpy(float)
    c = df["Close"].to_numpy(float)
    hl = int((h < lo).sum())
    hmax = int((h < np.maximum(o, c)).sum())
    lmin = int((lo > np.minimum(o, c)).sum())
    nonpos = int(((o <= 0) | (h <= 0) | (lo <= 0) | (c <= 0)).sum())
    nan = int(np.isnan(o).sum() + np.isnan(h).sum() + np.isnan(lo).sum() + np.isnan(c).sum())
    print(f"  OHLC: High<Low={hl} High<max(O,C)={hmax} Low>min(O,C)={lmin} precio<=0={nonpos} NaN={nan}")
    if hl + hmax + lmin + nonpos + nan:
        findings.append(("FAIL", f"{hl + hmax + lmin + nonpos + nan} barras con OHLC invalido"))

    # --- cobertura por anio ---
    yr = dt.dt.year.to_numpy()
    years, counts = np.unique(yr, return_counts=True)
    if len(years) >= 3:
        interior = counts[1:-1]
        med = np.median(interior)
        for y, cnt in zip(years[1:-1], interior):
            if cnt < COVERAGE_WARN_FRAC * med:
                findings.append(("WARN", f"cobertura baja {y}: {cnt:,} filas (<{int(COVERAGE_WARN_FRAC*100)}% de mediana {int(med):,})"))

    # --- gaps + costuras intra-sesion vs gaps legitimos ---
    gapmin = dt.diff().dt.total_seconds().to_numpy() / 60.0
    with np.errstate(divide="ignore", invalid="ignore"):
        ret = np.abs(np.concatenate([[np.nan], np.diff(c) / c[:-1]])) * 100.0
    post_gap = gapmin > GAP_MIN_FOR_REOPEN
    seam = (ret > JUMP_PCT) & (~post_gap)
    legit = (ret > JUMP_PCT) & post_gap
    seam_by_year = {int(y): int(seam[yr == y].sum()) for y in years}
    worst_year = max(seam_by_year, key=seam_by_year.get) if seam_by_year else None
    worst = seam_by_year.get(worst_year, 0)
    print(f"  saltos >{JUMP_PCT}%: costuras intra-sesion={int(seam.sum())} | legitimos post-gap={int(legit.sum())}")
    print(f"    peor anio de costuras: {worst_year} -> {worst}")
    if seam.sum():
        mi = int(np.nanargmax(np.where(seam, ret, np.nan)))
        print(f"    max costura intra-sesion: {ret[mi]:.3f}% en {dt.iloc[mi]}")
    if worst >= SEAM_FAIL_PER_YEAR:
        findings.append(("FAIL", f"{worst} costuras intra-sesion en {worst_year} (>= {SEAM_FAIL_PER_YEAR}/anio)"))
    elif worst >= SEAM_WARN_PER_YEAR:
        findings.append(("WARN", f"{worst} costuras intra-sesion en {worst_year} (>= {SEAM_WARN_PER_YEAR}/anio)"))

    # --- DST: hora de apertura (post gap de finde) verano vs invierno ---
    reopen = gapmin >= DST_REOPEN_GAP_MIN
    oh = dt.dt.hour.to_numpy()
    mo = dt.dt.month.to_numpy()
    h_sum = _mode_hour(oh[reopen & np.isin(mo, SUMMER)])
    h_win = _mode_hour(oh[reopen & np.isin(mo, WINTER)])
    print(f"  apertura (hora moda) verano={h_sum} invierno={h_win}")
    if h_sum is not None and h_win is not None and h_sum != h_win:
        findings.append(("WARN", f"posible DST: apertura corre verano={h_sum}h vs invierno={h_win}h"))

    # --- volumen (informativo, NO afecta veredicto: es una constante de la fuente Dukascopy) ---
    if "Volume" in df.columns:
        v = df["Volume"].to_numpy(float)
        vmed = float(np.median(v))
        nota = "  [INFO: escala Dukascopy, no comparable con tick del broker]" if vmed > VOL_SCALE_WARN else ""
        print(f"  volumen: mediana={vmed:.3g} max={np.max(v):.3g} ceros={int((v == 0).sum())}{nota}")

    # --- veredicto ---
    if any(f[0] == "FAIL" for f in findings):
        level = "FAIL"
    elif any(f[0] == "WARN" for f in findings):
        level = "WARN"
    else:
        level = "PASS"
    print(f"  VEREDICTO: {level}")
    for lv, m in findings:
        print(f"    [{lv}] {m}")

    del df, dt
    gc.collect()
    return level, findings


def main():
    ap = argparse.ArgumentParser(description="Gate de calidad de data M1 (Dukascopy).")
    ap.add_argument("files", nargs="*", help="CSV a chequear (si vacio, glob en --data-dir).")
    ap.add_argument("--data-dir", default=DATA_DIR_DEFAULT)
    ap.add_argument("--glob", default=GLOB_DEFAULT)
    args = ap.parse_args()

    paths = args.files or sorted(glob.glob(os.path.join(args.data_dir, args.glob)))
    if not paths:
        print("No se encontraron archivos.", file=sys.stderr)
        sys.exit(2)

    results = []
    for p in paths:
        lvl, _ = check_file(p)
        results.append((os.path.basename(p), lvl))

    print("=" * 78)
    print("RESUMEN")
    for name, lvl in results:
        print(f"  {lvl:5} {name}")
    sys.exit(1 if any(l == "FAIL" for _, l in results) else 0)


if __name__ == "__main__":
    main()
