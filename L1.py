# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.05 - INSTITUTIONAL REFINERY
# FILE: L1.py
# ROL: Ingesta y Feature Engineering PARALELIZADO con ADN Vitaminado.
# ##########################################################################
import os, sys, pandas as pd, numpy as np, talib as ta, warnings
import re, shutil
from pathlib import Path
from joblib import Parallel, delayed

warnings.filterwarnings("ignore")

LOCAL_TEMP = "C:/temp"
DATA_DIR = Path("data")
current_dir = os.getcwd()

if "Z:" in current_dir or "Google Drive" in current_dir:
    GLOBAL_CLOUD_BASE = os.path.join(current_dir, "COSECHA")
else:
    GLOBAL_CLOUD_BASE = os.path.join(current_dir, "COSECHA")

KNOWN_SYMBOLS = ["USATECHIDXUSD", "USATECH", "XAUUSD", "XAGUSD", "EURUSD", "GBPUSD",
                 "USDJPY", "EURJPY", "GBPJPY", "EURGBP", "US500", "USTEC"]

def get_symbol_from_path(path):
    """Detecta el simbolo por catalogo (robusto ante prefijos de fecha tipo
    '2026.6.13EURUSD_...'). Cae a un regex que EXIGE iniciar en letras para no
    confundir la fecha numerica con el simbolo (el regex viejo devolvia '2026')."""
    try:
        base = os.path.basename(path).upper()
        for s in sorted(KNOWN_SYMBOLS, key=len, reverse=True):
            if s in base:
                return s
        match = re.search(r'([A-Z]{3,}[A-Z0-9]{0,12})', base)
        return match.group(1) if match else "UNKNOWN"
    except: return "UNKNOWN"

def load_zoning_config(symbol):
    cfg = {"ph": 25, "pt": 50, "po": 25, "z1_start": None, "z2_start": None}
    try:
        path = DATA_DIR / "assets.csv"
        if path.exists():
            df = pd.read_csv(path)
            row = df[df['Symbol'].apply(lambda x: str(x).upper() in symbol.upper())]
            if not row.empty:
                r = row.iloc[0]
                if 'Pct_Hist' in df.columns: cfg["ph"] = int(r['Pct_Hist'])
                if 'Pct_Train' in df.columns: cfg["pt"] = int(r['Pct_Train'])
                if 'Pct_OOS' in df.columns: cfg["po"] = int(r['Pct_OOS'])
                # Zonificacion por FECHA (preferente sobre %): sella pre-z1_start a Z0.
                for k, col in (("z1_start", "Z1_Start"), ("z2_start", "Z2_Start")):
                    if col in df.columns and pd.notna(r[col]) and str(r[col]).strip():
                        cfg[k] = pd.Timestamp(str(r[col]).strip())
    except Exception: pass
    return cfg

def calculate_fractal_efficiency_internal(close_prices, p):
    """Cálculo de Eficiencia Fractal para detectar Tendencia vs Rango."""
    net_change = np.abs(close_prices - np.roll(close_prices, p))
    sum_changes = pd.Series(np.abs(close_prices - np.roll(close_prices, 1))).rolling(p).sum().values
    return net_change / (sum_changes + 1e-9)

