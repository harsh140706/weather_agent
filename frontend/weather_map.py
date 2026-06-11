"""
weather_map.py
OpenStreetMap-based weather visualization using Folium + streamlit-folium.
"""

import folium
from folium import plugins
import streamlit as st
from streamlit_folium import st_folium
from typing import Optional, List, Tuple
import sys
import os

# Allow imports from backend
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))
from weather_overlay import add_vessel_weather_marker, add_risk_circle


def build_weather_map(
    vessels: list,
    weather_data: dict,  # {mmsi: processed_weather_dict}
    selected_mmsi: Optional[str] = None,
    center: Optional[Tuple[float, float]] = None,
    zoom: int = 3,
) -> folium.Map:
    """
    Build a Folium map with weather-annotated vessel markers.

    Args:
        vessels: List of vessel dicts with lat/lon/mmsi/vessel_name
        weather_data: Dict of mmsi -> processed weather dict
        selected_mmsi: MMSI of selected vessel (highlighted)
        center: (lat, lon) center of map
        zoom: Initial zoom level
    """
    if center is None and vessels:
        lats = [v["latitude"] for v in vessels]
        lons = [v["longitude"] for v in vessels]
        center = (sum(lats) / len(lats), sum(lons) / len(lons))
    elif center is None:
        center = (20.0, 0.0)

    fmap = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=None,
        prefer_canvas=True,
    )

    # Base layers
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap",
        show=True,
    ).add_to(fmap)

    folium.TileLayer(
        tiles="https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
        attr="© Stadia Maps, © OpenMapTiles © OpenStreetMap contributors",
        name="Dark Mode",
        show=False,
    ).add_to(fmap)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/Ocean/World_Ocean_Base/MapServer/tile/{z}/{y}/{x}",
        attr="Esri, GEBCO, NOAA, National Geographic",
        name="Nautical Chart",
        show=False,
    ).add_to(fmap)

    # Vessel markers
    for vessel in vessels:
        mmsi = str(vessel.get("mmsi", ""))
        lat = vessel.get("latitude")
        lon = vessel.get("longitude")
        name = vessel.get("vessel_name", mmsi)

        if lat is None or lon is None:
            continue

        w = weather_data.get(mmsi, {})
        is_selected = (mmsi == str(selected_mmsi))

        if w:
            add_vessel_weather_marker(fmap, lat, lon, name, w, selected=is_selected)
            if is_selected:
                add_risk_circle(fmap, lat, lon, w.get("marine_risk_color", "#888"))
        else:
            # No weather: plain marker
            folium.Marker(
                location=[lat, lon],
                tooltip=f"🚢 {name}",
                icon=folium.Icon(color="gray", icon="anchor", prefix="fa"),
            ).add_to(fmap)

    # If selected vessel, pan to it
    if selected_mmsi:
        for v in vessels:
            if str(v.get("mmsi")) == str(selected_mmsi):
                fmap.location = [v["latitude"], v["longitude"]]
                fmap.zoom_start = 7
                break

    # Controls
    folium.LayerControl(position="topright", collapsed=False).add_to(fmap)
    plugins.Fullscreen(position="topright", title="Fullscreen").add_to(fmap)
    plugins.MiniMap(tile_layer="OpenStreetMap", toggle_display=True).add_to(fmap)

    return fmap


def render_map(
    vessels: list,
    weather_data: dict,
    selected_mmsi: Optional[str] = None,
    height: int = 520,
) -> None:
    """Render the Folium map in Streamlit."""
    fmap = build_weather_map(vessels, weather_data, selected_mmsi)
    st_folium(fmap, use_container_width=True, height=height, returned_objects=[])
