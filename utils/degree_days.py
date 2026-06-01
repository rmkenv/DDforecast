"""
utils/degree_days.py
Pure functions for HDD / CDD computation, 30-year normals, and anomaly scoring.
All temperatures in °F by default (pass base_temp in the same units as your data).
"""

from __future__ import annotations
from typing import Any


# ── daily degree days ─────────────────────────────────────────────────────────

def compute_degree_days(daily: dict[str, list], base_temp: float) -> list[dict]:
    """
    Given Open-Meteo daily dict with temperature_2m_max / temperature_2m_min,
    return a list of dicts with HDD, CDD, and mean temp per day.
    """
    times = daily["time"]
    tmax  = daily["temperature_2m_max"]
    tmin  = daily["temperature_2m_min"]

    rows = []
    for i, date in enumerate(times):
        mean = (tmax[i] + tmin[i]) / 2
        hdd  = max(0.0, base_temp - mean)
        cdd  = max(0.0, mean - base_temp)
        rows.append({
            "date":  date,
            "tmax":  round(tmax[i], 1),
            "tmin":  round(tmin[i], 1),
            "mean":  round(mean,    1),
            "hdd":   round(hdd,     2),
            "cdd":   round(cdd,     2),
        })
    return rows


# ── 30-year normals ───────────────────────────────────────────────────────────

def compute_normals(
    archive_daily: dict[str, list],
    base_temp: float,
) -> dict[str, dict]:
    """
    Build day-of-year normals (keyed MM-DD) from 30 years of archive data.
    Returns mean HDD, mean CDD, and std-dev for each calendar day.
    """
    times = archive_daily["time"]
    tmax  = archive_daily["temperature_2m_max"]
    tmin  = archive_daily["temperature_2m_min"]

    by_doy: dict[str, dict[str, list]] = {}
    for i, date in enumerate(times):
        doy = date[5:]          # "MM-DD"
        if doy not in by_doy:
            by_doy[doy] = {"hdd": [], "cdd": []}
        mean = (tmax[i] + tmin[i]) / 2
        by_doy[doy]["hdd"].append(max(0.0, base_temp - mean))
        by_doy[doy]["cdd"].append(max(0.0, mean - base_temp))

    normals = {}
    for doy, vals in by_doy.items():
        normals[doy] = {
            "hdd_mean": round(_mean(vals["hdd"]), 2),
            "hdd_sd":   round(_sd(vals["hdd"]),   2),
            "cdd_mean": round(_mean(vals["cdd"]), 2),
            "cdd_sd":   round(_sd(vals["cdd"]),   2),
            "n_years":  len(vals["hdd"]),
        }
    return normals


# ── anomaly ───────────────────────────────────────────────────────────────────

def compute_anomaly(
    daily: list[dict],
    normals: dict[str, dict],
) -> dict[str, Any]:
    """
    Compare forecast daily HDD/CDD against 30-year normals.
    Returns per-day anomalies and cumulative deltas.
    """
    per_day = []
    cum_hdd_forecast = 0.0
    cum_hdd_normal   = 0.0
    cum_cdd_forecast = 0.0
    cum_cdd_normal   = 0.0

    for d in daily:
        doy = d["date"][5:]
        norm = normals.get(doy, {"hdd_mean": 0, "cdd_mean": 0, "hdd_sd": 0, "cdd_sd": 0})

        hdd_delta = d["hdd"] - norm["hdd_mean"]
        cdd_delta = d["cdd"] - norm["cdd_mean"]
        cum_hdd_forecast += d["hdd"]
        cum_hdd_normal   += norm["hdd_mean"]
        cum_cdd_forecast += d["cdd"]
        cum_cdd_normal   += norm["cdd_mean"]

        # z-score: how many std-devs from normal
        hdd_z = (hdd_delta / norm["hdd_sd"]) if norm["hdd_sd"] > 0 else 0.0
        cdd_z = (cdd_delta / norm["cdd_sd"]) if norm["cdd_sd"] > 0 else 0.0

        per_day.append({
            "date":       d["date"],
            "hdd_delta":  round(hdd_delta, 2),
            "cdd_delta":  round(cdd_delta, 2),
            "hdd_z":      round(hdd_z,     2),
            "cdd_z":      round(cdd_z,     2),
        })

    return {
        "per_day":              per_day,
        "hdd_delta_cumulative": round(cum_hdd_forecast - cum_hdd_normal, 1),
        "cdd_delta_cumulative": round(cum_cdd_forecast - cum_cdd_normal, 1),
    }


# ── statistics helpers ────────────────────────────────────────────────────────

def _mean(arr: list[float]) -> float:
    return sum(arr) / len(arr) if arr else 0.0

def _sd(arr: list[float]) -> float:
    if len(arr) < 2:
        return 0.0
    m = _mean(arr)
    variance = sum((x - m) ** 2 for x in arr) / len(arr)
    return variance ** 0.5
