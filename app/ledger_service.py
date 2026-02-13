"""
Ledger service — customer + supplier ledger queries and payment processing.
All operations are company-isolated.
"""
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import Customer, Invoice, Payment, Supplier, Purchase
from app.schemas import PaymentCreate, SupplierPaymentCreate


def get_customers_with_balances(db: Session, company_id: str) -> list[dict]:
    """All customers with total invoiced, total paid, and outstanding."""
    customers = (
        db.query(Customer)
        .filter(Customer.company_id == company_id)
        .order_by(Customer.name)
        .all()
    )
    result = []
    for c in customers:
        invoiced = (
            db.query(func.coalesce(func.sum(Invoice.total), 0))
            .filter(Invoice.customer_id == c.id, Invoice.status != "cancelled")
            .scalar()
        )
        paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.customer_id == c.id, Payment.payment_type == "received")
            .scalar()
        )
        refunded = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.customer_id == c.id, Payment.payment_type == "refund")
            .scalar()
        )
        total_paid = float(paid) - float(refunded)
        total_invoiced = float(invoiced)
        result.append({
            "id": c.id,
            "company_id": c.company_id,
            "name": c.name,
            "phone": c.phone,
            "email": c.email,
            "address": c.address,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding": total_invoiced - total_paid,
        })
    return result


def get_customer_ledger(db: Session, company_id: str, customer_id: str) -> dict:
    """Full ledger for one customer: summary + interleaved transactions with running balance."""
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.company_id == company_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    invoices = (
        db.query(Invoice)
        .filter(Invoice.customer_id == customer_id, Invoice.status != "cancelled")
        .order_by(Invoice.created_at)
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.customer_id == customer_id)
        .order_by(Payment.created_at)
        .all()
    )

    transactions = []
    for inv in invoices:
        transactions.append({
            "date": inv.created_at.isoformat(),
            "type": "invoice",
            "reference": inv.invoice_number,
            "invoice_id": inv.id,
            "debit": inv.total,
            "credit": 0,
            "sort_key": inv.created_at,
        })
    for pmt in payments:
        transactions.append({
            "date": pmt.created_at.isoformat(),
            "type": "payment" if pmt.payment_type == "received" else "refund",
            "reference": f"PMT-{pmt.id[:8].upper()}",
            "invoice_id": pmt.invoice_id,
            "debit": 0 if pmt.payment_type == "received" else pmt.amount,
            "credit": pmt.amount if pmt.payment_type == "received" else 0,
            "sort_key": pmt.created_at,
        })

    transactions.sort(key=lambda t: t["sort_key"])
    balance = 0
    for t in transactions:
        balance += t["debit"] - t["credit"]
        t["running_balance"] = balance
        del t["sort_key"]

    total_invoiced = sum(t["debit"] for t in transactions if t["type"] == "invoice")
    total_paid = sum(t["credit"] for t in transactions if t["type"] == "payment")
    total_refunded = sum(t["debit"] for t in transactions if t["type"] == "refund")

    return {
        "customer": {
            "id": customer.id,
            "name": customer.name,
            "phone": customer.phone,
            "email": customer.email,
        },
        "summary": {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "total_refunded": total_refunded,
            "outstanding": total_invoiced - total_paid + total_refunded,
        },
        "transactions": transactions,
        "unpaid_invoices": [
            {"id": inv.id, "invoice_number": inv.invoice_number, "total": inv.total, "status": inv.status}
            for inv in invoices if inv.status in ("unpaid", "partially_paid")
        ],
    }


def _update_invoice_status(db: Session, invoice_id: str):
    """Recalculate and update invoice status based on payments."""
    invoice = db.query(Invoice).filter(Invoice.id == invoice_id).first()
    if not invoice:
        return
    total_received = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.invoice_id == invoice_id, Payment.payment_type == "received")
        .scalar()
    )
    total_refunded = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.invoice_id == invoice_id, Payment.payment_type == "refund")
        .scalar()
    )
    net_paid = float(total_received) - float(total_refunded)
    if net_paid >= invoice.total:
        invoice.status = "paid"
    elif net_paid > 0:
        invoice.status = "partially_paid"
    else:
        invoice.status = "unpaid"
    db.flush()


