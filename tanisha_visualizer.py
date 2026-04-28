import json
import folium
import os
from shapely.geometry import shape

def get_ward_data(geojson_path):
    """Returns a dictionary mapping WARD_NO to {'coords': [lat, lon], 'name': 'Ward Name'}"""
    if not os.path.exists(geojson_path):
        return {}

    with open(geojson_path, 'r') as f:
        gdf_data = json.load(f)
    
    ward_info = {}
    for feature in gdf_data['features']:
        props = feature['properties']
        w_id = props.get('WARD_NO') 
        w_name = props.get('WARD_NAME', 'Unknown')
        
        if w_id is not None:
            try:
                poly = shape(feature['geometry'])
                center = poly.centroid
                ward_info[int(w_id)] = {
                    'coords': [center.y, center.x],
                    'name': w_name
                }
            except:
                continue
    return ward_info

def generate_map():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_json = os.path.join(base_dir, '../data_shared/integration_demand.json')
    geojson_path = os.path.join(base_dir, 'bangalore_wards.json')
    output_html = os.path.join(base_dir, '../data_shared/traffic_map.html')

    # 1. Load spatial data
    ward_lookup = get_ward_data(geojson_path)
    
    with open(input_json, 'r') as f:
        demand_data = json.load(f)

    matrix = demand_data.get('demand_matrix', [])
    if not matrix: return

    # 2. Setup Map
    start_id = int(matrix[0]['sourceid'])
    map_center = ward_lookup.get(start_id, {'coords': [12.9716, 77.5946]})['coords']
    m = folium.Map(location=map_center, zoom_start=12, tiles='CartoDB dark_matter')

    # 3. Draw Flows with Labels
    for trip in matrix:
        src, dst = int(trip['sourceid']), int(trip['dstid'])
        count = int(trip['synthetic_trip_count'])

        if src in ward_lookup and dst in ward_lookup:
            src_name = ward_lookup[src]['name']
            dst_name = ward_lookup[dst]['name']
            
            # Create the flow line
            line = folium.PolyLine(
                locations=[ward_lookup[src]['coords'], ward_lookup[dst]['coords']],
                weight=max(2, count / 5),
                color='#00FFCC',
                opacity=0.6,
                # This adds a label when you hover!
                tooltip=f"<b>From:</b> {src_name}<br><b>To:</b> {dst_name}<br><b>Trips:</b> {count}"
            ).add_to(m)

            # Add a small text label at the start of the line for "Areas"
            folium.Marker(
                location=ward_lookup[src]['coords'],
                icon=folium.DivIcon(html=f"""<div style="font-family: sans-serif; color: white; font-size: 10px; width: 100px;">{src_name}</div>""")
            ).add_to(m)

    m.save(output_html)
    print(f"Success! Map with labels generated at: {output_html}")

    try:
        import subprocess
        subprocess.run(['open', output_html])
        print("Opening map in your default browser...")
    except Exception as e:
        print(f"Could not open browser automatically: {e}")

if __name__ == "__main__":
    generate_map()