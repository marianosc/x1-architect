# ##########################################################################
# SYSTEM: X1-ARCHITECT | TEST v108-B0
# FILE: tests/test_monkey_parity.py
# ROL: Paridad serial-vs-paralelo del monkey (prerequisito del fitness B1).
#      El kernel _monkey_core es nogil=True y monkey_batch lo corre en
#      threads. Este test garantiza que paralelizar NO cambia ningún veredicto:
#      mk_is/mk_oos deben ser BIT-IDÉNTICOS entre serial y paralelo, en
#      cualquier número de threads y cualquier orden.
# USO: python tests/test_monkey_parity.py
# ##########################################################################
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.x1_validators import monkey_test, monkey_batch

RNG = np.random.default_rng(2026)


def _make_jobs(n_jobs, n_bars=4000, n_monkeys=2000):
    """Jobs heterogéneos: distinta serie, cadencia, exposición, side, fricción,
    semilla — para que la paridad cubra el espacio real de uso de B1."""
    jobs = []
    for k in range(n_jobs):
        ret = RNG.normal(0.0002, 0.002, n_bars)
        jobs.append(dict(
            ret_1=ret,
            n_trades=int(RNG.integers(40, 300)),
            exposure=int(RNG.integers(6, 96)),
            strat_total=float(RNG.normal(0, 0.05)),
            side='LONG' if k % 2 == 0 else 'SHORT',
            n_monkeys=n_monkeys,
            seed=12345,
            friction_per_trade=float(RNG.uniform(0, 0.0005)),
        ))
    return jobs


def test_serial_es_determinista():
    """Misma llamada dos veces = mismo resultado (base de toda la paridad)."""
    job = _make_jobs(1)[0]
    a = monkey_test(**job)
    b = monkey_test(**job)
    for k in a:
        assert a[k] == b[k], f"monkey_test no determinista en '{k}': {a[k]} != {b[k]}"
    print("OK  monkey_test determinista (misma llamada == misma salida)")


def test_paridad_serial_vs_paralelo():
    """mk de monkey_batch (paralelo, N threads) == loop serial, BIT a BIT."""
    jobs = _make_jobs(60)
    serial = [monkey_test(**j) for j in jobs]
    for nth in (2, 4, 8, 16):
        par = monkey_batch(jobs, n_threads=nth)
        assert len(par) == len(serial)
        for i, (s, p) in enumerate(zip(serial, par)):
            for key in ('pvalue', 'beta', 'monkey_win_pct', 'monkey_trades'):
                assert s[key] == p[key], \
                    f"DIVERGENCIA job {i} '{key}' con {nth} threads: {s[key]} != {p[key]}"
    print(f"OK  paridad serial==paralelo BIT-IDÉNTICA en {len(jobs)} jobs × {{2,4,8,16}} threads")


def test_orden_preservado():
    """monkey_batch devuelve resultados en el MISMO orden que los jobs."""
    jobs = _make_jobs(20)
    par = monkey_batch(jobs, n_threads=8)
    serial = [monkey_test(**j) for j in jobs]
    for i in range(len(jobs)):
        assert par[i]['pvalue'] == serial[i]['pvalue'], f"orden roto en {i}"
    print("OK  orden de resultados preservado")


def test_speedup_real():
    """Reporta el speedup (no asercion dura: depende de cores). Calienta el JIT
    antes de medir para no contar la compilación."""
    jobs = _make_jobs(64, n_monkeys=5000)
    monkey_test(**jobs[0])  # warm-up JIT
    t0 = time.time(); [monkey_test(**j) for j in jobs]; t_ser = time.time() - t0
    t0 = time.time(); monkey_batch(jobs, n_threads=min(16, os.cpu_count() or 4)); t_par = time.time() - t0
    sp = t_ser / max(1e-9, t_par)
    print(f"OK  speedup: {len(jobs)} jobs × 5000 monos | serial {t_ser:.2f}s | "
          f"paralelo {t_par:.2f}s | {sp:.1f}x ({os.cpu_count()} cores)")


if __name__ == '__main__':
    tests = [test_serial_es_determinista, test_paridad_serial_vs_paralelo,
             test_orden_preservado, test_speedup_real]
    print(f"=== MONKEY PARIDAD serial/paralelo (v108-B0) - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
