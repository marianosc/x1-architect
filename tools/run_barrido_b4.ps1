# B4: ingesta de los parquets faltantes (gate + L1) y corrida del barrido.
$ErrorActionPreference = "Continue"
Set-Location C:\x1\x1-architect
$env:PYTHONUTF8 = "1"
$DATA = "Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON\data"
$PY = ".\.venv\Scripts\python.exe"

function Ingest($pair, $tfopt, $tflabel) {
  $pq = "C:\temp\X1_FULL_${pair}_${tflabel}.parquet"
  if (Test-Path $pq) { Write-Output "= $pair $tflabel ya existe, salteo L1"; return }
  $csv = Get-ChildItem "$DATA\2026.6.13${pair}_M1_*.csv" -ErrorAction SilentlyContinue | Select-Object -First 1
  if (-not $csv) { Write-Output "! ${pair}: no encuentro CSV Dukascopy"; return }
  Write-Output "== gate + L1 $pair $tflabel ($($csv.Name)) =="
  & $PY tools\check_data_quality.py $csv.FullName 2>&1 | Select-String "VEREDICTO"
  & $PY L1.py $csv.FullName $tfopt 2>&1 | Select-Object -Last 1
}

# H1 forex nuevos
Ingest "EURUSD" "0" "H1"
Ingest "GBPUSD" "0" "H1"
Ingest "USDJPY" "0" "H1"
# H4 (XAUUSD y EURGBP)
Ingest "XAUUSD" "3" "H4"
Ingest "EURGBP" "3" "H4"

Write-Output "=== corriendo barrido GA ==="
& $PY -u tools\run_barrido_b4.py
"BARRIDO B4 COMPLETO $(Get-Date)" | Out-File -Encoding utf8 barrido_b4_done.txt
