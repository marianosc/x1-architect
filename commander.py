# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.170 - SILO COMMANDER (LOCAL BEAST)
# FILE: commander.py
# ROL: Orquestador Central Local-Only para Ryzen 9 9950X.
# ##########################################################################
import os
import subprocess
import glob
import sys
import time
import platform
import re
import json
import pandas as pd
from pathlib import Path

# --- CONFIGURACIÓN DE RUTAS ABSOLUTAS (SSD SOBERANÍA) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
COSECHA_DIR = os.path.join(BASE_DIR, "COSECHA")
ASSETS_PATH = os.path.join(DATA_DIR, "assets.csv")
FUSE_PATH = os.path.join(DATA_DIR, "audit_config.json")

# Asegurar infraestructura local
os.makedirs(COSECHA_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

def update_farm_heartbeat(cycle, symbol, tf, side, family):
    """Latido local atómico para evitar colisiones con pulse.py."""
    heartbeat_path = os.path.join(DATA_DIR, "farm_heartbeat.json")
    status = {
        "cycle": cycle, "symbol": symbol, "tf": tf, "side": side,
        "family": family, "timestamp": time.time()
    }
    try:
        # Escribimos primero en un archivo temporal y luego renombramos (Atómico en SSD)
        temp_path = heartbeat_path + ".tmp"
        with open(temp_path, 'w') as f:
            json.dump(status, f)
        os.replace(temp_path, heartbeat_path) # Reemplazo instantáneo
    except:
        pass

def clear_terminal(): 
    os.system('cls' if os.name == 'nt' else 'clear')

def get_clean_symbol(filename):
    base_name = os.path.basename(filename).upper()
    symbol_match = re.search(r'([A-Z0-9]{3,15})', base_name)
    return symbol_match.group(1) if symbol_match else "UNKNOWN"

def print_audit_report(symbol, side, family, timeframe):
    """v104.170: Reporte Forense Local Sincronizado."""
    json_filename = f"AUDIT_{symbol}_{side}_{family}.json"
    json_full_path = os.path.join(COSECHA_DIR, json_filename)
    
    # Radar de espera (Máximo 2 segundos para SSD)
    for _ in range(10):
        if os.path.exists(json_full_path): break
        time.sleep(0.2)
    
    if not os.path.exists(json_full_path):
        print(f"   \033[91m[!] ALERTA: Auditor L3 no generó reporte para {family}\033[0m")
        return

    try:
        with open(json_full_path, 'r') as file_handle:
            audit_data = json.load(file_handle)
        
        # Mapeo de etiquetas v104
        qual = audit_data.get('qualified', 0)
        harv = audit_data.get('harvested', 0)
        fail_d = audit_data.get('details', {})
        
        print(f"\n   \033[96m[AUTOPSIA L3] {side}-{family} | {timeframe}\033[0m")
        print(f"   \033[92mCALIFICADOS: {qual:<6} | COSECHADOS (TOP 500): {harv:<6}\033[0m")
        print(f"   " + "-"*62)
        
        # Mostrar solo los filtros que han ejecutado Alphas
        for cause, count in fail_d.items():
            if count > 0 and cause != "PASS":
                color = "\033[91m" if "FAIL" in cause else "\033[90m"
                print(f"   {color}{cause:<20}: {count:>8}\033[0m")
        
        print(f"   " + "-"*62)
    except: pass

def run_main_commander():
    clear_terminal()
    print(f"\n" + "="*75)
    print(f"   X1-ARCHITECT v104.170 | LOCAL ORCHESTRATOR | {platform.node()}")
    print(f"   RYZEN 9 9950X - SOBERANÍA SSD ACTIVA")
    print("="*75 + "\033[0m")
    
    # 1. DETECCIÓN DE DATOS
    raw_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))
    valid_files = [f for f in raw_files if all(x not in os.path.basename(f).upper() for x in ["MASTER", "ASSETS", "FACTORY", "X1", "_CLEAN", "INYECTOR"])]
    
    if not valid_files: 
        print(f"\033[91m[ERROR] Coloque sus archivos CSV en la carpeta: {DATA_DIR}\033[0m"); return

    print(f"\nFUENTES DE DATOS LOCALES:")
    for i, file_path in enumerate(valid_files):
        print(f"  [{i}] {os.path.basename(file_path)}")
    
    try:
        selection_idx = int(input("\nÍndice del activo maestro: "))
        target_csv = valid_files[selection_idx]
    except: return

    target_symbol = get_clean_symbol(target_csv)
    tf_mapping = {"0": "H1", "1": "M30", "2": "M15", "3": "H4"}
    
    print("\nTEMPORALIDADES: [0] H1 [1] M30 [2] M15 [3] H4")
    tf_option = input("Selección: ").strip()
    target_tf = tf_mapping.get(tf_option, "H1")

    # Rutas de Scripts
    python_bin = sys.executable 
    s_l1 = os.path.join(BASE_DIR, "L1.py")
    s_l2 = os.path.join(BASE_DIR, "L2.py")
    s_l3 = os.path.join(BASE_DIR, "L3.py")
    s_l4 = os.path.join(BASE_DIR, "L4.py")
    s_l5 = os.path.join(BASE_DIR, "L5.py")

    print(f"\n\033[92m>>> INICIANDO GRANJA LOCAL: {target_symbol} @ {target_tf} <<<\033[0m")
    
    cycle_iteration = 0
    while True:
        cycle_iteration += 1
        print(f"\n\033[96m" + "#"*75)
        print(f"   CICLO DE MINERÍA #{cycle_iteration} | {target_symbol} | {target_tf}")
        print("#"*75 + "\033[0m")
        
        # PASO 1: REFINERÍA
        update_farm_heartbeat(cycle_iteration, target_symbol, target_tf, "REFINERY", "CORE")
        subprocess.run([python_bin, s_l1, target_csv, tf_option])

        # PASO 2: PRODUCCIÓN DE SILOS
        for side in ["LONG", "SHORT"]:
            for fam in ["MOMENTUM", "TREND", "VOLATILITY", "CYCLE"]:
                update_farm_heartbeat(cycle_iteration, target_symbol, target_tf, side, fam)
                print(f"\n\033[96m>>> PROCESANDO SILO: {side} / {fam}\033[0m")
                
                # Monitor de Fusibles (Amarillo)
                try:
                    if os.path.exists(FUSE_PATH):
                        with open(FUSE_PATH, 'r') as fj:
                            f_on = [k.upper() for k, v in json.load(fj).items() if v is True]
                            print(f"   \033[93m[LEY-SFT ACTIVE]: {', '.join(f_on) if f_on else 'NINGUNA'}\033[0m")
                except: pass

                # Ejecución en cadena
                subprocess.run([python_bin, s_l2, target_symbol, side, fam, target_tf])
                subprocess.run([python_bin, s_l3, target_symbol, target_tf, side, fam])
                
                # Autopsia Inmediata
                print_audit_report(target_symbol, side, fam, target_tf)

        # PASO 3: CONSOLIDACIÓN
        print(f"\n\033[94m[L5] Fusionando y eliminando clones...\033[0m")
        subprocess.run([python_bin, s_l5, target_symbol, target_tf])
        subprocess.run([python_bin, s_l4])
        
        print(f"\n\033[92m[OK] CICLO #{cycle_iteration} COMPLETADO. Reiniciando...\033[0m")
        time.sleep(5)

if __name__ == "__main__":
    try: run_main_commander()
    except KeyboardInterrupt: sys.exit()