def compute_indicator_block(p, h, l, c, v):
    """Calcula bloque de indicadores incluyendo ADN v104."""
    block = {}
    block[f'rsi_{p}'] = ta.RSI(c, p)
    block[f'mfi_{p}'] = ta.MFI(h, l, c, v, p)
    block[f'cci_{p}'] = ta.CCI(h, l, c, p)
    block[f'willr_{p}'] = ta.WILLR(h, l, c, p)
    block[f'adx_{p}'] = ta.ADX(h, l, c, p)
    block[f'aroon_{p}'] = ta.AROONOSC(h, l, p)
    up, mi, lo = ta.BBANDS(c, p)
    block[f'bbw_{p}'] = (up - lo) / (mi + 1e-6)
    block[f'ema_{p}'] = ta.EMA(c, p)
    block[f'slope_{p}'] = pd.Series(block[f'ema_{p}']).pct_change(3).values * 100
    block[f'cmo_{p}'] = ta.CMO(c, p)
    block[f'roc_{p}'] = ta.ROC(c, p)
    block[f'natr_{p}'] = ta.NATR(h, l, c, p)
    block[f'std_{p}'] = ta.STDDEV(c, p, nbdev=1.0)
    slowk, _ = ta.STOCH(h, l, c, fastk_period=p, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
    block[f'stoch_{p}'] = slowk
    
    # --- v104 ADN VITAMINADO ---
    block[f'linreg_{p}'] = ta.LINEARREG_SLOPE(c, p)
    block[f'efficiency_{p}'] = calculate_fractal_efficiency_internal(c, p)
    atr = ta.ATR(h, l, c, p)
    atr_ser = pd.Series(atr)
    block[f'vol_z_{p}'] = (atr_ser - atr_ser.rolling(p).mean()) / (atr_ser.rolling(p).std() + 1e-9)

    # --- v106 ADN AMPLIADO (todos con traducción MQL5 garantizada en el registro) ---
    block[f'mom_{p}'] = ta.MOM(c, p)
    _, _, macd_hist = ta.MACD(c, fastperiod=p, slowperiod=p * 2, signalperiod=9)
    block[f'macdh_{p}'] = macd_hist
    block[f'trix_{p}'] = ta.TRIX(c, p)
    block[f'plus_di_{p}'] = ta.PLUS_DI(h, l, c, p)
    block[f'minus_di_{p}'] = ta.MINUS_DI(h, l, c, p)
    # Force Index: EMA(p) de (deltaClose * volumen) — réplica exacta en X1_FORCE (MQL5)
    force_raw = (c - np.roll(c, 1)) * v
    force_raw[0] = 0.0
    block[f'force_{p}'] = ta.EMA(force_raw, p)

    return block

def layer1():
    try:
        if len(sys.argv) < 3: return
        csv_path, op = sys.argv[1], sys.argv[2]
        
        tf_mapping = {"0": "1h", "1": "30min", "2": "15min", "3": "4h"}
        label_mapping = {"0": "H1", "1": "M30", "2": "M15", "3": "H4"}
        
        target_tf, tf_label = tf_mapping.get(op, "1h"), label_mapping.get(op, "H1")
        sym = get_symbol_from_path(csv_path)
        z_cfg = load_zoning_config(sym)
        
        if not os.path.exists(LOCAL_TEMP): os.makedirs(LOCAL_TEMP)
        print(f"\033[96m[L1] REFINERÍA v104 | {sym} @ {tf_label}\033[0m")
        
        df = pd.read_csv(csv_path, sep=',', engine='c', on_bad_lines='skip')
        df.columns = [c.replace('<','').replace('>','').strip().capitalize() for c in df.columns]
        
        d_cols = [c for c in df.columns if any(x in c.lower() for x in ['date', 'gmt', 'time'])]
        dt_s = df[d_cols[0]].astype(str) + " " + df[d_cols[1]].astype(str) if len(d_cols) >= 2 else df[d_cols[0]].astype(str)
        # Formato Dukascopy nuevo (YYYYMMDD HH:MM:SS.mmm); si no cuaja, formato viejo europeo con puntos.
        df['DateTime'] = pd.to_datetime(dt_s, format='%Y%m%d %H:%M:%S.%f', errors='coerce')
        if df['DateTime'].isna().mean() > 0.5:
            df['DateTime'] = pd.to_datetime(dt_s.str.replace('.', '-', regex=False), dayfirst=True, errors='coerce')
        
        for c_name in ['Open', 'High', 'Low', 'Close', 'Volume']:
            if c_name in df.columns: 
                df[c_name] = pd.to_numeric(df[c_name].astype(str).str.replace(',', '.'), errors='coerce')
        
        df = df.dropna(subset=['DateTime', 'Close']).set_index('DateTime')
        df_res = df.resample(target_tf).agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last', 'Volume':'sum'}).dropna().reset_index()
        
        c, h, l, v = df_res.Close.values.astype(np.float64), df_res.High.values.astype(np.float64), df_res.Low.values.astype(np.float64), df_res.Volume.values.astype(np.float64)
        
        # FIBONACCI + CICLOS INSTITUCIONALES
        periods = [5, 8, 13, 21, 34, 55, 89, 144, 200, 24, 48, 120]
        results = Parallel(n_jobs=-1)(delayed(compute_indicator_block)(p, h, l, c, v) for p in periods)
        
        new_f = {}
        for r in results: new_f.update(r)
        
        for hor in [12, 24, 48, 72, 96]:
            new_f[f'Ret_{hor}'] = (pd.Series(c).shift(-hor) - c).values / c

        # B2 (exp. nocturno): features de sesión — la estructura horaria del
        # oro (Asia/Londres/NY) como gen minable. Numéricas, entran al shift
        # _sft como todo el ADN. dow se guarda en convención MQL5 (1=Lun..5=Vie:
        # pandas dayofweek+1), así el EA lee t.day_of_week sin mapeos.
        new_f['hour'] = df_res.DateTime.dt.hour.values.astype(np.float64)
        new_f['dow'] = (df_res.DateTime.dt.dayofweek.values + 1).astype(np.float64)

        df_features = pd.DataFrame(new_f).replace([np.inf, -np.inf], np.nan).ffill().bfill().fillna(0).astype(np.float32)
        shift_cols = {f'{k}_sft': df_features[k].shift(1) for k in df_features.columns if 'Ret_' not in k}
        shift_cols['Close_sft'] = pd.Series(c).shift(1).astype(np.float32)
        
        # v106: conservamos High/Low para medir MFE/MAE intra-trade (Excursion Score).
        # No introducen lookahead: solo se usan para valorar excursiones de trades pasados.
        df_fin = pd.concat([df_res[['DateTime', 'Close', 'High', 'Low']], df_features[[k for k in df_features.columns if 'Ret_' in k]], pd.DataFrame(shift_cols)], axis=1).dropna()
        df_fin.set_index('DateTime', drop=False, inplace=True)
        
        df_fin['Zone'] = 0
        if z_cfg['z1_start'] is not None and z_cfg['z2_start'] is not None:
            # Corte por FECHA: Z0 = contexto sellado (pre-z1_start), Z1 = train, Z2 = OOS.
            dt_idx = df_fin['DateTime']
            df_fin.loc[dt_idx >= z_cfg['z1_start'], 'Zone'] = 1
            df_fin.loc[dt_idx >= z_cfg['z2_start'], 'Zone'] = 2
        else:
            # Compatibilidad con data sin fechas de zona: corte por porcentaje de filas.
            t_len = len(df_fin)
            cut1, cut2 = int(t_len * z_cfg['ph'] / 100), int(t_len * (z_cfg['ph'] + z_cfg['pt']) / 100)
            df_fin.iloc[cut1:cut2, df_fin.columns.get_loc('Zone')] = 1
            df_fin.iloc[cut2:, df_fin.columns.get_loc('Zone')] = 2
        
        out_name = f"X1_FULL_{sym.upper()}_{tf_label.upper()}.parquet"
        local_target = os.path.join(LOCAL_TEMP, out_name)
        df_fin.to_parquet(local_target, compression='snappy')
        
        cloud_market_dir = os.path.join(GLOBAL_CLOUD_BASE, "DATOS_MERCADO")
        os.makedirs(cloud_market_dir, exist_ok=True)
        shutil.copy2(local_target, os.path.join(cloud_market_dir, out_name))
        print(f"\033[92m[L1] ÉXITO v104: {out_name} con ADN Vitaminado.\033[0m")

    except Exception as e: print(f"\033[91m[ERR L1] {e}\033[0m")

if __name__ == '__main__': layer1()