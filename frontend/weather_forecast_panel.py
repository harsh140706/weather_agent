"""
weather_forecast_panel.py
Enriched 7-day forecast UI panel.

Consumes WeatherIntelligence from ForecastEngine.
Displays: confidence bands, smoothed vs raw wind, day-level risk scores,
anomaly markers, alert banners, trend indicators.

Designed to sit alongside existing weather_charts.py without replacing it.
"""

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional

from forecasting.schemas import WeatherIntelligence, AlertLevel, MarineRisk, ForecastConfidence

# ─────────────────────────────────────────────────────────────────────────────
# Theme (matches weather_charts.py)
# ─────────────────────────────────────────────────────────────────────────────

T = {
    "bg":      "#0a1628",
    "paper":   "#0d2040",
    "grid":    "rgba(0,212,255,0.08)",
    "text":    "#8ab4d4",
    "accent":  "#00D4FF",
    "warm":    "#FF6B35",
    "cool":    "#4ECDC4",
    "danger":  "#FF2D2D",
    "warn":    "#FFD700",
    "ok":      "#00C851",
    "orange":  "#FF8C00",
    "purple":  "#9B59B6",
    "muted":   "rgba(138,180,212,0.4)",
}

ALERT_COLORS = {
    AlertLevel.NONE:     T["ok"],
    AlertLevel.ADVISORY: T["accent"],
    AlertLevel.WATCH:    T["warn"],
    AlertLevel.WARNING:  T["orange"],
    AlertLevel.CRITICAL: T["danger"],
}

CONFIDENCE_COLORS = {
    ForecastConfidence.HIGH:   T["ok"],
    ForecastConfidence.MEDIUM: T["warn"],
    ForecastConfidence.LOW:    T["orange"],
}

RISK_COLORS = {
    MarineRisk.LOW:      T["ok"],
    MarineRisk.MODERATE: T["warn"],
    MarineRisk.HIGH:     T["orange"],
    MarineRisk.CRITICAL: T["danger"],
}


