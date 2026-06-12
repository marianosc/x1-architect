# ANALISIS FANTASMA — 20,000 candidatos, 20,000 con OOS medible, 567 SIN solape (expo<=cooldown)

## A2.5 — ARTEFACTO: el monkey premia el apilamiento, no el timing

El motor imputa Ret_N en cada entrada con cooldown 25: si N>25 simula una
cartera PIRAMIDADA que el EA real (una posicion por vez) nunca ejecutara.
El mono (busyUntil) no puede apilar => pvalue inflado con el solape:

| Exit | n | solape | mk_oos mediana | % pasa 90 |
|---|---|---|---|---|
| SINTETICA_REVERSE | 280 | 0.4x | 83.2 | 17.1% |
| Ret_12 | 42 | 0.5x | 66.5 | 16.7% |
| Ret_24 | 249 | 1.0x | 62.8 | 10.8% |
| Ret_48 | 1541 | 1.9x | 42.1 | 2.1% |
| Ret_72 | 4358 | 2.9x | 44.4 | 7.5% |
| Ret_96 | 13530 | 3.8x | 44.3 | 9.9% |

Spearman solape vs monkey_oos: **+0.036** (p=4.9e-07). En los cohortes SIN solape la tasa de paso es ~10-13% = azar (el resultado honesto).

## A3 — Spearman IS -> OOS (la pregunta: ¿que metrica IS predice OOS?)

### Pool COMPLETO (contaminado por el gradiente de solape) (n=20,000)

| metrica IS | vs pf_oos | vs monkey_oos | vs profit_oos | vs xs_oos |
|---|---|---|---|---|
| PF_L2 | **+0.064** (p=1.4e-19) | -0.018 (p=1.1e-02) | -0.048 (p=1.1e-11) | +0.012 (p=7.8e-02) |
| pf_is | **+0.072** (p=1.1e-24) | -0.021 (p=3.6e-03) | -0.037 (p=1.8e-07) | +0.009 (p=2.3e-01) |
| r2_is | **+0.127** (p=4.9e-73) | +0.012 (p=1.0e-01) | **+0.191** (p=7.3e-164) | **+0.079** (p=2.6e-29) |
| xs_is | **+0.076** (p=2.6e-27) | -0.049 (p=3.2e-12) | +0.001 (p=9.0e-01) | -0.028 (p=5.7e-05) |
| monkey_is | **-0.200** (p=5.1e-179) | -0.030 (p=2.7e-05) | **-0.237** (p=1.5e-253) | **-0.141** (p=2.8e-89) |
| trades_is | +0.012 (p=1.0e-01) | **-0.059** (p=7.6e-17) | **+0.513** (p=0.0e+00) | -0.013 (p=7.6e-02) |
| expo_is | **+0.582** (p=0.0e+00) | +0.035 (p=5.2e-07) | **+0.598** (p=0.0e+00) | **+0.224** (p=3.7e-226) |
| stag | -0.050 (p=1.7e-12) | **-0.077** (p=2.3e-27) | **+0.056** (p=1.6e-15) | **-0.088** (p=1.5e-35) |
| n_conds | **-0.107** (p=5.5e-52) | +0.025 (p=4.5e-04) | **-0.250** (p=3.3e-283) | -0.020 (p=3.8e-03) |
| beta_is | **+0.461** (p=0.0e+00) | +0.015 (p=3.6e-02) | **+0.774** (p=0.0e+00) | **+0.173** (p=2.0e-133) |
| oer | **+0.335** (p=0.0e+00) | **+0.171** (p=2.1e-130) | **+0.343** (p=0.0e+00) | **+0.243** (p=3.5e-267) |

### Subset HONESTO sin solape (expo<=25: lo que el EA puede ejecutar) (n=567)

| metrica IS | vs pf_oos | vs monkey_oos | vs profit_oos | vs xs_oos |
|---|---|---|---|---|
| PF_L2 | +0.132 (p=1.6e-03) | **+0.184** (p=1.1e-05) | -0.111 (p=8.3e-03) | **+0.281** (p=9.6e-12) |
| pf_is | +0.131 (p=1.8e-03) | **+0.183** (p=1.1e-05) | -0.112 (p=7.8e-03) | **+0.280** (p=1.2e-11) |
| r2_is | +0.011 (p=7.9e-01) | +0.061 (p=1.5e-01) | +0.018 (p=6.8e-01) | **+0.158** (p=1.7e-04) |
| xs_is | +0.026 (p=5.4e-01) | +0.087 (p=3.8e-02) | +0.058 (p=1.7e-01) | +0.052 (p=2.2e-01) |
| monkey_is | +0.115 (p=6.0e-03) | **+0.387** (p=9.8e-22) | **-0.168** (p=6.0e-05) | **+0.201** (p=1.4e-06) |
| trades_is | -0.070 (p=9.5e-02) | **+0.201** (p=1.4e-06) | **+0.308** (p=6.4e-14) | +0.016 (p=7.1e-01) |
| expo_is | +0.046 (p=2.7e-01) | **-0.346** (p=2.3e-17) | **+0.373** (p=4.1e-20) | +0.040 (p=3.4e-01) |
| stag | **-0.148** (p=4.2e-04) | +0.047 (p=2.7e-01) | -0.034 (p=4.2e-01) | -0.083 (p=4.7e-02) |
| n_conds | -0.011 (p=8.0e-01) | -0.037 (p=3.8e-01) | +0.095 (p=2.4e-02) | +0.027 (p=5.3e-01) |
| beta_is | +0.040 (p=3.4e-01) | **-0.368** (p=1.1e-19) | **+0.214** (p=2.8e-07) | +0.109 (p=9.1e-03) |
| oer | **+0.484** (p=1.0e-34) | **+0.404** (p=1.2e-23) | **+0.636** (p=1.6e-65) | **+0.202** (p=1.2e-06) |

