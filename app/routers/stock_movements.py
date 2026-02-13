from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.stock_movement_service import (
    get_movements_for_product,
    get_movements_for_raw_material,
    get_all_movements,
)

router = APIRouter(prefix="/api/stock-movements", tags=["Stock Movements"])


@router.get("/product/{product_id}")
def product_movements(
    product_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stock movement history for a specific finished product."""
    return get_movements_for_product(db, user.company_id, product_id, skip, limit)


@router.get("/raw-material/{raw_material_id}")
def raw_material_movements(
    raw_material_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Stock movement history for a specific raw material."""
    return get_movements_for_raw_material(db, user.company_id, raw_material_id, skip, limit)


@router.get("/all")
def all_movements(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    movement_type: Optional[str] = Query(None),
    product_id: Optional[str] = Query(None),
    raw_material_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All stock movements, paginated, with optional filters."""
    return get_all_movements(
        db, user.company_id, skip, limit,
        movement_type=movement_type,
        product_id=product_id,
        raw_material_id=raw_material_id,
    )
