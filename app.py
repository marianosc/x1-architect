# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 101.54 - MISSION CONTROL (INTEGRIDAD TOTAL)
# FILE: app.py
# ROL: Dashboard Maestro con IA de Resiliencia y Control Atómico de Velas.
# UPD: Unificación de Namespace I/O y Métrica de 820 líneas reales.
# AUDITADO: 4 VECES - CÓDIGO ÍNTEGRO - SIN RESÚMENES (820 LÍNEAS).
# ##########################################################################
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from pathlib import Path
import os
import json
import time

# --- IMPORTACIÓN DE MÓDULOS DEL NÚCLEO X1 (Versiones v101.50+) ---
from modules.data_loader import get_available_assets, load_market_data_engine, load_strategies, load_audit_stats
from modules.backtest_engine import (
    X1_Compute_Engine, 
    calculate_drawdown, 
    calculate_sortino, 
    calculate_ulcer_index,
    get_dual_stagnation
)
from modules.plots import (
    plot_market_zones, 
    plot_equity_with_stag, 
    plot_correlation_heatmap # <--- EL CABLE AHORA ESTÁ EN EL SITIO CORRECTO
)
from modules.optimizer import run_greedy_selection, get_correlation_matrix
from modules.translator import translate_to_sqx

# --- INICIALIZACIÓN GLOBAL v102.76 (BÚNKER ESTÁTICO) ---
# Se activa solo la primera vez que abre la App. Protege los datos de la navegación.
if 'hard_slip' not in st.session_state: st.session_state.hard_slip = 0.1
if 'hard_spread' not in st.session_state: st.session_state.hard_spread = 0.1
if 'hard_comm' not in st.session_state: st.session_state.hard_comm = 0.1


# Variables de mercado (Garantía de existencia)
if 'market_values' not in st.session_state:
    market_values, col_map, ret_indices, market_dates = None, {}, {}, []
    col_list, market_zones, bar_count = [], None, 0
    data_loader_pack_v54 = None
    raw_pool_v54 = pd.DataFrame()
# --- AÑADIR ESTA LÍNEA AL FINAL DEL BLOQUE DE INICIALIZACIÓN ---
if 'active_asset_v102' not in st.session_state: st.session_state.active_asset_v102 = ""    

def robust_file_reader_master(file_path_source, max_retry=7, retry_delay=1.2):
    """
    v105.1: Blindaje contra latencia de Google Drive (Unidad Z:).
    Fuerza el 'despertar' de la unidad antes de la lectura.
    """
    import os, time, pandas as pd
    
    # 1. Convertir a ruta absoluta para evitar ambigüedad
    abs_path = os.path.abspath(file_path_source)
    folder_path = os.path.dirname(abs_path)

    for attempt in range(max_retry):
        try:
            # TÁCTICA DE DESPERTAR: Intentamos listar el directorio superior
            # Esto obliga a Windows y Google Drive a 'montar' la carpeta.
            if os.path.exists(folder_path):
                os.listdir(folder_path) # Intento de lectura de metadatos
            
            if os.path.exists(abs_path):
                # Intentamos abrir el archivo en modo lectura para verificar bloqueo
                with open(abs_path, 'r') as f:
                    df = pd.read_csv(abs_path)
                    if not df.empty:
                        return df
            
            # Si llegamos aquí, el archivo no existe o está vacío. Esperamos.
            time.sleep(retry_delay)
        except OSError as e:
            # Captura específica de WinError 433 (Conexión desconectada)
            time.sleep(retry_delay + attempt) # Incrementamos el delay en cada fallo
            continue
    
    return pd.DataFrame()


