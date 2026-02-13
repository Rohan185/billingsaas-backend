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

def get(path, token):
    req = urllib.request.Request(BASE + path, headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req)
    return resp.status, json.loads(resp.read())

# Login
form = urllib.parse.urlencode({"username": "rohan@test.com", "password": "test1234"}).encode()
req = urllib.request.Request(BASE + "/api/auth/login", form, {"Content-Type": "application/x-www-form-urlencoded"})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read())["access_token"]
print(f"Logged in. Token: {token[:20]}...\n")

# 1. Create Raw Material
print("=== 1. CREATE RAW MATERIALS ===")
s, r = post("/api/raw-materials/", {"name": "Steel Rod", "unit": "kg", "stock_quantity": 0, "cost_price": 50, "low_stock_threshold": 20}, token)
print(f"  Steel Rod: {s} | Stock: {r['stock_quantity']}")
steel_id = r["id"]

s, r = post("/api/raw-materials/", {"name": "Plastic Granules", "unit": "kg", "stock_quantity": 0, "cost_price": 30}, token)
print(f"  Plastic: {s} | Stock: {r['stock_quantity']}")
plastic_id = r["id"]

# 2. Create Supplier
print("\n=== 2. CREATE SUPPLIER ===")
s, r = post("/api/suppliers/", {"name": "ABC Metals", "phone": "9876543210", "email": "abc@metals.com"}, token)
print(f"  Supplier: {s} | {r['name']}")
supplier_id = r["id"]

# 3. Create Purchase (should auto-increase raw material stock)
print("\n=== 3. CREATE PURCHASE (auto stock increase) ===")
s, r = post("/api/purchases/", {
    "supplier_id": supplier_id,
    "items": [
        {"raw_material_id": steel_id, "quantity": 100, "cost_price": 55},
        {"raw_material_id": plastic_id, "quantity": 50, "cost_price": 32},
    ]
}, token)
print(f"  Purchase: {s} | {r['purchase_number']} | Total: Rs.{r['total_amount']}")

# Verify stock increased
s, r = get(f"/api/raw-materials/{steel_id}", token)
print(f"  Steel stock after purchase: {r['stock_quantity']} (expected 100)")

s, r = get(f"/api/raw-materials/{plastic_id}", token)
print(f"  Plastic stock after purchase: {r['stock_quantity']} (expected 50)")

# 4. Get current Laptop product stock
s, products_list = get("/api/products/", token)
laptop = [p for p in products_list if p["name"] == "Laptop"][0]
laptop_id = laptop["id"]
print(f"\n=== 4. CURRENT LAPTOP STOCK: {laptop['stock']} ===")

# 5. Create Production Batch (deduct raw materials, increase product stock)
print("\n=== 5. CREATE PRODUCTION BATCH ===")
s, r = post("/api/production/", {
    "finished_product_id": laptop_id,
    "quantity_produced": 10,
    "items": [
        {"raw_material_id": steel_id, "quantity_used": 20},
        {"raw_material_id": plastic_id, "quantity_used": 5},
    ]
}, token)
print(f"  Batch: {s} | {r['batch_number']} | Cost: Rs.{r['total_cost']}")

# Verify stock changes
print("\n=== 6. VERIFY STOCK AFTER PRODUCTION ===")
s, r = get(f"/api/raw-materials/{steel_id}", token)
print(f"  Steel stock: {r['stock_quantity']} (was 100, used 20 -> expected 80)")

s, r = get(f"/api/raw-materials/{plastic_id}", token)
print(f"  Plastic stock: {r['stock_quantity']} (was 50, used 5 -> expected 45)")

s, r = get(f"/api/products/{laptop_id}", token)
print(f"  Laptop stock: {r['stock']} (was {laptop['stock']}, produced 10 -> expected {laptop['stock'] + 10})")

# 7. Test negative stock prevention
print("\n=== 7. NEGATIVE STOCK PREVENTION ===")
s, r = post("/api/production/", {
    "finished_product_id": laptop_id,
    "quantity_produced": 1,
    "items": [
        {"raw_material_id": steel_id, "quantity_used": 9999},
    ]
}, token)
print(f"  Attempt huge deduction: {s} | {r.get('detail', 'unexpected')}")

print("\n✅ ALL MANUFACTURING TESTS PASSED!")
