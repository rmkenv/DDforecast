"""
app.py  —  Streamlit degree-day dashboard
Reads from data/*.json written by etl.py (or fetches live if files absent).
"""

import json
from pathlib import Path
from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

from utils.degree_days import compute_degree_days, compute_normals, compute_anomaly

# ── page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Degree Day Forecast",
    page_icon="🌡️",
    layout="wide",
)

st.title("🌡️ Degree Day Forecasting Platform")
st.caption("HDD & CDD — 16-day forecast + 30-year anomaly · Open-Meteo")

# ── sidebar controls ──────────────────────────────────────────────────────────

with st.sidebar:
    st.header("Settings")

    mode = st.radio("Data source", ["Live (Open-Meteo API)", "Local data/"])

    preset_locs = {
        "Cumberland, MD":  (39.65, -78.83),
        "Baltimore, MD":   (39.29, -76.61),
        "Washington, DC":  (38.91, -77.04),
        "Pittsburgh, PA":  (40.44, -79.99),
        "Richmond, VA":    (37.54, -77.44),
        "Custom":          None,
    }
    loc_choice = st.selectbox("Location", list(preset_locs.keys()))

    if loc_choice == "Custom" or preset_locs[loc_choice] is None:
        lat = st.number_input("Latitude",  value=39.65, format="%.4f")
        lon = st.number_input("Longitude", value=-78.83, format="%.4f")
    else:
        lat, lon = preset_locs[loc_choice]
        st.caption(f"lat {lat}, lon {lon}")

    base_temp = st.number_input("Base temperature (°F)", value=65, step=1)
    fetch_btn = st.button("Fetch / Refresh", type="primary", use_container_width=True)

# ── data loading ──────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def load_live(lat, lon, base_temp):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    hist_start = (date.today() - timedelta(days=365 * 30)).isoformat()

    def _get(url, params):
        r = requests.get(url, params=params, timeout=60)
        r.raise_for_status()
        return r.json()

    fj = _get("https://api.open-meteo.com/v1/forecast", {
        "latitude": lat, "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "forecast_days": 16, "timezone": "auto",
    })
    hj = _get("https://archive-api.open-meteo.com/v1/archive", {
        "latitude": lat, "longitude": lon,
        "start_date": hist_start, "end_date": yesterday,
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit", "timezone": "auto",
    })
    daily   = compute_degree_days(fj["daily"], base_temp)
    normals = compute_normals(hj["daily"], base_temp)
    anomaly = compute_anomaly(daily, normals)
    return daily, normals, anomaly

def load_local(loc_name):
    slug = loc_name.lower().replace(", ", "-").replace(" ", "-")
    path = Path("data") / f"{slug}.json"
    if not path.exists():
        st.error(f"No local file found at {path}. Run etl.py first.")
        st.stop()
    data = json.loads(path.read_text())
    return data["daily"], data["normals"], data["anomaly"]

if fetch_btn or "daily" not in st.session_state:
    with st.spinner("Fetching data…"):
        if mode.startswith("Live"):
            daily, normals, anomaly = load_live(lat, lon, base_temp)
        else:
            daily, normals, anomaly = load_local(loc_choice)
        st.session_state.update({"daily": daily, "normals": normals, "anomaly": anomaly})

daily   = st.session_state.get("daily", [])
normals = st.session_state.get("normals", {})
anomaly = st.session_state.get("anomaly", {})

if not daily:
    st.info("Configure settings in the sidebar and click Fetch / Refresh.")
    st.stop()

# ── summary metrics ───────────────────────────────────────────────────────────

