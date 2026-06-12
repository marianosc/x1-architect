# Ejecuta UN ciclo del commander instrumentado con tiempos por capa, sin bucle
# infinito ni input() interactivo. Llama EXACTAMENTE los mismos scripts y en el
# mismo orden que commander.run_main_commander (L1 -> 8x(L2,L3) -> L5,L4).
# USO: run_commander_cycle.py [tf_option] [symbol]   (0=H1 1=M30 2=M15 3=H4)
# Vuelca cycle_timings_<SYM>_<TF>.json para la autopsia.
import os, sys, subprocess, time, json, glob
from pathlib import Path

# Forzar UTF-8 en este proceso y en TODOS los hijos (L1/L2/L3/L4/L5): cuando la
# salida se redirige a archivo, Windows usa cp1252 y los emojis del log de L2
# rompen con UnicodeEncodeError, matando el minado. PYTHONUTF8 lo evita.
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
PY = sys.executable
# USO: run_commander_cycle.py [tf_option] [symbol]  (tf: 0=H1 1=M30 2=M15 3=H4)
TFOPT = sys.argv[1] if len(sys.argv) > 1 else "0"
SYM = sys.argv[2] if len(sys.argv) > 2 else "XAUUSD"
TF = {"0": "H1", "1": "M30", "2": "M15", "3": "H4"}.get(TFOPT, "H1")

_pref = SYM[:3].upper()
csvs = [f for f in glob.glob(str(DATA / "*.csv")) if _pref in os.path.basename(f).upper()]
if not csvs:
    print(f"No encuentro el CSV de {SYM} en data/"); sys.exit(1)
TARGET_CSV = csvs[0]
TIMINGS = BASE / f"cycle_timings_{SYM}_{TF}.json"
overrides = {k: v for k, v in os.environ.items() if k.startswith("X1_")}
if overrides:
    print(f"### OVERRIDES ACTIVOS: {overrides}", flush=True)


def run(tag, args):
    print(f"\n>>>>> {tag} START {time.strftime('%H:%M:%S')}", flush=True)
    t0 = time.time()
    rc = subprocess.run([PY] + args).returncode
    dt = time.time() - t0
    print(f"<<<<< {tag} END rc={rc} {dt:.1f}s", flush=True)
    return round(dt, 1)


t_cycle0 = time.time()
T = {"L1": None, "silos": {}, "L5": None, "L4": None}
print(f"### CICLO COMMANDER XAUUSD@H1 | inicio {time.strftime('%Y-%m-%d %H:%M:%S')}", flush=True)

T["L1"] = run("L1 refineria", [str(BASE / "L1.py"), TARGET_CSV, TFOPT])

for side in ["LONG", "SHORT"]:
    for fam in ["MOMENTUM", "TREND", "VOLATILITY", "CYCLE"]:
        k = f"{side}_{fam}"
        t_l2 = run(f"L2 {k}", [str(BASE / "L2.py"), SYM, side, fam, TF])
        t_l3 = run(f"L3 {k}", [str(BASE / "L3.py"), SYM, TF, side, fam])
        T["silos"][k] = {"L2_s": t_l2, "L3_s": t_l3}
        (TIMINGS).write_text(json.dumps(T, indent=2))  # checkpoint

T["L5"] = run("L5 consolidacion", [str(BASE / "L5.py"), SYM, TF])
T["L4"] = run("L4", [str(BASE / "L4.py")])
T["total_s"] = round(time.time() - t_cycle0, 1)
(TIMINGS).write_text(json.dumps(T, indent=2))
print(f"\n### CICLO COMPLETO en {T['total_s']}s ({T['total_s']/60:.1f} min)", flush=True)
print(json.dumps(T, indent=2), flush=True)

