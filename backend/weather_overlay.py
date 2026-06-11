"""
weather_overlay.py
Generate Folium map overlays for weather visualization.
"""

import folium
import math
from typing import Optional


def _wind_arrow_html(wind_dir: float, wind_speed: float, color: str = "#00D4FF") -> str:
    """Generate SVG arrow rotated to wind direction."""
    rotation = wind_dir if wind_dir is not None else 0
    size = min(40 + wind_speed * 0.5, 80)
    return f"""
    <div style="transform: rotate({rotation}deg); display:inline-block;">
      <svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="{color}" 
           xmlns="http://www.w3.org/2000/svg">
        <polygon points="12,2 18,18 12,14 6,18" />
      </svg>
    </div>
    """


def add_vessel_weather_marker(
    fmap: folium.Map,
    lat: float,
    lon: float,
    vessel_name: str,
    weather: dict,
    selected: bool = False,
) -> None:
    """Add a styled vessel marker with weather popup to a Folium map."""

    risk_color = weather.get("marine_risk_color", "#888888")
    condition_icon = weather.get("condition_icon", "🌊")
    temp = weather.get("temperature", "--")
    wind = weather.get("wind_speed", "--")
    wind_dir = weather.get("wind_direction", 0) or 0
    pressure = weather.get("pressure", "--")
    precip = weather.get("precipitation", 0)
    humidity = weather.get("humidity", "--")
    sea = weather.get("sea_state", "N/A")
    risk = weather.get("marine_risk", "N/A")
    condition = weather.get("condition", "N/A")
    bft = weather.get("beaufort_desc", "N/A")

    # Marker icon colour
    icon_color = "red" if risk == "CRITICAL" else \
                 "orange" if risk == "HIGH" else \
                 "blue" if risk == "MODERATE" else "green"

    # Build popup HTML
    popup_html = f"""
    <div style="font-family:'Segoe UI',sans-serif; min-width:240px; padding:4px;">
      <div style="background:{risk_color};color:#fff;padding:8px 12px;border-radius:6px 6px 0 0;margin:-4px -4px 8px;">
        <strong style="font-size:14px;">{vessel_name}</strong>
        <span style="float:right;font-size:18px;">{condition_icon}</span>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <tr><td style="padding:3px 6px;color:#666;">Condition</td>
            <td style="padding:3px 6px;font-weight:600;">{condition}</td></tr>
        <tr style="background:#f8f8f8;">
            <td style="padding:3px 6px;color:#666;">Temperature</td>
            <td style="padding:3px 6px;font-weight:600;">{temp}°C</td></tr>
        <tr><td style="padding:3px 6px;color:#666;">Wind Speed</td>
            <td style="padding:3px 6px;font-weight:600;">{wind} km/h</td></tr>
        <tr style="background:#f8f8f8;">
            <td style="padding:3px 6px;color:#666;">Sea State</td>
            <td style="padding:3px 6px;font-weight:600;">{sea}</td></tr>
        <tr><td style="padding:3px 6px;color:#666;">Beaufort</td>
            <td style="padding:3px 6px;font-weight:600;">{bft}</td></tr>
        <tr style="background:#f8f8f8;">
            <td style="padding:3px 6px;color:#666;">Pressure</td>
            <td style="padding:3px 6px;font-weight:600;">{pressure} hPa</td></tr>
        <tr><td style="padding:3px 6px;color:#666;">Rainfall</td>
            <td style="padding:3px 6px;font-weight:600;">{precip} mm</td></tr>
        <tr style="background:#f8f8f8;">
            <td style="padding:3px 6px;color:#666;">Humidity</td>
            <td style="padding:3px 6px;font-weight:600;">{humidity}%</td></tr>
        <tr><td style="padding:3px 6px;color:#666;">Marine Risk</td>
            <td style="padding:3px 6px;font-weight:600;color:{risk_color};">{risk}</td></tr>
      </table>
      <div style="background:#f0f0f0;padding:4px 8px;border-radius:0 0 6px 6px;
                  font-size:11px;color:#888;text-align:center;margin-top:4px;">
        {lat:.4f}°, {lon:.4f}°
      </div>
    </div>
    """

    tooltip_text = f"🚢 {vessel_name} | {condition_icon} {temp}°C | 💨 {wind} km/h"

    marker = folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(popup_html, max_width=280),
        tooltip=tooltip_text,
        icon=folium.Icon(
            color=icon_color,
            icon="ship" if selected else "anchor",
            prefix="fa",
        ),
    )
    marker.add_to(fmap)

    # Wind direction arrow
    wind_icon_html = folium.DivIcon(
        html=_wind_arrow_html(wind_dir, float(wind) if wind != "--" else 0),
        icon_size=(50, 50),
        icon_anchor=(25, 25),
    )
    folium.Marker(
        location=[lat + 0.05, lon + 0.05],
        icon=wind_icon_html,
    ).add_to(fmap)


def add_risk_circle(fmap: folium.Map, lat: float, lon: float, risk_color: str, radius_km: float = 50) -> None:
    """Draw a semi-transparent risk zone circle around a vessel."""
    folium.Circle(
        location=[lat, lon],
        radius=radius_km * 1000,
        color=risk_color,
        weight=1.5,
        fill=True,
        fill_color=risk_color,
        fill_opacity=0.06,
        dash_array="6 4",
    ).add_to(fmap)
