import urllib.request
import json

overpass_url = "http://overpass-api.de/api/interpreter"
overpass_query = """
[out:json];
(
  way["highway"="trunk"](20.0, 72.0, 28.0, 80.0);
);
out geom;
"""

try:
    req = urllib.request.Request(overpass_url, data=overpass_query.encode('utf-8'))
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    
    features = []
    for element in data['elements']:
        if element['type'] == 'way':
            coords = [[node['lon'], node['lat']] for node in element['geometry']]
            features.append({
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords
                },
                "properties": {
                    "name": element.get('tags', {}).get('name', 'Unknown')
                }
            })
            
    geojson = {
        "type": "FeatureCollection",
        "features": features
    }
    
    with open('frontend/public/roads.geojson', 'w') as f:
        json.dump(geojson, f)
    print("Saved roads.geojson")
except Exception as e:
    print(f"Error: {e}")
