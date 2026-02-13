from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.inventory_valuation_service import (
    get_raw_material_valuation,
    get_finished_goods_valuation,
    get_total_inventory_valuation,
)

router = APIRouter(prefix="/api/inventory-valuation", tags=["Inventory Valuation"])


@router.get("/raw-materials")
def raw_material_valuation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Valuation of all raw materials (stock × cost_price)."""
    return get_raw_material_valuation(db, user.company_id)


@router.get("/finished-goods")
def finished_goods_valuation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Valuation of all finished products (stock × latest cost_per_unit)."""
    return get_finished_goods_valuation(db, user.company_id)


@router.get("/total")
def total_valuation(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Total inventory value = raw materials + finished goods."""
    return get_total_inventory_valuation(db, user.company_id)
