import urllib.request
import json

overpass_url = "http://overpass-api.de/api/interpreter"
overpass_query = """
[out:json];
(
  way["highway"~"motorway|trunk"](8.0, 68.0, 37.0, 97.0);
);
out geom;
"""

try:
    req = urllib.request.Request(
        overpass_url, 
        data=overpass_query.encode('utf-8'),
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    
    features = []
    for element in data.get('elements', []):
        if element['type'] == 'way':
            coords = [[node['lon'], node['lat']] for node in element.get('geometry', [])]
            if len(coords) > 1:
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
    print(f"Saved {len(features)} roads to roads.geojson")
except Exception as e:
    print(f"Error: {e}")
