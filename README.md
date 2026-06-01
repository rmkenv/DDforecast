# Degree Day Forecasting Platform

16-day HDD / CDD forecast with 30-year anomaly detection, powered by [Open-Meteo](https://open-meteo.com/).  
No API key required. Free forever.

## Repo structure

```
degree-day-forecast/
├── etl.py                  # fetch + compute + write data/
├── app.py                  # Streamlit dashboard
├── utils/
│   └── degree_days.py      # HDD/CDD/normals/anomaly functions
├── data/                   # flat JSON, committed by GHA
│   ├── index.json
│   └── cumberland-md.json  # one file per location
├── .github/workflows/
│   └── nightly.yml         # 08:00 UTC daily ETL
└── requirements.txt
```

## Quickstart

```bash
git clone https://github.com/yourorg/degree-day-forecast
cd degree-day-forecast
pip install -r requirements.txt

# run ETL once to populate data/
python etl.py

# launch dashboard
streamlit run app.py
```

## Adding locations

Edit `LOCATIONS` in `etl.py`:

```python
LOCATIONS = [
    {"id": "my-city",  "name": "My City, ST",  "lat": 40.00, "lon": -75.00},
    ...
]
```

Each location gets its own `data/<id>.json` file.

## Changing the base temperature

```python
BASE_TEMP_F = 65    # standard energy base — change to 60 or 50 as needed
```

## GitHub Actions

The workflow in `.github/workflows/nightly.yml` runs every day at 08:00 UTC,
calls `etl.py`, and commits updated JSON back to the repo. The Streamlit app
deployed on Community Cloud will pick up the new files on next load.

## Deploy to Streamlit Community Cloud

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io) → New app
3. Select `app.py` as the entrypoint
4. Done — no secrets needed, Open-Meteo is fully public

## Data outputs

`data/index.json` — summary of all locations (no daily arrays):
```json
{
  "fetched_at": "2025-06-01",
  "base_temp": 65,
  "locations": [
    {
      "id": "cumberland-md",
      "name": "Cumberland, MD",
      "summary": {
        "total_hdd_16d": 142.3,
        "hdd_vs_normal": 18.1,
        ...
      }
    }
  ]
}
```

`data/<id>.json` — full daily arrays + normals + anomaly for one location.

## License

MIT
