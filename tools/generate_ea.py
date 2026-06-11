# ##########################################################################
# SYSTEM: X1-ARCHITECT | FASE MT5
# FILE: tools/generate_ea.py
# ROL: Genera un .mq5 desde la línea de comandos (canarios de calibración
#      y verificación de compilación sin abrir el dashboard).
# USO: python tools/generate_ea.py "<regla>" <LONG|SHORT> <Ret_N|SINTETICA_REVERSE> [nombre] [cooldown]
# EJ : python tools/generate_ea.py "rsi_14_sft <= 30" LONG Ret_24 CANARIO01 25
# ##########################################################################
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.translator_mql5 import generate_full_mql5_code


def default_cooldown(symbol="XAUUSD"):
    """Min_Dist_Bars del symbol en data/assets.csv (cooldown soberano del minero).

    Que el canario use el MISMO cooldown que el motor evita el off-by-one
    historico (EA 24 vs motor 25) que ensuciaba la calibracion Python<->MT5.
    """
    assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "assets.csv")
    try:
        with open(assets, newline="") as f:
            for row in csv.DictReader(f):
                if row.get("Symbol") == symbol and row.get("Min_Dist_Bars"):
                    return int(float(row["Min_Dist_Bars"]))
    except (OSError, ValueError, KeyError):
        pass
    return 25


def main():
    if len(sys.argv) < 4:
        print(__doc__ or "Uso: generate_ea.py <regla> <side> <exit> [nombre] [cooldown]")
        sys.exit(1)
    rule, side, exit_l = sys.argv[1], sys.argv[2].upper(), sys.argv[3]
    name = sys.argv[4] if len(sys.argv) > 4 else "X1_CANARIO"
    cooldown = int(sys.argv[5]) if len(sys.argv) > 5 else default_cooldown()

    alpha = {'Entry': rule, 'Side': side, 'Exit': exit_l}
    code = generate_full_mql5_code(name, alpha, cooldown=cooldown)

    out_path = os.path.abspath(f"{name}.mq5")
    # MetaEditor compila UTF-8 sin problema; evitamos UTF-16 por los diffs
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(code)
    print(f"OK  EA generado: {out_path}")
    print(f"    Regla   : {rule}")
    print(f"    Side    : {side} | Exit: {exit_l} | Cooldown: {cooldown}")
    print("    Siguiente paso: copiar a MQL5\\Experts y compilar en MetaEditor (F7).")


if __name__ == '__main__':
    main()
