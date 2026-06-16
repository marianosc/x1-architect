# ##########################################################################
# SYSTEM: X1-ARCHITECT | TEST v108-B1
# FILE: tests/test_fitness_v108.py
# ROL: El fitness del minero debe medir SKILL OOS-interno, no beta de régimen.
#   1. Candidato SKILL (entra justo antes de spikes que el azar se pierde) ->
#      fitness ALTO (mk_oos alto en los folds).
#   2. Candidato BETA (entra en la deriva, sin spikes; el monkey LONG lo
#      iguala/supera) -> fitness BAJO. Esta es la prueba clave: separa skill
#      de exposición al bull.
#   3. Purging: entradas pegadas al borde derecho del bloque (su Ret_N se
#      devenga fuera) se descartan -> folds inválidos.
#   4. Determinismo: misma regla -> mismo fitness (semilla por crc32 de la regla).
#   5. Parsimonia: fitness = core - lambda*complejidad.
# USO: python tests/test_fitness_v108.py
# ##########################################################################
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.fitness_v108 import fitness_v108, fitness_population, cpcv_blocks

RNG = np.random.default_rng(108)
N, Z1S, Z1E = 60000, 12000, 54000   # Z1 = 42.000 velas, como XAUUSD H1
EXIT_N = 24
DRIFT, NOISE, SPIKE = 5e-5, 1e-3, 0.012
CFG = {'cooldown': 25, 'f_points': 0.0}


def _build():
    """Mercado con deriva (beta) + spikes después de señales-skill repartidos
    por TODO Z1, para que cada fold CPCV tenga señal."""
    ret_1 = DRIFT + RNG.normal(0, NOISE, N)
    e_skill = np.arange(200, N - 200, 80)      # entradas-skill (cada 80 velas)
    e_beta = e_skill + 40                       # entradas-beta (entre spikes)
    e_beta = e_beta[e_beta < N - 200]
    ret_1[e_skill + 1] += SPIKE                 # el edge: spike justo tras la señal
    # entradas pegadas al borde derecho de cada bloque (para test de purga)
    blocks = cpcv_blocks(Z1S, Z1E, 6)
    e_edge = np.array([be - 5 for (_, be) in blocks])  # a 5 velas del borde (< N)

    close = 100.0 * np.cumprod(1.0 + ret_1)
    ret24 = np.zeros(N)
    ret24[:-EXIT_N] = (close[EXIT_N:] - close[:-EXIT_N]) / close[:-EXIT_N]

    def sig(entries):
        s = np.zeros(N, dtype=np.float32); s[entries] = 1.0; return s

    cols = ['Close', 'Close_sft', 'Ret_24', 'sig_skill_sft', 'sig_beta_sft', 'sig_edge_sft']
    data = np.column_stack([close, np.roll(close, 1), ret24,
                            sig(e_skill), sig(e_beta), sig(e_edge)]).astype(np.float32)
    cm = {n: i for i, n in enumerate(cols)}
    ri = {'Ret_24': 2}
    return data, cm, ri


DATA, CM, RI = _build()


def _fit(rule, **kw):
    return fitness_v108(rule, 'LONG', 'Ret_24', DATA, CM, RI, Z1S, Z1E, CFG,
                        n_monkeys=400, **kw)


def test_skill_alto_beta_bajo():
    """La prueba central: skill >> beta y skill supera el listón 90."""
    fs = _fit("sig_skill_sft >= 1")
    fb = _fit("sig_beta_sft >= 1")
    assert fs['n_valid'] >= 5 and fb['n_valid'] >= 5, "ambos deben operar en casi todos los folds"
    assert fs['fitness_core'] >= 90, f"skill debería pasar el listón OOS: {fs['fitness_core']:.1f}"
    assert fb['fitness_core'] <= 70, f"beta debería quedar bajo (el monkey lo iguala): {fb['fitness_core']:.1f}"
    assert fs['fitness_core'] - fb['fitness_core'] >= 30, "skill debe separarse claro de beta"
    print(f"OK  skill vs beta: fitness_core skill {fs['fitness_core']:.1f} (n_valid {fs['n_valid']}) "
          f">> beta {fb['fitness_core']:.1f} (n_valid {fb['n_valid']})")


def test_purga_borde_derecho():
    """Entradas a <N del borde derecho del bloque se purgan -> sin folds válidos."""
    fe = _fit("sig_edge_sft >= 1")
    assert fe['n_valid'] == 0, f"las entradas de borde debían purgarse, n_valid={fe['n_valid']}"
    assert fe['fitness_core'] == 0.0
    print(f"OK  purga del borde: regla de borde -> {fe['n_valid']} folds válidos, fitness_core 0")


def test_determinismo():
    """Misma regla evaluada dos veces = fitness idéntico (semilla por crc32)."""
    a = _fit("sig_skill_sft >= 1")
    b = _fit("sig_skill_sft >= 1")
    assert a['fitness'] == b['fitness'] and a['fold_mk'] == b['fold_mk'], "fitness no determinista"
    print(f"OK  determinismo: fitness {a['fitness']:.4f} reproducible bit a bit")


def test_parsimonia():
    """fitness = fitness_core - lambda*complejidad (nodos de la regla)."""
    lam = 5.0
    f1 = _fit("sig_skill_sft >= 1", lam=lam)                       # complejidad 1
    f2 = _fit("sig_skill_sft >= 1|sig_skill_sft >= 1", lam=lam)    # complejidad 2 (misma señal)
    assert f1['complexity'] == 1 and f2['complexity'] == 2
    assert abs((f1['fitness_core'] - lam * 1) - f1['fitness']) < 1e-9
    assert f2['fitness'] < f1['fitness'], "más nodos => más penalización"
    print(f"OK  parsimonia: 1 nodo fitness {f1['fitness']:.2f} > 2 nodos {f2['fitness']:.2f} (λ={lam})")


def test_batch_orden_y_paridad():
    """fitness_population devuelve en orden y == evaluación individual."""
    cands = [("sig_skill_sft >= 1", 'LONG', 'Ret_24'),
             ("sig_beta_sft >= 1", 'LONG', 'Ret_24')]
    pop = fitness_population(cands, DATA, CM, RI, Z1S, Z1E, CFG, n_monkeys=400)
    assert pop[0]['rule'] == cands[0][0] and pop[1]['rule'] == cands[1][0]
    solo = _fit("sig_skill_sft >= 1")
    assert pop[0]['fold_mk'] == solo['fold_mk'], "batch debe coincidir con individual"
    print(f"OK  batch: orden preservado y fitness idéntico al individual")


if __name__ == '__main__':
    tests = [test_skill_alto_beta_bajo, test_purga_borde_derecho, test_determinismo,
             test_parsimonia, test_batch_orden_y_paridad]
    print(f"=== FITNESS v108 (B1) - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
