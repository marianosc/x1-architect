# FASE 2 del programa post-fix v107: re-mapeo con el lente corregido.
# Encadena todo el computo para no dejar huecos (leccion operativa de anoche).
$ErrorActionPreference = "Continue"
Set-Location C:\x1\x1-architect
$env:PYTHONUTF8 = "1"

# 0. Archivar MASTERs pre-v107: la re-auditoria retroactiva de L3 los mezclaria
#    con la cosecha vieja (semantica apilada). Se preservan, no se borran.
New-Item -ItemType Directory -Force experimentos\pre_v107_masters | Out-Null
Move-Item COSECHA\MASTER_*.csv experimentos\pre_v107_masters\ -Force -ErrorAction SilentlyContinue

# 1. Ciclo H1 oficial (constitucion intacta)
.\.venv\Scripts\python.exe -u tools\run_commander_cycle.py 0 XAUUSD *> cycle_run_f2h1.log
New-Item -ItemType Directory -Force experimentos\F2_H1 | Out-Null
Copy-Item COSECHA\AUDIT_*.json experimentos\F2_H1\ -Force
Copy-Item COSECHA\MASTER_XAUUSD_H1_*.csv experimentos\F2_H1\ -Force -ErrorAction SilentlyContinue

# 2. Ciclo H4 escalado (mismos overrides que A1)
$env:X1_STAG_GLOBAL = "1250"; $env:X1_MIN_TRADES = "75"
$env:X1_COOLDOWN = "6"; $env:X1_L2_MIN_SIGNALS = "50"
.\.venv\Scripts\python.exe -u tools\run_commander_cycle.py 3 XAUUSD *> cycle_run_f2h4.log
New-Item -ItemType Directory -Force experimentos\F2_H4 | Out-Null
Copy-Item COSECHA\AUDIT_*.json experimentos\F2_H4\ -Force
Copy-Item COSECHA\MASTER_XAUUSD_H4_*.csv experimentos\F2_H4\ -Force -ErrorAction SilentlyContinue
Remove-Item Env:\X1_STAG_GLOBAL, Env:\X1_MIN_TRADES, Env:\X1_COOLDOWN, Env:\X1_L2_MIN_SIGNALS -ErrorAction SilentlyContinue

# 3. Fantasma v107 sobre H1 LONG MOMENTUM (XS_IS 0.55 en la frontera)
.\.venv\Scripts\python.exe L2.py XAUUSD LONG MOMENTUM H1 *> ghost_l2_v107.log
.\.venv\Scripts\python.exe -u tools\ghost_audit.py 20000 1000 *> ghost_run_v107.log
.\.venv\Scripts\python.exe tools\analyze_ghost.py | Out-File -Encoding utf8 experimentos\F2_analisis_fantasma_v107.md

# 4. Re-test B3: contexto H4 sobre H1 con motor honesto
.\.venv\Scripts\python.exe tools\build_h4_context.py *> b3_build_v107.log
foreach ($side in "LONG", "SHORT") {
  foreach ($fam in "MOMENTUM", "TREND", "VOLATILITY", "CYCLE") {
    .\.venv\Scripts\python.exe L2.py XAUUSD $side $fam H1C4 *>> b3_v107.log
    .\.venv\Scripts\python.exe L3.py XAUUSD H1C4 $side $fam *>> b3_v107.log
  }
}
New-Item -ItemType Directory -Force experimentos\F2_H1C4 | Out-Null
Copy-Item COSECHA\AUDIT_*.json experimentos\F2_H1C4\ -Force
Copy-Item COSECHA\MASTER_XAUUSD_H1C4_*.csv experimentos\F2_H1C4\ -Force -ErrorAction SilentlyContinue

"FASE2 COMPLETA $(Get-Date)" | Out-File -Encoding utf8 fase2_done.txt
