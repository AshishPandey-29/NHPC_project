import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import folium
import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon
import requests
from db import save_to_mysql
import traceback
from ui.catchment_popup import add_catchment_popup
from ui.catchment_zoom import add_catchment_zoom
from ui.grid_popup import add_grid_popup

from imd_ping import get_forecast, snap_grid, discover_latest_model

def get_risk(rain24):

    if rain24 < 10:
        return "🟢 Low", "#2E7D32"

    elif rain24 < 30:
        return "🟡 Moderate", "#F9A825"

    elif rain24 < 60:
        return "🟠 High", "#EF6C00"

    else:
        return "🔴 Extreme", "#C62828"

def catchment_alert(val):
    if val is None or pd.isna(val):
        return '<span style="color:#070101; font-size:22px;">●</span> No Data'

    if val < 0.1:
        return '<span style="color:#FFFFFF; font-size:22px;">●</span> No Rain'

    elif val < 2.5:
        return '<span style="color:#444A4D; font-size:22px;">●</span> Very Light'

    elif val < 15.5:
        return '<span style="color:#4FC3F7; font-size:22px;">●</span> Light'

    elif val < 64.4:
        return '<span style="color:#45F162; font-size:22px;">●</span> Moderate'

    elif val < 115.5:
        return '<span style="color:#FAF609; font-size:22px;">●</span> Heavy'

    elif val < 204.4:
        return '<span style="color:#F57C00; font-size:22px;">●</span> Very Heavy'

    else:
        return '<span style="color:#D32F2F; font-size:22px;">●</span> Extremely Heavy'

def color_for_rainfall(val):
    if val is None or pd.isna(val):
        return "#070101FF"  # BLACK (No data / Failed)
    if val < 0.1:
        return "#FFFFFF"  # White (No Rain)
    elif val < 2.5:
        return "#444A4D"  # LIGHT GRAY(VERY LIGHT RAIN)
    elif val < 15.5:
        return "#4FC3F7"  # Sky Blue(LIGHT RAIN)
    elif val < 64:
        return "#45F162"  # Dark GREEN(Moderate)
    elif val < 115.5:
        return "#FAF609"  # YELLOW (Heavy)
    elif val < 204.4:
        return "#F57C00"  # ORANGE (very heavy)
    else:
        return "#D32F2F"  # RED (extremely heavy)

