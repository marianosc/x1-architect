# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 104.115 - FARM PULSE (SYNC EDITION)
# FILE: pulse.py
# ROL: Visor de Telemetría en Tiempo Real y Auditoría de Productividad.
# UPD: Sincronización de etiquetas 'qualified'/'harvested' v104.
# ##########################################################################
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import json
import os
import time
from pathlib import Path
from datetime import datetime

# --- IMPORTACIÓN DE CEREBRO DE DATOS ---
from modules.data_loader import get_farm_analytics

# 1. CONFIGURACIÓN DE PANTALLA (GRADO MILITAR)
st.set_page_config(
    page_title="X1-PULSE | Mission Telemetry", 
    page_icon="🛰️", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS: Hardening de Interfaz (Cyber-Ops Style)
st.markdown("""
<style>
    .stApp { background-color: #020617 !important; }
    .status-card { 
        background-color: #0F172A; border: 1px solid #1E293B; padding: 20px; 
        border-radius: 10px; border-left: 5px solid #3B82F6; margin-bottom: 20px;
    }
    .metric-label { color: #94A3B8; font-size: 0.8rem; font-weight: bold; text-transform: uppercase; }
    .metric-value { color: #F1F5F9; font-size: 1.8rem; font-weight: 800; font-family: 'Courier New', monospace; }
    .live-badge { 
        background-color: #064E3B; color: #34D399; padding: 4px 12px; 
        border-radius: 20px; font-size: 0.7rem; font-weight: bold; border: 1px solid #059669;
    }
</style>
""", unsafe_allow_html=True)

def get_farm_heartbeat():
    """v104.175: Captura de latido con Blindaje contra archivos vacíos (Race Condition)."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    h_path = os.path.join(base_dir, "data", "farm_heartbeat.json")
    
    if not os.path.exists(h_path) or os.path.getsize(h_path) == 0:
        return None

    # Protocolo de reintento para evitar colisión de escritura
    for _ in range(5):
        try:
            with open(h_path, 'r') as f:
                data = json.load(f)
                diff = time.time() - data.get('timestamp', 0)
                data['is_alive'] = diff < 60
                return data
        except (json.JSONDecodeError, OSError):
            # Si el archivo está siendo escrito, esperamos 100ms y reintentamos
            time.sleep(0.1)
            continue
    return None

# -----------------------------------------------------------------------------
# 3. INTERFAZ DE USUARIO (OPERATIONS CENTER)
# -----------------------------------------------------------------------------
st.markdown("### 🛰️ X1-ARCHITECT | **FARM PULSE** <span class='live-badge'>V104.115 ACTIVE</span>", unsafe_allow_html=True)

# A. LIVE STATUS BAR
heartbeat = get_farm_heartbeat()
if heartbeat:
    st.markdown(f"""
    <div class="status-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div class="metric-label">CICLO ACTUAL</div>
                <div class="metric-value">#{heartbeat['cycle']}</div>
            </div>
            <div>
                <div class="metric-label">ACTIVO MAESTRO</div>
                <div class="metric-value">{heartbeat['symbol']} ({heartbeat['tf']})</div>
            </div>
            <div>
                <div class="metric-label">SILO EN PROCESO</div>
                <div class="metric-value" style="color:#3B82F6">{heartbeat['side']}-{heartbeat['family']}</div>
            </div>
            <div>
                <div class="metric-label">ESTADO RYZEN 9</div>
                <div class="metric-value" style="color:{'#10B981' if heartbeat['is_alive'] else '#EF4444'}">
                    {'ONLINE' if heartbeat['is_alive'] else 'LATENCY ALERT'}
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
else:
    st.error("❌ SISTEMA OFFLINE: El Commander no ha emitido señales en 'data/farm_heartbeat.json'")

# B. ANALÍTICA DE PRODUCCIÓN v104.115 (FULL SYNC)
df_raw = get_farm_analytics()

if not df_raw.empty:
    # 1. NORMALIZACIÓN DE COLUMNAS (Nuevas vs Viejas)
    if 'details' in df_raw.columns:
        df_details = pd.json_normalize(df_raw['details'])
        df_raw = pd.concat([df_raw.drop(columns=['details']), df_details], axis=1).fillna(0)
    
    # Determinamos qué columna usar para el éxito (v104 usa 'qualified')
    col_exito = 'qualified' if 'qualified' in df_raw.columns else 'passed'
    
    # 2. MÉTRICAS DE ALTO NIVEL
    total_candidatos = df_raw['total'].sum() if 'total' in df_raw.columns else 0
    total_diamantes = df_raw[col_exito].sum() if col_exito in df_raw.columns else 0
    yield_global = (total_diamantes / total_candidatos * 100) if total_candidatos > 0 else 0
    
    m1, m2, m3 = st.columns(3)
    m1.metric("CANDIDATOS EVALUADOS", f"{total_candidatos:,}")
    m2.metric("DIAMANTES TOTALES", f"{total_diamantes:,}", delta=f"{yield_global:.3f}% Yield", delta_color="normal")
    m3.metric("SILOS COMPLETADOS", len(df_raw))

    st.markdown("---")
    
    # 3. VISUALIZACIÓN BIFOCAL
    col_a, col_b = st.columns([2, 1])
    
    with col_a:
        st.markdown("#### 💀 THE REAPER'S REPORT (Mortalidad)")
        fail_cols = [c for c in df_raw.columns if c.startswith("FAIL_")]
        if fail_cols:
            df_melted = df_raw.melt(id_vars=['family', 'side'], value_vars=fail_cols, var_name='Causa', value_name='Muertes')
            fig_reaper = px.bar(df_melted, x='family', y='Muertes', color='Causa', facet_col='side',
                                template="plotly_dark", barmode='stack', color_discrete_sequence=px.colors.qualitative.Pastel)
            fig_reaper.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400)
            fig_reaper.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
            st.plotly_chart(fig_reaper, use_container_width=True)

    with col_b:
        st.markdown("#### 💎 YIELD POR FAMILIA (%)")
        df_yield = df_raw.groupby('family')[col_exito].sum() / df_raw.groupby('family')['total'].sum() * 100
        df_yield = df_yield.reset_index().rename(columns={0: 'Yield %'})
        
        fig_yield = px.bar(df_yield, x='family', y='Yield %', color='family', 
                           template="plotly_dark", color_discrete_sequence=px.colors.sequential.Greens_r)
        fig_yield.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=400, showlegend=False)
        st.plotly_chart(fig_yield, use_container_width=True)

    # 4. MATRIZ DE EFICIENCIA OPERATIVA (Heatmap)
    st.markdown("#### 🌡️ RADAR DE EFECTIVIDAD (Diamantes por Silo)")
    df_pivot = df_raw.pivot_table(index='side', columns='family', values=col_exito, aggfunc='sum').fillna(0)
    
    fig_heat = px.imshow(df_pivot, text_auto=True, color_continuous_scale='Viridis', aspect="auto",
                         labels=dict(x="Familia", y="Dirección", color="Diamantes"))
    fig_heat.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', height=300)
    st.plotly_chart(fig_heat, use_container_width=True)

else:
    st.info("⌛ Esperando datos de la Cosecha... (Ejecute el Commander)")

# 4. BOTONES Y MARCAPASOS
st.sidebar.markdown("### ⚙️ PULSE CONTROL")
if st.sidebar.button("♻️ FORCE REFRESH"):
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.write(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

# --- EL MARCAPASOS (Auto-Refresh) ---
st.sidebar.markdown("### ⏲️ MONITOR HEARTBEAT")
auto_refresh = st.sidebar.toggle("🔄 AUTO-REFRESH (10s)", value=True)

if auto_refresh:
    time.sleep(10)
    st.rerun()