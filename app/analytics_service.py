"""
Analytics service — read-only queries for dashboards / reporting.
All queries are filtered by company_id for multi-tenant isolation.
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, cast, Date
from sqlalchemy.orm import Session
from app.models import (
    Invoice, InvoiceItem, Product,
    RawMaterial, Purchase, ProductionBatch,
)


def _start_of_month() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


# ── 1. Revenue Trend (last 30 days, daily) ────────────────────────
def revenue_trend(db: Session, company_id: str) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    rows = (
        db.query(
            cast(Invoice.created_at, Date).label("day"),
            func.coalesce(func.sum(Invoice.total), 0).label("revenue"),
        )
        .filter(
            Invoice.company_id == company_id,
            Invoice.status != "cancelled",
            Invoice.created_at >= cutoff,
        )
        .group_by(cast(Invoice.created_at, Date))
        .order_by(cast(Invoice.created_at, Date))
        .all()
    )
    return [{"date": str(r.day), "revenue": float(r.revenue)} for r in rows]


# ── 2. Top Products (by qty sold) ─────────────────────────────────
def top_products(db: Session, company_id: str, limit: int = 5) -> list[dict]:
    rows = (
        db.query(
            InvoiceItem.product_name,
            func.sum(InvoiceItem.quantity).label("total_qty"),
            func.sum(InvoiceItem.total_price).label("total_revenue"),
        )
        .join(Invoice, Invoice.id == InvoiceItem.invoice_id)
        .filter(Invoice.company_id == company_id, Invoice.status != "cancelled")
        .group_by(InvoiceItem.product_name)
        .order_by(func.sum(InvoiceItem.quantity).desc())
        .limit(limit)
        .all()
    )
    return [
        {"product": r.product_name, "qty_sold": int(r.total_qty), "revenue": float(r.total_revenue)}
        for r in rows
    ]


# ── 3. Low Stock ──────────────────────────────────────────────────
def low_stock(db: Session, company_id: str) -> dict:
    products = (
        db.query(Product)
        .filter(Product.company_id == company_id, Product.stock <= 10, Product.is_active == True)
        .order_by(Product.stock)
        .all()
    )
    raw_materials = (
        db.query(RawMaterial)
        .filter(
            RawMaterial.company_id == company_id,
            RawMaterial.stock_quantity <= RawMaterial.low_stock_threshold,
            RawMaterial.is_active == True,
        )
        .order_by(RawMaterial.stock_quantity)
        .all()
    )
    return {
        "products": [
            {"id": p.id, "name": p.name, "stock": p.stock, "unit": p.unit}
            for p in products
        ],
        "raw_materials": [
            {"id": r.id, "name": r.name, "stock": r.stock_quantity, "unit": r.unit, "threshold": r.low_stock_threshold}
            for r in raw_materials
        ],
    }


# ── 4. Production Summary (current month) ─────────────────────────
def production_summary(db: Session, company_id: str) -> dict:
    start = _start_of_month()
    row = (
        db.query(
            func.coalesce(func.sum(ProductionBatch.quantity_produced), 0).label("units"),
            func.coalesce(func.sum(ProductionBatch.total_cost), 0).label("cost"),
            func.count(ProductionBatch.id).label("batches"),
        )
        .filter(ProductionBatch.company_id == company_id, ProductionBatch.created_at >= start)
        .one()
    )
    return {
        "total_units_produced": int(row.units),
        "total_production_cost": float(row.cost),
        "total_batches": int(row.batches),
        "period": f"{start.strftime('%b %Y')}",
    }


# ── 5. Profit Summary ─────────────────────────────────────────────
def profit_summary(db: Session, company_id: str) -> dict:
    start = _start_of_month()

    # Revenue (non-cancelled invoices this month)
    revenue = (
        db.query(func.coalesce(func.sum(Invoice.total), 0))
        .filter(Invoice.company_id == company_id, Invoice.status != "cancelled", Invoice.created_at >= start)
        .scalar()
    )

    # Purchase cost this month
    purchase_cost = (
        db.query(func.coalesce(func.sum(Purchase.total_amount), 0))
        .filter(Purchase.company_id == company_id, Purchase.created_at >= start)
        .scalar()
    )

    # Production cost this month
    production_cost = (
        db.query(func.coalesce(func.sum(ProductionBatch.total_cost), 0))
        .filter(ProductionBatch.company_id == company_id, ProductionBatch.created_at >= start)
        .scalar()
    )

    revenue = float(revenue)
    purchase_cost = float(purchase_cost)
    production_cost = float(production_cost)

    return {
        "revenue": revenue,
        "purchase_cost": purchase_cost,
        "production_cost": production_cost,
        "total_expenses": purchase_cost + production_cost,
        "gross_profit": revenue - (purchase_cost + production_cost),
        "period": f"{start.strftime('%b %Y')}",
    }
