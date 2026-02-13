from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Purchase, User
from app.schemas import PurchaseCreate, PurchaseOut
from app.services import create_purchase

router = APIRouter(prefix="/api/purchases", tags=["Purchases"])


@router.post("/", response_model=PurchaseOut, status_code=201)
def create_purchase_endpoint(
    data: PurchaseCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a purchase order. Automatically increases raw material stock."""
    return create_purchase(db, user.company_id, data)


@router.get("/", response_model=list[PurchaseOut])
def list_purchases(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Purchase)
        .filter(Purchase.company_id == user.company_id)
        .order_by(Purchase.created_at.desc())
        .all()
    )


@router.get("/{purchase_id}", response_model=PurchaseOut)
def get_purchase(
    purchase_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from fastapi import HTTPException
    p = db.query(Purchase).filter(
        Purchase.id == purchase_id, Purchase.company_id == user.company_id
    ).first()
    if not p:
        raise HTTPException(status_code=404, detail="Purchase not found")
    return p
