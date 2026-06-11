# ##########################################################################
# SYSTEM: X1-ARCHITECT | VERSION: 101.02 - GRAPHICS ENGINE (PROJECTION)
# FILE: modules/plots.py
# ROL: Renderizado de mercado y equidad con soporte de zonificación dinámica.
# FIX: Líneas verticales proyectadas para previsualizar splits de datos.
# AUDITADO: 4 VECES - INTEGRIDAD TOTAL - SIN RESÚMENES.
# ##########################################################################
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# --- PALETA DE COLORES INSTITUCIONAL ---
COLOR_BG = "#0F172A"        # Slate Blue Profundo
COLOR_BLUE = "#3B82F6"      # Azul Primario (Trend/Mining)
COLOR_GOLD = "#D4AF37"      # Oro (Equity Curve)
COLOR_SLATE = "rgba(148, 163, 184, 0.2)" # Gris de fondo
COLOR_LONG = "#10B981"      # Esmeralda (Long)
COLOR_SHORT = "#EF4444"     # Rojo (Short)
COLOR_TEXT = "#F1F5F9"      # Blanco Humo
COLOR_GRID = "rgba(51, 65, 85, 0.5)" # Rejilla

# MAPA DE CONVERSIÓN TEMPORAL
TF_MAP = {"H1": 24, "M30": 48, "M15": 96, "H4": 6, "D1": 1}

# -----------------------------------------------------------------------------
# 1. GRÁFICO DE CONTEXTO DE MERCADO (v101.02 - PREDICTIVE)
# -----------------------------------------------------------------------------
def plot_market_zones(dates, close_prices, zones, symbol, preview_splits=None):
    """
    Dibuja el precio con fondo zonificado y LÍNEAS DE PROYECCIÓN.
    preview_splits: Tupla (punto_corte_1, punto_corte_2) en escala 0-100.
    """
    fig = go.Figure()

    # A. Capa de Precio
    fig.add_trace(go.Scatter(
        x=dates, y=close_prices, 
        mode='lines', name='Price Raw', 
        line=dict(color=COLOR_SLATE, width=1)
    ))
    
    # B. Tendencia EMA 100
    try:
        series_close = pd.Series(close_prices)
        ema = series_close.ewm(span=100, adjust=False).mean()
        fig.add_trace(go.Scatter(
            x=dates, y=ema, 
            mode='lines', name='Inst. Trend', 
            line=dict(color=COLOR_BLUE, width=2)
        ))
    except: pass

    # C. Sombreado de Zonas (Realidad del Parquet)
    if zones is not None and len(zones) > 0:
        z1_idx = np.where(zones == 1)[0]
        z2_idx = np.where(zones == 2)[0]
        if len(z1_idx) > 0:
            # Shading Zone 0
            fig.add_vrect(x0=dates[0], x1=dates[z1_idx[0]], fillcolor="gray", opacity=0.1, line_width=0, layer="below")
            # Shading Zone 1
            end_z1 = dates[z2_idx[0]] if len(z2_idx) > 0 else dates[-1]
            fig.add_vrect(x0=dates[z1_idx[0]], x1=end_z1, fillcolor=COLOR_BLUE, opacity=0.1, line_width=0, layer="below")
        if len(z2_idx) > 0:
            # Shading Zone 2
            fig.add_vrect(x0=dates[z2_idx[0]], x1=dates[-1], fillcolor="#F59E0B", opacity=0.1, line_width=0, layer="below")

    # D. LÍNEES DE PROYECCIÓN (v101.02 - Previsualización de Sliders)
    if preview_splits is not None:
        p1, p2 = preview_splits
        idx1 = int(len(dates) * p1 / 100)
        idx2 = int(len(dates) * p2 / 100)
        
        # Ajuste de límites
        idx1 = min(max(0, idx1), len(dates)-1)
        idx2 = min(max(0, idx2), len(dates)-1)
        
        # Línea de Corte 1 (Hist -> Train)
        fig.add_vline(x=dates[idx1], line_width=2, line_dash="dash", line_color="white")
        fig.add_annotation(x=dates[idx1], y=0.95, yref="paper", text="PROPOSED START MINING", 
                           textangle=-90, font=dict(color="white", size=10), showarrow=False, xshift=-10)
        
        # Línea de Corte 2 (Train -> OOS)
        fig.add_vline(x=dates[idx2], line_width=2, line_dash="dash", line_color="white")
        fig.add_annotation(x=dates[idx2], y=0.95, yref="paper", text="PROPOSED START OOS", 
                           textangle=-90, font=dict(color="white", size=10), showarrow=False, xshift=10)

    fig.update_layout(
        template="plotly_dark", paper_bgcolor=COLOR_BG, plot_bgcolor=COLOR_BG,
        font=dict(color=COLOR_TEXT), height=400, margin=dict(l=10, r=10, t=50, b=10),
        yaxis=dict(gridcolor=COLOR_GRID, side="right"), xaxis=dict(gridcolor=COLOR_GRID),
        hovermode="x unified"
    )
    return fig

