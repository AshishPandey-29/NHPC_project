import mysql.connector
from datetime import datetime

def save_to_mysql(catchment_summary, latest_model):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="1605@abc",
        database="rainfall_db"
    )
    cursor = conn.cursor()

    for _, row in catchment_summary.iterrows():
        cursor.execute("""
            INSERT INTO catchment_rainfall
            (catchment_name, model_run, volume_3h_mcm, volume_6h_mcm, volume_12h_mcm, volume_24h_mcm)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            row["catchment"],
            latest_model,
            float(row["volume_3h_mcm"]),
            float(row["volume_6h_mcm"]),
            float(row["volume_12h_mcm"]),
            float(row["volume_24h_mcm"])
        ))

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Saved {len(catchment_summary)} catchment records to MySQL.")