### Cohorte Ret_96 (solape ~constante 3.8x: timing a apalancamiento igual) (n=13,530)

| metrica IS | vs pf_oos | vs monkey_oos | vs profit_oos | vs xs_oos |
|---|---|---|---|---|
| PF_L2 | -0.007 (p=4.4e-01) | **-0.061** (p=1.4e-12) | **-0.094** (p=3.7e-28) | -0.021 (p=1.3e-02) |
| pf_is | +0.009 (p=3.2e-01) | **-0.065** (p=3.7e-14) | **-0.070** (p=4.3e-16) | -0.031 (p=3.3e-04) |
| r2_is | **+0.082** (p=2.0e-21) | +0.003 (p=7.5e-01) | **+0.176** (p=4.7e-94) | +0.034 (p=8.9e-05) |
| xs_is | **-0.065** (p=2.6e-14) | **-0.056** (p=9.7e-11) | **-0.127** (p=4.5e-50) | -0.027 (p=1.5e-03) |
| monkey_is | +0.036 (p=3.6e-05) | **-0.063** (p=2.9e-13) | +0.021 (p=1.3e-02) | **-0.062** (p=5.6e-13) |
| trades_is | +0.013 (p=1.3e-01) | -0.042 (p=8.1e-07) | **+0.640** (p=0.0e+00) | **-0.126** (p=2.7e-49) |
| expo_is | +nan (p=nan) | +nan (p=nan) | +nan (p=nan) | +nan (p=nan) |
| stag | **-0.077** (p=4.9e-19) | **-0.099** (p=6.8e-31) | **+0.081** (p=4.8e-21) | **-0.142** (p=8.8e-62) |
| n_conds | +0.006 (p=4.8e-01) | **+0.057** (p=2.5e-11) | **-0.183** (p=2.4e-102) | **+0.058** (p=1.1e-11) |
| beta_is | -0.016 (p=6.8e-02) | -0.020 (p=2.0e-02) | **+0.605** (p=0.0e+00) | -0.049 (p=1.5e-08) |
| oer | **+0.109** (p=3.0e-37) | **+0.098** (p=5.0e-30) | **+0.112** (p=9.0e-39) | **+0.094** (p=1.1e-27) |


### Deciles sobre el pool completo (media de pf_oos y % que pasaria monkey_oos>=90)

**xs_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 0.481-0.510 | 2053 | 1.731 | 12.0% |
| 1 | 0.510-0.515 | 1972 | 1.745 | 8.2% |
| 2 | 0.515-0.519 | 2035 | 1.778 | 10.6% |
| 3 | 0.519-0.522 | 1971 | 1.804 | 10.6% |
| 4 | 0.522-0.524 | 2957 | 1.842 | 4.1% |
| 5 | 0.524-0.525 | 1032 | 1.780 | 6.9% |
| 6 | 0.525-0.529 | 2034 | 1.793 | 8.3% |
| 7 | 0.529-0.532 | 1957 | 1.811 | 8.8% |
| 8 | 0.532-0.537 | 1995 | 1.837 | 10.7% |
| 9 | 0.537-0.570 | 1994 | 1.764 | 9.9% |

**pf_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 1.038-1.081 | 2000 | 1.727 | 7.0% |
| 1 | 1.081-1.100 | 2000 | 1.753 | 4.8% |
| 2 | 1.100-1.118 | 2004 | 1.765 | 7.5% |
| 3 | 1.118-1.132 | 2015 | 1.833 | 14.4% |
| 4 | 1.132-1.144 | 1981 | 1.820 | 11.1% |
| 5 | 1.144-1.153 | 2913 | 1.849 | 7.7% |
| 6 | 1.153-1.163 | 1113 | 1.783 | 5.9% |
| 7 | 1.163-1.184 | 1974 | 1.807 | 6.6% |
| 8 | 1.184-1.222 | 2012 | 1.804 | 11.4% |
| 9 | 1.222-1.661 | 1988 | 1.742 | 11.6% |