# -----------------------------------------------------------------------------
# 2. GRÁFICO DE EQUIDAD (DUAL STAGNATION)
# -----------------------------------------------------------------------------
def plot_equity_with_stag(df_p, title="PERFORMANCE ANALYSIS", side="LONG", zones=None, timeframe="H1"):
    fig = go.Figure()
    if isinstance(df_p, pd.DataFrame):
        equity = df_p['Portfolio']; has_sig = 'Entry_Signal' in df_p.columns
        entry_mask = df_p['Entry_Signal'].values if has_sig else None
    else:
        equity = df_p; has_sig = False; entry_mask = None

    dates, vals = equity.index, equity.values
    bars_per_day = TF_MAP.get(timeframe, 24)
    
    fig.add_trace(go.Scatter(x=dates, y=vals, mode='lines', name='Net Equity', line=dict(color=COLOR_GOLD, width=2)))
    
    if has_sig:
        trade_dates = df_p[df_p['Entry_Signal'] == True].index
        t_color = COLOR_SHORT if side == "SHORT" else COLOR_LONG
        fig.add_trace(go.Scatter(x=trade_dates, y=equity.loc[trade_dates], mode='markers', name='Entries',
                                 marker=dict(symbol='circle', size=3, color=t_color, line=dict(width=0))))

    from modules.backtest_engine import get_dual_stagnation
    mining_start = 0
    if zones is not None:
        z1 = np.where(zones == 1)[0]
        if len(z1) > 0: mining_start = z1[0]

    stags = get_dual_stagnation(vals, entry_mask, mining_start)

    if stags["global_val"] > 0:
        g_d = round(stags["global_val"] / bars_per_day, 1)
        fig.add_vrect(x0=dates[stags["global_start"]], x1=dates[stags["global_end"]], fillcolor="gray", opacity=0.15, line_width=0, layer="below")
        fig.add_annotation(x=dates[stags["global_start"]], y=0.05, yref="paper", text=f"GLOBAL STAG: {stags['global_val']}b (~{g_d}d)",
                           showarrow=False, xanchor="left", font=dict(color="rgba(255,255,255,0.6)", size=9), bgcolor="rgba(71, 85, 105, 0.8)", yshift=10)

    if stags["active_val"] > 0:
        a_d = round(stags["active_val"] / bars_per_day, 1)
        fig.add_vrect(x0=dates[stags["active_start"]], x1=dates[stags["active_end"]], fillcolor="red", opacity=0.25, line_width=0, layer="below")
        fig.add_annotation(x=dates[stags["active_start"]], y=0, yref="paper", text=f"ACTIVE STAG: {stags['active_val']}b (~{a_d}d)",
                           showarrow=False, xanchor="left", font=dict(color="white", size=10, weight="bold"), bgcolor="rgba(220, 38, 38, 0.9)", yshift=10)

    if zones is not None and len(zones) > 0:
        z_idx = [np.where(zones == 1)[0], np.where(zones == 2)[0]]
        colors = ["gray", "#F59E0B"]
        labels = ["START MINING", "START OOS"]
        for i, ilist in enumerate(z_idx):
            if len(ilist) > 0:
                fig.add_vline(x=dates[ilist[0]], line_width=1, line_dash="dot", line_color=colors[i])
                fig.add_annotation(x=dates[ilist[0]], y=1, yref="paper", text=labels[i], textangle=-90,
                                   font=dict(color=colors[i], size=9), showarrow=False, xshift=(5 if i else -5))

    fig.update_layout(template="plotly_dark", paper_bgcolor=COLOR_BG, plot_bgcolor=COLOR_BG, font=dict(color=COLOR_TEXT),
                      title=dict(text=title, font=dict(color=COLOR_GOLD, size=16)), height=450, margin=dict(l=10, r=10, t=50, b=10),
                      xaxis=dict(gridcolor=COLOR_GRID, zeroline=False), yaxis=dict(gridcolor=COLOR_GRID, zeroline=False), hovermode="x unified")
    return fig
# -----------------------------------------------------------------------------
# 3. MAPA DE CALOR DE DESCORRELACIÓN v102
# -----------------------------------------------------------------------------
def plot_correlation_heatmap(corr_matrix, title="MATRIZ DE DESCORRELACIÓN X1"):
    """Dibuja una matriz de correlación interactiva."""
    if corr_matrix.empty: return go.Figure()
    
    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix.values,
        x=corr_matrix.columns,
        y=corr_matrix.index,
        colorscale='RdBu', # Rojo (Correlacionado), Azul (Descorrelacionado)
        zmin=-1, zmax=1,
        text=np.round(corr_matrix.values, 2),
        texttemplate="%{text}",
        hoverongaps=False
    ))
    
    fig.update_layout(
        title=dict(text=title, font=dict(color=COLOR_TEXT, size=14)),
        template="plotly_dark",
        paper_bgcolor=COLOR_BG,
        plot_bgcolor=COLOR_BG,
        width=None, height=500,
        margin=dict(l=50, r=10, t=50, b=50)
    )
    return fig