def receive_payment(db: Session, company_id: str, data: PaymentCreate) -> Payment:
    """Receive a payment from a customer. Validates ownership and prevents overpayment."""
    customer = (
        db.query(Customer)
        .filter(Customer.id == data.customer_id, Customer.company_id == company_id)
        .first()
    )
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if data.invoice_id:
        invoice = (
            db.query(Invoice)
            .filter(Invoice.id == data.invoice_id, Invoice.company_id == company_id)
            .first()
        )
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if invoice.customer_id and invoice.customer_id != data.customer_id:
            raise HTTPException(status_code=400, detail="Invoice does not belong to this customer")

        already_paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == data.invoice_id, Payment.payment_type == "received")
            .scalar()
        )
        already_refunded = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == data.invoice_id, Payment.payment_type == "refund")
            .scalar()
        )
        net_paid = float(already_paid) - float(already_refunded)

        if data.payment_type == "received" and (net_paid + data.amount) > invoice.total:
            remaining = invoice.total - net_paid
            raise HTTPException(
                status_code=400,
                detail=f"Overpayment! Invoice total is ₹{invoice.total:.2f}, "
                       f"already paid ₹{net_paid:.2f}, max payable ₹{remaining:.2f}",
            )

    payment = Payment(
        company_id=company_id,
        customer_id=data.customer_id,
        invoice_id=data.invoice_id,
        amount=data.amount,
        payment_type=data.payment_type,
        payment_method=data.payment_method,
        notes=data.notes,
    )
    db.add(payment)
    db.flush()
    if data.invoice_id:
        _update_invoice_status(db, data.invoice_id)
    db.commit()
    db.refresh(payment)
    return payment


# ═══════════════════════════════════════════════════════════════════════
# SUPPLIER LEDGER
# ═══════════════════════════════════════════════════════════════════════

def get_suppliers_with_balances(db: Session, company_id: str) -> list[dict]:
    """All suppliers with total purchased, total paid, and outstanding payable."""
    suppliers = (
        db.query(Supplier)
        .filter(Supplier.company_id == company_id)
        .order_by(Supplier.name)
        .all()
    )
    result = []
    for s in suppliers:
        purchased = (
            db.query(func.coalesce(func.sum(Purchase.total_amount), 0))
            .filter(Purchase.supplier_id == s.id)
            .scalar()
        )
        paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.supplier_id == s.id, Payment.payment_type == "paid")
            .scalar()
        )
        refunded = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.supplier_id == s.id, Payment.payment_type == "supplier_refund")
            .scalar()
        )
        total_paid = float(paid) - float(refunded)
        total_purchased = float(purchased)
        result.append({
            "id": s.id,
            "company_id": s.company_id,
            "name": s.name,
            "phone": s.phone,
            "email": s.email,
            "address": s.address,
            "is_active": s.is_active,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "total_purchased": total_purchased,
            "total_paid": total_paid,
            "outstanding": total_purchased - total_paid,
        })
    return result


