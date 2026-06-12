# ANALISIS FANTASMA — 20,000 candidatos, 20,000 con OOS medible, 389 SIN solape (expo<=cooldown)

## A2.5 — ARTEFACTO: el monkey premia el apilamiento, no el timing

El motor imputa Ret_N en cada entrada con cooldown 25: si N>25 simula una
cartera PIRAMIDADA que el EA real (una posicion por vez) nunca ejecutara.
El mono (busyUntil) no puede apilar => pvalue inflado con el solape:

| Exit | n | solape | mk_oos mediana | % pasa 90 |
|---|---|---|---|---|
| Ret_12 | 29 | 0.5x | 54.6 | 10.3% |
| SINTETICA_REVERSE | 315 | 0.7x | 67.5 | 13.3% |
| Ret_24 | 58 | 1.0x | 69.5 | 32.8% |
| Ret_48 | 319 | 1.9x | 94.1 | 55.8% |
| Ret_72 | 1133 | 2.9x | 100.0 | 67.1% |
| Ret_96 | 18146 | 3.8x | 100.0 | 94.2% |

Spearman solape vs monkey_oos: **+0.425** (p=0.0e+00). En los cohortes SIN solape la tasa de paso es ~10-13% = azar (el resultado honesto).

## A3 — Spearman IS -> OOS (la pregunta: ¿que metrica IS predice OOS?)

### Pool COMPLETO (contaminado por el gradiente de solape) (n=20,000)

| metrica IS | vs pf_oos | vs monkey_oos | vs profit_oos | vs xs_oos |
|---|---|---|---|---|
| PF_L2 | -0.038 (p=7.7e-08) | **-0.251** (p=2.4e-285) | **-0.243** (p=2.9e-267) | **-0.201** (p=3.4e-181) |
| pf_is | +0.036 (p=2.9e-07) | **-0.261** (p=8.0e-310) | **-0.322** (p=0.0e+00) | **-0.206** (p=1.1e-190) |
| r2_is | **+0.083** (p=6.0e-32) | -0.001 (p=9.2e-01) | **+0.128** (p=3.8e-74) | +0.008 (p=2.8e-01) |
| xs_is | -0.047 (p=1.9e-11) | **-0.085** (p=2.0e-33) | **-0.160** (p=3.3e-115) | **-0.154** (p=5.3e-107) |
| monkey_is | **+0.183** (p=9.7e-151) | **+0.509** (p=0.0e+00) | **+0.497** (p=0.0e+00) | **+0.057** (p=6.4e-16) |
| trades_is | **+0.082** (p=1.5e-31) | **+0.496** (p=0.0e+00) | **+0.931** (p=0.0e+00) | **+0.197** (p=1.6e-174) |
| expo_is | **+0.355** (p=0.0e+00) | **+0.425** (p=0.0e+00) | **+0.415** (p=0.0e+00) | **+0.113** (p=5.5e-58) |
| stag | **-0.218** (p=8.6e-213) | -0.018 (p=1.1e-02) | **+0.182** (p=9.6e-149) | -0.001 (p=8.9e-01) |
| n_conds | **+0.071** (p=1.5e-23) | **-0.135** (p=3.7e-82) | **-0.313** (p=0.0e+00) | **-0.051** (p=5.6e-13) |
| beta_is | **+0.319** (p=0.0e+00) | **+0.631** (p=0.0e+00) | **+0.561** (p=0.0e+00) | **+0.128** (p=3.6e-74) |
| oer | **+0.246** (p=5.3e-273) | **+0.507** (p=0.0e+00) | **+0.313** (p=0.0e+00) | **+0.204** (p=2.1e-187) |

### Subset HONESTO sin solape (expo<=25: lo que el EA puede ejecutar) (n=389)

