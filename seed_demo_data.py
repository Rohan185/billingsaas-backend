"""
Seed script — Populate 5 months of realistic Indian manufacturing
business data for the demo company (rohan@test.com).
Run: python seed_demo_data.py
"""
import uuid
import random
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv()

from app.database import SessionLocal
from app.models import (
    Product, Customer, Supplier, RawMaterial,
    Invoice, InvoiceItem,
    Purchase, PurchaseItem,
    ProductionBatch, ProductionItem,
    Payment,
)

# ── Config ──────────────────────────────────────────────────────────
COMPANY_ID = "93f43afe-5844-4c2a-9f16-eaf07e0543d5"
MONTHS_BACK = 5
random.seed(42)

def uid():
    return str(uuid.uuid4())

def rand_date(start: datetime, end: datetime) -> datetime:
    delta = end - start
    secs = random.randint(0, int(delta.total_seconds()))
    return start + timedelta(seconds=secs)


# ── Master Data ─────────────────────────────────────────────────────
PRODUCTS = [
    {"name": "Premium Agarbatti (100 sticks)", "price": 120.0, "unit": "pack", "stock": 450},
    {"name": "Royal Dhoop Batti (50 sticks)", "price": 85.0, "unit": "pack", "stock": 320},
    {"name": "Sandalwood Agarbatti (30 sticks)", "price": 200.0, "unit": "pack", "stock": 180},
    {"name": "Mogra Agarbatti (100 sticks)", "price": 95.0, "unit": "pack", "stock": 520},
    {"name": "Lavender Dhoop Cone (25 pcs)", "price": 150.0, "unit": "box", "stock": 8},
    {"name": "Rose Agarbatti (50 sticks)", "price": 75.0, "unit": "pack", "stock": 600},
    {"name": "Guggal Dhoop (200g)", "price": 180.0, "unit": "pack", "stock": 5},
    {"name": "Chandan Cup Sambrani (12 pcs)", "price": 60.0, "unit": "box", "stock": 280},
]

CUSTOMERS = [
    {"name": "Sharma General Store", "phone": "9876543210", "email": "sharma@store.com", "address": "MG Road, Indore"},
    {"name": "Patel Pooja Samagri", "phone": "9823456789", "email": "patel@pooja.com", "address": "Ring Road, Ahmedabad"},
    {"name": "Krishna Traders", "phone": "9812345678", "email": "krishna@traders.in", "address": "Lal Darwaja, Surat"},
    {"name": "Balaji Enterprises", "phone": "9876123456", "email": "balaji@enter.com", "address": "Station Road, Pune"},
    {"name": "Om Sai Distributors", "phone": "9845678901", "email": "omsai@dist.com", "address": "Kankaria, Ahmedabad"},
    {"name": "Gupta & Sons", "phone": "9834567890", "email": "gupta@sons.com", "address": "Paltan Bazaar, Dehradun"},
    {"name": "Mahalaxmi Stores", "phone": "9856789012", "email": "mahalaxmi@stores.in", "address": "Camp Area, Pune"},
    {"name": "Bhagwati Traders", "phone": "9867890123", "email": "bhagwati@traders.com", "address": "Civil Lines, Jaipur"},
]

SUPPLIERS = [
    {"name": "Mysore Sandal Essentials", "phone": "9900112233", "address": "Mysore, Karnataka"},
    {"name": "Gujarat Bamboo Co.", "phone": "9911223344", "address": "Rajkot, Gujarat"},
    {"name": "Kannauj Fragrance House", "phone": "9922334455", "address": "Kannauj, UP"},
    {"name": "Vrindavan Flower Oils", "phone": "9933445566", "address": "Vrindavan, UP"},
]

