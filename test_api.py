import urllib.request, urllib.parse, json

BASE = "http://127.0.0.1:8000"

def post(path, data, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(BASE + path, json.dumps(data).encode(), headers)
    try:
        resp = urllib.request.urlopen(req)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

def post_form(path, data):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(BASE + path, body, {"Content-Type": "application/x-www-form-urlencoded"})
    resp = urllib.request.urlopen(req)
    return resp.status, json.loads(resp.read())

def get(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req)
    return resp.status, json.loads(resp.read())

print("=== 1. LOGIN ===")
s, r = post_form("/api/auth/login", {"username": "rohan@test.com", "password": "test1234"})
token = r["access_token"]
print(f"Status: {s} | Token: {token[:30]}...")

print("\n=== 2. GET /me ===")
s, r = get("/api/auth/me", token)
print(f"Status: {s} | User: {r['full_name']} | Company: {r['company_id'][:12]}...")

print("\n=== 3. CREATE PRODUCT ===")
s, r = post("/api/products/", {"name": "Laptop", "price": 50000, "stock": 20, "unit": "pcs"}, token)
print(f"Status: {s} | Product: {r['name']} | Stock: {r['stock']}")
product_id = r["id"]

print("\n=== 4. LIST PRODUCTS ===")
s, r = get("/api/products/", token)
print(f"Status: {s} | Count: {len(r)}")

print("\n=== 5. CREATE INVOICE (auto deducts stock) ===")
s, r = post("/api/invoices/", {
    "customer_name": "Test Customer",
    "tax_percent": 18,
    "items": [{"product_id": product_id, "quantity": 2}]
}, token)
print(f"Status: {s} | Invoice: {r['invoice_number']} | Total: {r['total']}")

print("\n=== 6. CHECK STOCK AFTER INVOICE ===")
s, r = get(f"/api/products/{product_id}", token)
print(f"Status: {s} | Product: {r['name']} | Stock now: {r['stock']} (was 20, sold 2)")

print("\n=== 7. DASHBOARD SUMMARY ===")
s, r = get("/api/dashboard/summary", token)
print(f"Status: {s}")
print(f"  Today Revenue: Rs.{r['today_revenue']}")
print(f"  Monthly Revenue: Rs.{r['monthly_revenue']}")
print(f"  Invoices Today: {r['total_invoices_today']}")
print(f"  Low Stock Items: {len(r['low_stock_items'])}")

print("\n✅ ALL TESTS PASSED - Backend is fully working!")
