# ⚓ Maritime Weather Intelligence Agent
**Phase 1 — Real-time Weather Monitoring Dashboard**

## Overview
A Python + Streamlit dashboard that overlays live weather data from [Open-Meteo](https://open-meteo.com/) onto an OpenStreetMap visualization for AIS vessel positions.

- **No API key required** — uses Open-Meteo free tier
- **Real-time weather** for any vessel coordinates worldwide
- **Interactive map** with weather popups, risk circles, and layer toggles
- **Marine-specific metrics** — Beaufort scale, sea state, marine risk scoring
- **24h + 7-day forecasts** with Plotly charts

---

## Project Structure
```
weather_agent/
├── app.py                        ← Main Streamlit dashboard
├── ships.csv                     ← AIS vessel dataset
├── backend/
│   ├── dataset_loader.py         ← Load AIS ship data
│   ├── weather_client.py         ← Open-Meteo API client
│   ├── weather_processor.py      ← Normalize & enrich responses
│   ├── weather_cache.py          ← TTL in-memory cache
│   ├── weather_timeline.py       ← Timeline manager (24h / 7d)
│   ├── weather_overlay.py        ← Folium map overlays
│   └── requirements.txt
└── frontend/
    ├── weather_panel.py          ← Main weather panel composer
    ├── weather_map.py            ← OpenStreetMap visualization
    ├── weather_cards.py          ← Metric cards display
    └── weather_charts.py         ← Plotly trend charts
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r backend/requirements.txt
```

### 2. (Optional) Add your AIS dataset
Replace `ships.csv` with your own dataset. Required columns:
```
mmsi, vessel_name, latitude, longitude, timestamp, speed, course, status
```
If no file is found, the app loads 10 sample vessels automatically.

### 3. Run the dashboard
```bash
streamlit run app.py
```

---

## Dashboard Features

### 🗺️ Weather Map Tab
- OpenStreetMap base with Nautical Chart + Dark Mode layer options
- Color-coded vessel markers by marine risk level
- Click any marker for full weather popup
- Wind direction arrows at each vessel position
- Risk zone circles around selected vessel
- MiniMap + Fullscreen controls

### 📊 Weather Intel Tab
- **Current**: 12-card metric grid + detailed breakdown
- **24 Hours**: Temperature, wind, precipitation, cloud/humidity charts
- **7 Days**: Temperature range band + daily precipitation

### 🚢 Fleet Overview Tab
- Full fleet table with live weather per vessel
- Risk-level highlighted rows
- Summary metrics: total vessels, critical/high/low risk counts

---

## Weather Parameters
| Parameter | Unit | Source |
|-----------|------|--------|
| Temperature | °C | Open-Meteo |
| Feels Like | °C | Open-Meteo |
| Humidity | % | Open-Meteo |
| Wind Speed | km/h | Open-Meteo |
| Wind Direction | degrees + cardinal | Open-Meteo |
| Wind Gusts | km/h | Open-Meteo |
| Pressure | hPa | Open-Meteo |
| Precipitation | mm | Open-Meteo |
| Cloud Cover | % | Open-Meteo |
| Visibility | m / km | Open-Meteo |
| Beaufort Scale | 0–12 | Derived |
| Sea State | Douglas scale | Derived |
| Marine Risk | LOW/MODERATE/HIGH/CRITICAL | Derived |

---

## Marine Risk Scoring
Risk is computed from wind speed, visibility, and precipitation:
- **LOW** (green) — Normal operations
- **MODERATE** (yellow) — Caution advised
- **HIGH** (orange) — Reduced operations
- **CRITICAL** (red) — Severe marine conditions

---

## Phase 2 Roadmap
- NOAA Marine Weather integration
- Wave height analysis
- Storm surge alerts
- ERA5 historical weather

## Phase 3 Roadmap
- Weather–AIS correlation analysis
- Maritime route risk scoring
- Weather risk heat maps
