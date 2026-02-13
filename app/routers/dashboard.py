from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from app.database import get_db
from app.models import User, Invoice, Product
from app.schemas import DashboardSummary, LowStockItem
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])

LOW_STOCK_THRESHOLD = 10


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    company_filter = Invoice.company_id == user.company_id

    # Today revenue
    today_result = db.query(
        func.coalesce(func.sum(Invoice.total), 0),
        func.count(Invoice.id),
    ).filter(
        and_(company_filter, Invoice.created_at >= today_start, Invoice.status != "cancelled")
    ).first()
    today_revenue = float(today_result[0])
    today_count = today_result[1]

    # Monthly revenue
    month_result = db.query(
        func.coalesce(func.sum(Invoice.total), 0),
        func.count(Invoice.id),
    ).filter(
        and_(company_filter, Invoice.created_at >= month_start, Invoice.status != "cancelled")
    ).first()
    monthly_revenue = float(month_result[0])
    month_count = month_result[1]

    # Low stock items
    low_stock = (
        db.query(Product)
        .filter(
            Product.company_id == user.company_id,
            Product.stock <= LOW_STOCK_THRESHOLD,
            Product.is_active == True,
        )
        .order_by(Product.stock.asc())
        .limit(20)
        .all()
    )

    return DashboardSummary(
        today_revenue=today_revenue,
        monthly_revenue=monthly_revenue,
        total_invoices_today=today_count,
        total_invoices_month=month_count,
        low_stock_items=[
            LowStockItem(id=p.id, name=p.name, stock=p.stock, unit=p.unit)
            for p in low_stock
        ],
    )
