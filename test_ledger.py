"""Simple step-by-step test for customer ledger endpoints."""
import requests, random, string, json, traceback

BASE = "http://127.0.0.1:8000"
rand = ''.join(random.choices(string.ascii_lowercase, k=4))
email = f"t_{rand}@test.com"

def step(name, r):
    """Print step result and check for errors."""
    ok = r.status_code < 400
    print(f"{'PASS' if ok else 'FAIL'} [{r.status_code}] {name}")
    if not ok:
        print(f"  Body: {r.text[:300]}")
    return ok

# Register + Login
r = requests.post(f"{BASE}/api/auth/register", json={"company_name": f"Co {rand}", "full_name": "Test", "email": email, "password": "pass"})
step("Register", r)
r = requests.post(f"{BASE}/api/auth/login", data={"username": email, "password": "pass"})
step("Login", r)
h = {"Authorization": f"Bearer {r.json()['access_token']}"}

# 1. Create customer
r = requests.post(f"{BASE}/api/customers/", headers=h, json={"name": "CustA"})
step("Create customer", r)
cust_id = r.json()["id"]

# 2. Create product
r = requests.post(f"{BASE}/api/products/", headers=h, json={"name": "ProdA", "price": 100, "stock": 50})
step("Create product", r)
prod_id = r.json()["id"]

# 3. Create invoice
r = requests.post(f"{BASE}/api/invoices/", headers=h, json={
    "customer_name": "CustA", "customer_id": cust_id,
    "items": [{"product_id": prod_id, "quantity": 2}]
})
step("Create invoice", r)
inv_id = r.json()["id"]
inv_total = r.json()["total"]

# 4. List customers
r = requests.get(f"{BASE}/api/customers/", headers=h)
step("List customers", r)

# 5. Get ledger
r = requests.get(f"{BASE}/api/ledger/customer/{cust_id}", headers=h)
step("Get ledger", r)

# 6. Partial payment
r = requests.post(f"{BASE}/api/payments/receive", headers=h, json={
    "customer_id": cust_id, "invoice_id": inv_id, "amount": 50, "payment_method": "upi"
})
step("Partial payment", r)

# 7. Check invoice status
r = requests.get(f"{BASE}/api/invoices/{inv_id}", headers=h)
if step("Invoice after partial", r):
    print(f"  Status: {r.json()['status']}")

# 8. Overpayment
r = requests.post(f"{BASE}/api/payments/receive", headers=h, json={
    "customer_id": cust_id, "invoice_id": inv_id, "amount": 99999, "payment_method": "cash"
})
step("Overpayment guard (expect 400)", r)

# 9. Full remaining payment
remaining = inv_total - 50
r = requests.post(f"{BASE}/api/payments/receive", headers=h, json={
    "customer_id": cust_id, "invoice_id": inv_id, "amount": remaining, "payment_method": "bank"
})
step("Full payment", r)

# 10. Invoice should be paid
r = requests.get(f"{BASE}/api/invoices/{inv_id}", headers=h)
if step("Invoice after full", r):
    print(f"  Status: {r.json()['status']}")

# 11. Final ledger
r = requests.get(f"{BASE}/api/ledger/customer/{cust_id}", headers=h)
if step("Final ledger", r):
    led = r.json()
    print(f"  Summary: {json.dumps(led['summary'])}")

print("\nDone.")
