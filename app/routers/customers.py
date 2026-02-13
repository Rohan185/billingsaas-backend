from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Customer
from app.schemas import CustomerCreate, CustomerUpdate, CustomerOut

router = APIRouter(prefix="/api/customers", tags=["Customers"])


@router.post("/", response_model=CustomerOut)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = (
        db.query(Customer)
        .filter(Customer.company_id == user.company_id, Customer.name == data.name)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Customer with this name already exists")

    customer = Customer(company_id=user.company_id, **data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("/")
def list_customers(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from app.ledger_service import get_customers_with_balances
    return get_customers_with_balances(db, user.company_id)


@router.get("/{customer_id}", response_model=CustomerOut)
def get_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Customer).filter(
        Customer.id == customer_id, Customer.company_id == user.company_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    return c


@router.put("/{customer_id}", response_model=CustomerOut)
def update_customer(
    customer_id: str,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Customer).filter(
        Customer.id == customer_id, Customer.company_id == user.company_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/{customer_id}")
def delete_customer(
    customer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    c = db.query(Customer).filter(
        Customer.id == customer_id, Customer.company_id == user.company_id
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail="Customer not found")
    db.delete(c)
    db.commit()
    return {"detail": "Deleted"}