def _base_layout(title: str, height: int = 300) -> dict:
    return dict(
        title=dict(text=title, font=dict(color=T["text"], size=13), x=0.01, y=0.97),
        height=height,
        margin=dict(l=44, r=20, t=40, b=44),
        paper_bgcolor=T["paper"],
        plot_bgcolor=T["bg"],
        font=dict(color=T["text"], size=11),
        xaxis=dict(gridcolor=T["grid"], tickfont=dict(size=10)),
        yaxis=dict(gridcolor=T["grid"], tickfont=dict(size=10)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Alert banner
# ─────────────────────────────────────────────────────────────────────────────

def render_intelligence_alerts(intel: WeatherIntelligence) -> None:
    """Render alert banners at the top of the forecast section."""
    if intel.overall_alert_level == AlertLevel.NONE:
        return

    color = ALERT_COLORS[intel.overall_alert_level]
    icon_map = {
        AlertLevel.ADVISORY: "ℹ️",
        AlertLevel.WATCH:    "👁️",
        AlertLevel.WARNING:  "⚠️",
        AlertLevel.CRITICAL: "🚨",
    }
    icon = icon_map.get(intel.overall_alert_level, "⚠️")

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,{color}22,{color}11);
                border-left:3px solid {color};border-radius:4px;
                padding:10px 14px;margin-bottom:12px;">
        <div style="color:{color};font-weight:700;font-size:13px;">
            {icon} {intel.overall_alert_level.value} — 7-Day Forecast Alert
        </div>
        <div style="color:#c8d8e8;font-size:12px;margin-top:4px;">
            {"<br>".join(set(a.message for a in intel.alerts[:5]))}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if intel.anomaly_detected:
        st.markdown(f"""
        <div style="background:rgba(155,89,182,0.1);border-left:3px solid {T['purple']};
                    border-radius:4px;padding:8px 14px;margin-bottom:12px;">
            <span style="color:{T['purple']};font-weight:600;font-size:12px;">
                🔁 Anomaly Detected:
            </span>
            <span style="color:#c8d8e8;font-size:12px;"> {intel.anomaly_description}</span>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# 7-day summary cards
# ─────────────────────────────────────────────────────────────────────────────

def render_7day_cards(intel: WeatherIntelligence) -> None:
    """Render one card per forecast day with enriched metrics."""
    if not intel.forecast:
        st.info("No forecast data available.")
        return

    cols = st.columns(len(intel.forecast))

    for i, (col, day) in enumerate(zip(cols, intel.forecast)):
        risk_color = RISK_COLORS[day.marine_risk]
        conf_color = CONFIDENCE_COLORS[day.confidence]
        alert_icon = {
            AlertLevel.NONE:     "",
            AlertLevel.ADVISORY: "ℹ️",
            AlertLevel.WATCH:    "👁️",
            AlertLevel.WARNING:  "⚠️",
            AlertLevel.CRITICAL: "🚨",
        }.get(day.alert_level, "")

        # Trend arrows
        trend_icons = {"rising": "↗", "falling": "↘", "stable": "→"}
        wind_arrow = trend_icons.get(day.wind_trend, "→")

        is_worst = (i == intel.worst_day_index)
        border = f"border: 1px solid {T['danger']};" if is_worst else \
                 f"border: 1px solid rgba(0,212,255,0.15);"

        with col:
            st.markdown(f"""
            <div style="background:#0d2040;border-radius:8px;padding:10px 8px;
                        text-align:center;{border}position:relative;">
                {"<div style='position:absolute;top:4px;right:6px;font-size:10px;'>🔴 WORST</div>" if is_worst else ""}
                <div style="font-size:11px;color:#6a8aaa;font-weight:600;
                            letter-spacing:0.5px;">{day.day_label}</div>
                <div style="font-size:22px;margin:4px 0;">{day.condition_icon}</div>
                <div style="font-size:18px;color:#e8f4ff;font-weight:700;">
                    {day.temp_max:.0f}°
                    <span style="font-size:12px;color:#6a8aaa;">/ {day.temp_min:.0f}°</span>
                </div>
                <div style="font-size:11px;color:{T['accent']};margin-top:4px;">
                    💨 {day.wind_smoothed:.0f} km/h {wind_arrow}
                </div>
                <div style="font-size:10px;color:#6a8aaa;">Bft {day.beaufort_num}</div>
                <div style="margin-top:6px;padding:3px 6px;border-radius:4px;
                            background:{risk_color}22;
                            font-size:10px;font-weight:700;color:{risk_color};">
                    {day.marine_risk.value} {alert_icon}
                </div>
                <div style="margin-top:4px;font-size:9px;color:{conf_color};">
                    {day.confidence.value} ({day.confidence_pct*100:.0f}%)
                </div>
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# Wind forecast chart — raw + smoothed + confidence band
# ─────────────────────────────────────────────────────────────────────────────

def render_wind_forecast_chart(intel: WeatherIntelligence) -> None:
    """Plot raw wind, smoothed wind, and confidence-shaded area."""
    if not intel.forecast:
        return

    days      = [d.day_label for d in intel.forecast]
    raw_wind  = [d.wind_max for d in intel.forecast]
    smt_wind  = [d.wind_smoothed for d in intel.forecast]
    conf_pcts = [d.confidence_pct for d in intel.forecast]

    # Confidence band: ±(1 - conf) * value
    upper = [v * (1 + (1 - c) * 0.5) for v, c in zip(smt_wind, conf_pcts)]
    lower = [max(0, v * (1 - (1 - c) * 0.5)) for v, c in zip(smt_wind, conf_pcts)]

    fig = go.Figure()

    # Confidence band (shaded area)
    fig.add_trace(go.Scatter(
        x=days + days[::-1],
        y=upper + lower[::-1],
        fill="toself",
        fillcolor="rgba(0,212,255,0.07)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Confidence Band",
        hoverinfo="skip",
    ))

    # Smoothed (primary)
    fig.add_trace(go.Scatter(
        x=days, y=smt_wind,
        name="Wind (smoothed)",
        line=dict(color=T["accent"], width=2.5),
        mode="lines+markers",
        marker=dict(size=6, color=T["accent"]),
    ))

    # Raw (secondary)
    fig.add_trace(go.Scatter(
        x=days, y=raw_wind,
        name="Wind (raw API)",
        line=dict(color=T["muted"], width=1.2, dash="dot"),
        mode="lines",
    ))

    # Beaufort reference lines
    for level, label, color in [(39, "Bft 5", T["warn"]), (62, "Bft 8 Gale", T["orange"]),
                                  (89, "Bft 10 Storm", T["danger"])]:
        fig.add_hline(y=level, line_dash="dash", line_color=color,
                      annotation_text=label, annotation_font_color=color,
                      annotation_font_size=9)

    # Anomaly markers
    for day in intel.forecast:
        if day.alert_level not in (AlertLevel.NONE, AlertLevel.ADVISORY):
            fig.add_vline(
                x=day.day_label,
                line_dash="dot",
                line_color=ALERT_COLORS[day.alert_level],
                line_width=1.5,
                annotation_text=day.alert_level.value,
                annotation_font_color=ALERT_COLORS[day.alert_level],
                annotation_font_size=9,
            )

    layout = _base_layout("💨 7-Day Wind Forecast (km/h) — Smoothed + Confidence", height=300)
    layout["showlegend"] = True
    layout["legend"] = dict(orientation="h", y=1.08, x=0, font=dict(size=10))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Marine risk score timeline
# ─────────────────────────────────────────────────────────────────────────────

def render_risk_score_chart(intel: WeatherIntelligence) -> None:
    """Bar chart of per-day marine risk score (0–10)."""
    if not intel.forecast:
        return

    days   = [d.day_label for d in intel.forecast]
    scores = [d.marine_risk_score for d in intel.forecast]
    colors = [d.marine_risk_color for d in intel.forecast]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=days, y=scores,
        marker_color=colors,
        name="Marine Risk Score",
        text=[str(s) for s in scores],
        textposition="outside",
        textfont=dict(color=T["text"], size=11),
    ))

    fig.add_hline(y=3, line_dash="dash", line_color=T["warn"],
                  annotation_text="MODERATE threshold", annotation_font_size=9,
                  annotation_font_color=T["warn"])
    fig.add_hline(y=5, line_dash="dash", line_color=T["orange"],
                  annotation_text="HIGH threshold", annotation_font_size=9,
                  annotation_font_color=T["orange"])
    fig.add_hline(y=7, line_dash="dash", line_color=T["danger"],
                  annotation_text="CRITICAL threshold", annotation_font_size=9,
                  annotation_font_color=T["danger"])

    layout = _base_layout("⚓ 7-Day Marine Risk Score (0–10)", height=260)
    layout["yaxis"] = dict(range=[0, 11], gridcolor=T["grid"], tickfont=dict(size=10))
    fig.update_layout(**layout)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Temperature + precip combined