| metrica IS | vs pf_oos | vs monkey_oos | vs profit_oos | vs xs_oos |
|---|---|---|---|---|
| PF_L2 | **+0.311** (p=3.5e-10) | **+0.208** (p=3.5e-05) | **-0.483** (p=3.5e-24) | **+0.424** (p=2.0e-18) |
| pf_is | **+0.305** (p=7.7e-10) | **+0.202** (p=6.2e-05) | **-0.484** (p=2.9e-24) | **+0.418** (p=6.8e-18) |
| r2_is | +0.110 (p=3.0e-02) | +0.066 (p=1.9e-01) | -0.129 (p=1.1e-02) | +0.153 (p=2.5e-03) |
| xs_is | **+0.359** (p=3.0e-13) | **+0.197** (p=9.0e-05) | **-0.319** (p=1.1e-10) | **+0.509** (p=4.4e-27) |
| monkey_is | +0.067 (p=1.9e-01) | +0.138 (p=6.2e-03) | -0.051 (p=3.1e-01) | +0.014 (p=7.9e-01) |
| trades_is | -0.165 (p=1.1e-03) | -0.089 (p=7.8e-02) | **+0.499** (p=7.1e-26) | **-0.396** (p=4.9e-16) |
| expo_is | **+0.265** (p=1.1e-07) | +0.135 (p=7.6e-03) | **+0.679** (p=7.5e-54) | -0.010 (p=8.4e-01) |
| stag | **-0.176** (p=4.9e-04) | -0.151 (p=2.8e-03) | +0.086 (p=8.9e-02) | -0.149 (p=3.3e-03) |
| n_conds | -0.133 (p=8.4e-03) | -0.027 (p=5.9e-01) | -0.138 (p=6.3e-03) | -0.047 (p=3.6e-01) |
| beta_is | **+0.359** (p=2.7e-13) | **+0.202** (p=6.2e-05) | **-0.182** (p=3.1e-04) | **+0.493** (p=3.6e-25) |
| oer | **+0.167** (p=9.4e-04) | **+0.218** (p=1.4e-05) | **+0.834** (p=5.4e-102) | **-0.248** (p=7.4e-07) |

### Cohorte Ret_96 (solape ~constante 3.8x: timing a apalancamiento igual) (n=18,146)

| metrica IS | vs pf_oos | vs monkey_oos | vs profit_oos | vs xs_oos |
|---|---|---|---|---|
| PF_L2 | **-0.053** (p=6.8e-13) | **-0.281** (p=0.0e+00) | **-0.254** (p=1.6e-265) | **-0.224** (p=1.0e-204) |
| pf_is | +0.045 (p=1.6e-09) | **-0.288** (p=0.0e+00) | **-0.344** (p=0.0e+00) | **-0.228** (p=3.0e-213) |
| r2_is | **+0.105** (p=1.8e-45) | +0.029 (p=1.0e-04) | **+0.180** (p=2.9e-131) | +0.015 (p=3.7e-02) |
| xs_is | **-0.081** (p=7.7e-28) | **-0.119** (p=5.6e-58) | **-0.218** (p=1.7e-193) | **-0.190** (p=9.8e-148) |
| monkey_is | +0.037 (p=6.8e-07) | **+0.392** (p=0.0e+00) | **+0.398** (p=0.0e+00) | -0.015 (p=3.9e-02) |
| trades_is | **-0.068** (p=8.8e-20) | **+0.420** (p=0.0e+00) | **+0.929** (p=0.0e+00) | **+0.185** (p=2.4e-139) |
| expo_is | +nan (p=nan) | +nan (p=nan) | +nan (p=nan) | +nan (p=nan) |
| stag | **-0.223** (p=1.2e-202) | +0.019 (p=9.5e-03) | **+0.223** (p=5.4e-204) | +0.032 (p=1.4e-05) |
| n_conds | **+0.108** (p=1.5e-48) | **-0.135** (p=6.0e-75) | **-0.331** (p=0.0e+00) | -0.049 (p=5.3e-11) |
| beta_is | **+0.061** (p=3.2e-16) | **+0.594** (p=0.0e+00) | **+0.395** (p=0.0e+00) | **+0.059** (p=3.0e-15) |
| oer | **+0.181** (p=9.1e-134) | **+0.444** (p=0.0e+00) | **+0.227** (p=7.5e-210) | **+0.135** (p=1.1e-74) |


### Deciles sobre el pool completo (media de pf_oos y % que pasaria monkey_oos>=90)

**xs_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 0.482-0.515 | 2065 | 1.847 | 81.0% |
| 1 | 0.515-0.518 | 1983 | 1.897 | 92.1% |
| 2 | 0.518-0.519 | 2019 | 1.903 | 95.7% |
| 3 | 0.519-0.520 | 2671 | 1.857 | 98.6% |
| 4 | 0.520-0.521 | 1392 | 1.910 | 94.0% |
| 5 | 0.521-0.522 | 1906 | 1.898 | 96.0% |
| 6 | 0.522-0.524 | 1985 | 1.906 | 95.2% |
| 7 | 0.524-0.526 | 2056 | 1.885 | 93.4% |
| 8 | 0.526-0.530 | 1924 | 1.887 | 92.2% |
| 9 | 0.530-0.582 | 1999 | 1.786 | 65.8% |

