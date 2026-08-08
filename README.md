# NHPC Rainfall Monitoring System For Dam Catchment

An automated rainfall monitoring and risk assessment pipeline for NHPC hydroelectric dam catchments across India. The system fetches high-resolution 0.125° Numerical Weather Prediction (NWP) forecast data from the India Meteorological Department (IMD) Multi-Model Ensemble (MME/GFS), computes cumulative rainfall depth and runoff volume (in Million Cubic Meters - MCM) over catchment basins, persists historical model run data in MySQL, and builds an interactive GIS web dashboard (`Catchment_Rain_Dashboard.html`).

---

## 📌 Architecture & Data Flow

```
                        ┌──────────────────────────────────────────┐
                        │      IMD Mausamgram API Endpoint         │
                        │  (https://mausamgram.imd.gov.in/...)     │
                        └────────────────────┬─────────────────────┘
                                             │
                                             ▼
                        ┌──────────────────────────────────────────┐
                        │  imd_ping.py                             │
                        │  • Auto-discovers latest GFS/MME run     │
                        │  • Concurrent 3-hr APCP rainfall pings   │
                        └────────────────────┬─────────────────────┘
                                             │
                                             ▼
                        ┌──────────────────────────────────────────┐
                        │  map.py                                  │
                        │  • Spatial Join (0.125° grid ∩ catchments)│
                        │  • Cumulative Depth (3h, 6h, 12h, 24h)   │
                        │  • Runoff Volume (MCM) Calculation       │
                        │  • Risk Level Categorization             │
                        └──────────┬────────────────────┬──────────┘
                                   │                    │
                                   ▼                    ▼
   ┌──────────────────────────────────┐      ┌──────────────────────────────────┐
   │  db.py                           │      │  ui/ (Folium UI Components)      │
   │  • MySQL `catchment_rainfall` DB │      │  • Custom Catchment Popups       │
   │  • Local File Cache (`cache/`)   │      │  • Grid Cell Popups & Details    │
   └──────────────────────────────────┘      │  • Quick Zoom & Navigation       │
                                             └──────────────────┬───────────────┘
                                                                │
                                                                ▼
                                             ┌──────────────────────────────────┐
                                             │ Catchment_Rain_Dashboard.html    │
                                             │ (Interactive Folium Web Map)     │
                                             └──────────────────────────────────┘
```

---

## ✨ Key Features

1. **Dynamic IMD Model Run Discovery**: Bypasses stagnant text files by dynamically scanning candidates (00 UTC / 12 UTC runs over the past 3 days) against benchmark Indian coordinates to detect freshly published model datasets.
2. **Parallel Async Data Extraction**: Uses `ThreadPoolExecutor` and optimized `requests.Session` connections to rapidly fetch grid point time-series forecasts across hundreds of 0.125° spatial grid cells.
3. **Geospatial & Volumetric Analysis**:
   - Performs spatial overlay of 0.125° grid polygons against catchment shapefiles (`catchments.gpkg`).
   - Calculates 3-hour, 6-hour, 12-hour, and 24-hour cumulative rainfall.
   - Computes catchment volume forecasts in Million Cubic Meters ($\text{MCM} = \frac{\text{Rainfall (mm)} \times \text{Area (m}^2\text{)}}{10^6 \times 10^3}$).
4. **Interactive Dashboard**:
   - Color-coded grid cells using standard IMD precipitation intensity scales.
   - Catchment boundary layer with risk indicators (🟢 Low, 🟡 Moderate, 🟠 High, 🔴 Extreme).
   - Marker cluster pinpoints for NHPC dam project coordinates.
   - Sidebar UI for quick catchment zoom, search filters, and metric summaries.
5. **Database Sync & Intelligent Caching**:
   - Stores summary records per model run into MySQL (`rainfall_db.catchment_rainfall`).
   - Maintains local cache files (`cache/last_saved_model.txt`) to avoid redundant database writes or duplicate API requests.
6. **Automated Scheduler**:
   - Includes `run_scheduler.py` to poll IMD for updated weather model runs hourly and re-render the dashboard automatically when new data is detected.

---

## 📁 Repository Structure