**monkey_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 0.000-19.300 | 2001 | 1.865 | 9.1% |
| 1 | 19.400-33.000 | 2002 | 1.851 | 9.4% |
| 2 | 33.100-44.400 | 2028 | 1.840 | 11.7% |
| 3 | 44.500-53.800 | 1970 | 1.829 | 10.1% |
| 4 | 53.900-63.500 | 1999 | 1.784 | 10.7% |
| 5 | 63.600-71.500 | 2011 | 1.752 | 8.9% |
| 6 | 71.600-73.000 | 2030 | 1.859 | 0.5% |
| 7 | 73.100-80.400 | 1959 | 1.744 | 9.3% |
| 8 | 80.500-90.000 | 2001 | 1.736 | 8.1% |
| 9 | 90.100-100.000 | 1999 | 1.652 | 10.9% |

**r2_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 0.000-0.246 | 2008 | 1.702 | 8.0% |
| 1 | 0.246-0.366 | 2007 | 1.774 | 6.5% |
| 2 | 0.366-0.450 | 1985 | 1.762 | 7.0% |
| 3 | 0.450-0.512 | 2000 | 1.808 | 13.4% |
| 4 | 0.512-0.562 | 2006 | 1.782 | 6.7% |
| 5 | 0.562-0.606 | 1994 | 1.808 | 11.7% |
| 6 | 0.606-0.622 | 2426 | 1.858 | 4.5% |
| 7 | 0.622-0.658 | 1574 | 1.816 | 10.2% |
| 8 | 0.659-0.725 | 2032 | 1.814 | 11.4% |
| 9 | 0.726-0.934 | 1968 | 1.779 | 10.6% |


## A4 — Sondas de frontera (mapa del terreno, NO cosecha; etiqueta FRONTERA)

### pool completo (CONTAMINADO por solape) — cruzan gates fijos (trades>=300, stag<=5000, profit>0, mk_is>=99): 1 de 20,000

**sin filtro XS** (cruzan: 1)

| monkey_oos \ min_pf | 1.25 | 1.15 | 1.05 |
|---|---|---|---|
| >=90 | 0 | 0 | 0 |
| >=80 | 0 | 0 | 0 |
| >=70 | 0 | 0 | 0 |
| >=60 | 1 | 1 | 1 |
| >=50 | 1 | 1 | 1 |

**con XS_IS>=0.55 (umbral candidato, Fase 2)** (cruzan: 0)

| monkey_oos \ min_pf | 1.25 | 1.15 | 1.05 |
|---|---|---|---|
| >=90 | 0 | 0 | 0 |
| >=80 | 0 | 0 | 0 |
| >=70 | 0 | 0 | 0 |
| >=60 | 0 | 0 | 0 |
| >=50 | 0 | 0 | 0 |

### subset honesto sin solape — cruzan gates fijos (trades>=300, stag<=5000, profit>0, mk_is>=99): 0 de 567

**sin filtro XS** (cruzan: 0)

| monkey_oos \ min_pf | 1.25 | 1.15 | 1.05 |
|---|---|---|---|
| >=90 | 0 | 0 | 0 |
| >=80 | 0 | 0 | 0 |
| >=70 | 0 | 0 | 0 |
| >=60 | 0 | 0 | 0 |
| >=50 | 0 | 0 | 0 |

**con XS_IS>=0.55 (umbral candidato, Fase 2)** (cruzan: 0)

| monkey_oos \ min_pf | 1.25 | 1.15 | 1.05 |
|---|---|---|---|
| >=90 | 0 | 0 | 0 |
| >=80 | 0 | 0 | 0 |
| >=70 | 0 | 0 | 0 |
| >=60 | 0 | 0 | 0 |
| >=50 | 0 | 0 | 0 |


## B1 — Metricas institucionales (columnas fantasma, no gates)

(n=20,000 con >=10 trades OOS | V[SR] del pool=0.00262 | SR0 con N=1e+06 pruebas = 0.249 por trade)

| metrica | media | p95 | max | n>umbral |
|---|---|---|---|---|
| t-stat OOS | +2.57 | +3.29 | +4.46 | 17101 con t>=2 |
| PSR OOS | 0.981 | 0.999 | 1.000 | 18275 con PSR>=0.95 |
| DSR (N=1M) | 0.384 | 0.652 | 0.974 | 3 con DSR>=0.95 |

### ¿Separan mejor que las nuestras? (Spearman contra pf_oos y monkey_oos)

| metrica institucional (IS-side: t-stat de r_is no disponible; se usa OOS-honesto: correlacion entre metricas) |
- tstat_oos: vs pf_oos +0.871 (p=0.0e+00) | vs monkey_oos +0.636 (p=0.0e+00)
- psr_oos: vs pf_oos +0.869 (p=0.0e+00) | vs monkey_oos +0.630 (p=0.0e+00)
- dsr: vs pf_oos +0.984 (p=0.0e+00) | vs monkey_oos +0.640 (p=0.0e+00)

### PBO (CSCV, 8 bloques Z1, C(8,4)=70 particiones, 20,000 estrategias)

**PBO = 0.71** (probabilidad de que el campeon in-sample quede bajo la mediana out-of-sample; >0.5 = seleccion = ruido puro; lambda medio -1.63)
