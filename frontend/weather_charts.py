"""
weather_charts.py
Plotly-based trend visualization for weather timelines.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
from typing import Optional

CHART_THEME = {
    "bg":     "#0a1628",
    "paper":  "#0d2040",
    "grid":   "rgba(0,212,255,0.08)",
    "text":   "#8ab4d4",
    "accent": "#00D4FF",
    "warm":   "#FF6B35",
    "cool":   "#4ECDC4",
    "danger": "#FF2D2D",
    "warn":   "#FFD700",
    "ok":     "#00C851",
}


def _base_layout(title: str, height: int = 280) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=CHART_THEME["text"], size=13),
                   x=0.01, y=0.97),
        height=height,
        margin=dict(l=40, r=20, t=36, b=40),
        paper_bgcolor=CHART_THEME["paper"],
        plot_bgcolor=CHART_THEME["bg"],
        font=dict(color=CHART_THEME["text"], size=11),
        xaxis=dict(gridcolor=CHART_THEME["grid"], tickfont=dict(size=10)),
        yaxis=dict(gridcolor=CHART_THEME["grid"], tickfont=dict(size=10)),
    )


def render_temperature_chart(df_hourly: pd.DataFrame) -> None:
    """24h temperature + feels-like trend."""
    if df_hourly is None or "time" not in df_hourly.columns:
        st.info("No hourly data available.")
        return

    fig = go.Figure()

    if "temperature_2m" in df_hourly.columns:
        fig.add_trace(go.Scatter(
            x=df_hourly["time"], y=df_hourly["temperature_2m"],
            name="Temperature", line=dict(color=CHART_THEME["warm"], width=2.5),
            fill="tozeroy", fillcolor="rgba(255,107,53,0.08)",
        ))

    layout = _base_layout("🌡️ 24-Hour Temperature Trend (°C)")
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_wind_chart(df_hourly: pd.DataFrame) -> None:
    """24h wind speed chart."""
    if df_hourly is None or "wind_speed_10m" not in df_hourly.columns:
        st.info("No wind data available.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_hourly["time"], y=df_hourly["wind_speed_10m"],
        name="Wind Speed", line=dict(color=CHART_THEME["accent"], width=2),
        fill="tozeroy", fillcolor="rgba(0,212,255,0.08)",
    ))

    # Beaufort reference lines
    for level, label, color in [
        (30, "Bft 6", "#FFD700"),
        (50, "Bft 8 Gale", "#FF8C00"),
        (75, "Bft 10 Storm", "#FF2D2D"),
    ]:
        fig.add_hline(
            y=level, line_dash="dash", line_color=color,
            annotation_text=label,
            annotation_font_color=color,
            annotation_font_size=9,
        )

    layout = _base_layout("💨 24-Hour Wind Speed (km/h)")
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_precipitation_chart(df_hourly: pd.DataFrame) -> None:
    """24h precipitation bar chart."""
    if df_hourly is None or "precipitation" not in df_hourly.columns:
        st.info("No precipitation data available.")
        return

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_hourly["time"],
        y=df_hourly["precipitation"],
        name="Rainfall",
        marker_color=CHART_THEME["cool"],
        marker_line_width=0,
        opacity=0.85,
    ))

    layout = _base_layout("🌧️ 24-Hour Precipitation (mm)")
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_7day_forecast(df_daily: pd.DataFrame) -> None:
    """7-day temperature range + precipitation bar."""
    if df_daily is None or "time" not in df_daily.columns:
        st.info("No 7-day forecast available.")
        return

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        shared_xaxes=True,
        vertical_spacing=0.06,
    )

    # Temperature min/max band
    if "temperature_2m_max" in df_daily.columns and "temperature_2m_min" in df_daily.columns:
        fig.add_trace(go.Scatter(
            x=df_daily["time"], y=df_daily["temperature_2m_max"],
            name="Max Temp", line=dict(color=CHART_THEME["warm"], width=2),
            fill=None,
        ), row=1, col=1)
        fig.add_trace(go.Scatter(
            x=df_daily["time"], y=df_daily["temperature_2m_min"],
            name="Min Temp", line=dict(color=CHART_THEME["cool"], width=2),
            fill="tonexty", fillcolor="rgba(255,107,53,0.12)",
        ), row=1, col=1)

    # Daily precipitation
    if "precipitation_sum" in df_daily.columns:
        fig.add_trace(go.Bar(
            x=df_daily["time"], y=df_daily["precipitation_sum"],
            name="Rain Sum", marker_color=CHART_THEME["cool"], opacity=0.8,
        ), row=2, col=1)

    fig.update_layout(
        height=340,
        margin=dict(l=40, r=20, t=36, b=40),
        paper_bgcolor=CHART_THEME["paper"],
        plot_bgcolor=CHART_THEME["bg"],
        font=dict(color=CHART_THEME["text"], size=11),
        title=dict(text="📅 7-Day Forecast", font=dict(color=CHART_THEME["text"], size=13), x=0.01),
        xaxis2=dict(gridcolor=CHART_THEME["grid"]),
        yaxis=dict(gridcolor=CHART_THEME["grid"]),
        yaxis2=dict(gridcolor=CHART_THEME["grid"]),
        showlegend=True,
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10)),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_cloud_humidity_chart(df_hourly: pd.DataFrame) -> None:
    """Cloud cover and humidity dual-line chart."""
    if df_hourly is None:
        return

    fig = go.Figure()
    if "cloud_cover" in df_hourly.columns:
        fig.add_trace(go.Scatter(
            x=df_hourly["time"], y=df_hourly["cloud_cover"],
            name="Cloud Cover %", line=dict(color="#B0C4DE", width=2),
            fill="tozeroy", fillcolor="rgba(176,196,222,0.07)",
        ))
    if "relative_humidity_2m" in df_hourly.columns:
        fig.add_trace(go.Scatter(
            x=df_hourly["time"], y=df_hourly["relative_humidity_2m"],
            name="Humidity %", line=dict(color=CHART_THEME["cool"], width=2, dash="dot"),
        ))

    layout = _base_layout("☁️ Cloud Cover & Humidity (%)")
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
