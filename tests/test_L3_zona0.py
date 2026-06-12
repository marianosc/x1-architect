# ##########################################################################
# SYSTEM: X1-ARCHITECT | TEST v106.1 - ZONA 0 ES CONTEXTO, NO TRIBUNAL
# FILE: tests/test_L3_zona0.py
# ROL: Verifica el veredicto del ciclo 1 (notebook + Mariano, opcion b):
#      el estancamiento (FAIL_GAP) y el profit total se juzgan desde z1_start.
#      - Estrategia que PIERDE en Zona 0 pero es sana en Z1+Z2 -> NO muere.
#      - Estrategia estancada DENTRO de Z1/Z2 -> SI muere por FAIL_GAP.
#      - Regresion: con el criterio viejo (z1_start=0) la primera moria.
# ##########################################################################
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import L3

# --- DATASET SINTETICO: Z0=[0,10000) Z1=[10000,22000) Z2=[22000,30000) ---
N, Z1_START, Z2_START = 30000, 10000, 22000
STAG_GLOBAL = 5000

zone = np.zeros(N, dtype=np.int64)
zone[Z1_START:Z2_START] = 1
zone[Z2_START:] = 2

# Entradas cada 30 velas (> cooldown 25), arrancando en la vela 10 para que
# la vela 0 sea pico de equity bajo el criterio viejo (eq[0]=0 > -1e-9).
bars_a = np.arange(10, N, 30)                      # toda la historia
bars_b = np.arange(Z1_START + 10, Z1_START + 2000, 30)  # solo inicio de Z1

ret24 = np.zeros(N, dtype=np.float32)
ret24[bars_a[bars_a < Z1_START]] = -0.001          # A pierde en Zona 0
ret24[bars_a[bars_a >= Z1_START]] = +0.01          # A gana en Z1+Z2
ret24[bars_b] = +0.01                              # B gana solo 2000 velas y se apaga

sig_a = np.zeros(N, dtype=np.float32); sig_a[bars_a] = 1.0
sig_b = np.zeros(N, dtype=np.float32); sig_b[bars_b] = 1.0
close = np.full(N, 100.0, dtype=np.float32)

cols = ['Close', 'Close_sft', 'Ret_24', 'sig_a_sft', 'sig_b_sft']
L3.G_DF = np.column_stack([close, close, ret24, sig_a, sig_b]).astype(np.float32)
L3.G_C_MAP = {n: i for i, n in enumerate(cols)}
L3.G_RI_MAP = {'Ret_24': 2}
L3.G_RET_1 = np.zeros(N)
L3.G_ZONES = {'is': zone == 1, 'oos': zone == 2}
L3.G_FUSES = {"anti_gap": True, "monkey_test": False}

CFG = {"min_t": 50, "min_pf": 1.1, "f_points": 0.0, "Stag_Global": STAG_GLOBAL,
       "cooldown": 25, "monkey_train_min": 99.0, "monkey_test_min": 90.0,
       "monkey_n": 100, "z1_start": Z1_START}

print("=== L3 ZONA 0 = CONTEXTO (v106.1) - 3 pruebas ===")

# 1. Sana en Z1+Z2 que pierde en Z0: NO debe morir por FAIL_GAP
L3.G_CFG = dict(CFG)
res, status = L3.audit_worker(["sig_a_sft >= 1", "LONG", "Ret_24", 0.0])
assert status != "FAIL_GAP", f"A murio por FAIL_GAP juzgando desde z1_start: {status}"
assert status == "PASS", f"A deberia PASAR entera (sana en Z1+Z2): {status}"
print(f"OK  pierde-en-Z0/sana-en-Z1+Z2 sobrevive: {status} "
      f"(PF {res[3]}, trades {res[6]}, stag {res[5]} <= {STAG_GLOBAL})")

# 2. Estancada DENTRO de Z1/Z2 (opera 2000 velas y se apaga): SI debe morir
res_b, status_b = L3.audit_worker(["sig_b_sft >= 1", "LONG", "Ret_24", 0.0])
assert status_b == "FAIL_GAP", f"B estancada en Z1/Z2 deberia morir FAIL_GAP: {status_b}"
print(f"OK  estancada dentro de Z1/Z2 muere: {status_b}")

# 3. Regresion: con el criterio viejo (juzgar desde la vela 0) A moria FAIL_GAP
L3.G_CFG = dict(CFG, z1_start=0)
_, status_old = L3.audit_worker(["sig_a_sft >= 1", "LONG", "Ret_24", 0.0])
assert status_old == "FAIL_GAP", f"con z1_start=0 A deberia morir FAIL_GAP (criterio viejo): {status_old}"
print(f"OK  regresion: criterio viejo (z1_start=0) la mataba: {status_old}")

print("=== TODAS LAS PRUEBAS PASARON ===")
