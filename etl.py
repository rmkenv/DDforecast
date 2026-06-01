"""
degree-day-forecast / etl.py
Fetches Open-Meteo forecast + 30-year archive for a set of locations,
computes HDD / CDD, writes flat JSON to data/.
Run locally or via GitHub Actions.
"""

import json
import os
import requests
from datetime import date, timedelta
from pathlib import Path
from utils.degree_days import compute_degree_days, compute_normals, compute_anomaly

# ── configuration ────────────────────────────────────────────────────────────

BASE_TEMP_F = 65          # standard energy base
FORECAST_DAYS = 16
HIST_YEARS = 30
DATA_DIR = Path("data")

LOCATIONS = [
    {"id": "cumberland-md",   "name": "Cumberland, MD",      "lat": 39.65,  "lon": -78.83},
    {"id": "baltimore-md",    "name": "Baltimore, MD",        "lat": 39.29,  "lon": -76.61},
    {"id": "washington-dc",   "name": "Washington, DC",       "lat": 38.91,  "lon": -77.04},
    {"id": "pittsburgh-pa",   "name": "Pittsburgh, PA",       "lat": 40.44,  "lon": -79.99},
    {"id": "richmond-va",     "name": "Richmond, VA",         "lat": 37.54,  "lon": -77.44},
]

# ── helpers ───────────────────────────────────────────────────────────────────

def hist_start() -> str:
    return (date.today() - timedelta(days=365 * HIST_YEARS)).isoformat()

def yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()

def fetch_forecast(lat: float, lon: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "forecast_days": FORECAST_DAYS,
        "timezone": "auto",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def fetch_archive(lat: float, lon: float) -> dict:
    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": hist_start(),
        "end_date": yesterday(),
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "timezone": "auto",
    }
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()
    return r.json()

# ── main ──────────────────────────────────────────────────────────────────────

def process_location(loc: dict) -> dict:
    print(f"  → {loc['name']}")

    forecast_raw = fetch_forecast(loc["lat"], loc["lon"])
    archive_raw  = fetch_archive(loc["lat"], loc["lon"])

    daily    = compute_degree_days(forecast_raw["daily"], BASE_TEMP_F)
    normals  = compute_normals(archive_raw["daily"], BASE_TEMP_F)
    anomaly  = compute_anomaly(daily, normals)

    return {
        "id":         loc["id"],
        "name":       loc["name"],
        "lat":        loc["lat"],
        "lon":        loc["lon"],
        "base_temp":  BASE_TEMP_F,
        "units":      "fahrenheit",
        "fetched_at": date.today().isoformat(),
        "daily":      daily,
        "normals":    normals,
        "anomaly":    anomaly,
        "summary": {
            "total_hdd_16d":  round(sum(d["hdd"] for d in daily), 1),
            "total_cdd_16d":  round(sum(d["cdd"] for d in daily), 1),
            "hdd_vs_normal":  round(anomaly["hdd_delta_cumulative"], 1),
            "cdd_vs_normal":  round(anomaly["cdd_delta_cumulative"], 1),
            "peak_hdd":       round(max(d["hdd"] for d in daily), 1),
            "peak_hdd_date":  max(daily, key=lambda d: d["hdd"])["date"],
            "peak_cdd":       round(max(d["cdd"] for d in daily), 1),
            "peak_cdd_date":  max(daily, key=lambda d: d["cdd"])["date"],
        },
    }

def run():
    DATA_DIR.mkdir(exist_ok=True)
    all_locations = []

    for loc in LOCATIONS:
        try:
            result = process_location(loc)
            # per-location file
            out_path = DATA_DIR / f"{loc['id']}.json"
            out_path.write_text(json.dumps(result, indent=2))
            all_locations.append(result)
        except Exception as e:
            print(f"  ✗ failed {loc['name']}: {e}")

    # combined index
    index = {
        "fetched_at": date.today().isoformat(),
        "base_temp":  BASE_TEMP_F,
        "locations":  [
            {k: v for k, v in loc.items() if k not in ("daily", "normals")}
            for loc in all_locations
        ],
    }
    (DATA_DIR / "index.json").write_text(json.dumps(index, indent=2))
    print(f"\n✓ Wrote {len(all_locations)} locations to data/")

if __name__ == "__main__":
    print(f"Fetching degree day data — base {BASE_TEMP_F}°F\n")
    run()
