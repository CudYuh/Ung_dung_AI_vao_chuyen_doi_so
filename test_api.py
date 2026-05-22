import urllib.request
import json
import urllib.error

data = json.dumps({
    'name': 'Test2', 
    'price': '1000', 
    'source': 'Test2', 
    'specifications': 'Test', 
    'category': 'Test', 
    'unit': 'Test'
}).encode('utf-8')

req = urllib.request.Request(
    'http://localhost:8000/products/approve', 
    data=data, 
    headers={'Content-Type': 'application/json'}
)

try:
    response = urllib.request.urlopen(req)
    print(response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print(f"Error {e.code}: {e.read().decode('utf-8')}")
