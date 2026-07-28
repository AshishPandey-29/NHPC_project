import time
import sys
from datetime import datetime
from map import generate_map
from imd_ping import discover_latest_model

def main():
    print("====================================================")
    print(" Rainfall Forecast Auto-Update Scheduler Started")
    print(f" Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(" Check Interval: 1 hour (3600 seconds)")
    print("====================================================")
    
    last_processed_model = None
    
    while True:
        try:
            print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking latest IMD model run...")
            current_model = discover_latest_model()
            
            if current_model != last_processed_model:
                print(f"New model run detected: '{current_model}' (previous: '{last_processed_model}')")
                print("Initiating map update...")
                
                # Run the map generation pipeline
                last_processed_model = generate_map()
                
                print(f"Map successfully updated for model run: {last_processed_model}")
            else:
                print(f"No new model run. Still on model run: {last_processed_model}")
                
        except Exception as e:
            print(f"Error during map update cycle: {e}", file=sys.stderr)
            
        # Sleep for 1 hour (3600 seconds) before checking again
        time.sleep(3600)

if __name__ == "__main__":
    main()
