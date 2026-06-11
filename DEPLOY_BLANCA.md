# DEPLOY EN BLANCA — checklist ejecutable v106

> PC dedicada de ejecución. El código vive en este repo (clon LOCAL en C:,
> nunca en Z:). El G-Drive (Z:) es solo cinta transportadora de datos/cosecha.
> Si este archivo lo ejecuta una sesión de Claude Code en blanca: seguir las
> fases en orden, verificar cada una antes de pasar a la siguiente, y reportar
> los resultados de las verificaciones.

## Fase 0 — Requisitos

- [ ] Git instalado (`git --version`)
- [ ] **Python 3.12 x64** (¡no 3.14!): numba y la wheel de TA-Lib no soportan
      aún 3.14. Verificar: `python --version`
- [ ] MetaTrader 5 (Darwinex) instalado — anotar la ruta del terminal y la
      carpeta `MQL5\Experts` del usuario actual (las rutas viejas del código
      apuntan a `C:\Users\pc\...`, que era la máquina anterior)
- [ ] Unidad Z: (G-Drive) montada y accesible

## Fase 1 — Clonar el repo (local, fuera de Z:)

```powershell
mkdir C:\x1; cd C:\x1
git clone https://github.com/marianosc/x1-architect.git
cd x1-architect
```
El primer acceso pedirá autorización de GitHub en el navegador (una sola vez).

## Fase 2 — Entorno Python

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```
Si `pip install TA-Lib` falla: descargar la wheel para Python 3.12 desde
https://github.com/cgohlke/talib-build/releases e instalar con
`pip install <archivo>.whl`.

**Verificación**: `python -c "import numba, talib; print('JIT OK')"`

## Fase 3 — Tests (ahora con numba activa)

```powershell
python tests\test_x1_engine.py
python tests\test_x1_validators.py
python tests\test_translator_mql5.py
```
**Verificación**: 26 pruebas OK. La primera ejecución tarda más (compilación JIT).

## Fase 4 — Datos y regeneración de Parquet

Los CSV fuente M1 están en `Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1
PYTHON\data\`. Copiarlos al `data\` del clon (SSD local = velocidad):

```powershell
Copy-Item "Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON\data\*M1*.csv" data\
python L0_setup.py
python L1.py "data\XAUUSD_A_UTC2-M1-No Session.csv" 0
```

**Verificación** (Parquet nuevo con High/Low y ADN v106):
```powershell
python -c "import pandas as pd; df = pd.read_parquet('C:/temp/X1_FULL_XAUUSD_H1.parquet'); print(len(df), 'velas |', len(df.columns), 'cols | High/Low:', 'High' in df.columns, '| ADN nuevo:', 'mom_21_sft' in df.columns)"
```
Esperado: High/Low True, ADN nuevo True, ~285 columnas (213 viejas + 72 nuevas).

## Fase 5 — Smoke audit con el monkey oficial (5000 monos JIT)

```powershell
python tools\smoke_audit_real.py "Z:\Mi unidad\PYTHON\38_42_X1_V_105 SISTEMA X1 PYTHON" 12 5000
```
**Verificación**: corre en segundos por estrategia (no minutos) y reporta
estados FAIL_*/PASS. Con el Parquet regenerado de la Fase 4 en
`COSECHA/DATOS_MERCADO`, las columnas XS dejan de ser NaN.

## Fase 6 — LA PRUEBA DE FUEGO: compilar un EA generado

```powershell
python tools\generate_ea.py "rsi_14_sft <= 30|ema_55_sft <= Close_sft" LONG Ret_24 CANARIO01
```
Genera `CANARIO01.mq5`. Copiarlo a la carpeta `MQL5\Experts` del MT5 de
blanca, abrir MetaEditor y compilar (F7).

**Verificación**: 0 errors, 0 warnings (o solo warnings menores). Repetir con
una salida sintética:
```powershell
python tools\generate_ea.py "cmo_24_sft <= 1.94|mfi_144_sft <= 50.78" SHORT SINTETICA_REVERSE CANARIO02
```

## Fase 7 — Pendientes que se resuelven EN blanca (discutir antes de tocar)

- Actualizar rutas MT5 de `modules/mt5_bridge.py` a las reales de blanca
  (terminal64.exe, MetaEditor, carpeta Experts, Common\Files).
- Backtest del canario en el Strategy Tester y primera calibración
  Python ↔ MT5 (comparar trades del canario contra `x1_engine.simulate`).
- Ciclo completo del commander (minería + auditoría con monkey 99/90).
