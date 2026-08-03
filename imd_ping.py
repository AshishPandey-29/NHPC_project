import sys
import json
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)

MODEL_FILE = CACHE_DIR / "last_model.txt"
FORECAST_FILE = CACHE_DIR / "forecast_cache.json"

BASE = "https://mausamgram.imd.gov.in"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "Accept": "*/*",
    "Referer": BASE
}


def snap_grid(value):
    grid = 0.125
    return round(round(float(value) / grid) * grid, 3)


def get_model(session=None):
    url = f"{BASE}/mmem_3hr.txt"
    requester = session if session else requests
    
    for attempt in range(3):
        try:
            r = requester.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            return r.text.split(",")[0].strip()
        except Exception as e:
            if attempt == 2:
                raise e
            time.sleep(0.5)


def discover_latest_model(session=None):
    """
    Dynamically finds the latest available GFS/MME model run date
    by testing candidate timestamps against a known Indian coordinate.
    Bypasses sluggish/outdated mmem_3hr.txt updates on the server.
    """
    requester = session if session else requests
    text_model = None
    try:
        text_model = get_model(session=requester)
    except Exception:
        pass

    now_utc = datetime.now(timezone.utc)
    candidates = []
    # Generate 00 and 12 runs for the last 3 days
    for days_back in range(4):
        dt = now_utc - timedelta(days=days_back)
        date_str = dt.strftime("%Y%m%d")
        candidates.append(f"{date_str}12")
        candidates.append(f"{date_str}00")

    if text_model and text_model not in candidates:
        candidates.append(text_model)

    # Test coordinate (Delhi)
    test_lat, test_lon = 28.5, 77.5
    for candidate in candidates:
        url = (
            f"{BASE}/test4_mme.php"
            f"?lat_gfs={test_lat}"
            f"&lon_gfs={test_lon}"
            f"&date={candidate}_3hr_0p125"
        )
        try:
            r = requester.get(url, headers=HEADERS, timeout=5)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict) and "apcp" in data:
                    # Save latest model run date
                    try:
                        MODEL_FILE.write_text(candidate)
                    except Exception:
                        pass
                    return candidate
        except Exception:
            pass

    # Use cached model run if network check fails
    if MODEL_FILE.exists():
        try:
            return MODEL_FILE.read_text().strip()
        except Exception:
            pass

    return text_model if text_model else "2026072100"


def parse_rain_val(val):
    if val is None or val == "NaN":
        return 0.0
    try:
        v = float(val)
        return v if v >= 0 else 0.0
    except (ValueError, TypeError):
        return 0.0


def extract_rainfall_summary(forecast_data):
    """
    Extracts 24h total rainfall, next 12h rainfall, next 6h rainfall, next 3h rainfall, and max 3h spike from forecast data.
    """
    if not isinstance(forecast_data, dict) or "apcp" not in forecast_data:
        return {
            "rain_3h": None,
            "rain_6h": None,
            "rain_12h": None,
            "rain_24h": None,
            "max_3h": None,
            "status": "error"
        }
    
    apcp_list = forecast_data.get("apcp", [])
    valid_apcp = [parse_rain_val(v) for v in apcp_list[1:]]  # Index 0 is often 'NaN' header
    
    if not valid_apcp:
        return {
            "rain_3h": 0.0,
            "rain_6h": 0.0,
            "rain_12h": 0.0,
            "rain_24h": 0.0,
            "max_3h": 0.0,
            "status": "empty"
        }
        
    rain_3h = valid_apcp[0] if len(valid_apcp) > 0 else 0.0
    rain_6h = sum(valid_apcp[:2])
    rain_12h = sum(valid_apcp[:4])
    rain_24h = sum(valid_apcp[:8])  # First 8 periods (8 * 3 = 24 hours)
    max_3h = max(valid_apcp[:8]) if len(valid_apcp) >= 8 else max(valid_apcp)
    rain_2nd_day_6hr= sum(valid_apcp[8:10])
    rain_2nd_day_12hr= sum(valid_apcp[8:12])
    rain_2nd_day_24hr= sum(valid_apcp[8:16])
    return {
        "rain_3h": round(rain_3h, 2),
        "rain_6h": round(rain_6h, 2),
        "rain_12h": round(rain_12h, 2),
        "rain_24h": round(rain_24h, 2),
        "max_3h": round(max_3h, 2),
        "rain_2nd_day_6hr": round(rain_2nd_day_6hr, 2),
        "rain_2nd_day_12hr": round(rain_2nd_day_12hr, 2),
        "rain_2nd_day_24hr": round(rain_2nd_day_24hr, 2),
        "status": "ok"
    }


def get_forecast(lat, lon, session=None, retries=3, model=None):
    lat_gfs = snap_grid(lat)
    lon_gfs = snap_grid(lon)
    requester = session if session else requests

    if not model:
        model = discover_latest_model(session=requester)

    url = (
        f"{BASE}/test4_mme.php"
        f"?lat_gfs={lat_gfs}"
        f"&lon_gfs={lon_gfs}"
        f"&date={model}_3hr_0p125"
    )

    data = None
    for attempt in range(retries):
        try:
            r = requester.get(url, headers=HEADERS, timeout=8)
            data = r.json()
            break
        except Exception:
            if attempt == retries - 1:
                data = None
            time.sleep(0.3)

    summary = extract_rainfall_summary(data)

    result = {
        "original": {"lat": lat, "lon": lon},
        "gfs_grid": {"lat": lat_gfs, "lon": lon_gfs},
        "model": model,
        "forecast": data,
        "summary": summary
    }

    # Optionally cache the last successful forecast point for debugging
    if data is not None:
        try:
            with open(FORECAST_FILE, "w") as f:
                json.dump(result, f, indent=4)
        except Exception:
            pass

    return result


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: python imd_ping.py LAT LON")
        sys.exit(1)

    result = get_forecast(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=4))
