# FASE 3 (los C2 que faltaron, ya con motor honesto v107):
#   1. M30 XAUUSD  - escala tiempo-equivalente x2 desde H1 (1 H1 = 2 M30):
#      Stag 10000, Min_Trades 600, cooldown 50, senales L2 400.
#   2. EURUSD H4   - escala /4 desde la fila EURUSD H1 (mismo criterio que
#      XAUUSD H4): Stag 3750, Min_Trades 75, cooldown 3, senales 50.
#      Friccion override 0.0001 (~1 pip round-trip Darwinex): la de
#      assets.csv (1.0) esta mal escalada para un precio ~1.1 (83%/trade).
#      PROVISIONAL hasta calibracion canario EURUSD; documentado en BITACORA.
$ErrorActionPreference = "Continue"
Set-Location C:\x1\x1-architect
$env:PYTHONUTF8 = "1"

# 1. M30 XAUUSD
$env:X1_STAG_GLOBAL = "10000"; $env:X1_MIN_TRADES = "600"
$env:X1_COOLDOWN = "50"; $env:X1_L2_MIN_SIGNALS = "400"
.\.venv\Scripts\python.exe -u tools\run_commander_cycle.py 1 XAUUSD *> cycle_run_f3m30.log
New-Item -ItemType Directory -Force experimentos\F3_M30 | Out-Null
Copy-Item COSECHA\AUDIT_XAUUSD_*.json experimentos\F3_M30\ -Force
Copy-Item COSECHA\MASTER_XAUUSD_M30_*.csv experimentos\F3_M30\ -Force -ErrorAction SilentlyContinue
Remove-Item Env:\X1_STAG_GLOBAL, Env:\X1_MIN_TRADES, Env:\X1_COOLDOWN, Env:\X1_L2_MIN_SIGNALS -ErrorAction SilentlyContinue

# 2. EURUSD H4
$env:X1_STAG_GLOBAL = "3750"; $env:X1_MIN_TRADES = "75"
$env:X1_COOLDOWN = "3"; $env:X1_L2_MIN_SIGNALS = "50"
$env:X1_F_POINTS = "0.0001"
.\.venv\Scripts\python.exe -u tools\run_commander_cycle.py 3 EURUSD *> cycle_run_f3eur.log
New-Item -ItemType Directory -Force experimentos\F3_EURH4 | Out-Null
Copy-Item COSECHA\AUDIT_EURUSD_*.json experimentos\F3_EURH4\ -Force
Copy-Item COSECHA\MASTER_EURUSD_H4_*.csv experimentos\F3_EURH4\ -Force -ErrorAction SilentlyContinue
Remove-Item Env:\X1_STAG_GLOBAL, Env:\X1_MIN_TRADES, Env:\X1_COOLDOWN, Env:\X1_L2_MIN_SIGNALS, Env:\X1_F_POINTS -ErrorAction SilentlyContinue

"FASE3 COMPLETA $(Get-Date)" | Out-File -Encoding utf8 fase3_done.txt
