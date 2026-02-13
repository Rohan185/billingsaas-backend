from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.ledger_service import get_customer_ledger, get_supplier_ledger

router = APIRouter(prefix="/api/ledger", tags=["Ledger"])


@router.get("/customer/{customer_id}")
def customer_ledger(
    customer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full ledger for a customer: summary cards + transaction list + running balance."""
    return get_customer_ledger(db, user.company_id, customer_id)


@router.get("/supplier/{supplier_id}")
def supplier_ledger(
    supplier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Full ledger for a supplier: summary cards + transaction list + running balance."""
    return get_supplier_ledger(db, user.company_id, supplier_id)

