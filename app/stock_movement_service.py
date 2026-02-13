"""
Stock Movement Audit Trail service.
Logs every stock change and provides query functions.
"""
from typing import Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import desc
from fastapi import HTTPException
from app.models import StockMovement, Product, RawMaterial

# ── Valid movement types (enum-like) ─────────────────────────────────
VALID_MOVEMENT_TYPES = {"purchase", "production_in", "production_out", "sale", "adjustment"}


def log_stock_movement(
    db: Session,
    company_id: str,
    *,
    product_id: Optional[str] = None,
    raw_material_id: Optional[str] = None,
    movement_type: str,
    quantity_change: float,
    reference_type: str,
    reference_id: str,
    notes: Optional[str] = None,
) -> StockMovement:
    """
    Create a stock movement record inside the CURRENT transaction.
    Must be called within the same db session/transaction as the stock update.
    Enforces XOR: exactly one of product_id or raw_material_id must be set.
    """
    # ── Validate movement type ──
    if movement_type not in VALID_MOVEMENT_TYPES:
        raise ValueError(f"Invalid movement_type '{movement_type}'. Must be one of {VALID_MOVEMENT_TYPES}")

    # ── XOR validation ──
    if product_id and raw_material_id:
        raise ValueError("Cannot set both product_id and raw_material_id")
    if not product_id and not raw_material_id:
        raise ValueError("Must set either product_id or raw_material_id")

    movement = StockMovement(
        company_id=company_id,
        product_id=product_id,
        raw_material_id=raw_material_id,
        movement_type=movement_type,
        quantity_change=quantity_change,
        reference_type=reference_type,
        reference_id=reference_id,
        notes=notes,
    )
    db.add(movement)
    # Do NOT commit — caller handles the transaction
    return movement


# ── Query functions ──────────────────────────────────────────────────

def get_movements_for_product(
    db: Session, company_id: str, product_id: str,
    skip: int = 0, limit: int = 50,
) -> dict:
    """Return stock movements for a specific finished product."""
    product = db.query(Product).filter(
        Product.id == product_id, Product.company_id == company_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    query = db.query(StockMovement).filter(
        StockMovement.company_id == company_id,
        StockMovement.product_id == product_id,
    )
    total = query.count()
    movements = query.order_by(desc(StockMovement.created_at)).offset(skip).limit(limit).all()

    return {
        "item": {"id": product.id, "name": product.name, "type": "product", "current_stock": product.stock},
        "total": total,
        "movements": [_serialize(m) for m in movements],
    }


def get_movements_for_raw_material(
    db: Session, company_id: str, raw_material_id: str,
    skip: int = 0, limit: int = 50,
) -> dict:
    """Return stock movements for a specific raw material."""
    rm = db.query(RawMaterial).filter(
        RawMaterial.id == raw_material_id, RawMaterial.company_id == company_id
    ).first()
    if not rm:
        raise HTTPException(status_code=404, detail="Raw material not found")

    query = db.query(StockMovement).filter(
        StockMovement.company_id == company_id,
        StockMovement.raw_material_id == raw_material_id,
    )
    total = query.count()
    movements = query.order_by(desc(StockMovement.created_at)).offset(skip).limit(limit).all()

    return {
        "item": {"id": rm.id, "name": rm.name, "type": "raw_material", "current_stock": rm.stock_quantity},
        "total": total,
        "movements": [_serialize(m) for m in movements],
    }


def get_all_movements(
    db: Session,
    company_id: str,
    skip: int = 0,
    limit: int = 50,
    movement_type: Optional[str] = None,
    product_id: Optional[str] = None,
    raw_material_id: Optional[str] = None,
) -> dict:
    """Return paginated stock movements with optional filters."""
    query = db.query(StockMovement).options(
        joinedload(StockMovement.product),
        joinedload(StockMovement.raw_material),
    ).filter(StockMovement.company_id == company_id)

    if movement_type:
        query = query.filter(StockMovement.movement_type == movement_type)
    if product_id:
        query = query.filter(StockMovement.product_id == product_id)
    if raw_material_id:
        query = query.filter(StockMovement.raw_material_id == raw_material_id)

    total = query.count()
    movements = query.order_by(desc(StockMovement.created_at)).offset(skip).limit(limit).all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "movements": [_serialize_with_item(m) for m in movements],
    }


# ── Serializers ──────────────────────────────────────────────────────

def _serialize(m: StockMovement) -> dict:
    return {
        "id": m.id,
        "movement_type": m.movement_type,
        "quantity_change": m.quantity_change,
        "reference_type": m.reference_type,
        "reference_id": m.reference_id,
        "notes": m.notes,
        "created_at": m.created_at.isoformat() if m.created_at else None,
    }


def _serialize_with_item(m: StockMovement) -> dict:
    d = _serialize(m)
    if m.product:
        d["item_name"] = m.product.name
        d["item_type"] = "product"
    elif m.raw_material:
        d["item_name"] = m.raw_material.name
        d["item_type"] = "raw_material"
    else:
        d["item_name"] = "Unknown"
        d["item_type"] = "unknown"
    return d
