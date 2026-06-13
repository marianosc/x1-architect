# Ciclo DIAGNÓSTICO sin L1 (v108, opción b de NOTEBOOK 2026-06-13).
# Igual que run_commander_cycle.py pero SALTEA la refinería L1: el Parquet fresco
# X1_FULL_<SYM>_<TF>.parquet (Dukascopy limpio, zonas por fecha) YA existe en
# C:/temp y está verificado; re-correr L1 lo regeneraría desde el CSV VIEJO de
# data/ (XAUUSD_A_UTC2 = el podrido) y clobbearía el terreno fresco. Por eso se
# arranca directo en los 8 silos L2->L3 sobre el parquet existente.
# Estrena el Min_Trades DINÁMICO (no se setea X1_MIN_TRADES). Constitución intacta.
# USO: run_cycle_no_l1.py [tf_option] [symbol]   (0=H1 1=M30 2=M15 3=H4)
import os, sys, subprocess, time, json
from pathlib import Path

os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
PY = sys.executable
TFOPT = sys.argv[1] if len(sys.argv) > 1 else "0"
SYM = sys.argv[2] if len(sys.argv) > 2 else "XAUUSD"
TF = {"0": "H1", "1": "M30", "2": "M15", "3": "H4"}.get(TFOPT, "H1")

full_parquet = Path("C:/temp") / f"X1_FULL_{SYM.upper()}_{TF.upper()}.parquet"
if not full_parquet.exists():
    print(f"FALTA el parquet fresco {full_parquet} — corré L1 sobre el CSV Dukascopy primero."); sys.exit(1)

TIMINGS = BASE / f"cycle_timings_{SYM}_{TF}_nol1.json"
overrides = {k: v for k, v in os.environ.items() if k.startswith("X1_")}
print(f"### CICLO DIAGNÓSTICO (SIN L1) {SYM}@{TF} | parquet={full_parquet.name} | overrides={overrides or 'NINGUNO'}", flush=True)


def run(tag, args):
    print(f"\n>>>>> {tag} START {time.strftime('%H:%M:%S')}", flush=True)
    t0 = time.time()
    rc = subprocess.run([PY] + args).returncode
    dt = time.time() - t0
    print(f"<<<<< {tag} END rc={rc} {dt:.1f}s", flush=True)
    return round(dt, 1)


t_cycle0 = time.time()
T = {"L1": "SKIPPED (parquet fresco preservado)", "silos": {}, "L5": None, "L4": None}

for side in ["LONG", "SHORT"]:
    for fam in ["MOMENTUM", "TREND", "VOLATILITY", "CYCLE"]:
        k = f"{side}_{fam}"
        t_l2 = run(f"L2 {k}", [str(BASE / "L2.py"), SYM, side, fam, TF])
        t_l3 = run(f"L3 {k}", [str(BASE / "L3.py"), SYM, TF, side, fam])
        T["silos"][k] = {"L2_s": t_l2, "L3_s": t_l3}
        (TIMINGS).write_text(json.dumps(T, indent=2))

T["L5"] = run("L5 consolidacion", [str(BASE / "L5.py"), SYM, TF])
T["L4"] = run("L4", [str(BASE / "L4.py")])
T["total_s"] = round(time.time() - t_cycle0, 1)
(TIMINGS).write_text(json.dumps(T, indent=2))
print(f"\n### CICLO COMPLETO (sin L1) en {T['total_s']}s ({T['total_s']/60:.1f} min)", flush=True)
print(json.dumps(T, indent=2), flush=True)