**pf_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 1.048-1.072 | 2014 | 1.862 | 95.8% |
| 1 | 1.072-1.093 | 1986 | 1.856 | 93.3% |
| 2 | 1.093-1.109 | 2007 | 1.849 | 90.4% |
| 3 | 1.109-1.116 | 2789 | 1.845 | 98.5% |
| 4 | 1.116-1.124 | 1204 | 1.891 | 96.0% |
| 5 | 1.124-1.139 | 2000 | 1.891 | 97.0% |
| 6 | 1.139-1.155 | 2000 | 1.893 | 97.5% |
| 7 | 1.155-1.191 | 2000 | 1.889 | 91.3% |
| 8 | 1.191-1.245 | 2002 | 1.915 | 83.8% |
| 9 | 1.245-2.082 | 1998 | 1.884 | 60.3% |

**monkey_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 0.000-91.200 | 2003 | 1.814 | 68.0% |
| 1 | 91.300-100.000 | 17997 | 1.883 | 93.0% |

**r2_is** (decil 0=bajo, 9=alto):
| decil | rango | n | pf_oos medio | % monkey_oos>=90 |
|---|---|---|---|---|
| 0 | 0.000-0.234 | 2010 | 1.829 | 87.4% |
| 1 | 0.234-0.350 | 1998 | 1.849 | 87.5% |
| 2 | 0.350-0.436 | 1992 | 1.900 | 87.4% |
| 3 | 0.436-0.502 | 2000 | 1.914 | 92.5% |
| 4 | 0.502-0.542 | 3277 | 1.852 | 97.0% |
| 5 | 0.542-0.556 | 727 | 1.893 | 91.3% |
| 6 | 0.556-0.590 | 1996 | 1.900 | 94.0% |
| 7 | 0.590-0.629 | 2000 | 1.879 | 92.8% |
| 8 | 0.629-0.684 | 2003 | 1.895 | 93.9% |
| 9 | 0.684-0.955 | 1997 | 1.874 | 77.5% |


## A4 — Sondas de frontera (mapa del terreno, NO cosecha; etiqueta FRONTERA)

### pool completo (CONTAMINADO por solape) — cruzan gates fijos (trades>=300, stag<=5000, profit>0, mk_is>=99): 5 de 20,000

| monkey_oos \ min_pf | 1.25 | 1.15 | 1.05 |
|---|---|---|---|
| >=90 | 4 | 4 | 4 |
| >=80 | 4 | 4 | 4 |
| >=70 | 4 | 4 | 4 |
| >=60 | 4 | 4 | 4 |
| >=50 | 4 | 4 | 4 |

### subset honesto sin solape — cruzan gates fijos (trades>=300, stag<=5000, profit>0, mk_is>=99): 0 de 389

| monkey_oos \ min_pf | 1.25 | 1.15 | 1.05 |
|---|---|---|---|
| >=90 | 0 | 0 | 0 |
| >=80 | 0 | 0 | 0 |
| >=70 | 0 | 0 | 0 |
| >=60 | 0 | 0 | 0 |
| >=50 | 0 | 0 | 0 |


## B1 — Metricas institucionales (columnas fantasma, no gates)

(n=20,000 con >=10 trades OOS | V[SR] del pool=0.00171 | SR0 con N=1e+06 pruebas = 0.201 por trade)

| metrica | media | p95 | max | n>umbral |
|---|---|---|---|---|
| t-stat OOS | +4.61 | +5.98 | +6.69 | 19155 con t>=2 |
| PSR OOS | 0.995 | 1.000 | 1.000 | 19526 con PSR>=0.95 |
| DSR (N=1M) | 0.737 | 0.944 | 1.000 | 813 con DSR>=0.95 |

### ¿Separan mejor que las nuestras? (Spearman contra pf_oos y monkey_oos)

| metrica institucional (IS-side: t-stat de r_is no disponible; se usa OOS-honesto: correlacion entre metricas) |
- tstat_oos: vs pf_oos +0.441 (p=0.0e+00) | vs monkey_oos +0.535 (p=0.0e+00)
- psr_oos: vs pf_oos +0.464 (p=0.0e+00) | vs monkey_oos +0.534 (p=0.0e+00)
- dsr: vs pf_oos +0.924 (p=0.0e+00) | vs monkey_oos +0.395 (p=0.0e+00)

### PBO (CSCV, 8 bloques Z1, C(8,4)=70 particiones, 20,000 estrategias)

**PBO = 0.29** (probabilidad de que el campeon in-sample quede bajo la mediana out-of-sample; >0.5 = seleccion = ruido puro; lambda medio +0.89)
