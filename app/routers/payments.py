from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import PaymentCreate, PaymentOut, SupplierPaymentCreate
from app.ledger_service import receive_payment, pay_supplier

router = APIRouter(prefix="/api/payments", tags=["Payments"])


@router.post("/receive", response_model=PaymentOut)
def receive_payment_endpoint(
    data: PaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Receive a payment from a customer against an invoice."""
    return receive_payment(db, user.company_id, data)


@router.post("/pay", response_model=PaymentOut)
def pay_supplier_endpoint(
    data: SupplierPaymentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Pay a supplier against a purchase order."""
    return pay_supplier(db, user.company_id, data)