RAW_MATERIALS = [
    {"name": "Bamboo Sticks (thin)", "unit": "kg", "stock": 350, "cost": 45.0, "threshold": 50},
    {"name": "Sandalwood Powder", "unit": "kg", "stock": 25, "cost": 800.0, "threshold": 10},
    {"name": "Charcoal Powder", "unit": "kg", "stock": 180, "cost": 30.0, "threshold": 40},
    {"name": "Jigat Powder (binding)", "unit": "kg", "stock": 120, "cost": 55.0, "threshold": 25},
    {"name": "Rose Fragrance Oil", "unit": "litre", "stock": 8, "cost": 1200.0, "threshold": 5},
    {"name": "Mogra Fragrance Oil", "unit": "litre", "stock": 12, "cost": 950.0, "threshold": 5},
    {"name": "Lavender Essential Oil", "unit": "litre", "stock": 3, "cost": 1500.0, "threshold": 5},
    {"name": "Guggal Resin", "unit": "kg", "stock": 45, "cost": 350.0, "threshold": 15},
    {"name": "Packaging Boxes (printed)", "unit": "pcs", "stock": 2000, "cost": 5.0, "threshold": 500},
    {"name": "Shrink Wrap Roll", "unit": "roll", "stock": 15, "cost": 250.0, "threshold": 5},
]


