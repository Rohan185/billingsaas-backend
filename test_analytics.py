import urllib.request, urllib.parse, json

BASE = "http://127.0.0.1:8000"

# Login
form = urllib.parse.urlencode({"username": "rohan@test.com", "password": "test1234"}).encode()
req = urllib.request.Request(BASE + "/api/auth/login", form, {"Content-Type": "application/x-www-form-urlencoded"})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read())["access_token"]
print(f"Logged in.\n")

def get(path):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())

endpoints = [
    ("/api/analytics/revenue-trend", "Revenue Trend (30d)"),
    ("/api/analytics/top-products", "Top Products"),
    ("/api/analytics/low-stock", "Low Stock"),
    ("/api/analytics/production-summary", "Production Summary"),
    ("/api/analytics/profit-summary", "Profit Summary"),
]

for path, label in endpoints:
    try:
        data = get(path)
        print(f"✅ {label}: {json.dumps(data, indent=2)[:300]}")
    except Exception as e:
        print(f"❌ {label}: {e}")
    print()

print("Done!")