df = pd.DataFrame(daily)
total_hdd = df["hdd"].sum()
total_cdd = df["cdd"].sum()
peak_hdd_row = df.loc[df["hdd"].idxmax()]
peak_cdd_row = df.loc[df["cdd"].idxmax()]
hdd_delta = anomaly.get("hdd_delta_cumulative", 0)
cdd_delta = anomaly.get("cdd_delta_cumulative", 0)

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("16-day HDD", f"{total_hdd:.0f}", f"vs normal: {hdd_delta:+.0f}")
col2.metric("16-day CDD", f"{total_cdd:.0f}", f"vs normal: {cdd_delta:+.0f}")
col3.metric("Peak HDD", f"{peak_hdd_row['hdd']:.0f}", peak_hdd_row["date"])
col4.metric("Peak CDD", f"{peak_cdd_row['cdd']:.0f}", peak_cdd_row["date"])
col5.metric("Avg mean temp", f"{df['mean'].mean():.1f}°F")

# anomaly banner
if hdd_delta > 15:
    st.warning(f"🔥 Heating demand **{hdd_delta:.0f} HDD above** 30-year normal over this 16-day window")
elif hdd_delta < -15:
    st.success(f"📉 Heating demand **{abs(hdd_delta):.0f} HDD below** 30-year normal over this 16-day window")
else:
    st.info(f"✓ Heating demand tracking near 30-year normal ({hdd_delta:+.0f} HDD)")

st.divider()

# ── tabs ──────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4 = st.tabs(["Forecast", "Accumulation", "Anomaly", "Daily table"])

COLORS = {"hdd": "#185FA5", "cdd": "#D85A30"}

# ── tab 1: daily forecast bars ────────────────────────────────────────────────
with tab1:
    fig = go.Figure()
    fig.add_bar(x=df["date"], y=df["hdd"], name="HDD", marker_color=COLORS["hdd"], opacity=0.8)
    fig.add_bar(x=df["date"], y=df["cdd"], name="CDD", marker_color=COLORS["cdd"], opacity=0.8)
    fig.update_layout(
        barmode="group",
        xaxis_title="Date", yaxis_title="Degree days",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=40, b=40), height=400,
    )
    st.plotly_chart(fig, use_container_width=True)

