from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app import analytics_service as svc

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/revenue-trend")
def revenue_trend(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Daily revenue for last 30 days."""
    return svc.revenue_trend(db, user.company_id)


@router.get("/top-products")
def top_products(
    limit: int = 5,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Top N products by quantity sold."""
    return svc.top_products(db, user.company_id, limit)


@router.get("/low-stock")
def low_stock(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Products and raw materials below stock thresholds."""
    return svc.low_stock(db, user.company_id)


@router.get("/production-summary")
def production_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Current month production totals."""
    return svc.production_summary(db, user.company_id)


@router.get("/profit-summary")
def profit_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Revenue, costs, and gross profit for current month."""
    return svc.profit_summary(db, user.company_id)
