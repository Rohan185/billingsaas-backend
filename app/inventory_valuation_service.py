"""
Inventory Valuation service.
Calculates raw material, finished goods, and total inventory value.
"""
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models import RawMaterial, Product, ProductionBatch


def get_raw_material_valuation(db: Session, company_id: str) -> dict:
    """
    Raw material valuation = stock_quantity × cost_price per material.
    """
    materials = db.query(RawMaterial).filter(
        RawMaterial.company_id == company_id,
        RawMaterial.is_active == True,
    ).order_by(RawMaterial.name).all()

    items = []
    total_value = 0.0
    for rm in materials:
        value = round(rm.stock_quantity * rm.cost_price, 2)
        total_value += value
        items.append({
            "id": rm.id,
            "name": rm.name,
            "unit": rm.unit,
            "stock_quantity": rm.stock_quantity,
            "cost_price": rm.cost_price,
            "value": value,
        })

    return {
        "type": "raw_materials",
        "total_value": round(total_value, 2),
        "item_count": len(items),
        "items": items,
    }


def get_finished_goods_valuation(db: Session, company_id: str) -> dict:
    """
    Finished goods valuation = stock × latest cost_per_unit per product.
    Falls back to 0 if no production batch exists for a product.
    """
    products = db.query(Product).filter(
        Product.company_id == company_id,
        Product.is_active == True,
    ).order_by(Product.name).all()

    items = []
    total_value = 0.0
    for prod in products:
        # Get latest production batch for this product to find cost_per_unit
        latest_batch = db.query(ProductionBatch).filter(
            ProductionBatch.company_id == company_id,
            ProductionBatch.finished_product_id == prod.id,
        ).order_by(desc(ProductionBatch.created_at)).first()

        cost_per_unit = latest_batch.cost_per_unit if latest_batch and latest_batch.cost_per_unit else 0.0
        value = round(prod.stock * cost_per_unit, 2)
        total_value += value

        items.append({
            "id": prod.id,
            "name": prod.name,
            "unit": prod.unit,
            "stock": prod.stock,
            "selling_price": prod.price,
            "cost_per_unit": cost_per_unit,
            "value": value,
        })

    return {
        "type": "finished_goods",
        "total_value": round(total_value, 2),
        "item_count": len(items),
        "items": items,
    }


def get_total_inventory_valuation(db: Session, company_id: str) -> dict:
    """
    Total inventory = raw material value + finished goods value.
    """
    rm_val = get_raw_material_valuation(db, company_id)
    fg_val = get_finished_goods_valuation(db, company_id)

    return {
        "raw_materials_value": rm_val["total_value"],
        "finished_goods_value": fg_val["total_value"],
        "total_inventory_value": round(rm_val["total_value"] + fg_val["total_value"], 2),
        "raw_materials": rm_val,
        "finished_goods": fg_val,
    }
