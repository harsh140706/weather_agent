"""
weather_panel.py
Composable weather intelligence panel.

Changes vs original:
  • 7 Days view now calls render_7day_intelligence_panel() from
    weather_forecast_panel.py instead of the plain render_7day_forecast().
  • Accepts optional WeatherIntelligence object alongside the flat weather dict.
  • All other views/paths unchanged.
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from weather_cards   import render_weather_cards, render_risk_banner
from weather_charts  import (
    render_temperature_chart,
    render_wind_chart,
    render_precipitation_chart,
    render_cloud_humidity_chart,
)
from weather_forecast_panel import render_7day_intelligence_panel
from weather_timeline import WeatherTimeline

try:
    from forecasting.schemas import WeatherIntelligence
    _INTEL_AVAILABLE = True
except ImportError:
    _INTEL_AVAILABLE = False
    WeatherIntelligence = None


def render_weather_panel(
    weather: dict,
    timeline_view: str = "Current",
    intelligence=None,          # WeatherIntelligence | None
) -> None:
    """
    Render the full weather intelligence panel.

    Args:
        weather:       Flat processed dict from WeatherProcessor
        timeline_view: "Current" | "24 Hours" | "7 Days"
        intelligence:  WeatherIntelligence from ForecastEngine (optional)
    """
    if not weather:
        st.warning("⚠️ No weather data available for this vessel.")
        return

    render_risk_banner(weather)

    vessel         = weather.get("vessel_name", "Unknown Vessel")
    condition_icon = weather.get("condition_icon", "🌊")
    condition      = weather.get("condition", "")
    tz             = weather.get("timezone", "UTC")
    ts             = weather.get("current_time", "")

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:12px;margin:8px 0 12px;">
        <span style="font-size:32px;">{condition_icon}</span>
        <div>
            <div style="font-size:18px;font-weight:700;color:#e8f4ff;">{vessel}</div>
            <div style="font-size:12px;color:#6a8aaa;">{condition} &nbsp;·&nbsp; {ts} ({tz})</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    render_weather_cards(weather)
    timeline = WeatherTimeline(weather)

    if timeline_view == "Current":
        st.markdown("---")
        _render_current_detail(weather)

    elif timeline_view == "24 Hours":
        df_hourly = timeline.get_hourly_dataframe()
        if df_hourly is not None:
            col1, col2 = st.columns(2)
            with col1:
                render_temperature_chart(df_hourly)
                render_precipitation_chart(df_hourly)
            with col2:
                render_wind_chart(df_hourly)
                render_cloud_humidity_chart(df_hourly)
        else:
            st.info("Hourly forecast data not available.")

    elif timeline_view == "7 Days":
        # ── Enhanced predictive forecast panel ───────────────────────────────
        render_7day_intelligence_panel(intelligence)

        # Fallback: also show hourly wind/precip from existing charts
        df_hourly = timeline.get_hourly_dataframe()
        if df_hourly is not None:
            st.markdown("---")
            st.markdown("**📊 48-Hour Detail**")
            col1, col2 = st.columns(2)
            with col1:
                render_wind_chart(df_hourly)
            with col2:
                render_precipitation_chart(df_hourly)


def _render_current_detail(weather: dict) -> None:
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**🌊 Maritime Conditions**")
        st.markdown(f"""
        <div style="background:#0d2040;border-radius:8px;padding:12px;font-size:13px;">
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Sea State:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('sea_state','N/A')}</span></div>
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Beaufort Scale:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">Bft {weather.get('beaufort_num','--')} – {weather.get('beaufort_desc','')}</span></div>
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Wind Gusts:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('wind_gusts','--')} km/h</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("**🌡️ Atmospheric**")
        st.markdown(f"""
        <div style="background:#0d2040;border-radius:8px;padding:12px;font-size:13px;">
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Temperature:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('temperature','--')}°C</span></div>
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Feels Like:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('feels_like','--')}°C</span></div>
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Pressure:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('pressure','--')} hPa</span></div>
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Humidity:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('humidity','--')}%</span></div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown("**👁️ Visibility & Cloud**")
        from weather_cards import _fmt_visibility
        vis_str = _fmt_visibility(weather.get("visibility"))
        st.markdown(f"""
        <div style="background:#0d2040;border-radius:8px;padding:12px;font-size:13px;">
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Visibility:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{vis_str}</span></div>
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Cloud Cover:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('cloud_cover','--')}%</span></div>
            <div style="margin:4px 0;"><span style="color:#6a8aaa;">Rainfall:</span>
                <span style="color:#e8f4ff;float:right;font-weight:600;">{weather.get('precipitation','--')} mm</span></div>
        </div>
        """, unsafe_allow_html=True)
