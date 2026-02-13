from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base, SessionLocal
from app.routers import auth, products, invoices, dashboard
from app.routers import raw_materials, suppliers, purchases, production
from app.routers import analytics, stock_movements
from app.routers import customers, ledger, payments
from app.routers import inventory_valuation
from app.routers import whatsapp
from app.routers import whatsapp_webhook


def _migrate_customers():
    """
    One-time migration:
    1. Add customer_id column to invoices if missing (create_all doesn't ALTER)
    2. Create Customer records from existing invoice data
    3. Back-fill customer_id on invoices
    """
    from sqlalchemy import text, inspect
    from app.models import Invoice, Customer
    db = SessionLocal()
    try:
        # Step 1: Check if customer_id column exists on invoices
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns("invoices")]
        if "customer_id" not in columns:
            db.execute(text("ALTER TABLE invoices ADD COLUMN customer_id VARCHAR REFERENCES customers(id)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_invoices_customer_id ON invoices (customer_id)"))
            db.commit()
            print("[migration] Added customer_id column to invoices")

        # Step 2: Create customers from unmigrated invoices
        unmigrated = (
            db.query(Invoice)
            .filter(Invoice.customer_id.is_(None))
            .all()
        )
        if not unmigrated:
            return
        for inv in unmigrated:
            existing = (
                db.query(Customer)
                .filter(Customer.company_id == inv.company_id, Customer.name == inv.customer_name)
                .first()
            )
            if not existing:
                existing = Customer(
                    company_id=inv.company_id,
                    name=inv.customer_name,
                    email=inv.customer_email,
                    phone=inv.customer_phone,
                )
                db.add(existing)
                db.flush()
            inv.customer_id = existing.id
        db.commit()
        print(f"[migration] Migrated {len(unmigrated)} invoices to customer FK")
    except Exception as e:
        db.rollback()
        print(f"[migration] Error: {e}")
    finally:
        db.close()


def _migrate_supplier_ledger():
    """
    Add supplier_id, purchase_id columns to payments table,
    status column to purchases table, and make customer_id nullable.
    Works with PostgreSQL (Supabase).
    """
    from sqlalchemy import text, inspect
    db = SessionLocal()
    try:
        inspector = inspect(engine)

        # If a botched SQLite-style migration left _payments_old, recover it
        table_names = inspector.get_table_names()
        if "_payments_old" in table_names and "payments" not in table_names:
            db.execute(text("ALTER TABLE _payments_old RENAME TO payments"))
            db.commit()
            print("[migration] Recovered payments table from _payments_old")
            # Refresh inspector
            inspector = inspect(engine)
        elif "_payments_old" in table_names and "payments" in table_names:
            db.execute(text("DROP TABLE IF EXISTS _payments_old"))
            db.commit()
            print("[migration] Dropped leftover _payments_old table")
            inspector = inspect(engine)

        # Payments table: add supplier_id column  
        pay_cols = [c["name"] for c in inspector.get_columns("payments")]
        if "supplier_id" not in pay_cols:
            db.execute(text("ALTER TABLE payments ADD COLUMN supplier_id VARCHAR REFERENCES suppliers(id)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_supplier_id ON payments (supplier_id)"))
            print("[migration] Added supplier_id column to payments")

        # Payments table: add purchase_id column
        if "purchase_id" not in pay_cols:
            db.execute(text("ALTER TABLE payments ADD COLUMN purchase_id VARCHAR REFERENCES purchases(id)"))
            db.execute(text("CREATE INDEX IF NOT EXISTS ix_payments_purchase_id ON payments (purchase_id)"))
            print("[migration] Added purchase_id column to payments")

        # Make customer_id nullable (PostgreSQL ALTER COLUMN)
        pay_col_map = {c["name"]: c for c in inspector.get_columns("payments")}
        if "customer_id" in pay_col_map and not pay_col_map["customer_id"]["nullable"]:
            db.execute(text("ALTER TABLE payments ALTER COLUMN customer_id DROP NOT NULL"))
            print("[migration] Made customer_id nullable in payments")

        # Purchases table: add status column
        pur_cols = [c["name"] for c in inspector.get_columns("purchases")]
        if "status" not in pur_cols:
            db.execute(text("ALTER TABLE purchases ADD COLUMN status VARCHAR(20) DEFAULT 'unpaid'"))
            print("[migration] Added status column to purchases")

        # Production batches: add cost_per_unit column
        if "production_batches" in inspector.get_table_names():
            pb_cols = [c["name"] for c in inspector.get_columns("production_batches")]
            if "cost_per_unit" not in pb_cols:
                db.execute(text("ALTER TABLE production_batches ADD COLUMN cost_per_unit DOUBLE PRECISION DEFAULT 0"))
                # Backfill existing batches
                db.execute(text("""
                    UPDATE production_batches
                    SET cost_per_unit = CASE WHEN quantity_produced > 0 THEN total_cost / quantity_produced ELSE 0 END
                    WHERE cost_per_unit = 0 OR cost_per_unit IS NULL
                """))
                print("[migration] Added cost_per_unit to production_batches")

        # Companies table: add gst_number column
        comp_cols = [c["name"] for c in inspector.get_columns("companies")]
        if "gst_number" not in comp_cols:
            db.execute(text("ALTER TABLE companies ADD COLUMN gst_number VARCHAR(20)"))
            print("[migration] Added gst_number to companies")

        db.commit()
    except Exception as e:
        db.rollback()
        print(f"[migration] Supplier ledger error: {e}")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    # Create tables on startup
    Base.metadata.create_all(bind=engine)
    _migrate_customers()
    _migrate_supplier_ledger()
    yield


app = FastAPI(
    title="Billing SaaS API",
    description="Multi-tenant billing backend with company isolation",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS – adjust origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(products.router)
app.include_router(invoices.router)
app.include_router(dashboard.router)

# Manufacturing routers
app.include_router(raw_materials.router)
app.include_router(suppliers.router)
app.include_router(purchases.router)
app.include_router(production.router)

# Analytics
app.include_router(analytics.router)
app.include_router(stock_movements.router)
app.include_router(inventory_valuation.router)

# Customer, Ledger & Payments
app.include_router(customers.router)
app.include_router(ledger.router)
app.include_router(payments.router)

# WhatsApp
app.include_router(whatsapp.router)
app.include_router(whatsapp_webhook.router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "service": "Billing SaaS API"}