def main():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    start_date = now - timedelta(days=MONTHS_BACK * 30)

    print("🌱 Seeding demo data...")

    # ── 1. Products ──
    product_ids = []
    for p in PRODUCTS:
        pid = uid()
        product_ids.append(pid)
        db.add(Product(
            id=pid, company_id=COMPANY_ID,
            name=p["name"], price=p["price"],
            stock=p["stock"], unit=p["unit"],
            is_active=True,
            created_at=start_date - timedelta(days=10),
        ))
    db.flush()
    print(f"  ✅ {len(PRODUCTS)} products")

    # ── 2. Customers ──
    customer_ids = []
    for c in CUSTOMERS:
        cid = uid()
        customer_ids.append(cid)
        db.add(Customer(
            id=cid, company_id=COMPANY_ID,
            name=c["name"], phone=c["phone"],
            email=c["email"], address=c["address"],
            created_at=start_date - timedelta(days=10),
        ))
    db.flush()
    print(f"  ✅ {len(CUSTOMERS)} customers")

    # ── 3. Suppliers ──
    supplier_ids = []
    for s in SUPPLIERS:
        sid = uid()
        supplier_ids.append(sid)
        db.add(Supplier(
            id=sid, company_id=COMPANY_ID,
            name=s["name"], phone=s["phone"],
            address=s["address"], is_active=True,
            created_at=start_date - timedelta(days=10),
        ))
    db.flush()
    print(f"  ✅ {len(SUPPLIERS)} suppliers")

    # ── 4. Raw Materials ──
    material_ids = []
    for rm in RAW_MATERIALS:
        mid = uid()
        material_ids.append(mid)
        db.add(RawMaterial(
            id=mid, company_id=COMPANY_ID,
            name=rm["name"], unit=rm["unit"],
            stock_quantity=rm["stock"], cost_price=rm["cost"],
            low_stock_threshold=rm["threshold"], is_active=True,
            created_at=start_date - timedelta(days=10),
        ))
    db.flush()
    print(f"  ✅ {len(RAW_MATERIALS)} raw materials")

    # ── 5. Invoices (Sales) — ~8-15 per month over 5 months ──
    invoice_count = 0
    payment_count = 0
    statuses = ["paid", "paid", "paid", "unpaid", "partially_paid"]

    for month_offset in range(MONTHS_BACK, -1, -1):
        month_start = now - timedelta(days=month_offset * 30)
        month_end = now - timedelta(days=max(0, (month_offset - 1) * 30))
        num_invoices = random.randint(8, 15)

        for i in range(num_invoices):
            inv_date = rand_date(month_start, month_end)
            customer_idx = random.randint(0, len(customer_ids) - 1)
            cust = CUSTOMERS[customer_idx]
            status = random.choice(statuses)

            # 1-4 items per invoice
            num_items = random.randint(1, 4)
            chosen_products = random.sample(range(len(PRODUCTS)), min(num_items, len(PRODUCTS)))

            subtotal = 0.0
            items = []
            for pi in chosen_products:
                qty = random.randint(5, 50)
                price = PRODUCTS[pi]["price"]
                total = qty * price
                subtotal += total
                items.append({
                    "product_idx": pi,
                    "qty": qty,
                    "price": price,
                    "total": total,
                })

            tax_pct = random.choice([0, 5, 12, 18])
            tax_amt = round(subtotal * tax_pct / 100, 2)
            discount = round(random.uniform(0, subtotal * 0.05), 2)
            grand_total = round(subtotal + tax_amt - discount, 2)

            inv_id = uid()
            inv_num = f"INV-{inv_date.strftime('%y%m')}-{invoice_count + 1:04d}"

            db.add(Invoice(
                id=inv_id, company_id=COMPANY_ID,
                customer_id=customer_ids[customer_idx],
                invoice_number=inv_num,
                customer_name=cust["name"],
                customer_email=cust["email"],
                customer_phone=cust["phone"],
                subtotal=subtotal, tax_percent=tax_pct,
                tax_amount=tax_amt, discount=discount,
                total=grand_total, status=status,
                created_at=inv_date,
            ))

            for item in items:
                db.add(InvoiceItem(
                    id=uid(), invoice_id=inv_id,
                    product_id=product_ids[item["product_idx"]],
                    product_name=PRODUCTS[item["product_idx"]]["name"],
                    quantity=item["qty"],
                    unit_price=item["price"],
                    total_price=item["total"],
                ))

            # Payment for paid/partially_paid invoices
            if status == "paid":
                db.add(Payment(
                    id=uid(), company_id=COMPANY_ID,
                    customer_id=customer_ids[customer_idx],
                    invoice_id=inv_id,
                    amount=grand_total,
                    payment_type="received",
                    payment_method=random.choice(["cash", "bank", "upi"]),
                    created_at=inv_date + timedelta(days=random.randint(0, 7)),
                ))
                payment_count += 1
            elif status == "partially_paid":
                partial = round(grand_total * random.uniform(0.3, 0.7), 2)
                db.add(Payment(
                    id=uid(), company_id=COMPANY_ID,
                    customer_id=customer_ids[customer_idx],
                    invoice_id=inv_id,
                    amount=partial,
                    payment_type="received",
                    payment_method=random.choice(["cash", "upi"]),
                    created_at=inv_date + timedelta(days=random.randint(1, 10)),
                ))
                payment_count += 1

            invoice_count += 1

    db.flush()
    print(f"  ✅ {invoice_count} invoices + {payment_count} payments")

    # ── 6. Purchases (Raw Material buying) — ~3-6 per month ──
    purchase_count = 0
    for month_offset in range(MONTHS_BACK, -1, -1):
        month_start = now - timedelta(days=month_offset * 30)
        month_end = now - timedelta(days=max(0, (month_offset - 1) * 30))
        num_purchases = random.randint(3, 6)

        for i in range(num_purchases):
            pur_date = rand_date(month_start, month_end)
            supplier_idx = random.randint(0, len(supplier_ids) - 1)

            num_items = random.randint(1, 3)
            chosen_mats = random.sample(range(len(RAW_MATERIALS)), min(num_items, len(RAW_MATERIALS)))

            total_amount = 0.0
            pur_items = []
            for mi in chosen_mats:
                qty = round(random.uniform(10, 100), 1)
                cost = RAW_MATERIALS[mi]["cost"]
                total = round(qty * cost, 2)
                total_amount += total
                pur_items.append({
                    "mat_idx": mi,
                    "qty": qty,
                    "cost": cost,
                    "total": total,
                })

            pur_id = uid()
            pur_num = f"PUR-{pur_date.strftime('%y%m')}-{purchase_count + 1:04d}"

            db.add(Purchase(
                id=pur_id, company_id=COMPANY_ID,
                supplier_id=supplier_ids[supplier_idx],
                purchase_number=pur_num,
                total_amount=round(total_amount, 2),
                status=random.choice(["paid", "paid", "unpaid"]),
                created_at=pur_date,
            ))

            for item in pur_items:
                db.add(PurchaseItem(
                    id=uid(), purchase_id=pur_id,
                    raw_material_id=material_ids[item["mat_idx"]],
                    raw_material_name=RAW_MATERIALS[item["mat_idx"]]["name"],
                    quantity=item["qty"],
                    cost_price=item["cost"],
                    total=item["total"],
                ))

            # Supplier payment
            db.add(Payment(
                id=uid(), company_id=COMPANY_ID,
                supplier_id=supplier_ids[supplier_idx],
                purchase_id=pur_id,
                amount=round(total_amount, 2),
                payment_type="paid",
                payment_method=random.choice(["bank", "upi"]),
                created_at=pur_date + timedelta(days=random.randint(0, 5)),
            ))

            purchase_count += 1

    db.flush()
    print(f"  ✅ {purchase_count} purchases")

    # ── 7. Production Batches — ~4-8 per month ──
    batch_count = 0
    for month_offset in range(MONTHS_BACK, -1, -1):
        month_start = now - timedelta(days=month_offset * 30)
        month_end = now - timedelta(days=max(0, (month_offset - 1) * 30))
        num_batches = random.randint(4, 8)

        for i in range(num_batches):
            batch_date = rand_date(month_start, month_end)
            product_idx = random.randint(0, len(product_ids) - 1)
            qty_produced = random.randint(50, 300)

            # Use 2-3 raw materials per batch
            num_mats = random.randint(2, 3)
            chosen_mats = random.sample(range(len(RAW_MATERIALS)), min(num_mats, len(RAW_MATERIALS)))

            total_cost = 0.0
            batch_items = []
            for mi in chosen_mats:
                qty_used = round(random.uniform(2, 20), 2)
                mat_cost = RAW_MATERIALS[mi]["cost"]
                total_cost += qty_used * mat_cost
                batch_items.append({
                    "mat_idx": mi,
                    "qty_used": qty_used,
                })

            total_cost = round(total_cost, 2)
            cost_per_unit = round(total_cost / qty_produced, 2)

            batch_id = uid()
            batch_num = f"BATCH-{batch_date.strftime('%y%m')}-{batch_count + 1:04d}"

            db.add(ProductionBatch(
                id=batch_id, company_id=COMPANY_ID,
                batch_number=batch_num,
                finished_product_id=product_ids[product_idx],
                quantity_produced=qty_produced,
                total_cost=total_cost,
                cost_per_unit=cost_per_unit,
                created_at=batch_date,
            ))

            for item in batch_items:
                db.add(ProductionItem(
                    id=uid(),
                    production_batch_id=batch_id,
                    raw_material_id=material_ids[item["mat_idx"]],
                    raw_material_name=RAW_MATERIALS[item["mat_idx"]]["name"],
                    quantity_used=item["qty_used"],
                ))

            batch_count += 1

    db.flush()
    print(f"  ✅ {batch_count} production batches")

    # ── Commit ──
    db.commit()
    db.close()

    print(f"\n🎉 Done! Seeded data for company {COMPANY_ID}")
    print(f"   📦 {len(PRODUCTS)} products | 👥 {len(CUSTOMERS)} customers")
    print(f"   🏭 {len(SUPPLIERS)} suppliers | 🧱 {len(RAW_MATERIALS)} raw materials")
    print(f"   🧾 {invoice_count} invoices | 🛒 {purchase_count} purchases")
    print(f"   ⚙️ {batch_count} production batches | 💰 {payment_count + purchase_count} payments")
    print(f"   📅 Covering {MONTHS_BACK} months of data")


if __name__ == "__main__":
    main()