# ── tab 2: cumulative accumulation ───────────────────────────────────────────
with tab2:
    df["cum_hdd"] = df["hdd"].cumsum()
    df["cum_cdd"] = df["cdd"].cumsum()

    # build normal + band arrays
    norm_hdd, upper_hdd, lower_hdd, norm_cdd = [], [], [], []
    for d in daily:
        doy = d["date"][5:]
        n = normals.get(doy, {"hdd_mean": 0, "hdd_sd": 0, "cdd_mean": 0})
        norm_hdd.append(n["hdd_mean"])
        upper_hdd.append(n["hdd_mean"] + n["hdd_sd"])
        lower_hdd.append(max(0, n["hdd_mean"] - n["hdd_sd"]))
        norm_cdd.append(n["cdd_mean"])

    cum_norm_hdd   = pd.Series(norm_hdd).cumsum()
    cum_upper_hdd  = pd.Series(upper_hdd).cumsum()
    cum_lower_hdd  = pd.Series(lower_hdd).cumsum()
    cum_norm_cdd   = pd.Series(norm_cdd).cumsum()

    fig2 = go.Figure()
    # ±1σ band
    fig2.add_scatter(
        x=list(df["date"]) + list(df["date"])[::-1],
        y=list(cum_upper_hdd) + list(cum_lower_hdd)[::-1],
        fill="toself", fillcolor="rgba(24,95,165,0.10)",
        line=dict(color="rgba(0,0,0,0)"), name="HDD ±1σ", showlegend=True,
    )
    fig2.add_scatter(x=df["date"], y=cum_norm_hdd,  name="HDD normal", line=dict(color=COLORS["hdd"], dash="dash", width=1.5))
    fig2.add_scatter(x=df["date"], y=df["cum_hdd"], name="HDD forecast", line=dict(color=COLORS["hdd"], width=2.5), mode="lines+markers", marker_size=5)
    fig2.add_scatter(x=df["date"], y=cum_norm_cdd,  name="CDD normal", line=dict(color=COLORS["cdd"], dash="dash", width=1.5))
    fig2.add_scatter(x=df["date"], y=df["cum_cdd"], name="CDD forecast", line=dict(color=COLORS["cdd"], width=2.5), mode="lines+markers", marker_size=5)
    fig2.update_layout(
        xaxis_title="Date", yaxis_title="Cumulative degree days",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(t=40, b=40), height=420,
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── tab 3: anomaly ────────────────────────────────────────────────────────────
with tab3:
    anom_df = pd.DataFrame(anomaly.get("per_day", []))
    if not anom_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.caption("HDD anomaly vs 30-year normal")
            fig3 = go.Figure()
            colors_hdd = [COLORS["hdd"] if v >= 0 else COLORS["cdd"] for v in anom_df["hdd_delta"]]
            fig3.add_bar(x=anom_df["date"], y=anom_df["hdd_delta"], marker_color=colors_hdd, name="HDD Δ")
            fig3.add_hline(y=0, line_width=1, line_color="gray")
            fig3.update_layout(showlegend=False, height=320, margin=dict(t=20, b=40),
                               yaxis_title="HDD vs normal")
            st.plotly_chart(fig3, use_container_width=True)

        with c2:
            st.caption("CDD anomaly vs 30-year normal")
            fig4 = go.Figure()
            colors_cdd = [COLORS["cdd"] if v >= 0 else COLORS["hdd"] for v in anom_df["cdd_delta"]]
            fig4.add_bar(x=anom_df["date"], y=anom_df["cdd_delta"], marker_color=colors_cdd, name="CDD Δ")
            fig4.add_hline(y=0, line_width=1, line_color="gray")
            fig4.update_layout(showlegend=False, height=320, margin=dict(t=20, b=40),
                               yaxis_title="CDD vs normal")
            st.plotly_chart(fig4, use_container_width=True)

        st.caption("Z-scores (standard deviations from 30-year mean)")
        fig5 = go.Figure()
        fig5.add_scatter(x=anom_df["date"], y=anom_df["hdd_z"], mode="lines+markers",
                         name="HDD z-score", line=dict(color=COLORS["hdd"]))
        fig5.add_scatter(x=anom_df["date"], y=anom_df["cdd_z"], mode="lines+markers",
                         name="CDD z-score", line=dict(color=COLORS["cdd"]))
        fig5.add_hline(y=0, line_width=1, line_color="gray")
        fig5.add_hrect(y0=-1, y1=1, fillcolor="rgba(0,0,0,0.04)", line_width=0)
        fig5.update_layout(height=280, margin=dict(t=20, b=40), yaxis_title="z-score",
                           legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig5, use_container_width=True)

# ── tab 4: daily table ────────────────────────────────────────────────────────
with tab4:
    anom_per_day = {d["date"]: d for d in anomaly.get("per_day", [])}
    table_rows = []
    cum_hdd = cum_cdd = 0.0
    for d in daily:
        cum_hdd += d["hdd"]; cum_cdd += d["cdd"]
        an = anom_per_day.get(d["date"], {})
        table_rows.append({
            "Date":     d["date"],
            "T-max °F": d["tmax"],
            "T-min °F": d["tmin"],
            "Mean °F":  d["mean"],
            "HDD":      d["hdd"],
            "CDD":      d["cdd"],
            "HDD Δ norm": an.get("hdd_delta", ""),
            "HDD z":    an.get("hdd_z", ""),
            "Cum HDD":  round(cum_hdd, 1),
            "Cum CDD":  round(cum_cdd, 1),
        })

    tdf = pd.DataFrame(table_rows)
    st.dataframe(
        tdf.style
           .background_gradient(subset=["HDD"], cmap="Blues")
           .background_gradient(subset=["CDD"], cmap="Oranges")
           .format(precision=1),
        use_container_width=True,
        height=560,
    )
    csv = tdf.to_csv(index=False)
    st.download_button("Download CSV", csv, "degree_days.csv", "text/csv")
