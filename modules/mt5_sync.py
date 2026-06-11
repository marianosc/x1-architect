# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.980 - MT5 AUTO-TESTER
# FILE: modules/mt5_sync.py
# ##########################################################################
import os
import subprocess
import time

def run_mt5_backtest(ea_name, symbol, timeframe, from_date, to_date):
    """Lanza MT5, ejecuta backtest y genera reporte."""
    # 1. Rutas (Ajuste estas rutas a su instalación)
    mt5_path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    common_path = os.path.dirname(os.path.abspath(__file__))
    config_file = os.path.join(common_path, "mt5_config.ini")
    report_path = os.path.join(common_path, "mt5_report")

    # 2. CREACIÓN DEL ARCHIVO .INI (Instrucciones para MT5)
    # Aquí configuramos MT5 para que use su EA, su activo y sus fechas
    config_content = f"""
[Tester]
Expert=X1_Experts\\{ea_name}.ex5
Symbol={symbol}
Period={timeframe}
Deposit=10000
Currency=USD
Leverage=1:100
Model=1
ExecutionMode=0
Optimization=0
FromDate={from_date}
ToDate={to_date}
Report={report_path}
ReplaceReport=1
ShutdownTerminal=1
Visual=1
"""
    with open(config_file, "w") as f:
        f.write(config_content)

    # 3. LANZAMIENTO DEL TERMINAL
    # /config indica a MT5 que lea nuestro archivo .ini y ejecute el test
    print(f"🚀 Lanzando MetaTrader 5 para validar Alpha {ea_name}...")
    subprocess.run([mt5_path, f"/config:{config_file}"])
    
    return report_path + ".xml" # MT5 genera un XML con el gráfico