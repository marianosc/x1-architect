# ##########################################################################
# SYSTEM: X1-ARCHITECT | FASE MT5 SANEAMIENTO
# FILE: tests/test_translator_mql5.py
# ROL: Verifica que el generador de EAs cubre TODO el ADN de L1, que el EA
#      generado tiene salida real (el bug v104 nunca cerraba posiciones),
#      y que lo intraducible falla ruidosamente.
# USO: python tests/test_translator_mql5.py
# ##########################################################################
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.translator import SQX_TEMPLATES, translate_to_sqx
from modules.translator_mql5 import (
    HELPERS, REGISTRY, generate_full_mql5_code, magic_from_uid,
    parse_rule_mql5, translate_to_mql5,
)

PERIODS_L1 = [5, 8, 13, 21, 34, 55, 89, 144, 200, 24, 48, 120]


def test_cobertura_total_del_adn():
    """Cada indicador del registro traduce sin error en todos los períodos L1."""
    genes = 0
    for name in REGISTRY:
        for p in PERIODS_L1:
            rule = f"{name}_{p}_sft >= 1.5"
            logic = translate_to_mql5(rule)
            assert 'ERR' not in logic, f"Fallo traduciendo {name}_{p}: {logic}"
            assert '_sft' not in logic, f"Token sin limpiar en {name}_{p}"
            genes += 1
    print(f"OK  cobertura total: {len(REGISTRY)} indicadores x {len(PERIODS_L1)} "
          f"períodos = {genes} genes traducidos a MQL5")


def test_helpers_consistentes():
    """Todo helper referenciado en el registro existe en HELPERS."""
    for name, spec in REGISTRY.items():
        if spec['helper'] is not None:
            assert spec['helper'] in HELPERS, f"Helper faltante: {spec['helper']} ({name})"
    print(f"OK  {len(HELPERS)} helpers X1_* definidos y referenciados")


def test_ea_salida_por_tiempo_real():
    """BUG v104 CORREGIDO: el EA con Ret_N ahora CIERRA la posición."""
    alpha = {'Entry': 'rsi_14_sft <= 30|ema_55_sft <= Close_sft', 'Side': 'LONG', 'Exit': 'Ret_24'}
    ea = generate_full_mql5_code('A1B2C3D4', alpha, cooldown=25)
    assert 'if(held >= 24)' in ea, "Falta la salida por tiempo"
    assert 'trade.PositionClose(_Symbol)' in ea, "El EA no cierra posiciones"
    assert '#define SHIFT_SIGNAL   2' in ea, "Shift de sincronía X1 ausente"
    assert 'InpCooldownBars = 25' in ea, "Cooldown del minero ausente"
    assert 'trade.Buy(InpLots, _Symbol)' in ea
    assert ea.count('{') == ea.count('}'), "Llaves desbalanceadas"
    print("OK  EA Ret_24: cierra por tiempo, shift=2, cooldown 25, llaves balanceadas")


def test_ea_sintetica_con_tope():
    """La sintética cierra por rotura de regla Y por tope de 48 velas."""
    alpha = {'Entry': 'cmo_24_sft <= 1.94|mfi_144_sft <= 50.78', 'Side': 'SHORT',
             'Exit': 'SINTETICA_REVERSE'}
    ea = generate_full_mql5_code('FFEE0011', alpha)
    assert 'held >= MAX_HOLD_SYNTH || !X1_EntryRule(SHIFT_SIGNAL)' in ea
    assert '#define MAX_HOLD_SYNTH 48' in ea
    assert 'trade.Sell(InpLots, _Symbol)' in ea
    assert 'h_mfi_144' in ea and 'X1_CMO' in ea, "Faltan handle/helper de la regla"
    assert ea.count('{') == ea.count('}')
    print("OK  EA sintética: rotura de regla + tope 48 velas + handles/helpers")


def test_regla_real_del_master():
    """Una regla real del MASTER de XAUUSD (antes intraducible) ahora compila lógica completa."""
    rule = "cmo_24_sft <= 1.94|mfi_144_sft <= 50.781849|roc_120_sft >= -1.53"
    logic, handles, helpers = parse_rule_mql5(rule)
    assert 'X1_CMO(24, s)' in logic and 'X1_ROC(120, s)' in logic
    assert 'h_mfi_144' in handles
    assert {'cmo', 'roc'} <= helpers
    print(f"OK  regla real del MASTER traducida: {len(handles)} handles, {len(helpers)} helpers")


def test_intraducible_falla_ruidosamente():
    """Indicador desconocido => ValueError (nada de EAs a medias)."""
    alpha = {'Entry': 'hechizo_42_sft >= 7', 'Side': 'LONG', 'Exit': 'Ret_24'}
    try:
        generate_full_mql5_code('AA00', alpha)
    except ValueError:
        print("OK  indicador desconocido lanza ValueError (no genera EA roto)")
        return
    raise AssertionError("Debería haber fallado con indicador desconocido")


def test_magic_determinista():
    assert magic_from_uid('A1B2C3D4') == magic_from_uid('A1B2C3D4')
    assert 0 < magic_from_uid('A1B2C3D4') < 2**31
    assert 0 < magic_from_uid('no-hex-uid') < 2**31
    print("OK  magic number determinista de 31 bits")


def test_sqx_cubre_el_mismo_adn():
    """El export SQX traduce todos los indicadores del registro MQL5."""
    faltantes = [n for n in REGISTRY if n not in SQX_TEMPLATES]
    assert not faltantes, f"SQX sin plantilla para: {faltantes}"
    out = translate_to_sqx("plus_di_21_sft >= minus_di_21_sft|trix_55_sft >= 0")
    assert 'ERR' not in out and 'ADX_DIPlus(21)' in out
    print(f"OK  SQX cubre los {len(REGISTRY)} indicadores del registro")


if __name__ == '__main__':
    tests = [v for k, v in sorted(globals().items()) if k.startswith('test_')]
    print(f"=== TRADUCTOR MQL5/SQX - {len(tests)} pruebas ===")
    for t in tests:
        t()
    print("=== TODAS LAS PRUEBAS PASARON ===")