def get_supplier_ledger(db: Session, company_id: str, supplier_id: str) -> dict:
    """Full ledger for one supplier: summary + interleaved transactions with running balance."""
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == supplier_id, Supplier.company_id == company_id)
        .first()
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    purchases = (
        db.query(Purchase)
        .filter(Purchase.supplier_id == supplier_id)
        .order_by(Purchase.created_at)
        .all()
    )
    payments = (
        db.query(Payment)
        .filter(Payment.supplier_id == supplier_id)
        .order_by(Payment.created_at)
        .all()
    )

    transactions = []
    for pur in purchases:
        transactions.append({
            "date": pur.created_at.isoformat(),
            "type": "purchase",
            "reference": pur.purchase_number,
            "purchase_id": pur.id,
            "debit": pur.total_amount,
            "credit": 0,
            "sort_key": pur.created_at,
        })
    for pmt in payments:
        transactions.append({
            "date": pmt.created_at.isoformat(),
            "type": "payment" if pmt.payment_type == "paid" else "refund",
            "reference": f"PAY-{pmt.id[:8].upper()}",
            "purchase_id": pmt.purchase_id,
            "debit": 0 if pmt.payment_type == "paid" else pmt.amount,
            "credit": pmt.amount if pmt.payment_type == "paid" else 0,
            "sort_key": pmt.created_at,
        })

    transactions.sort(key=lambda t: t["sort_key"])
    balance = 0
    for t in transactions:
        balance += t["debit"] - t["credit"]
        t["running_balance"] = balance
        del t["sort_key"]

    total_purchased = sum(t["debit"] for t in transactions if t["type"] == "purchase")
    total_paid = sum(t["credit"] for t in transactions if t["type"] == "payment")
    total_refunded = sum(t["debit"] for t in transactions if t["type"] == "refund")

    return {
        "supplier": {
            "id": supplier.id,
            "name": supplier.name,
            "phone": supplier.phone,
            "email": supplier.email,
        },
        "summary": {
            "total_purchased": total_purchased,
            "total_paid": total_paid,
            "total_refunded": total_refunded,
            "outstanding": total_purchased - total_paid + total_refunded,
        },
        "transactions": transactions,
        "unpaid_purchases": [
            {"id": p.id, "purchase_number": p.purchase_number, "total_amount": p.total_amount, "status": getattr(p, "status", "unpaid")}
            for p in purchases if getattr(p, "status", "unpaid") in ("unpaid", "partially_paid")
        ],
    }


def _update_purchase_status(db: Session, purchase_id: str):
    """Recalculate and update purchase status based on payments."""
    purchase = db.query(Purchase).filter(Purchase.id == purchase_id).first()
    if not purchase:
        return
    total_paid = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.purchase_id == purchase_id, Payment.payment_type == "paid")
        .scalar()
    )
    total_refunded = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.purchase_id == purchase_id, Payment.payment_type == "supplier_refund")
        .scalar()
    )
    net_paid = float(total_paid) - float(total_refunded)
    if net_paid >= purchase.total_amount:
        purchase.status = "paid"
    elif net_paid > 0:
        purchase.status = "partially_paid"
    else:
        purchase.status = "unpaid"
    db.flush()


def pay_supplier(db: Session, company_id: str, data: SupplierPaymentCreate) -> Payment:
    """Pay a supplier. Validates ownership and prevents overpayment."""
    supplier = (
        db.query(Supplier)
        .filter(Supplier.id == data.supplier_id, Supplier.company_id == company_id)
        .first()
    )
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    if data.purchase_id:
        purchase = (
            db.query(Purchase)
            .filter(Purchase.id == data.purchase_id, Purchase.company_id == company_id)
            .first()
        )
        if not purchase:
            raise HTTPException(status_code=404, detail="Purchase not found")
        if purchase.supplier_id != data.supplier_id:
            raise HTTPException(status_code=400, detail="Purchase does not belong to this supplier")

        already_paid = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.purchase_id == data.purchase_id, Payment.payment_type == "paid")
            .scalar()
        )
        already_refunded = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.purchase_id == data.purchase_id, Payment.payment_type == "supplier_refund")
            .scalar()
        )
        net_paid = float(already_paid) - float(already_refunded)

        if (net_paid + data.amount) > purchase.total_amount:
            remaining = purchase.total_amount - net_paid
            raise HTTPException(
                status_code=400,
                detail=f"Overpayment! Purchase total is ₹{purchase.total_amount:.2f}, "
                       f"already paid ₹{net_paid:.2f}, max payable ₹{remaining:.2f}",
            )

    payment = Payment(
        company_id=company_id,
        supplier_id=data.supplier_id,
        purchase_id=data.purchase_id,
        amount=data.amount,
        payment_type="paid",
        payment_method=data.payment_method,
        notes=data.notes,
    )
    db.add(payment)
    db.flush()
    if data.purchase_id:
        _update_purchase_status(db, data.purchase_id)
    db.commit()
    db.refresh(payment)
    return payment

