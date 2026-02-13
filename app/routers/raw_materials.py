from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import RawMaterial, User
from app.schemas import RawMaterialCreate, RawMaterialUpdate, RawMaterialOut

router = APIRouter(prefix="/api/raw-materials", tags=["Raw Materials"])


@router.post("/", response_model=RawMaterialOut, status_code=201)
def create_raw_material(
    data: RawMaterialCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rm = RawMaterial(company_id=user.company_id, **data.model_dump())
    db.add(rm)
    db.commit()
    db.refresh(rm)
    return rm


@router.get("/", response_model=list[RawMaterialOut])
def list_raw_materials(
    search: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(RawMaterial).filter(RawMaterial.company_id == user.company_id)
    if search:
        q = q.filter(RawMaterial.name.ilike(f"%{search}%"))
    return q.order_by(RawMaterial.name).all()


@router.get("/{rm_id}", response_model=RawMaterialOut)
def get_raw_material(
    rm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rm = db.query(RawMaterial).filter(
        RawMaterial.id == rm_id, RawMaterial.company_id == user.company_id
    ).first()
    if not rm:
        raise HTTPException(status_code=404, detail="Raw material not found")
    return rm


@router.put("/{rm_id}", response_model=RawMaterialOut)
def update_raw_material(
    rm_id: str,
    data: RawMaterialUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rm = db.query(RawMaterial).filter(
        RawMaterial.id == rm_id, RawMaterial.company_id == user.company_id
    ).first()
    if not rm:
        raise HTTPException(status_code=404, detail="Raw material not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(rm, k, v)
    db.commit()
    db.refresh(rm)
    return rm


@router.delete("/{rm_id}", status_code=204)
def delete_raw_material(
    rm_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rm = db.query(RawMaterial).filter(
        RawMaterial.id == rm_id, RawMaterial.company_id == user.company_id
    ).first()
    if not rm:
        raise HTTPException(status_code=404, detail="Raw material not found")
    db.delete(rm)
    db.commit()