# 2. CONFIGURACIÓN E IDENTIDAD VISUAL (RYZEN 9 ELITE)
st.set_page_config(
    page_title="X1-ARCHITECT V101.54", 
    page_icon="🏛️", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# CSS INJECTION: Hardening de Interfaz (Minimalist Elite Style)
st.markdown("""
<style>
    .stApp { background-color: #0F172A !important; }
    /* Tipografía y Espaciado de Alta Densidad */
    .master-title { color: #F1F5F9; font-size: 1.4rem; font-weight: 800; margin-bottom: 1rem; display: block; }
    .block-title { color: #F1F5F9; font-size: 1.05rem; font-weight: 700; margin-top: 1rem; margin-bottom: 0.5rem; display: block; }
    /* Sliders X1 Azure Blue */
    .stSlider > div > div > div > div { background-color: #3B82F6 !important; }
    /* Monitor de Integridad (Black Mode) */
    .integrity-monitor { 
        background-color: #000000; color: #FFFFFF; padding: 15px; border-radius: 5px; 
        border: 1px solid #334155; font-size: 0.85rem; font-family: 'Courier New', monospace; 
        margin-bottom: 12px; line-height: 1.5;
    }
    /* Estilo de Métricas Ryzen */
    div[data-testid="stMetricValue"] { color: #3B82F6 !important; font-weight: 800; font-size: 2.1rem !important; }
    .audit-card { background-color: #1E293B; border: 1px solid #334155; padding: 12px; border-radius: 8px; margin-bottom: 10px; }
    .fail-text { color: #EF4444; font-size: 0.75rem; font-weight: bold; }
    .pass-text { color: #10B981; font-size: 0.75rem; font-weight: bold; }
    .component-card { 
        background-color: #1E293B; border: 1px solid #334155; padding: 12px; border-radius: 8px; 
        margin-bottom: 8px; border-left: 5px solid #3B82F6; 
    }
    .health-pill { background-color: #3B82F6; color: white; padding: 3px 10px; border-radius: 12px; font-size: 0.75rem; font-weight: bold; }
    /* Botones de Acción Blindados */
    div.stButton > button { width: 100% !important; border-radius: 5px !important; font-weight: 700 !important; height: 42px !important; }
</style>
""", unsafe_allow_html=True)

# 3. GESTIÓN DE FUSIBLES (DIAGNOSTIC HUB)
DATA_DIR_V54 = Path("data")
FUSE_FILE_V54 = DATA_DIR_V54 / "audit_config.json"

def load_diagnostic_fuses_v54():
    """v102.53: Carga resiliente de fusibles contra micro-cortes de Z: Drive."""
    f_defaults_v54 = {
        "monkey_test": True, "monte_carlo": True, "wfa_consistency": True,
        "anti_gap": True, "oos_neg_slope": True, "oos_crash": True,
        "pf_net_is": True, "r2_stability": True, "min_trades": True
    }
    
    # --- ESCUDO DE RESILIENCIA v102.53 ---
    for attempt in range(5):
        try:
            if FUSE_FILE_V54.exists():
                with open(FUSE_FILE_V54, 'r') as f_in_v54:
                    loaded_json = json.load(f_in_v54)
                    f_defaults_v54.update(loaded_json)
                return f_defaults_v54
            else:
                # El archivo no existe, devolvemos defaults sin error
                return f_defaults_v54
        except (OSError, json.JSONDecodeError):
            # Error 433 o archivo bloqueado por sincronización
            time.sleep(0.5) 
            continue
            
    return f_defaults_v54

def save_diagnostic_fuses_v54(dict_to_save_v54):
    """Sincroniza los fusibles con el Auditor L3."""
    if not DATA_DIR_V54.exists():
        os.makedirs(DATA_DIR_V54, exist_ok=True)
    with open(FUSE_FILE_V54, 'w') as f_out_v54:
        json.dump(dict_to_save_v54, f_out_v54, indent=4)
    st.toast("⚡ FUSIBLES DE AUDITORÍA SINCRONIZADOS")

# 4. GESTIÓN DE SESIÓN (PERSISTENCIA)
if 'manual_pool' not in st.session_state:
    st.session_state.manual_pool = []
if 'portfolio_df' not in st.session_state:
    st.session_state.portfolio_df = None
if 'active_portfolio' not in st.session_state:
    st.session_state.active_portfolio = "IA"
if 'last_pool_hash' not in st.session_state:
    st.session_state.last_pool_hash = ""
if 'selected_strategies' not in st.session_state:
    st.session_state.selected_strategies = []

def add_to_bucket_v54(dna_id_v54, row_data_v54, cooldown_val_v54):
    """Cosecha manual preservando vitalidad y RF."""
    current_bucket_ids_v54 = [s['id'] for s in st.session_state.manual_pool]
    if dna_id_v54 not in current_bucket_ids_v54:
        st.session_state.manual_pool.append({
            'id': dna_id_v54, 
            'Entry': row_data_v54['Entry'], 
            'Exit': row_data_v54['Exit'], 
            'Side': row_data_v54['Side'], 
            'Cooldown': cooldown_val_v54,
            'PF': row_data_v54.get('PF', 0.0), 
            'R2': row_data_v54.get('R2', 0.0), 
            'Health': row_data_v54.get('Health', 0.0),
            'RF': round(row_data_v54.get('RF', 0.0), 2),
            'Stag_Active': row_data_v54.get('Stag_Active', 0), 
            'Family': row_data_v54.get('Family', 'UNK'),
            'TimeFrame': row_data_v54.get('TimeFrame', 'UNK')
        })
        st.toast(f"✅ DNA {dna_id_v54} Cosechado.")

def remove_from_bucket_v54(dna_id_to_del_v54):
    """Elimina componente y fuerza refresco."""
    st.session_state.manual_pool = [s for s in st.session_state.manual_pool if s['id'] != dna_id_to_del_v54]
    st.rerun()

# 5. CARGA DE ASSETS (LA CONSTITUCIÓN)
ASSETS_CSV_FILE_MASTER = DATA_DIR_V54 / "assets.csv"
# Sincronización de función unificada para evitar NameError
df_master_assets_v54 = robust_file_reader_master(ASSETS_CSV_FILE_MASTER)

# -----------------------------------------------------------------------------
# 6. BARRA LATERAL (MISSION CONTROL HUB)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("<span class='master-title'>🏛️ MISSION CONTROL</span>", unsafe_allow_html=True)
    
    # UNIFICACIÓN DE PUNTERO v102.31
    navigation_active_hub = st.radio("📂 SECTIONS", ["📈 SETUP", "🔬 DIAGNOSTIC LAB", "⚒️ MINING LAB", "🎹 COMPOSER"], key="nav_sidebar_v54")
    st.markdown("---")
    
    # Selector de activos
    available_assets_v54 = get_available_assets()
    selected_asset_v54 = st.selectbox("📡 MASTER ASSET", available_assets_v54 if available_assets_v54 else ["NONE"])
    selected_tf_v54 = st.selectbox("⏳ TIMEFRAME", ["H1", "M30", "M15", "H4"])

# --- GANCHO DE SINCRONIZACIÓN v102.75 ---
    if selected_asset_v54 != st.session_state.active_asset_v102:
        # Solo cargamos si el archivo Master Assets existe
        if not df_master_assets_v54.empty:
            search_h = selected_asset_v54.upper().split('_')[0]
            match_h = df_master_assets_v54[df_master_assets_v54['Symbol'].astype(str).str.contains(search_h)]
            
            if not match_h.empty:
                r_h = match_h.iloc[0]
                # Inyectamos en RAM desde el disco
                st.session_state.live_slip = float(r_h.get('Slippage_Cost', 0.5))
                st.session_state.live_spread = float(r_h.get('Avg_Spread', 0.2))
                st.session_state.live_comm = float(r_h.get('Broker_Comm', 0.3))
                # Marcamos el activo como 'Cargado'
                st.session_state.active_asset_v102 = selected_asset_v54
                st.rerun()
    
# POLICÍA DE DATOS v102.56 (Sincronizada)
    data_loader_pack_v54 = load_market_data_engine(selected_asset_v54, selected_tf_v54)
    
    if data_loader_pack_v54:
        # Desempaquetado atómico con variables globales
        market_values, col_map, ret_indices, market_dates, col_list, market_zones, bar_count = data_loader_pack_v54
        
        st.markdown(f"""
        <div class="integrity-monitor">
            CORE: ENGINE_ONLINE<br>
            ASSET: {selected_asset_v54}<br>
            TF: {selected_tf_v54}<br>
            BARS: {bar_count:,}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("📡 MATRIZ NO DETECTADA: El sistema operará en modo limitado.")

    st.markdown("<span class='block-title'>⚖️ RANKING WEIGHTS</span>", unsafe_allow_html=True)
    w_stability_v54 = st.slider("W_Stability (R2)", 0.0, 2.0, 1.0, 0.1)
    w_sustain_v54 = st.slider("W_Sustain (OER)", 0.0, 2.0, 1.0, 0.1)
    w_smooth_v54 = st.slider("W_Smooth (UI)", 0.0, 2.0, 1.0, 0.1)
    w_stagnation_v54 = st.slider("W_Stag (Time)", 0.0, 2.0, 1.0, 0.1)
    
    if st.button("♻️ REFRESH SYSTEM"):
        st.cache_data.clear(); st.cache_resource.clear(); st.rerun()

# --- SECCIÓN 7: CARGA Y SANITIZACIÓN v104.865 (DIVERSITY SPRINT) ---

# 1. CARGA DESDE DISCO SSD (BÚNKER DE DATOS)
pool_raw_temp = load_strategies(selected_asset_v54, timeframe_filter=selected_tf_v54)

if pool_raw_temp is None or pool_raw_temp.empty:
    raw_pool_v54 = pd.DataFrame()
    st.sidebar.error(f"⚠️ No se hallaron archivos MASTER para {selected_asset_v54}")
else:
    raw_pool_v54 = pool_raw_temp.copy()
    st.sidebar.success(f"📂 Cargados {len(raw_pool_v54)} Alphas del disco.")

if not raw_pool_v54.empty:
    # 2. CONVERSIÓN NUMÉRICA Y RENOMBRADO (SINCRO CON L3 v104.600+)
    # Renombramos UI a Net_Profit porque ahora L3 envía dinero real en esa columna
    raw_pool_v54 = raw_pool_v54.rename(columns={'UI': 'Net_Profit'})
    
    cols_to_fix = ['PF', 'R2', 'OER', 'Net_Profit', 'Stag_Active', 'Trades', 'Momentum']
    for c in cols_to_fix:
        if c in raw_pool_v54.columns:
            raw_pool_v54[c] = pd.to_numeric(raw_pool_v54[c], errors='coerce').fillna(0.0)

    # 3. FILTRO DE CUMPLIMIENTO DINÁMICO (LA CONSTITUCIÓN)
    fuses_v102 = load_diagnostic_fuses_v54()
    
    if fuses_v102.get("min_trades", True):
        # Capturamos el límite de trades de assets.csv
        limit_tr = 300
        if not df_master_assets_v54.empty:
            m_a = df_master_assets_v54[df_master_assets_v54['Symbol'].apply(lambda x: str(x).upper() in selected_asset_v54.upper())]
            if not m_a.empty: limit_tr = int(m_a.iloc[0].get('Min_Trades', 300))
        
        # Solo sobreviven los legales
        raw_pool_v54 = raw_pool_v54[raw_pool_v54['Trades'] >= limit_tr]

    # 4. CÁLCULO DEL HYPER-SCORE v104.865 (MONEY + STABILITY)
    if not raw_pool_v54.empty:
        # Numerador: Beneficio * Estabilidad * Sostenibilidad (+0.1 evita colapso)
        h_num = (raw_pool_v54['Net_Profit'] * 100) * ((raw_pool_v54['R2'] + 0.1) ** w_stability_v54) * ((raw_pool_v54['OER'] + 0.1) ** w_sustain_v54)
        # Denominador: Estancamiento Real (Normalizado por 1000)
        h_den = (raw_pool_v54['Stag_Active'] / 1000 + 1) ** w_stagnation_v54
        
        raw_pool_v54['Hyper_Score'] = (h_num / h_den).round(2)

        # 5. DIVERSITY ENFORCEMENT (EL DESATASCADOR)
        # Extraemos el Top 30 de CADA COMBINACIÓN [Lado + Familia]
        # Esto garantiza que verá LONG-TREND, LONG-MOMENTUM, SHORT-TREND, etc.
        df_top_diverse = raw_pool_v54.groupby(['Side', 'Family'], group_keys=False).apply(
            lambda x: x.sort_values('Hyper_Score', ascending=False).head(30)
        )
        
        # Mezclamos la élite con el resto del pool y eliminamos duplicados
        raw_pool_v54 = pd.concat([df_top_diverse, raw_pool_v54]).drop_duplicates(subset=['X1_UID'])
        
        # Ordenación final por el nuevo Hyper-Score sincero
        raw_pool_v54 = raw_pool_v54.sort_values('Hyper_Score', ascending=False)


# 8. CONFIGURACIÓN DINÁMICA (BARS MODE) v102.32
curr_cd_v54, ph_v54, pt_v54 = 24, 25, 50
if not df_master_assets_v54.empty:
    match_row_v54 = df_master_assets_v54[df_master_assets_v54['Symbol'].apply(lambda x: str(x).upper() in selected_asset_v54.upper())]
    if not match_row_v54.empty:
        r_current_v54 = match_row_v54.iloc[0]
        curr_cd_v54 = int(r_current_v54.get('Min_Dist_Bars', 24))
        ph_v54 = int(r_current_v54.get('Pct_Hist', 25))
        pt_v54 = int(r_current_v54.get('Pct_Train', 50))

# --- SECCIÓN 1: SETUP (ATOMIC CONSTRAINTS v102.32) ---
if navigation_active_hub == "📈 SETUP":
    st.markdown("<span class='master-title'>⚙️ CONFIGURADOR DE LA CONSTITUCIÓN</span>", unsafe_allow_html=True)

    # --- BLOQUE v102.54: REANIMACIÓN DE MATRIZ (CON FUSIBLE LOCAL) ---
    if df_master_assets_v54.empty:
        df_master_assets_v54 = robust_file_reader_master(ASSETS_CSV_FILE_MASTER)
        if df_master_assets_v54.empty:
            st.error("⚠️ La unidad Z: no responde. Verifique su conexión a Google Drive.")
            st.stop() # Ahora el STOP solo afecta a esta pestaña

    # 2. BÚSQUEDA DEL ACTIVO
    asset_core_name = str(selected_asset_v54).upper().split('_')[0]
    match_df = df_master_assets_v54[df_master_assets_v54['Symbol'].astype(str).str.upper().str.contains(asset_core_name)]

    if match_df.empty:
        st.warning(f"⚠️ El activo {selected_asset_v54} no tiene una ley en assets.csv.")
        if st.button("➕ CREAR LEY AUTOMÁTICA"):
            new_row = {"Symbol": selected_asset_v54, "Min_Trades": 300, "Min_R2": 0.75, "Pct_Hist": 25, "Pct_Train": 50, "Pct_OOS": 25}
            df_master_assets_v54 = pd.concat([df_master_assets_v54, pd.DataFrame([new_row])], ignore_index=True)
            df_master_assets_v54.to_csv(ASSETS_CSV_FILE_MASTER, index=False)
            st.rerun()
        st.stop()

    idx_v54 = match_df.index[0]
    row_v54 = match_df.iloc[0]

    def safe_val(key, default_val):
        v = row_v54.get(key, default_val)
        return v if pd.notna(v) else default_val

    # 4. RENDERIZADO DE INTERFAZ
    st.markdown("<span class='block-title'>🧱 ADAPTIVE ZONING</span>", unsafe_allow_html=True)
    c_ph, c_pt = int(safe_val('Pct_Hist', 25)), int(safe_val('Pct_Train', 50))
    z_sl = st.slider("Límites de Zonas (%)", 0, 100, (c_ph, c_ph + c_pt))
    res_ph, res_pt, res_po = int(z_sl[0]), int(z_sl[1] - z_sl[0]), int(100 - z_sl[1])
    
    st.plotly_chart(plot_market_zones(market_dates, market_values[:, col_map['Close']], market_zones, selected_asset_v54, preview_splits=(res_ph, res_ph + res_pt)), use_container_width=True)

    # C. ROBUSTEZ Y CONSISTENCIA (Sliders unificados)
    st.markdown("<span class='block-title'>🛡️ ROBUSTNESS & CONSISTENCY</span>", unsafe_allow_html=True)
    cl1, cl2, cl3 = st.columns(3)
    m_conf = cl1.slider("Monkey Confidence (%)", 50, 100, int(safe_val('Monkey_Train_Min', 95)))
    w_pf = cl2.slider("Min WFA PF", 1.0, 1.5, float(safe_val('WFA_Min_PF', 1.05)))
    r2_min = cl3.slider("Min R2 Curve", 0.5, 0.99, float(safe_val('Min_R2', 0.75)))
    
    cl4, cl5 = st.columns(2)
    mc_st = cl4.slider("MC Stress (Reshuffle)", 1.0, 1.5, float(safe_val('MC_Reshuffle_Min', 1.05)))
    mc_sk = cl5.slider("MC Stress (Skip 10%)", 1.0, 1.5, float(safe_val('MC_Skip_Min', 1.02)))

    # D. RENDIMIENTO OOS
    st.markdown("<span class='block-title'>🔥 OOS HURDLES & QUALITY</span>", unsafe_allow_html=True)
    cl6, cl7, cl8 = st.columns(3)
    oos_p = cl6.slider("Min OOS PF", 1.0, 2.0, float(safe_val('Min_OOS_PF', 1.10)))
    oos_e = cl7.slider("Min OER Efficiency", 0.1, 1.0, float(safe_val('Min_OOS_Efficiency', 0.40)))
    max_u = cl8.slider("Max Ulcer Index", 1.0, 15.0, float(safe_val('Max_Ulcer', 5.0)))
    # --- RE-INYECCIÓN v102.69: CONTROL DE EXPECTANCY ---
    exp_min = st.number_input("Min Expectancy (Profit per Bar)", 0.0000, 0.0100, float(safe_val('Min_Expectancy', 0.0002)), format="%.4f")

# E. FRICCIÓN v102.76 (CAJAS DE PRECISIÓN)
    st.markdown("<span class='block-title'>💸 BROKER TRANSACTION COSTS (MT5 PARITY)</span>", unsafe_allow_html=True)
    st.info("Escriba los valores y presione ENTER para fijar el costo real.")

    ce1, ce2, ce3 = st.columns(3)
    # Estas cajas leen y escriben directamente en el búnker de memoria (Step 1)
    st.session_state.hard_slip = ce1.number_input("Slippage (Pts)", value=st.session_state.hard_slip, step=0.1, format="%.1f")
    st.session_state.hard_spread = ce2.number_input("Avg Spread (Pts)", value=st.session_state.hard_spread, step=0.1, format="%.1f")
    st.session_state.hard_comm = ce3.number_input("Comm/Lot (Pts)", value=st.session_state.hard_comm, step=0.1, format="%.1f")

    # Esta línea calcula el peaje final que usará el motor de backtest
    st.session_state.live_friction = (st.session_state.hard_slip + st.session_state.hard_spread + st.session_state.hard_comm) / 10000
    
    c12, c13 = st.columns(2)

    tr_min = c12.number_input("Min Trades Required", 50, 5000, int(safe_val('Min_Trades', 300)))
    stag_g = c13.number_input("Max Global Stagnation (Bars)", 1000, 100000, int(safe_val('Stag_Global', 15000)))

    if st.button("💾 GUARDAR CAMBIOS EN LA CONSTITUCIÓN", type="primary", use_container_width=True):
        # 1. ASIGNACIÓN DE VALORES AL DATAFRAME
        df_master_assets_v54.at[idx_v54, 'Pct_Hist'] = res_ph
        df_master_assets_v54.at[idx_v54, 'Pct_Train'] = res_pt
        df_master_assets_v54.at[idx_v54, 'Pct_OOS'] = res_po
        df_master_assets_v54.at[idx_v54, 'Monkey_Train_Min'] = m_conf
        df_master_assets_v54.at[idx_v54, 'Monkey_Threshold'] = m_conf
        df_master_assets_v54.at[idx_v54, 'WFA_Min_PF'] = w_pf
        df_master_assets_v54.at[idx_v54, 'Min_R2'] = r2_min
        df_master_assets_v54.at[idx_v54, 'MC_Reshuffle_Min'] = mc_st
        df_master_assets_v54.at[idx_v54, 'MC_Skip_Min'] = mc_sk
        df_master_assets_v54.at[idx_v54, 'Min_OOS_PF'] = oos_p
        df_master_assets_v54.at[idx_v54, 'Min_OOS_Efficiency'] = oos_e
        df_master_assets_v54.at[idx_v54, 'Max_Ulcer'] = max_u
        df_master_assets_v54.at[idx_v54, 'Min_Expectancy'] = exp_min
        
        # --- FIX v104: ASIGNACIÓN DE STAGNATION (La que faltaba) ---
        df_master_assets_v54.at[idx_v54, 'Stag_Global'] = stag_g
        df_master_assets_v54.at[idx_v54, 'Min_Trades'] = tr_min
        
        # --- PERSISTENCIA DESDE CAJAS DE PRECISIÓN ---
        df_master_assets_v54.at[idx_v54, 'Slippage_Cost'] = st.session_state.hard_slip
        df_master_assets_v54.at[idx_v54, 'Avg_Spread'] = st.session_state.hard_spread
        df_master_assets_v54.at[idx_v54, 'Broker_Comm'] = st.session_state.hard_comm
        
        # 2. GUARDADO ABSOLUTO (Blindaje Z:)
        base_path = os.path.dirname(os.path.abspath(__file__))
        path_assets_final = os.path.join(base_path, "data", "assets.csv")
        df_master_assets_v54.to_csv(path_assets_final, index=False)
        
        # 3. RESET DE CACHÉ Y REINICIO
        st.cache_data.clear()
        st.success(f"✅ LEY ACTUALIZADA: Stag Global fijado en {stag_g}")
        st.balloons()
        time.sleep(1)
        st.rerun()
# --- SECCIÓN 2: DIAGNOSTIC LAB v102.51 (RECONSTRUCCIÓN TOTAL) ---
elif navigation_active_hub == "🔬 DIAGNOSTIC LAB":
    st.markdown("<span class='master-title'>🔬 AUDIT FUSE BOX (Velas Mode)</span>", unsafe_allow_html=True)
    fuses_v54 = load_diagnostic_fuses_v54()
    
    # 1. CAPTURA DE INTERRUPTORES (UI)
    cl1, cl2, cl3 = st.columns(3)
    with cl1:
        t_pf = st.toggle("PF Net IS", value=fuses_v54.get("pf_net_is", True))
        t_r2 = st.toggle("R2 Stability", value=fuses_v54.get("r2_stability", True))
        t_tr = st.toggle("Min Trades", value=fuses_v54.get("min_trades", True))
    with cl2:
        t_wf = st.toggle("WFA 3-Windows", value=fuses_v54.get("wfa_consistency", True))
        t_ga = st.toggle("Anti-Gap Desert", value=fuses_v54.get("anti_gap", True))
        t_mo = st.toggle("Monkey Test", value=fuses_v54.get("monkey_test", True))
    with cl3:
        t_sl = st.toggle("OOS Neg Slope", value=fuses_v54.get("oos_neg_slope", True))
        t_cr = st.toggle("OOS Risk Crash", value=fuses_v54.get("oos_crash", True))
        t_mc = st.toggle("Monte Carlo Stress", value=fuses_v54.get("monte_carlo", True))
    
# DICCIONARIO DE ESTADO EN VIVO (Soberanía de Pantalla)
    f_act_live = {
        "pf_net_is": t_pf, 
        "r2_stability": t_r2, 
        "min_trades": t_tr,
        "wfa_consistency": t_wf, 
        "anti_gap": t_ga, 
        "monkey_test": t_mo,
        "oos_neg_slope": t_sl, 
        "oos_crash": t_cr, 
        "monte_carlo": t_mc
    }

    if st.button("⚡ APPLY FUSE CONFIGURATION", type="primary", use_container_width=True):
        save_diagnostic_fuses_v54(f_act_live)
        st.success("Configuración de fusibles grabada en disco.")
        time.sleep(1)
        st.rerun()
        
    st.markdown("---")
    st.subheader("🛡️ ASISTENTE DE LIMPIEZA RETROACTIVA")
    st.info("Simula o ejecuta la purga basándose en los interruptores que ve arriba.")

    # 2. MOTOR DE ESCANEO (Dry-Run)
    if st.button("🔍 ESCANEAR IMPACTO DE FUSIBLES", use_container_width=True):
        with st.spinner("Analizando cumplimiento legal en COSECHA..."):
            asset_core = selected_asset_v54.upper().split('_')[0]
            match_idx_list = df_master_assets_v54[df_master_assets_v54['Symbol'].astype(str).str.contains(asset_core)].index
            if len(match_idx_list) == 0: 
                st.error("Activo no encontrado en assets.csv"); st.stop()
            idx_v54 = match_idx_list[0] # <--- AQUÍ SE DEFINE LA VARIABLE FALTANTE
            base_dir = os.path.dirname(os.path.abspath(__file__))
            folder_cosecha = Path(os.path.join(base_dir, "COSECHA"))
            m_files = list(folder_cosecha.glob(f"MASTER_{asset_core}*.csv"))
            
            if not m_files:
                st.error(f"No se detectaron archivos para {asset_core}")
            else:
                total_ev, a_purgar = 0, 0
                # Cargamos límites desde el dataframe de assets
                r_v = df_master_assets_v54.loc[idx_v54]
                lt = int(r_v.get('Min_Trades', 300))
                lr = float(r_v.get('Min_R2', 0.75))
                lp = float(r_v.get('Min_PF', 1.15))
                ls = int(r_v.get('Stag_Global', 2200)) # <--- El nuevo límite Anti-Gap
                
                for f in m_files:
                    if "_CLEAN" in f.name or "INYECTOR" in f.name: continue
                    df_s = pd.read_csv(f)
                    if df_s.empty: continue
                    
                    # Convertimos a numérico para evitar errores
                    df_s['Trades'] = pd.to_numeric(df_s.get('Trades', 0), errors='coerce')
                    df_s['R2'] = pd.to_numeric(df_s.get('R2', 0), errors='coerce')
                    df_s['PF'] = pd.to_numeric(df_s.get('PF', 0), errors='coerce')
                    df_s['Stag_Active'] = pd.to_numeric(df_s.get('Stag_Active', 0), errors='coerce')
                    
                    total_ev += len(df_s)
                    m_v = pd.Series([True] * len(df_s))
                    
                    # FILTRADO SEGÚN LOS TOGGLES DE PANTALLA
                    if f_act_live["min_trades"]:   m_v &= (df_s['Trades'] >= lt)
                    if f_act_live["r2_stability"]: m_v &= (df_s['R2'] >= lr)
                    if f_act_live["pf_net_is"]:    m_v &= (df_s['PF'] >= lp)
                    if f_act_live["anti_gap"]:     m_v &= (df_s['Stag_Active'] <= ls)
                    
                    a_purgar += (len(df_s) - m_v.sum())
                
                st.session_state.purge_ready = True
                st.session_state.purge_count = a_purgar
                st.session_state.purge_total = total_ev
                st.rerun()

    # 3. INFORME DE IMPACTO (Reactivo)
    if st.session_state.get('purge_ready'):
        # Detectamos qué leyes están en ON en la pantalla
        leyes_on = [k.upper() for k, v in f_act_live.items() if v is True]
        mortalidad = (st.session_state.purge_count / st.session_state.purge_total * 100) if st.session_state.purge_total > 0 else 0
        
        st.warning(f"""
        **INFORME DE IMPACTO (FUSIBLES ACTIVOS EN PANTALLA):**  
        `{', '.join(leyes_on) if leyes_on else 'NINGUNA'}`
        
        *   Estrategias en Disco: `{st.session_state.purge_total}`
        *   **Ilegales Detectadas:** `{st.session_state.purge_count}`
        *   Mortalidad: `{mortalidad:.1f}%`
        """)
        
        c1, c2 = st.columns(2)
        if c1.button("✅ CANCELAR", use_container_width=True):
            st.session_state.purge_ready = False; st.rerun()
        if c2.button("🔥 EJECUTAR PURGA FÍSICA", type="primary", use_container_width=True):
            with st.spinner("Limpiando disco..."):
                # Ejecución real usando los mismos f_act_live
                for f in list(Path("COSECHA").glob(f"MASTER_{selected_asset_v54.upper().split('_')[0]}*.csv")):
                    if "_CLEAN" in f.name or "INYECTOR" in f.name: continue
                    df_exe = pd.read_csv(f)
                    # Re-capturar límites para el borrado
                    match_c = df_master_assets_v54[df_master_assets_v54['Symbol'].astype(str).str.contains(selected_asset_v54.upper().split('_')[0])]
                    r_v = match_c.iloc[0]
                    lt, lr, lp = int(r_v.get('Min_Trades', 300)), float(r_v.get('Min_R2', 0.75)), float(r_v.get('Min_PF', 1.15))
                    
                    if f_act_live["min_trades"]: df_exe = df_exe[df_exe['Trades'] >= lt]
                    if f_act_live["r2_stability"]: df_exe = df_exe[df_exe['R2'] >= lr]
                    if f_act_live["pf_net_is"]: df_exe = df_exe[df_exe['PF'] >= lp]
                    df_exe.to_csv(f, index=False)
                
                st.session_state.purge_ready = False
                st.success("LIMPIEZA FINALIZADA."); time.sleep(1.5); st.rerun()

    # --- PROTOCOLO DE EXTERMINIO ---
    st.markdown("---")
    st.error("💣 PROTOCOLO DE EXTERMINIO")
    if st.button("🗑️ PURGAR TODA LA CARPETA COSECHA", use_container_width=True):
        with st.spinner("Exterminando..."):
            for f_item in list(Path("COSECHA").glob("*.*")):
                try: os.remove(f_item)
                except: continue
            st.success("GRANJA RESETEADA."); time.sleep(1.5); st.rerun()

# --- SECCIÓN 3: MINING LAB v104 ---
elif navigation_active_hub == "⚒️ MINING LAB":
    st.subheader("📊 MINING TELEMETRY (FAIL AUTOPSY)")
    # ... (bloque de auditoría anterior) ...

    if not raw_pool_v54.empty:
        # --- v104.185 COLUMNS SAFETY CHECK (INYECCIÓN DE EXIT) ---
        # Añadimos 'Exit' a la lista de columnas mandatorias
        mandat_cols = ['X1_UID', 'Hyper_Score', 'Health', 'Side', 'Exit', 'Stag_Active', 'R2', 'OER', 'Trades', 'Family']
        
        for c_check in mandat_cols:
            if c_check not in raw_pool_v54.columns:
                # Si falta la columna Exit, la creamos como 'UNK' (Unknown)
                raw_pool_v54[c_check] = "UNK" if c_check == 'Exit' else 0.0
        
        # Tabla Maestra (Alineada con el FOR)
        grid_elite = st.dataframe(
            raw_pool_v54[mandat_cols].head(100), 
            use_container_width=True, 
            height=350, 
            selection_mode="single-row", 
            on_select="rerun", 
            key="table_v54_final"
        )
        
        if len(grid_elite.selection.rows) > 0:
            act_idx = grid_elite.selection.rows[0]
            # Usamos head(100) para asegurar que el índice coincida con lo que ve el usuario
            act_id = raw_pool_v54.head(100).iloc[act_idx].name
            act_alpha = raw_pool_v54.loc[act_id]
            
            st.markdown(f"#### 📈 DNA ALPHA: {act_id} <span class='health-pill'>Health: {act_alpha.get('Health', 0.0)}</span>", unsafe_allow_html=True)
            
            c1_b, c2_b = st.columns(2)
            if c1_b.button("➕ ADD TO BUCKET", type="primary"): 
                add_to_bucket_v54(act_id, act_alpha, curr_cd_v54)
            if c2_b.button("📦 EXPORT SQX CODE"): 
                st.code(translate_to_sqx(act_alpha['Entry']), language="markdown")
                
# --- v104.996 BRIDGE: REALITY CHECK (AUTO-DARWINEX) ---
            from modules.translator_mql5 import generate_full_mql5_code
            from modules.mt5_bridge import compile_and_run_mt5
            
            # Botón de validación institucional
            if st.button("⚖️ REALITY CHECK (AUTO-DARWINEX)", use_container_width=True):
                with st.status("🏗️ Iniciando Protocolo de Sincronía...", expanded=True) as status:
                    # 1. Generar Código Fuente
                    status.update(label="🧬 Generando código MQL5...")
                    ea_source = generate_full_mql5_code(act_id, act_alpha)
                    
                    # 2. Guardar en Carpeta de Darwinex
                    # Usamos la ruta absoluta que usted me proporcionó
                    mt5_experts_path = r"C:\Users\pc\AppData\Roaming\MetaQuotes\Terminal\6C3C6A11D1C3791DD4DBF45421BF8028\MQL5\Experts"
                    full_path = os.path.join(mt5_experts_path, f"X1_{act_id}.mq5")
                    
                    try:
                        with open(full_path, "w", encoding="utf-16") as f: # MQL5 prefiere UTF-16
                            f.write(ea_source)
                        
                        # 3. Compilar y Ejecutar Backtest
                        status.update(label="🔨 Compilando y ejecutando en MT5 (Darwinex)...")
                        # Esta función abre el terminal, corre el test y devuelve la ruta del CSV
                        csv_truth = compile_and_run_mt5(f"X1_{act_id}", selected_asset_v54, selected_tf_v54)
                        
                        # 4. Verificación de Resultados
                        status.update(label="📊 Analizando respuesta del Bróker...", state="complete")
                        if os.path.exists(csv_truth):
                            df_truth = pd.read_csv(csv_truth)
                            final_eq = df_truth['Equity'].iloc[-1]
                            st.success(f"✅ VALIDACIÓN EXITOSA: Equidad en Darwinex: {final_eq}")
                        else:
                            st.warning("⚠️ El backtest terminó pero no se detectó el archivo de exportación. Verifique si el EA compiló correctamente.")
                    except Exception as e_bridge:
                        st.error(f"❌ FALLO EN EL BRIDGE: {str(e_bridge)}")
# --- v104.960 BRIDGE: EXPORTACIÓN INDIVIDUAL MT5 ---
            from modules.translator_mql5 import translate_to_mql5, get_required_handles
            
            if st.button("🚀 GENERATE MT5 EXPERT (.MQ5)", type="primary"):
                mql5_logic = translate_to_mql5(act_alpha['Entry'])
                req_handles = get_required_handles(act_alpha['Entry'])
                
                # --- CONSTRUCCIÓN DEL SOURCE CODE ---
                ea_code = f"""//+------------------------------------------------------------------+
//|                                     X1-ARCHITECT: {act_id}
//|                                     Side: {act_alpha['Side']} | Exit: {act_alpha['Exit']}
//+------------------------------------------------------------------+
#property strict
#include <Trade\\Trade.mqh>

CTrade trade;
"""
                # Declaración de Handles
                for ind, per in req_handles:
                    ea_code += f"int h_{ind}_{per};\n"

                ea_code += f"""
int OnInit() {{
"""
                for ind, per in req_handles:
                    if ind == 'rsi': ea_code += f"   h_rsi_{per} = iRSI(_Symbol, _Period, {per}, PRICE_CLOSE);\n"
                    if ind == 'ema': ea_code += f"   h_ema_{per} = iMA(_Symbol, _Period, {per}, 0, MODE_EMA, PRICE_CLOSE);\n"
                
                ea_code += f"""   return(INIT_SUCCEEDED);
}}

void OnTick() {{
   if(PositionsTotal() > 0) {{
      // Lógica de Salida
"""
                if act_alpha['Exit'] == "SINTETICA_REVERSE":
                    ea_code += f"      if(!({mql5_logic})) trade.PositionClose(PositionGetTicket(0));\n"
                else:
                    bars = act_alpha['Exit'].replace('Ret_', '')
                    ea_code += f"      // Salida por tiempo ({bars} velas) gestionada por MT5\n"

                ea_code += f"""      return;
   }}

   // Lógica de Entrada
   if({mql5_logic}) {{
      double lot = 0.1;
      if("{act_alpha['Side']}" == "LONG") trade.Buy(lot);
      else trade.Sell(lot);
   }}
}}

double GetVal(int handle, int shift) {{ 
   double buf[]; 
   if(CopyBuffer(handle, 0, shift, 1, buf) > 0) return buf[0];
   return 0;
}}
"""
                st.code(ea_code, language="cpp")
                st.download_button(f"💾 Download {act_id}.mq5", ea_code, file_name=f"X1_{act_id}.mq5")               


# --- PEAJE SOBERANO v102.78 (PUNTOS PUROS) ---
            # Sumamos lo que hay en las cajas de texto sin escalas intermedias
            f_puntos_v102 = (st.session_state.hard_slip + 
                             st.session_state.hard_spread + 
                             st.session_state.hard_comm)
            
            # El motor (X1_Compute_Engine) hará la normalización dinámica interna
            df_bt_ind = X1_Compute_Engine(
                data_loader_pack_v54, 
                [{'id':act_id, 'Entry':act_alpha['Entry'], 'Exit':act_alpha['Exit'], 'Side':act_alpha['Side'], 'Cooldown':curr_cd_v54}],
                total_friction=f_puntos_v102
            )

# 3. RENDERIZADO DE MÉTRICAS VIVAS Y GRÁFICO v102.78
            if df_bt_ind is not None and not df_bt_ind.empty:
                # Análisis de la curva generada (ya normalizada 1/N por el motor)
                eq_viva = df_bt_ind['Portfolio'].values
                ret_vivos = np.diff(eq_viva, prepend=0)
                
                # Métrica de Bolsillo Real
                profit_real = round(eq_viva[-1] * 100, 2)
                win, loss = np.sum(ret_vivos[ret_vivos > 0]), abs(ret_vivos[ret_vivos < 0].sum()) + 1e-9
                pf_real = round(win / loss, 2)
                
                # Tarjetas de Sinceridad
                m1, m2 = st.columns(2)
                m1.metric("NET PROFIT (REAL)", f"{profit_real}%", 
                          delta=f"{round(profit_real - (act_alpha['PF']-1)*100, 2)}% vs CSV", delta_color="inverse")
                m2.metric("PROFIT FACTOR (LIVE)", f"{pf_real}x", 
                          delta=f"{round(pf_real - act_alpha['PF'], 2)} vs CSV", delta_color="inverse")

                # El Gráfico Realista
                st.plotly_chart(plot_equity_with_stag(df_bt_ind, title=f"Backtest Realista: {act_id}", side=act_alpha['Side'], zones=market_zones, timeframe=selected_tf_v54), use_container_width=True)    
    # Cierre de la validación del pool
    else: 
        st.warning("Sin Alphas validados en esta categoría.")


# --- SECCIÓN 4: COMPOSER v104.300 (MÁXIMA DIVERSIFICACIÓN & BULK EXPORT) ---
elif navigation_active_hub == "🎹 COMPOSER":
    st.markdown("<span class='master-title'>🎹 PORTFOLIO COMPOSER</span>", unsafe_allow_html=True)
    
    # 1. SINCRONIZACIÓN DE PORTAFOLIO MANUAL
    pool_ids_h_v54 = "-".join([str(s_m['id']) for s_m in st.session_state.manual_pool])
    if pool_ids_h_v54 != st.session_state.last_pool_hash and st.session_state.manual_pool:
        f_puntos_man = (st.session_state.hard_slip + st.session_state.hard_spread + st.session_state.hard_comm)
        st.session_state.portfolio_df = X1_Compute_Engine(data_loader_pack_v54, st.session_state.manual_pool, total_friction=f_puntos_man)
        st.session_state.last_pool_hash = pool_ids_h_v54
        st.session_state.active_portfolio = "MANUAL"
    
    col_ia_v54, col_res_v54 = st.columns([1, 2.5])
    
    with col_ia_v54:
        st.subheader("🧠 IA OPTIMIZER")
        t_qty_v54 = st.number_input("Target Alphas", 2, 20, 5, key="target_qty")
        m_pea_v54 = st.slider("Max Pearson (Riesgo)", 0.0, 1.0, 0.4, key="max_p")
        m_jac_v54 = st.slider("Max Jaccard (Exposición)", 0.0, 1.0, 0.45, key="max_j")
        m_mdd_v54 = st.slider("Max Portfolio DD (%)", 1.0, 30.0, 5.0, key="max_d") # Default institucional 5%
        
        if st.button("⚡ GENERATE IA PORTFOLIO", type="primary"):
            with st.status("🧠 IA Analizando Confluencia Estructural...", expanded=True) as status_ia:
                ia_team = run_greedy_selection(data_loader_pack_v54, raw_pool_v54, t_qty_v54, m_pea_v54, max_jac=m_jac_v54, max_mdd=m_mdd_v54)

                if ia_team:
                    for s_ia in ia_team: s_ia['Cooldown'] = curr_cd_v54
                    st.session_state.selected_strategies = ia_team
                    f_puntos_ia = (st.session_state.hard_slip + st.session_state.hard_spread + st.session_state.hard_comm)
                    st.session_state.portfolio_df = X1_Compute_Engine(data_loader_pack_v54, ia_team, total_friction=f_puntos_ia)
                    st.session_state.active_portfolio = "IA"
                    status_ia.update(label="✅ EQUIPO DE ÉLITE FORMADO", state="complete", expanded=False)
                else: 
                    status_ia.update(label="❌ FALLO: SIN COMBINACIÓN LEGAL", state="error", expanded=True)
                    st.error("Pruebe a relajar los Sliders de Pearson/Jaccard.")
        
        st.markdown("---")
        st.subheader("📂 MANUAL BUCKET")
        for s_buck in st.session_state.manual_pool:
            cm1, cm2 = st.columns([5, 1])
            cm1.write(f"**DNA {s_buck['id']}** | {s_buck['Side']} | {s_buck['Exit']}")
            if cm2.button("❌", key=f"del_{s_buck['id']}"): remove_from_bucket_v54(s_buck['id'])
    
    with col_res_v54:
        if st.session_state.portfolio_df is not None:
            v_eq = st.session_state.portfolio_df['Portfolio'].values
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Net Profit", f"{round(v_eq[-1]*100, 2)}%")
            m2.metric("Ulcer Index", calculate_ulcer_index(v_eq))
            _, _, dd_p = calculate_drawdown(v_eq, 1.0)
            m3.metric("Max DD", f"{dd_p:.2f}%", delta="TARGET < 3%" if abs(dd_p) < 3 else "HIGH RISK", delta_color="normal" if abs(dd_p) < 3 else "inverse")
            m4.metric("Recovery Factor", round(abs(v_eq[-1]*100)/(abs(dd_p)+1e-9), 2))
            
            st.plotly_chart(plot_equity_with_stag(st.session_state.portfolio_df, title=f"PORTFOLIO: {st.session_state.active_portfolio} SELECTION", zones=market_zones, timeframe=selected_tf_v54), use_container_width=True)
            
            # Radar de Descorrelación Estructural
            st.markdown("---")
            st.subheader("📡 RADAR DE DIVERSIFICACIÓN (Drawdown Correlation)")
            df_corr = get_correlation_matrix(st.session_state.portfolio_df)
            if not df_corr.empty:
                st.plotly_chart(plot_correlation_heatmap(df_corr), use_container_width=True)

            # --- v104.300 BLOQUE DE EXPORTACIÓN MASIVA (BULK EXPORT) ---
            st.markdown("---")
            st.subheader("📦 ALGO WIZARD / SQX BULK EXPORT")
            
            active_team = st.session_state.selected_strategies if st.session_state.active_portfolio == "IA" else st.session_state.manual_pool
            
            if active_team:
                col_exp1, col_exp2 = st.columns([2, 1])
                with col_exp1:
                    st.info(f"Preparado para exportar {len(active_team)} Alphas del equipo {st.session_state.active_portfolio}")
                
                if st.button("🧬 GENERATE BULK SOURCE CODE", type="primary"):
                    bulk_text = "##########################################################################\n"
                    bulk_text += f"# X1-ARCHITECT v104 BULK EXPORT | ASSET: {selected_asset_v54} | TF: {selected_tf_v54}\n"
                    bulk_text += "##########################################################################\n\n"
                    
                    for m in active_team:
                        bulk_text += f"// >>> ID: {m['id']} | SIDE: {m['Side']} | PF: {m.get('PF', 'N/A')} | R2: {m.get('R2', 'N/A')}\n"
                        bulk_text += f"// EXIT RULE: {m['Exit']}\n"
                        
                        # Traducción de lógica de entrada
                        sqx_rule = translate_to_sqx(m['Entry'])
                        bulk_text += f"IF ({sqx_rule})\n"
                        bulk_text += f"   ORDER: {m['Side']} AT MARKET\n"
                        
                        # Traducción de lógica de salida
                        if m['Exit'] == "SINTETICA_REVERSE":
                            bulk_text += f"   EXIT: WHEN NOT ({sqx_rule}) // LOGIC REVERSAL\n"
                        else:
                            bulk_text += f"   EXIT: AFTER {m['Exit'].replace('Ret_', '')} BARS\n"
                        
                        bulk_text += "// " + ("-" * 60) + "\n\n"
                    
                    st.code(bulk_text, language="javascript")
                    st.download_button(
                        label="💾 DOWNLOAD .TXT FOR ALGOWIZARD",
                        data=bulk_text,
                        file_name=f"X1_PORTFOLIO_{selected_asset_v54}_{st.session_state.active_portfolio}.txt",
                        mime="text/plain"
                    )
            else:
                st.warning("Forme un equipo primero para habilitar la exportación.")