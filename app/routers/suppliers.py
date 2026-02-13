from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import Supplier, User
from app.schemas import SupplierCreate, SupplierUpdate, SupplierOut

router = APIRouter(prefix="/api/suppliers", tags=["Suppliers"])


@router.post("/", response_model=SupplierOut, status_code=201)
def create_supplier(
    data: SupplierCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    supplier = Supplier(company_id=user.company_id, **data.model_dump())
    db.add(supplier)
    db.commit()
    db.refresh(supplier)
    return supplier


@router.get("/with-balances")
def list_suppliers_with_balances(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Suppliers with total purchased / paid / outstanding."""
    from app.ledger_service import get_suppliers_with_balances
    return get_suppliers_with_balances(db, user.company_id)


@router.get("/", response_model=list[SupplierOut])
def list_suppliers(
    search: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Supplier).filter(Supplier.company_id == user.company_id)
    if search:
        q = q.filter(Supplier.name.ilike(f"%{search}%"))
    return q.order_by(Supplier.name).all()


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(
    supplier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.company_id == user.company_id
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return s


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(
    supplier_id: str,
    data: SupplierUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.company_id == user.company_id
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{supplier_id}", status_code=204)
def delete_supplier(
    supplier_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    s = db.query(Supplier).filter(
        Supplier.id == supplier_id, Supplier.company_id == user.company_id
    ).first()
    if not s:
        raise HTTPException(status_code=404, detail="Supplier not found")
    db.delete(s)
    db.commit()
