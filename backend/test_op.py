import requests

url = 'https://overpass.osm.ch/api/interpreter'
q = '''[out:json];
(
  node(51.500,-0.130,51.501,-0.129);
);
out body;'''
r = requests.post(url, data={'data': q})
data = r.json()
print("Nodes:", len(data.get('elements', [])))
