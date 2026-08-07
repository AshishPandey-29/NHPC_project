import mysql.connector
from datetime import datetime
from pathlib import Path
from config import *

CACHE_DIR = Path("cache")
CACHE_DIR.mkdir(exist_ok=True)
SAVED_MODEL_FILE = CACHE_DIR / "last_saved_model.txt"

def save_to_mysql(catchment_summary, latest_model):
    latest_model_str = str(latest_model).strip() # model detected from api
    
    # 1. Fast check via cache file
    if SAVED_MODEL_FILE.exists():
        try:
            last_saved = SAVED_MODEL_FILE.read_text().strip()
            if last_saved == latest_model_str:
                print(f"Model '{latest_model_str}' is already saved (checked via cache). Skipping duplicate save.")
                return
        except Exception:
            pass

    conn = mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = conn.cursor()

    # 2. Database check: Verify if records for this model_run already exist in MySQL
    try:
        cursor.execute("SELECT COUNT(*) FROM catchment_rainfall WHERE model_run = %s", (latest_model_str,))
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"Model '{latest_model_str}' is already saved in MySQL ({count} existing records). Skipping duplicate save.")
            cursor.close()
            conn.close()
            # Sync cache file so future checks hit the fast cache check
            try:
                SAVED_MODEL_FILE.write_text(latest_model_str)
                (CACHE_DIR / "last_model.txt").write_text(latest_model_str)
            except Exception:
                pass
            return
    except Exception as check_err:
        print(f"Notice: Could not query existing model records: {check_err}")

    # 3. Insert new records if model run is not yet saved
    for _, row in catchment_summary.iterrows():
        cursor.execute("""
            INSERT INTO catchment_rainfall
            (catchment_name, model_run, volume_3h_mcm, volume_6h_mcm, volume_12h_mcm, volume_24h_mcm)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            row["catchment"],
            latest_model_str,
            float(row["volume_3h_mcm"]),
            float(row["volume_6h_mcm"]),
            float(row["volume_12h_mcm"]),
            float(row["volume_24h_mcm"])
        ))

    conn.commit()
    cursor.close()
    conn.close()

    # Save the latest model run to cache after successful DB commit
    try:
        SAVED_MODEL_FILE.write_text(latest_model_str)
        (CACHE_DIR / "last_model.txt").write_text(latest_model_str)
    except Exception as e:
        print(f"Warning: Could not update model cache: {e}")

    print(f"Saved {len(catchment_summary)} catchment records to MySQL for model run: {latest_model_str}.")


def fetch_catchment_projects():
    """Fetch catchment_name to projects mapping from MySQL catchment_details table."""
    projects_map = {}
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()
        cursor.execute("SELECT catchment_name, projects FROM catchment_details")
        for row in cursor.fetchall():
            cname, projs = row[0], row[1]
            if cname:
                projects_map[cname.strip()] = projs.strip() if projs else ""
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Notice: Could not fetch catchment projects from MySQL: {e}")
    return projects_map


