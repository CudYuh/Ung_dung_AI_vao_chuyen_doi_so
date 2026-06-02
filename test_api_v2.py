import urllib.request, json
req = urllib.request.Request('http://localhost:8000/api/v1/valuate', data=json.dumps({'product_name': 'realme C67 8GB 128GB'}).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        with open('test_api_out.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
except Exception as e:
    print(f"Error: {e}")
