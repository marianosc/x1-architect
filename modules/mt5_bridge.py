# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.996 - DARWINEX MT5 BRIDGE (CORE)
# FILE: modules/mt5_bridge.py
# ROL: Compilación y Ejecución Automática en MetaTrader 5.
# ##########################################################################
import os
import subprocess
import time
from pathlib import Path

# --- RUTAS SOBERANAS (DARWINEX SSD) ---
MT5_TERMINAL = r"C:\Program Files\Darwinex MetaTrader 5\terminal64.exe"
MT5_EDITOR = r"C:\Program Files\Darwinex MetaTrader 5\metaeditor64.exe"
MT5_EXPERTS = r"C:\Users\pc\AppData\Roaming\MetaQuotes\Terminal\6C3C6A11D1C3791DD4DBF45421BF8028\MQL5\Experts"
MT5_COMMON_FILES = r"C:\Users\pc\AppData\Roaming\MetaQuotes\Terminal\Common\Files"

def compile_and_run_mt5(ea_name, symbol, tf):
    """Compila el EA, genera el .ini y lanza el backtest en Darwinex."""
    ea_mq5_path = os.path.join(MT5_EXPERTS, f"{ea_name}.mq5")
    
    # 1. COMPILACIÓN REMOTA
    # Lanzamos el MetaEditor para convertir el .mq5 en .ex5
    print(f"🔨 MetaEditor compilando {ea_mq5_path}...")
    subprocess.run([MT5_EDITOR, f"/compile:{ea_mq5_path}", "/log"], check=True)
    
    # 2. GENERACIÓN DEL ARCHIVO DE CONFIGURACIÓN (.INI)
    # Este archivo le dice a MT5 qué hacer al abrirse
    config_ini_path = os.path.join(os.getcwd(), "data", "mt5_config.ini")
    
    # Asegurar que la carpeta data existe
    os.makedirs(os.path.dirname(config_ini_path), exist_ok=True)
    
    tf_map = {"H1": "H1", "M30": "M30", "M15": "M15", "H4": "H4"}
    
    ini_content = f"""
[Tester]
Expert={ea_name}.ex5
Symbol={symbol}
Period={tf_map.get(tf, "H1")}
Deposit=10000
Leverage=1:100
Model=1
ExecutionMode=0
Optimization=0
FromDate=2020.01.01
ToDate=2025.01.01
Report=X1_Reality_Report
ReplaceReport=1
ShutdownTerminal=1
Visual=0
"""
    with open(config_ini_path, "w") as f:
        f.write(ini_content)

    # 3. LANZAMIENTO DEL TESTER EN DARWINEX
    print(f"🚀 Lanzando Darwinex MT5 en modo Headless...")
    subprocess.run([MT5_TERMINAL, f"/config:{config_ini_path}"])
    
    # Tiempo de cortesía para que el sistema de archivos de Windows asiente el CSV
    time.sleep(2)
    
    # Devolvemos la ruta donde el EA debió soltar la "verdad" (Truth CSV)
    return os.path.join(MT5_COMMON_FILES, f"X1_TRUTH_{ea_name.replace('X1_', '')}.csv")