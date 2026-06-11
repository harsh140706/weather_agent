"""
weather_cards.py
Streamlit weather metric cards display component.
"""

import streamlit as st
import streamlit.components.v1 as components
from typing import Optional


CARD_CSS = """
<style>
.weather-card-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 10px;
    margin: 8px 0;
}
.weather-card {
    background: linear-gradient(135deg, #0a1628 0%, #0d2040 100%);
    border: 1px solid rgba(0, 212, 255, 0.2);
    border-radius: 12px;
    padding: 14px 16px;
    text-align: center;
    position: relative;
    overflow: hidden;
    transition: transform 0.2s ease, border-color 0.2s ease;
}
.weather-card:hover {
    transform: translateY(-2px);
    border-color: rgba(0, 212, 255, 0.5);
}
.weather-card::before {
    content: '';
    position: absolute;
    top: -30px; right: -30px;
    width: 80px; height: 80px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(0,212,255,0.08) 0%, transparent 70%);
}
.card-icon   { font-size: 22px; margin-bottom: 4px; }
.card-label  { font-size: 10px; color: #6a8aaa; text-transform: uppercase;
               letter-spacing: 0.8px; font-weight: 600; margin-bottom: 2px; }
.card-value  { font-size: 20px; font-weight: 700; color: #e8f4ff;
               font-family: 'Courier New', monospace; }
.card-sub    { font-size: 10px; color: #4a8aaa; margin-top: 2px; }
.risk-badge  { display: inline-block; padding: 3px 10px; border-radius: 20px;
               font-size: 11px; font-weight: 700; letter-spacing: 1px; }
@media (max-width: 768px) {
    .weather-card-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
"""


def render_weather_cards(weather: dict) -> None:
    """Render a grid of weather metric cards using HTML."""

    risk_color = weather.get("marine_risk_color", "#888")
    risk = weather.get("marine_risk", "N/A")

    cards = [
        {
            "icon": weather.get("condition_icon", "🌊"),
            "label": "Condition",
            "value": weather.get("condition", "N/A"),
            "sub": f"WMO Code",
        },
        {
            "icon": "🌡️",
            "label": "Temperature",
            "value": f"{weather.get('temperature', '--')}°C",
            "sub": f"Feels like {weather.get('feels_like', '--')}°C",
        },
        {
            "icon": "💧",
            "label": "Humidity",
            "value": f"{weather.get('humidity', '--')}%",
            "sub": "Relative humidity",
        },
        {
            "icon": "💨",
            "label": "Wind Speed",
            "value": f"{weather.get('wind_speed', '--')} km/h",
            "sub": f"{weather.get('wind_cardinal', '')} | Gusts {weather.get('wind_gusts', '--')} km/h",
        },
        {
            "icon": "🧭",
            "label": "Wind Direction",
            "value": f"{weather.get('wind_cardinal', 'N/A')}",
            "sub": f"{weather.get('wind_direction', '--')}°",
        },
        {
            "icon": "🔵",
            "label": "Pressure",
            "value": f"{weather.get('pressure', '--')} hPa",
            "sub": "Surface pressure",
        },
        {
            "icon": "🌧️",
            "label": "Rainfall",
            "value": f"{weather.get('precipitation', '--')} mm",
            "sub": "Current precipitation",
        },
        {
            "icon": "☁️",
            "label": "Cloud Cover",
            "value": f"{weather.get('cloud_cover', '--')}%",
            "sub": "Sky coverage",
        },
        {
            "icon": "👁️",
            "label": "Visibility",
            "value": _fmt_visibility(weather.get("visibility")),
            "sub": "Horizontal visibility",
        },
        {
            "icon": "⚓",
            "label": "Beaufort",
            "value": f"Bft {weather.get('beaufort_num', '--')}",
            "sub": weather.get("beaufort_desc", ""),
        },
        {
            "icon": "🌊",
            "label": "Sea State",
            "value": weather.get("sea_state", "N/A"),
            "sub": "Douglas scale estimate",
        },
        {
            "icon": "⚠️",
            "label": "Marine Risk",
            "value": f'<span class="risk-badge" style="background:{risk_color}22;color:{risk_color};border:1px solid {risk_color}55;">{risk}</span>',
            "sub": "Operational risk level",
            "raw_value": True,
        },
    ]

    # Build grid HTML
    html = CARD_CSS + '<div class="weather-card-grid">'
    for card in cards:
        if not card.get("raw_value"):
            val_html = f'<div class="card-value">{card["value"]}</div>'
        else:
            val_html = f'<div class="card-value" style="font-size:14px;padding-top:4px;">{card["value"]}</div>'

        html += f"""
        <div class="weather-card">
            <div class="card-icon">{card["icon"]}</div>
            <div class="card-label">{card["label"]}</div>
            {val_html}
            <div class="card-sub">{card["sub"]}</div>
        </div>
        """
    html += "</div>"
    components.html(html, height=430, scrolling=False)


def render_risk_banner(weather: dict) -> None:
    """Render a prominent risk status banner."""
    risk = weather.get("marine_risk", "N/A")
    color = weather.get("marine_risk_color", "#888")
    vessel = weather.get("vessel_name", "")
    sea = weather.get("sea_state", "")
    bft = weather.get("beaufort_desc", "")

    st.markdown(f"""
    <div style="
        background: linear-gradient(90deg, {color}22 0%, transparent 100%);
        border-left: 4px solid {color};
        border-radius: 8px;
        padding: 12px 20px;
        margin: 8px 0;
        display: flex;
        justify-content: space-between;
        align-items: center;
    ">
        <div>
            <span style="color:{color};font-weight:700;font-size:13px;letter-spacing:1px;">
                ⚠️ MARINE RISK: {risk}
            </span>
            <span style="color:#6a8aaa;font-size:12px;margin-left:16px;">
                {vessel} &nbsp;|&nbsp; Sea State: {sea} &nbsp;|&nbsp; {bft}
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)


def _fmt_visibility(vis_m) -> str:
    if vis_m is None:
        return "N/A"
    if vis_m >= 10000:
        return f"{vis_m/1000:.0f}+ km"
    if vis_m >= 1000:
        return f"{vis_m/1000:.1f} km"
    return f"{int(vis_m)} m"
