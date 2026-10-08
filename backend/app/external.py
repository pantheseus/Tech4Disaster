"""Free public data sources - no API key needed."""
import requests

TIMEOUT = 12


def earthquakes(min_magnitude: float = 4.5, limit: int = 20) -> list:
    """Recent worldwide earthquakes from USGS (last 7 days)."""
    url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
    data = requests.get(url, timeout=TIMEOUT).json()
    out = []
    for f in data.get("features", []):
        mag = f["properties"].get("mag") or 0
        if mag >= min_magnitude:
            lng, lat, depth = f["geometry"]["coordinates"]
            out.append({"place": f["properties"].get("place"), "magnitude": mag,
                        "lat": lat, "lng": lng, "depth_km": depth, "time": f["properties"].get("time")})
    return out[:limit]


def weather(lat: float, lng: float) -> dict:
    """Current weather + 3-day rain forecast from Open-Meteo."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat, "longitude": lng,
        "current": "temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m",
        "daily": "precipitation_sum,precipitation_probability_max,wind_speed_10m_max",
        "forecast_days": 3, "timezone": "auto",
    }
    data = requests.get(url, params=params, timeout=TIMEOUT).json()
    daily = data.get("daily", {})
    rain = daily.get("precipitation_sum", [0])
    total = sum(x or 0 for x in rain)
    risk = "HIGH" if total > 100 else "MEDIUM" if total > 40 else "LOW"
    return {"current": data.get("current", {}), "daily": daily,
            "flood_risk": risk, "rain_3day_mm": round(total, 1)}
