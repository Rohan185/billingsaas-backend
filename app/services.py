"""
Service layer for manufacturing business logic.
Handles stock updates, validations, and complex create operations.
"""
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import (
    RawMaterial, Purchase, PurchaseItem,
    ProductionBatch, ProductionItem, Product, Supplier
)
from app.stock_movement_service import log_stock_movement


# ── Purchase Service ─────────────────────────────────────────────────

def create_purchase(db: Session, company_id: str, data) -> Purchase:
    """
    Create a purchase and automatically increase raw material stock.
    Logs stock movements inside the same transaction.
    """
    # Validate supplier belongs to company
    supplier = db.query(Supplier).filter(
        Supplier.id == data.supplier_id,
        Supplier.company_id == company_id
    ).first()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    if not data.items:
        raise HTTPException(status_code=422, detail="At least one item is required")

    # Generate purchase number
    count = db.query(Purchase).filter(Purchase.company_id == company_id).count()
    purchase_number = f"PO-{count + 1:05d}"

    total_amount = 0.0
    purchase_items = []

    purchase = Purchase(
        company_id=company_id,
        supplier_id=data.supplier_id,
        purchase_number=purchase_number,
        total_amount=0,
        notes=data.notes,
    )
    db.add(purchase)
    db.flush()  # get purchase.id for reference

    for item in data.items:
        # Validate raw material belongs to company
        raw_mat = db.query(RawMaterial).filter(
            RawMaterial.id == item.raw_material_id,
            RawMaterial.company_id == company_id
        ).first()
        if not raw_mat:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {item.raw_material_id} not found"
            )

        line_total = item.quantity * item.cost_price
        total_amount += line_total

        purchase_items.append(PurchaseItem(
            purchase_id=purchase.id,
            raw_material_id=raw_mat.id,
            raw_material_name=raw_mat.name,
            quantity=item.quantity,
            cost_price=item.cost_price,
            total=line_total,
        ))

        # ── Increase raw material stock ──
        raw_mat.stock_quantity += item.quantity
        # Update cost price to latest purchase price
        raw_mat.cost_price = item.cost_price

        # ── Log stock movement (same transaction) ──
        log_stock_movement(
            db, company_id,
            raw_material_id=raw_mat.id,
            movement_type="purchase",
            quantity_change=+item.quantity,
            reference_type="purchase",
            reference_id=purchase.id,
            notes=f"Purchase {purchase_number} from {supplier.name}",
        )

    purchase.total_amount = total_amount
    for pi in purchase_items:
        db.add(pi)

    db.commit()
    db.refresh(purchase)
    return purchase


# ── Production Service ───────────────────────────────────────────────

def create_production_batch(db: Session, company_id: str, data) -> ProductionBatch:
    """
    Create a production batch:
    - Deduct raw material stock (with negative-stock prevention)
    - Increase finished product stock
    - Log all stock movements inside the same transaction
    """
    # Validate finished product belongs to company
    product = db.query(Product).filter(
        Product.id == data.finished_product_id,
        Product.company_id == company_id
    ).first()
    if not product:
        raise HTTPException(status_code=404, detail="Finished product not found")

    if not data.items:
        raise HTTPException(status_code=422, detail="At least one raw material item is required")

    if data.quantity_produced <= 0:
        raise HTTPException(status_code=422, detail="Quantity produced must be positive")

    # Generate batch number
    count = db.query(ProductionBatch).filter(
        ProductionBatch.company_id == company_id
    ).count()
    batch_number = f"BATCH-{count + 1:05d}"

    batch = ProductionBatch(
        company_id=company_id,
        batch_number=batch_number,
        finished_product_id=data.finished_product_id,
        quantity_produced=data.quantity_produced,
        total_cost=0,
        notes=data.notes,
    )
    db.add(batch)
    db.flush()  # get batch.id for reference

    total_cost = 0.0

    for item in data.items:
        # Validate raw material belongs to company
        raw_mat = db.query(RawMaterial).filter(
            RawMaterial.id == item.raw_material_id,
            RawMaterial.company_id == company_id
        ).first()
        if not raw_mat:
            raise HTTPException(
                status_code=404,
                detail=f"Raw material {item.raw_material_id} not found"
            )

        # ── Prevent negative stock ──
        if raw_mat.stock_quantity < item.quantity_used:
            raise HTTPException(
                status_code=422,
                detail=f"Insufficient stock for '{raw_mat.name}': "
                       f"available={raw_mat.stock_quantity}, required={item.quantity_used}"
            )

        # Deduct raw material stock
        raw_mat.stock_quantity -= item.quantity_used
        item_cost = item.quantity_used * raw_mat.cost_price
        total_cost += item_cost

        db.add(ProductionItem(
            production_batch_id=batch.id,
            raw_material_id=raw_mat.id,
            raw_material_name=raw_mat.name,
            quantity_used=item.quantity_used,
        ))

        # ── Log raw material deduction (same transaction) ──
        log_stock_movement(
            db, company_id,
            raw_material_id=raw_mat.id,
            movement_type="production_out",
            quantity_change=-item.quantity_used,
            reference_type="production_batch",
            reference_id=batch.id,
            notes=f"Used in {batch_number} for {product.name}",
        )

    # ── Increase finished product stock ──
    product.stock += data.quantity_produced
    batch.total_cost = total_cost
    batch.cost_per_unit = round(total_cost / data.quantity_produced, 2)

    # ── Log finished product addition (same transaction) ──
    log_stock_movement(
        db, company_id,
        product_id=product.id,
        movement_type="production_in",
        quantity_change=+data.quantity_produced,
        reference_type="production_batch",
        reference_id=batch.id,
        notes=f"Produced in {batch_number}",
    )

    db.commit()
    db.refresh(batch)
    return batch