```
NHPC_project/
│
├── map.py                        # Main execution script; handles spatial overlay, risk computation, map rendering, and DB saves
├── imd_ping.py                   # IMD API client module; discovers model runs and fetches 3-hr APCP forecast series
├── db.py                         # MySQL persistence layer with local cache checking logic
├── config.py                     # Configuration file storing MySQL connection credentials
├── run_scheduler.py              # Automation daemon; checks IMD hourly and runs pipeline on new model updates
├── requirements.txt              # List of Python dependencies
├── README.md                     # Project documentation
│
├── data/                         # Geospatial datasets & project coordinates
│   ├── catchments.gpkg           # GeoPackage polygon layer of dam catchment boundaries
│   ├── final_grid.gpkg           # GeoPackage layer containing 0.125° spatial grid cells
│   ├── India_Outline.gpkg        # GeoPackage layer of India country/state outline
│   └── project_dam_coordinates.csv # CSV containing dam names and lat/lon coordinates
│
├── database/                     # Database schemas and scripts
│   └── schema+database.sql       # Database schema & sample data dump for `rainfall_db`
│
├── ui/                           # Custom Folium HTML/JS UI extensions
│   ├── catchment_popup.py        # Generates detailed HTML popups for catchment polygon features
│   ├── catchment_zoom.py         # JavaScript & HTML overlay for quick zoom navigation buttons
│   └── grid_popup.py             # HTML popup renderer for individual 0.125° grid cells
│
├── Catchment_Rain_Dashboard.html # Generated output file (Interactive HTML web map dashboard)
│
└── cache/                        # Local runtime cache folder (auto-created)
    ├── last_model.txt            # Cache file storing latest detected IMD model ID
    └── last_saved_model.txt      # Cache file storing last model run saved to MySQL
```

---

## 🛠️ Setup & Installation

### 1. Prerequisites
- **Python 3.9+** installed on your system.
- **MySQL Server 8.0+** (or MariaDB) running locally or remotely.

### 2. Environment Setup
Clone or navigate to the project workspace and create a Python virtual environment:

```bash
# Create a virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate on Linux/macOS
source venv/bin/activate
```

Install the required packages:

```bash
pip install -r requirements.txt
```

> **Note**: Core geospatial libraries used include `geopandas`, `folium`, `shapely`, `pandas`, `requests`, and `mysql-connector-python`.

### 3. Database Configuration

1. Import the SQL schema to create the `rainfall_db` database and `catchment_rainfall` table:
   ```bash
   mysql -u root -p < schema+database.sql
   ```
2. Update database credentials in `config.py`:
   ```python
   # config.py
   DB_HOST = "localhost"
   DB_PORT = 3306
   DB_USER = "root"
   DB_PASSWORD = "your_mysql_password"
   DB_NAME = "rainfall_db"
   ```

---

## 🚀 Running the Project

### Option A: Manual Single Execution
To trigger a manual run that fetches current IMD forecasts, updates MySQL, and generates `Catchment_Rain_Dashboard.html`:

```bash
python map.py
```

### Option B: Automated Hourly Scheduler
To keep the dashboard updated 24/7 without manual intervention:

```bash
python run_scheduler.py
```
*The scheduler checks `mausamgram.imd.gov.in` every hour for new model runs (e.g. `2026080300`, `2026080312`). When a new run is detected, it automatically executes the processing pipeline.*

### Option C: Test IMD Forecast Ping for Specific Coordinates
To inspect raw JSON output and rainfall summaries for a specific Latitude/Longitude:

```bash
python imd_ping.py 28.5 77.5
```

---

## 🎨 Risk & Precipitation Classification

### Grid Cell Rainfall Scale (`color_for_rainfall`)
| Rainfall Depth (mm) | Intensity Level | Hex Color | Visual Indicator |
| :--- | :--- | :--- | :--- |
| `< 0.1` | No Rain | `#FFFFFF` | White |
| `0.1 - 2.5` | Very Light | `#444A4D` | Light Gray |
| `2.5 - 15.5` | Light Rain | `#4FC3F7` | Sky Blue |
| `15.5 - 64.4` | Moderate | `#45F162` | Dark Green |
| `64.4 - 115.5` | Heavy | `#FAF609` | Yellow |
| `115.5 - 204.4` | Very Heavy | `#F57C00` | Orange |
| `>= 204.4` | Extremely Heavy | `#D32F2F` | Red |

### Catchment Alert Levels (`catchment_alert`)
- 🟢 **Low Risk**: Catchment risk score < 15
- 🟡 **Moderate Risk**: Catchment risk score 15 - 40
- 🟠 **High Risk**: Catchment risk score 40 - 80
- 🔴 **Extreme Risk**: Catchment risk score >= 80

---

## 💡 Developer Guidelines & Troubleshooting

- **Adding New Catchments**: Update `catchments.gpkg` with new catchment boundary geometries and ensure names align with your reporting standards.
- **Adding New Dam Coordinates**: Add a row to `project_dam_coordinates.csv` with columns `Project`, `Latitude`, `Longitude`, `Status`.
- **UI Customizations**: Modify scripts inside `ui/` (`catchment_popup.py`, `grid_popup.py`, `catchment_zoom.py`) to adjust popup styles, HTML structure, or JS interaction callbacks.
- **Cache Invalidation**: If you need to force a database re-insertion for an existing model run, delete the `cache/` folder or modify `cache/last_saved_model.txt`.
