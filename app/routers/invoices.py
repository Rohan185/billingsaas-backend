from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import User, Product, Invoice, InvoiceItem, Customer
from app.schemas import InvoiceCreate, InvoiceOut
from app.dependencies import get_current_user

router = APIRouter(prefix="/api/invoices", tags=["Invoices"])


def _next_invoice_number(db: Session, company_id: str) -> str:
    count = db.query(func.count(Invoice.id)).filter(
        Invoice.company_id == company_id
    ).scalar() or 0
    return f"INV-{count + 1:05d}"


@router.post("/", response_model=InvoiceOut, status_code=201)
def create_invoice(
    payload: InvoiceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not payload.items:
        raise HTTPException(status_code=400, detail="Invoice must have at least one item")

    # Resolve customer_id
    customer_id = getattr(payload, "customer_id", None)
    customer_name = payload.customer_name
    if customer_id:
        cust = db.query(Customer).filter(
            Customer.id == customer_id, Customer.company_id == user.company_id
        ).first()
        if not cust:
            raise HTTPException(status_code=404, detail="Customer not found")
        customer_name = cust.name  # denormalized cache

    invoice = Invoice(
        company_id=user.company_id,
        customer_id=customer_id,
        invoice_number=_next_invoice_number(db, user.company_id),
        customer_name=customer_name,
        customer_email=payload.customer_email,
        customer_phone=payload.customer_phone,
        tax_percent=payload.tax_percent,
        discount=payload.discount,
        notes=payload.notes,
    )
    db.add(invoice)
    db.flush()

    subtotal = 0.0
    for item in payload.items:
        product = db.query(Product).filter(
            Product.id == item.product_id,
            Product.company_id == user.company_id,
        ).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for '{product.name}'. Available: {product.stock}",
            )

        line_total = product.price * item.quantity
        subtotal += line_total

        invoice_item = InvoiceItem(
            invoice_id=invoice.id,
            product_id=product.id,
            product_name=product.name,
            quantity=item.quantity,
            unit_price=product.price,
            total_price=line_total,
        )
        db.add(invoice_item)

        # Deduct stock
        product.stock -= item.quantity

        # ── Log stock movement (same transaction) ──
        from app.stock_movement_service import log_stock_movement
        log_stock_movement(
            db, user.company_id,
            product_id=product.id,
            movement_type="sale",
            quantity_change=-item.quantity,
            reference_type="invoice",
            reference_id=invoice.id,
            notes=f"Sold via {invoice.invoice_number}",
        )

    tax_amount = subtotal * (payload.tax_percent / 100)
    total = subtotal + tax_amount - payload.discount

    invoice.subtotal = subtotal
    invoice.tax_amount = tax_amount
    invoice.total = total

    db.commit()
    db.refresh(invoice)
    return invoice


@router.get("/", response_model=list[InvoiceOut])
def list_invoices(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: str = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Invoice).filter(Invoice.company_id == user.company_id)
    if status:
        query = query.filter(Invoice.status == status)
    return query.order_by(Invoice.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{invoice_id}", response_model=InvoiceOut)
def get_invoice(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.company_id == user.company_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return invoice


@router.patch("/{invoice_id}/status")
def update_invoice_status(
    invoice_id: str,
    new_status: str = Query(..., pattern="^(unpaid|partially_paid|paid|cancelled)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.company_id == user.company_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.status = new_status
    db.commit()
    return {"detail": f"Invoice status updated to '{new_status}'"}


@router.get("/{invoice_id}/pdf")
def download_invoice_pdf(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Generate and download a professional GST-compliant invoice PDF."""
    from fastapi.responses import StreamingResponse
    from app.invoice_pdf_service import generate_invoice_pdf

    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.company_id == user.company_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    buffer = generate_invoice_pdf(db, invoice)

    filename = f"{invoice.invoice_number}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.post("/{invoice_id}/send-whatsapp")
async def send_invoice_whatsapp(
    invoice_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send invoice PDF to customer via WhatsApp."""
    from app.invoice_pdf_service import generate_invoice_pdf
    from app.whatsapp_service import send_whatsapp_document

    invoice = db.query(Invoice).filter(
        Invoice.id == invoice_id, Invoice.company_id == user.company_id
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if not invoice.customer:
        raise HTTPException(status_code=400, detail="Invoice has no linked customer")

    phone = invoice.customer.phone
    if not phone:
        raise HTTPException(
            status_code=400,
            detail="Customer does not have a phone number"
        )

    # Ensure phone has country code
    if not phone.startswith("91"):
        phone = f"91{phone}"

    pdf_buffer = generate_invoice_pdf(db, invoice)

    success = await send_whatsapp_document(
        to_number=phone,
        file_bytes=pdf_buffer.getvalue(),
        filename=f"{invoice.invoice_number}.pdf",
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send invoice via WhatsApp"
        )

    return {"message": "Invoice sent via WhatsApp successfully"}