# ─────────────────────────────────────────────────────────────────────────────

def render_temp_precip_chart(intel: WeatherIntelligence) -> None:
    """Dual-axis chart: temp range band (left) + precip bars (right)."""
    if not intel.forecast:
        return

    days      = [d.day_label for d in intel.forecast]
    temp_max  = [d.temp_max for d in intel.forecast]
    temp_min  = [d.temp_min for d in intel.forecast]
    precip    = [d.precip_smoothed for d in intel.forecast]

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    fig.add_trace(go.Scatter(
        x=days, y=temp_max,
        name="Temp Max", line=dict(color=T["warm"], width=2),
        fill=None,
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=days, y=temp_min,
        name="Temp Min", line=dict(color=T["cool"], width=2),
        fill="tonexty", fillcolor="rgba(255,107,53,0.1)",
    ), secondary_y=False)

    fig.add_trace(go.Bar(
        x=days, y=precip,
        name="Precip (smoothed mm)",
        marker_color=T["cool"],
        opacity=0.7,
    ), secondary_y=True)

    fig.update_layout(
        height=300,
        margin=dict(l=44, r=50, t=40, b=44),
        paper_bgcolor=T["paper"],
        plot_bgcolor=T["bg"],
        font=dict(color=T["text"], size=11),
        title=dict(text="🌡️ 7-Day Temp Range & Precipitation", font=dict(color=T["text"], size=13), x=0.01),
        legend=dict(orientation="h", y=1.08, x=0, font=dict(size=10)),
        xaxis=dict(gridcolor=T["grid"]),
        yaxis=dict(gridcolor=T["grid"], title="Temperature (°C)", title_font_color=T["warm"]),
    )
    fig.update_yaxes(title_text="Precip (mm)", secondary_y=True,
                     title_font_color=T["cool"])
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


# ─────────────────────────────────────────────────────────────────────────────
# Summary intelligence row
# ─────────────────────────────────────────────────────────────────────────────

def render_intelligence_summary(intel: WeatherIntelligence) -> None:
    """Metrics row: confidence, worst day, trend, anomaly status."""
    conf_color  = T["ok"] if intel.avg_confidence >= 0.75 else \
                  T["warn"] if intel.avg_confidence >= 0.55 else T["orange"]
    worst_day   = intel.forecast[intel.worst_day_index].day_label if intel.forecast else "—"
    worst_risk  = intel.worst_marine_risk.value

    trend_icon = {"rising": "↗ Rising", "falling": "↘ Falling", "stable": "→ Stable"}

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Avg Forecast Confidence",
                  f"{intel.avg_confidence * 100:.0f}%")
    with col2:
        st.metric("7-Day Wind Trend", trend_icon.get(intel.wind_7day_trend, "—"))
    with col3:
        st.metric("7-Day Precip Trend", trend_icon.get(intel.precip_7day_trend, "—"))
    with col4:
        st.metric("Worst Day", f"{worst_day} ({worst_risk})")
    with col5:
        st.metric("Anomaly", "⚠️ Detected" if intel.anomaly_detected else "✅ None")


# ─────────────────────────────────────────────────────────────────────────────
# Top-level entry point
# ─────────────────────────────────────────────────────────────────────────────

def render_7day_intelligence_panel(intel: Optional[WeatherIntelligence]) -> None:
    """
    Full enriched 7-day forecast panel.
    Called from weather_panel.py when timeline_view == '7 Days'.
    """
    if intel is None:
        st.info("⏳ Advanced forecast intelligence not available for this vessel.")
        return

    render_intelligence_alerts(intel)
    render_intelligence_summary(intel)

    st.markdown("---")
    render_7day_cards(intel)

    st.markdown("---")
    col_left, col_right = st.columns(2)
    with col_left:
        render_wind_forecast_chart(intel)
    with col_right:
        render_risk_score_chart(intel)

    render_temp_precip_chart(intel)