def generate_map():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting map generation pipeline...")
    
    print("1. Loading GeoPackage layers...")
    catchment = gpd.read_file("data/catchments.gpkg")
    outline = gpd.read_file("data/India_Outline.gpkg", layer="single_parts")
    data = pd.read_csv("data/project_dam_coordinates.csv")
    dams=pd.DataFrame(data)

    # Reproject to metric CRS to calculate centroids without geographic CRS warnings
    catchment_metric = catchment.to_crs("EPSG:3857")
    center_pt = catchment_metric.geometry.centroid.to_crs("EPSG:4326").iloc[0]
    center_lat, center_lon = center_pt.y, center_pt.x

    print("2. Generating 0.125° grid over catchments...")
    
    grid = gpd.read_file(r"data/final_grid.gpkg")

    # Compute centroids for querying IMD
    grid_metric = grid.to_crs("EPSG:3857")
    grid_centroids = grid_metric.geometry.centroid.to_crs("EPSG:4326")
    grid["lat"] = grid_centroids.y
    grid["lon"] = grid_centroids.x

    # Snap to IMD GFS grid
    grid["lat_gfs"] = grid["lat"].apply(snap_grid)
    grid["lon_gfs"] = grid["lon"].apply(snap_grid)

    unique_coords = grid[["lat_gfs", "lon_gfs"]].drop_duplicates().to_dict("records")
    print(f"Total grid cells: {len(grid)} | Unique GFS grid points: {len(unique_coords)}")

    print("3. Checking latest available model run...")
    # Use a clean session to discover the latest model run
    temp_session = requests.Session()
    latest_model = discover_latest_model(session=temp_session)
    print(f"Active IMD model run: {latest_model}")

    print("4. Fetching IMD rainfall forecast data...")
    cache = {}
    
    # Shared session with optimized connection pool for threads
    shared_session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
    shared_session.mount("https://", adapter)
    shared_session.mount("http://", adapter)

    def fetch_unique(point):
        lat, lon = point["lat_gfs"], point["lon_gfs"]
        try:
            res = get_forecast(lat, lon, session=shared_session, model=latest_model)
            summary = res.get("summary", {})
            return (lat, lon), summary
        except Exception:
            return (lat, lon), {"rain_24h": 0.0, "rain_3h": 0.0, "max_3h": 0.0, "status": "error"}

    start_t = time.time()
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_unique, pt) for pt in unique_coords]
        for f in as_completed(futures):
            key, summary = f.result()
            cache[key] = summary

    print(f"Data fetched in {round(time.time() - start_t, 2)} seconds.")

    # Assign forecast values to grid cells
    grid["rain_24h"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("rain_24h", 0.0), axis=1)
    grid["rain_3h"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("rain_3h", 0.0), axis=1)
    grid["rain_6h"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("rain_6h", 0.0), axis=1)
    grid["rain_12h"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("rain_12h", 0.0), axis=1)
    grid["rain_2nd_day_6hr"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("rain_2nd_day_6hr", 0.0), axis=1)
    grid["rain_2nd_day_12hr"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("rain_2nd_day_12hr", 0.0), axis=1)
    grid["rain_2nd_day_24hr"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("rain_2nd_day_24hr", 0.0), axis=1)
    grid["max_3h"] = grid.apply(lambda r: cache.get((r["lat_gfs"], r["lon_gfs"]), {}).get("max_3h", 0.0), axis=1)

    # Rainfall Volume (Million Cubic Metres)
    
    grid["vol_3h"] = (grid["rain_3h"] / 1000 * grid["area_m2"]) / 1_000_000
    grid["vol_6h"] = (grid["rain_6h"] / 1000 * grid["area_m2"]) / 1_000_000
    grid["vol_12h"] = (grid["rain_12h"] / 1000 * grid["area_m2"]) / 1_000_000
    grid["vol_24h"] = (grid["rain_24h"] / 1000 * grid["area_m2"]) / 1_000_000
    grid["vol_2nd_day_6hr"] = (grid["rain_2nd_day_6hr"] / 1000 * grid["area_m2"]) / 1_000_000
    grid["vol_2nd_day_12hr"] = (grid["rain_2nd_day_12hr"] / 1000 * grid["area_m2"]) / 1_000_000
    grid["vol_2nd_day_24hr"] = (grid["rain_2nd_day_24hr"] / 1000 * grid["area_m2"]) / 1_000_000

    grid["risk"], grid["risk_color"] = zip(
    *grid["rain_24h"].apply(get_risk)
    )

    #Creating CATCHMENT RAIN SUMMARY
    catchment_summary = (
    grid.groupby("catchment", dropna=False)
        .agg(
            volume_3h_mcm=("vol_3h", "sum"),
            volume_6h_mcm=("vol_6h", "sum"),
            volume_12h_mcm=("vol_12h", "sum"),
            volume_24h_mcm=("vol_24h", "sum"),
            volume_2nd_day_6hr_mcm=("vol_2nd_day_6hr", "sum"),
            volume_2nd_day_12hr_mcm=("vol_2nd_day_12hr", "sum"),
            volume_2nd_day_24hr_mcm=("vol_2nd_day_24hr", "sum")
        )
        .reset_index()
    )
    catchment_summary = catchment_summary.sort_values(
    by="volume_24h_mcm",
    ascending=False
    )

    catchment_alert_summary = (
    grid.groupby("catchment", dropna=False)
        .agg(
            avg_rain_3h=("rain_3h", "mean"),
            avg_rain_6h=("rain_6h", "mean"),
            avg_rain_12h=("rain_12h", "mean"),
            avg_rain_24h=("rain_24h", "mean"),
            avg_rain_2nd_day_6hr=("rain_2nd_day_6hr", "mean"),
            avg_rain_2nd_day_12hr=("rain_2nd_day_12hr", "mean"),
            avg_rain_2nd_day_24hr=("rain_2nd_day_24hr", "mean"),

            max_rain_3h=("rain_3h", "max"),
            max_rain_6h=("rain_6h", "max"),
            max_rain_12h=("rain_12h", "max"),
            max_rain_24h=("rain_24h", "max"),
            max_rain_2nd_day_6hr=("rain_2nd_day_6hr", "max"),
            max_rain_2nd_day_12hr=("rain_2nd_day_12hr", "max"),
            max_rain_2nd_day_24hr=("rain_2nd_day_24hr", "max"),

            volume_3h_mcm=("vol_3h", "sum"),
            volume_6h_mcm=("vol_6h", "sum"),
            volume_12h_mcm=("vol_12h", "sum"),
            volume_24h_mcm=("vol_24h", "sum"),
            volume_2nd_day_6hr_mcm=("vol_2nd_day_6hr", "sum"),
            volume_2nd_day_12hr_mcm=("vol_2nd_day_12hr", "sum"),
            volume_2nd_day_24hr_mcm=("vol_2nd_day_24hr", "sum")
        )
        .reset_index()
    )

    catchment_alert_summary["alert"] = (
        catchment_alert_summary["avg_rain_24h"]
        .apply(catchment_alert)
    )
    catchment_alert_summary = catchment_alert_summary.sort_values(
        by="avg_rain_24h",
        ascending=False
    )

    # Connect To MySQL Database
    try:
        save_to_mysql(catchment_summary, latest_model)
    except Exception as e:
        print(f"Error saving to MySQL: {e}")
        traceback.print_exc()

    # Full height Left Side Alert & Summary Panel HTML with 2 Tabs
    alert_panel_html = """
    <style>
        .leaflet-left {
            left: 470px !important;
            transition: left 0.3s ease !important;
        }
        .leaflet-tooltip {
            font-size: 13px !important;
        }
        .leaflet-popup-content {
            font-size: 15px !important;
        }
        .leaflet-control-layers {
            font-size: 14px !important;
        }
        .alert-side-panel {
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            width: 460px !important;
            height: 100vh !important;
            background: rgba(255, 255, 255, 0.96) !important;
            border-right: 2px solid #666 !important;
            box-shadow: 4px 0 15px rgba(0, 0, 0, 0.3) !important;
            z-index: 999999 !important;
            font-family: Arial, sans-serif !important;
            display: flex !important;
            flex-direction: column !important;
            box-sizing: border-box !important;
        }
        .panel-tab-bar {
            display: flex !important;
            background: #e0e0e0 !important;
            border-bottom: 2px solid #ccc !important;
        }
        .panel-tab-btn {
            flex: 1 !important;
            padding: 12px 8px !important;
            background: none !important;
            border: none !important;
            border-bottom: 3px solid transparent !important;
            outline: none !important;
            cursor: pointer !important;
            font-size: 15px !important;
            font-weight: bold !important;
            color: #444 !important;
            transition: all 0.2s ease !important;
            text-align: center !important;
        }
        .panel-tab-btn.active {
            color: #0288D1 !important;
            border-bottom: 3px solid #0288D1 !important;
            background: #ffffff !important;
        }
        .panel-tab-btn:hover {
            background: #ededed !important;
        }
        .panel-tab-content {
            display: none !important;
            padding: 12px !important;
            overflow-y: auto !important;
            flex: 1 !important;
        }
        .panel-tab-content.active {
            display: block !important;
        }
        /* Priority / Catchment Alerts Tab */
        .priority-panel-container h4 {
            font-weight: 700 !important;
            font-size: 18px !important;
            color: #b71c1c !important;
            margin-top: 0 !important;
            margin-bottom: 12px !important;
        }
        .priority-table {
            width: 100% !important;
            border-collapse: collapse !important;
        }
        .priority-table td {
            padding: 8px 6px !important;
            border-bottom: 1px solid #ddd !important;
            cursor: pointer !important;
            font-size: 15px !important;
        }
        .priority-table tr:hover {
            background: #f5f5f5 !important;
        }
        /* Rainfall Volume Tab */
        .rainfall-table-container h4 {
            margin-top: 0 !important;
            margin-bottom: 10px !important;
            font-size: 17px !important;
            font-weight: bold !important;
        }
        .rainfall-table-wrapper {
            overflow-x: auto !important;
        }
        .rainfall-table {
            width: 100% !important;
            border-collapse: collapse !important;
            font-size: 14px !important;
        }
        .rainfall-table th {
            text-align: right !important;
            padding: 6px 4px !important;
            border-bottom: 2px solid #ddd !important;
            background: #f8f9fa !important;
            position: sticky !important;
            top: 0 !important;
            white-space: nowrap !important;
        }
        .rainfall-table th:first-child {
            text-align: left !important;
        }
        .rainfall-table td {
            text-align: right !important;
            padding: 6px 4px !important;
            border-bottom: 1px solid #eee !important;
            white-space: nowrap !important;
        }
        .rainfall-table td:first-child {
            text-align: left !important;
        }
    </style>

    <div class="alert-side-panel">
        <div class="panel-tab-bar">
            <button class="panel-tab-btn active" onclick="switchSideTab(event, 'tab-catchment-alerts')">catchment_alerts</button>
            <button class="panel-tab-btn" onclick="switchSideTab(event, 'tab-rainfall-volume')">Catchment Rainfall Volume (MCM)</button>
        </div>

        <!-- Tab 1: catchment_alerts -->
        <div id="tab-catchment-alerts" class="panel-tab-content priority-panel-container active">
            <h4>⚠ Catchments Requiring Attention (24hr based)</h4>
            <table class="priority-table">
    """
    for _, row in catchment_alert_summary.iterrows():
        alert_panel_html += f"""
                <tr onclick="focusCatchment('{row['catchment']}');
                             openCatchmentPopup('{row['catchment']}');">
                    <td style="font-weight:bold;">
                        {row['alert']} &nbsp; {row['catchment']}
                    </td>
                </tr>
        """

    alert_panel_html += """
            </table>
        </div>

        <!-- Tab 2: Catchment Rainfall Volume (MCM) -->
        <div id="tab-rainfall-volume" class="panel-tab-content rainfall-table-container">
            <h4 class="table-title">💧 Catchment Rainfall Volume (MCM)</h4>
            <div class="rainfall-table-wrapper">
                <table class="rainfall-table">
                    <thead>
                        <tr>
                            <th>Catchment</th>
                            <th>3hr</th>
                            <th>6hr</th>
                            <th>12hr</th>
                            <th>24hr</th>
                            <th>2nd Day 6hr</th>
                            <th>2nd Day 12hr</th>
                            <th>2nd Day 24hr</th>
                        </tr>
                    </thead>
                    <tbody>
    """
    for _, row in catchment_summary.iterrows():
        alert_panel_html += f"""
                        <tr>
                            <td>{row['catchment']}</td>
                            <td align="right">{row['volume_3h_mcm']:.2f}</td>
                            <td align="right">{row['volume_6h_mcm']:.2f}</td>
                            <td align="right">{row['volume_12h_mcm']:.2f}</td>
                            <td align="right">{row['volume_24h_mcm']:.2f}</td>
                            <td align="right">{row['volume_2nd_day_6hr_mcm']:.2f}</td>
                            <td align="right">{row['volume_2nd_day_12hr_mcm']:.2f}</td>
                            <td align="right">{row['volume_2nd_day_24hr_mcm']:.2f}</td>
                        </tr>
        """

    alert_panel_html += """
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
    function switchSideTab(evt, tabId) {
        var i, tabcontent, tablinks;
        tabcontent = document.getElementsByClassName("panel-tab-content");
        for (i = 0; i < tabcontent.length; i++) {
            tabcontent[i].style.display = "none";
            tabcontent[i].classList.remove("active");
        }
        tablinks = document.getElementsByClassName("panel-tab-btn");
        for (i = 0; i < tablinks.length; i++) {
            tablinks[i].classList.remove("active");
        }
        var targetTab = document.getElementById(tabId);
        if (targetTab) {
            targetTab.style.display = "block";
            targetTab.classList.add("active");
        }
        evt.currentTarget.classList.add("active");
    }
    </script>
    """
    print("5. Building interactive map...")
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=7,
        tiles="OpenStreetMap",
        prefer_canvas=True
    )

    # Base layers
    folium.TileLayer("CartoDB positron", name="CartoDB Light").add_to(m)
    folium.TileLayer("Esri.WorldImagery", name="Satellite (Esri)").add_to(m)

    # India Boundary
    folium.GeoJson(
        outline,
        name="India Boundary",
        style_function=lambda f: {
            "color": "#D32F2F",
            "weight": 2,
            "fillOpacity": 0
        }
    ).add_to(m)

    # Catchment Boundary
    folium.GeoJson(
        catchment,
        name="Catchments",
        style_function=lambda f: {
            "color": "#0288D1",
            "weight": 2,
            "fillColor": "#0288D1",
            "fillOpacity": 0.05
        }
    ).add_to(m)

    # Rainfall Grid Layer
    grid_layer = folium.GeoJson(
        grid,
        name="Rainfall Forecast (24h Total)",
        style_function=lambda feature: {
            "fillColor": color_for_rainfall(feature["properties"]["rain_24h"]),
            "color": "#444444",
            "weight": 0.4,
            "fillOpacity": 0.75
        },
        highlight_function=lambda feature: {
            "weight": 2,
            "color": "#000000",
            "fillOpacity": 0.9
        },
        tooltip=folium.GeoJsonTooltip(
            fields=[
                "rain_24h","catchment","rain_3h",
                "max_3h","lat_gfs","lon_gfs","area_km2"
            ],
            aliases=[
                "24h Total Rain (mm):",
                "Catchment:",
                "Next 3h Rain (mm):",
                "Peak 3h Rain (mm):",
                "Grid Lat:",
                "Grid Lon:",
                "Area(km²):"
            ],
            sticky=True,
            localize=True
        ),
    )    
    grid_layer.add_to(m)

    add_grid_popup(m, grid_layer)
    add_catchment_zoom(m, grid_layer)

    # Add full-height side panel with tabs to the map
    from branca.element import Element
    m.get_root().html.add_child(folium.Element(alert_panel_html))
    
    # Dam Layer
    dam_group = folium.FeatureGroup(name="NHPC Dams")
    for _, dam in dams.iterrows():
        coords = [dam["lat"], dam["lng"]]
        dam_name = dam["project_name"]
        folium.Marker(
            location=coords,
            popup=folium.Popup(f"<b>{dam_name}</b><br>Lat: {coords[0]:.4f}, Lon: {coords[1]:.4f}", max_width=450),
            tooltip=(
                f"<b>{dam['project_name']}</b><br>"
                f"Latitude : {dam['lat']:.6f}<br>"
                f"Longitude : {dam['lng']:.6f}"
            ),
            icon=folium.Icon(color="gray", icon="tint", prefix="fa")
        ).add_to(dam_group)
    dam_group.add_to(m)
    
    

    # Generation timestamps for display
    current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S Local")
    model_run_formatted = f"{latest_model[:4]}-{latest_model[4:6]}-{latest_model[6:8]} {latest_model[8:]}:00 UTC"

    # Legend HTML with dynamic timestamps
    legend_html = f"""
     <div style="
     position: fixed; 
     bottom: 30px; right: 30px; width: 240px;
     background-color: white; z-index:9999; font-size:14px;
     border:2px solid grey; border-radius:8px; padding: 10px;
     box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
     font-family: Arial, sans-serif;
     ">
     <h4 style="margin-top:0; margin-bottom:4px; font-size:15px; text-align:center;"><b>Rainfall Forecast (24h)</b></h4>
     <div style="font-size:12px; color:#555; text-align:center; margin-bottom:8px; line-height: 1.3;">
         Model Run: <b>{model_run_formatted}</b><br>
         Updated: <b>{current_time_str}</b>
     </div>
     <div><i style="background:#FFFFFF; width:18px; height:18px; float:left; margin-right:8px; border:1px solid #ccc;"></i> 0 (No Rain)</div>
     <div><i style="background:#6D6F70; width:18px; height:18px; float:left; margin-right:8px; border:1px solid #ccc;"></i> 0.1 - 2.4 mm (Very Light)</div>
     <div><i style="background:#4FC3F7; width:18px; height:18px; float:left; margin-right:8px; border:1px solid #ccc;"></i> 2.5 - 15.5 mm (Light)</div>
     <div><i style="background:#25DF44; width:18px; height:18px; float:left; margin-right:8px; border:1px solid #ccc;"></i> 15.6 - 64.4 mm (Moderate)</div>
     <div><i style="background:#FAF609; width:18px; height:18px; float:left; margin-right:8px; border:1px solid #ccc;"></i> 64.5 - 115.5 mm (Heavy)</div>
     <div><i style="background:#F57C00; width:18px; height:18px; float:left; margin-right:8px; border:1px solid #ccc;"></i> 115.6 - 204.4 mm(Very Heavy)</div>
     <div><i style="background:#D32F2F; width:18px; height:18px; float:left; margin-right:8px; border:1px solid #ccc;"></i> >204.4 mm (Extremely Heavy)</div>
     </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))


    folium.LayerControl().add_to(m)

    output_path = "Catchment_Rain_Dashboard.html"
    add_catchment_popup(m, catchment_alert_summary)
    m.save(output_path)
    print(f"6. Map successfully updated and saved to '{output_path}'!")
    return latest_model

if __name__ == "__main__":
    generate_map()
