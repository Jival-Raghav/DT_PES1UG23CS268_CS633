import pandas as pd
import json
import sys
import os

class TanishaTrafficPipeline:
    def __init__(self, uber_csv):
        self.uber_csv = uber_csv
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.geojson_path = os.path.join(self.base_dir, 'bangalore_wards.json')

    def get_ward_name_map(self):
        """Creates a lookup of ID -> Name from the GeoJSON file."""
        name_map = {}
        if os.path.exists(self.geojson_path):
            try:
                with open(self.geojson_path, 'r') as f:
                    geo_data = json.load(f)
                    for feature in geo_data['features']:
                        props = feature['properties']
                        w_id = props.get('WARD_NO') # Using your exact key
                        w_name = props.get('WARD_NAME', 'Unknown')
                        if w_id:
                            name_map[int(w_id)] = w_name
            except Exception as e:
                print(f"Warning: Could not parse GeoJSON for names: {e}")
        return name_map

    def generate_demand(self, congestion_multiplier=1.0, target_hour=9):
        if not os.path.exists(self.uber_csv):
            print(f"Error: CSV not found at {self.uber_csv}")
            return None
            
        df = pd.read_csv(self.uber_csv)
        rush_hour = df[df['hod'] == target_hour].copy()
        
        # Spatial Filter for Ward 163 Corridor
        corridor_filter = (rush_hour['sourceid'] == 163) | (rush_hour['dstid'] == 163)
        rush_hour = rush_hour[corridor_filter]

        if rush_hour.empty:
            print("Warning: No data found for Ward 163.")
            return None

        rush_hour['mean_travel_min'] = rush_hour['mean_travel_time'] / 60
        
        od_matrix = rush_hour.groupby(['sourceid', 'dstid']).agg({
            'mean_travel_min': 'mean',
            'standard_deviation_travel_time': 'mean'
        }).reset_index()

        od_matrix['synthetic_trip_count'] = (100 / od_matrix['mean_travel_min']) * congestion_multiplier
        hotspots = od_matrix.sort_values(by='synthetic_trip_count', ascending=False).head(10)

        # --- NEW: Get Names ---
        ward_names = self.get_ward_name_map()
        
        # Convert hotspots to a list of records with names included
        final_matrix = []
        for _, row in hotspots.iterrows():
            final_matrix.append({
                "sourceid": int(row['sourceid']),
                "sourcename": ward_names.get(int(row['sourceid']), "Unknown Ward"),
                "dstid": int(row['dstid']),
                "dstname": ward_names.get(int(row['dstid']), "Unknown Ward"),
                "synthetic_trip_count": round(float(row['synthetic_trip_count']), 2),
                "travel_time_min": round(float(row['mean_travel_min']), 2)
            })

        output = {
            "scenario_metadata": {
                "multiplier": congestion_multiplier,
                "description": f"Ward 163 Corridor - {'Heavy' if congestion_multiplier > 1.2 else 'Normal'}",
                "target_hour": target_hour
            },
            "demand_matrix": final_matrix
        }

        output_path = os.path.join(self.base_dir, '../data_shared/integration_demand.json')
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(output, f, indent=4)
        
        return output_path

if __name__ == "__main__":
    try:
        mult = float(sys.argv[1])
    except (IndexError, ValueError):
        mult = 1.0
        
    csv_file = '/Users/tanishajayabalan/Desktop/Capstone_Project/Phase1_Tanisha/bangalore-wards-2019-3-OnlyWeekdays-HourlyAggregate.csv'
    
    pipeline = TanishaTrafficPipeline(csv_file)
    saved_file = pipeline.generate_demand(congestion_multiplier=mult)
    
    if saved_file:
        print(f"Success! Output saved with Ward Names.")