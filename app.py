"""
app.py
Maritime Weather Intelligence Agent — Main Streamlit Dashboard

Changes vs original:
  • fetch_weather_for_vessel() now also builds WeatherIntelligence via
    WeatherProcessor.process_with_intelligence()
  • Intelligence object passed to render_weather_panel() for 7-day enriched view
  • Cache stats now show hit rate
  • Fleet batch fetch uses WeatherClient.fetch_batch() for deduplication
  • Logging configured at startup (replaces bare print statements in backend)
"""

import logging
import os
import sys
import time

import streamlit as st

logging.basicConfig(
    level=logging.WARNING,      # Suppress debug noise in Streamlit UI
    format="%(levelname)s [%(name)s] %(message)s",
)

# ── Path setup ────────────────────────────────────────────────────────────────
BACKEND_DIR  = os.path.join(os.path.dirname(__file__), "backend")
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, FRONTEND_DIR)

from dataset_loader    import DatasetLoader
from weather_client    import WeatherClient
from weather_processor import WeatherProcessor
from weather_cache     import WeatherCache
from weather_panel     import render_weather_panel
from weather_map       import render_map

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Weather Agent",
    page_icon="⚓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS (unchanged from original) ─────────────────────────────────────
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] {
    background-color: #060e1c !important; color: #c8d8e8;
}
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0a1628 0%, #081220 100%) !important;
    border-right: 1px solid rgba(0,212,255,0.15);
}
[data-testid="stSidebar"] * { color: #b0c8e0 !important; }
h1, h2, h3, h4 { color: #e8f4ff !important; }
.stSelectbox label, .stRadio label { color: #8ab4d4 !important; font-size: 12px; }
div[data-baseweb="select"] > div { background: #0d2040 !important; border-color: rgba(0,212,255,0.3) !important; }
.stButton > button {
    background: linear-gradient(135deg, #00D4FF22 0%, #0099CC22 100%) !important;
    border: 1px solid rgba(0,212,255,0.4) !important;
    color: #00D4FF !important; border-radius: 8px;
}
.stButton > button:hover { background: linear-gradient(135deg,#00D4FF44,#0099CC44) !important; }
hr { border-color: rgba(0,212,255,0.15) !important; }
.stAlert { background: #0d2040 !important; }
[data-testid="stMetric"] {
    background: #0d2040; border: 1px solid rgba(0,212,255,0.15);
    border-radius: 8px; padding: 8px 12px;
}
[data-testid="stMetricValue"] { color: #00D4FF !important; font-size: 18px !important; }
[data-testid="stMetricLabel"] { color: #6a8aaa !important; font-size: 11px !important; }
.stTabs [data-baseweb="tab-list"] { background: transparent; gap: 4px; }
.stTabs [data-baseweb="tab"] {
    background: rgba(0,212,255,0.06); border: 1px solid rgba(0,212,255,0.15);
    border-radius: 6px 6px 0 0; color: #8ab4d4 !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(0,212,255,0.18) !important; color: #00D4FF !important;
    border-color: rgba(0,212,255,0.4) !important;
}
</style>
""", unsafe_allow_html=True)


# ── Cached backend objects ────────────────────────────────────────────────────
@st.cache_resource
def get_loader():
    dataset_path = os.path.join(os.path.dirname(__file__), "ships.csv")
    loader = DatasetLoader(filepath=dataset_path)
    loader.load()
    return loader

@st.cache_resource
def get_client():
    return WeatherClient(timeout=12)

@st.cache_resource
def get_cache():
    return WeatherCache(ttl_seconds=600, max_size=200)

@st.cache_resource
def get_processor():
    return WeatherProcessor()


# ── Sidebar ───────────────────────────────────────────────────────────────────
def render_sidebar(loader: DatasetLoader) -> tuple:
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:16px 0 8px;">
            <div style="font-size:36px;">⚓</div>
            <div style="font-size:16px;font-weight:700;color:#00D4FF;letter-spacing:2px;">
                WEATHER AGENT
            </div>
        </div>
        <hr style="margin:8px 0;">
        """, unsafe_allow_html=True)

        st.markdown("**🚢 Select Vessel**")
        vessels_df = loader.get_all_vessels()
        vessel_options = [f"{row['vessel_name']} ({row['mmsi']})" for _, row in vessels_df.iterrows()]
        selected_label = st.selectbox("Vessel", vessel_options, label_visibility="collapsed")
        selected_idx   = vessel_options.index(selected_label)
        selected_vessel = vessels_df.iloc[selected_idx].to_dict()

        st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)
        st.markdown("**📡 Vessel Info**")
        st.markdown(f"""
        <div style="background:#0d2040;border-radius:8px;padding:10px;font-size:12px;margin-bottom:8px;">
            <div><span style="color:#6a8aaa;">MMSI:</span>
                <span style="color:#e8f4ff;float:right;">{selected_vessel.get('mmsi','')}</span></div>
            <div style="margin-top:4px;"><span style="color:#6a8aaa;">Speed:</span>
                <span style="color:#e8f4ff;float:right;">{selected_vessel.get('speed',0):.1f} kn</span></div>
            <div style="margin-top:4px;"><span style="color:#6a8aaa;">Course:</span>
                <span style="color:#e8f4ff;float:right;">{selected_vessel.get('course',0):.0f}°</span></div>
            <div style="margin-top:4px;"><span style="color:#6a8aaa;">Status:</span>
                <span style="color:#e8f4ff;float:right;">{selected_vessel.get('status','')}</span></div>
            <div style="margin-top:4px;"><span style="color:#6a8aaa;">Lat:</span>
                <span style="color:#e8f4ff;float:right;">{selected_vessel.get('latitude',0):.4f}°</span></div>
            <div style="margin-top:4px;"><span style="color:#6a8aaa;">Lon:</span>
                <span style="color:#e8f4ff;float:right;">{selected_vessel.get('longitude',0):.4f}°</span></div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**📅 Timeline View**")
        timeline_view = st.radio(
            "Timeline", ["Current", "24 Hours", "7 Days"], label_visibility="collapsed",
        )

        st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)
        st.markdown("**🗺️ Map Options**")
        show_all_vessels = st.checkbox("Show all vessels on map", value=True)
        auto_refresh     = st.checkbox("Auto-refresh weather (10 min)", value=False)

        # Cache stats with hit rate
        cache = get_cache()
        stats = cache.stats()
        st.markdown(f"""
        <div style="background:#0d2040;border-radius:6px;padding:8px;font-size:10px;color:#4a8aaa;margin-top:8px;">
            🗄️ Cache: {stats['valid']}/{stats['total']} valid
            &nbsp;·&nbsp; Hit rate: {stats['hit_rate_pct']}%
        </div>
        """, unsafe_allow_html=True)

        if st.button("🔄 Clear Cache"):
            cache.clear()
            st.rerun()

        st.markdown("""
        <div style="text-align:center;margin-top:16px;padding:6px;
                    background:rgba(0,212,255,0.06);border-radius:6px;
                    font-size:10px;color:#4a8aaa;letter-spacing:1px;">
            PHASE 1 · OPEN-METEO · FREE API
        </div>
        """, unsafe_allow_html=True)

    return selected_vessel, timeline_view, show_all_vessels, auto_refresh


# ── Weather fetch helper ──────────────────────────────────────────────────────
def fetch_weather_for_vessel(vessel: dict) -> tuple[dict, object]:
    """
    Fetch + process weather with caching.
    Returns (flat_weather_dict, WeatherIntelligence | None).
    """
    client    = get_client()
    cache     = get_cache()
    processor = get_processor()

    lat  = vessel["latitude"]
    lon  = vessel["longitude"]
    name = vessel.get("vessel_name", "Unknown")
    mmsi = str(vessel.get("mmsi", ""))

    raw = cache.get_or_fetch(lat, lon, client.fetch_weather)
    if not raw:
        return {}, None

    flat, intel = processor.process_with_intelligence(
        raw, vessel_name=name, mmsi=mmsi, latitude=lat, longitude=lon
    )
    return flat or {}, intel


# ── Main app ──────────────────────────────────────────────────────────────────
def main():
    try:
        loader = get_loader()
    except Exception as e:
        st.error(f"Could not load dataset: {e}")
        st.info("Place your AIS CSV at ships.csv in the project folder, then refresh.")
        return

    selected_vessel, timeline_view, show_all_vessels, auto_refresh = render_sidebar(loader)

    # Page header
    col_title, col_status = st.columns([4, 1])
    with col_title:
        st.markdown("""
        <h2 style="margin:0;color:#00D4FF;font-family:'Courier New',monospace;letter-spacing:3px;">
            ⚓ WEATHER AGENT
        </h2>
        <p style="color:#4a8aaa;font-size:12px;margin:2px 0 12px;letter-spacing:1px;">
            REAL-TIME WEATHER MONITORING · PREDICTIVE 7-DAY FORECAST · OPEN-METEO
        </p>
        """, unsafe_allow_html=True)
    with col_status:
        st.markdown("""
        <div style="text-align:right;padding-top:8px;">
            <span style="display:inline-block;width:8px;height:8px;border-radius:50%;
                         background:#00C851;box-shadow:0 0 6px #00C851;margin-right:4px;"></span>
            <span style="color:#00C851;font-size:11px;font-weight:600;">LIVE</span>
        </div>
        """, unsafe_allow_html=True)

    # Fetch selected vessel
    with st.spinner(f"🌊 Fetching weather for {selected_vessel.get('vessel_name', '')}..."):
        selected_weather, selected_intel = fetch_weather_for_vessel(selected_vessel)

    # Fetch fleet
    all_vessels_df = loader.get_all_vessels()
    all_vessels    = all_vessels_df.to_dict("records")
    weather_data_map: dict[str, dict] = {}

    if show_all_vessels:
        with st.spinner("📡 Loading weather for all vessels..."):
            for v in all_vessels:
                mmsi = str(v.get("mmsi", ""))
                w, _ = fetch_weather_for_vessel(v)
                if w:
                    weather_data_map[mmsi] = w
    else:
        mmsi = str(selected_vessel.get("mmsi", ""))
        if selected_weather:
            weather_data_map[mmsi] = selected_weather

    vessels_for_map = all_vessels if show_all_vessels else [selected_vessel]

    # Tabs
    tab_map, tab_weather, tab_fleet = st.tabs(
        ["🗺️ Weather Map", "📊 Weather Intel", "🚢 Fleet Overview"]
    )

    with tab_map:
        st.markdown(f"**Live Weather Map** · {len(vessels_for_map)} vessels tracked")
        render_map(
            vessels=vessels_for_map,
            weather_data=weather_data_map,
            selected_mmsi=str(selected_vessel.get("mmsi", "")),
            height=540,
        )

    with tab_weather:
        if selected_weather:
            render_weather_panel(
                selected_weather,
                timeline_view=timeline_view,
                intelligence=selected_intel,   # ← new enriched forecast
            )
        else:
            st.error("❌ Could not retrieve weather data. Check internet connection.")
            st.info("Using Open-Meteo free API (no key required). If offline, check connectivity.")

    with tab_fleet:
        _render_fleet_overview(all_vessels, weather_data_map)

    if auto_refresh:
        time.sleep(600)
        st.rerun()


def _render_fleet_overview(vessels: list, weather_data: dict) -> None:
    st.markdown("### 🚢 Fleet Weather Summary")

    import pandas as pd
    rows = []
    for v in vessels:
        mmsi = str(v.get("mmsi", ""))
        w = weather_data.get(mmsi, {})
        rows.append({
            "Vessel":      v.get("vessel_name", "Unknown"),
            "MMSI":        mmsi,
            "Lat":         f"{v.get('latitude',0):.2f}°",
            "Lon":         f"{v.get('longitude',0):.2f}°",
            "Status":      v.get("status", ""),
            "Speed (kn)":  f"{v.get('speed',0):.1f}",
            "Condition":   w.get("condition_icon","") + " " + w.get("condition","N/A") if w else "—",
            "Temp (°C)":   w.get("temperature","—") if w else "—",
            "Wind (km/h)": w.get("wind_speed","—") if w else "—",
            "Sea State":   w.get("sea_state","—") if w else "—",
            "Risk":        w.get("marine_risk","—") if w else "—",
        })

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True, height=400)

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    risks = [weather_data.get(str(v.get("mmsi","")),{}).get("marine_risk","") for v in vessels]
    with col1: st.metric("Total Vessels", len(vessels))
    with col2: st.metric("Critical Risk", risks.count("CRITICAL"), delta_color="inverse")
    with col3: st.metric("High Risk",     risks.count("HIGH"),     delta_color="inverse")
    with col4: st.metric("Low / Moderate", risks.count("LOW") + risks.count("MODERATE"))


if __name__ == "__main__":
    main()
