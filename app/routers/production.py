from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import ProductionBatch, User
from app.schemas import ProductionBatchCreate, ProductionBatchOut
from app.services import create_production_batch

router = APIRouter(prefix="/api/production", tags=["Production"])


@router.post("/", response_model=ProductionBatchOut, status_code=201)
def create_batch_endpoint(
    data: ProductionBatchCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """
    Create a production batch.
    - Deducts raw material stock (prevents negative stock)
    - Increases finished product stock
    """
    return create_production_batch(db, user.company_id, data)


@router.get("/", response_model=list[ProductionBatchOut])
def list_batches(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(ProductionBatch)
        .filter(ProductionBatch.company_id == user.company_id)
        .order_by(ProductionBatch.created_at.desc())
        .all()
    )


@router.get("/{batch_id}", response_model=ProductionBatchOut)
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from fastapi import HTTPException
    b = db.query(ProductionBatch).filter(
        ProductionBatch.id == batch_id, ProductionBatch.company_id == user.company_id
    ).first()
    if not b:
        raise HTTPException(status_code=404, detail="Production batch not found")
    return b
