"""
WhatsApp invoice commands — detect natural-language invoice requests
and generate + send PDF invoices via WhatsApp.
"""
import re
import logging
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import Invoice, Customer
from app.invoice_pdf_service import generate_invoice_pdf
from app.whatsapp_service import send_whatsapp_document

logger = logging.getLogger("whatsapp_invoice")

# ── In-memory store: sender → last sent invoice ID ──────────────────
last_sent_invoice_by_user: dict[str, str] = {}


# ── Pattern matching ────────────────────────────────────────────────
# English: "send last invoice", "last bill", "last invoice"
_RE_LAST_INVOICE = re.compile(
    r"^(?:send\s+)?(?:last|latest|recent)\s+(?:invoice|bill)$", re.IGNORECASE
)

# English: "send invoice to <name>" / "send <name> invoice" / "send <name> bill"
_RE_SEND_TO = re.compile(
    r"^send\s+(?:invoice|bill)\s+to\s+(.+)$", re.IGNORECASE
)
_RE_SEND_NAME = re.compile(
    r"^send\s+(.+?)\s+(?:invoice|bill)$", re.IGNORECASE
)

# Hindi: "<name> ka bill bhejo" / "<name> ko invoice bhejo"
_RE_HINDI = re.compile(
    r"^(.+?)\s+(?:ka|ko|ki)\s+(?:bill|invoice)\s+(?:bhejo|bhej|send\s*karo)$",
    re.IGNORECASE,
)


def _extract_customer_name(text: str) -> str | None:
    """Try all patterns to extract a customer name. Returns None if no match."""
    cmd = text.strip()
    m = _RE_SEND_TO.match(cmd)
    if m:
        return m.group(1).strip()
    m = _RE_SEND_NAME.match(cmd)
    if m:
        return m.group(1).strip()
    m = _RE_HINDI.match(cmd)
    if m:
        return m.group(1).strip()
    return None


def is_invoice_command(text: str) -> bool:
    """Check if message is an invoice-related command."""
    cmd = text.strip()
    if _RE_LAST_INVOICE.match(cmd):
        return True
    if _extract_customer_name(cmd) is not None:
        return True
    if cmd.lower() == "copy":
        return True
    return False


async def handle_invoice_command(
    text: str, sender: str, company_id: str, db: Session
) -> str:
    """
    Process invoice WhatsApp commands. Returns reply text.
    """
    cmd = text.strip()

    # ── "copy" — resend last invoice to owner ────────────────────────
    if cmd.lower() == "copy":
        return await _handle_copy(sender, company_id, db)

    # ── "send last invoice" / "last bill" ────────────────────────────
    if _RE_LAST_INVOICE.match(cmd):
        return await _handle_last_invoice(sender, company_id, db)

    # ── Name-based: "send invoice to X", "send X invoice", "X ka bill bhejo"
    name = _extract_customer_name(cmd)
    if name:
        return await _handle_send_to(sender, name, company_id, db)

    return "❌ Could not understand invoice command."


# ── Handlers ────────────────────────────────────────────────────────

async def _handle_last_invoice(
    sender: str, company_id: str, db: Session
) -> str:
    """Fetch the most recent invoice that has a customer, send to customer."""
    invoice = (
        db.query(Invoice)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status != "cancelled",
            Invoice.customer_id.isnot(None),
        )
        .order_by(Invoice.created_at.desc())
        .first()
    )
    if not invoice:
        return "❌ No invoices found."

    return await _send_invoice_pdf(invoice, sender, db)


async def _handle_send_to(
    sender: str, customer_name: str, company_id: str, db: Session
) -> str:
    """Find latest invoice for a customer name, send to customer."""
    invoice = (
        db.query(Invoice)
        .join(Customer, Customer.id == Invoice.customer_id)
        .filter(
            Invoice.company_id == company_id,
            Invoice.status != "cancelled",
            func.lower(Customer.name).contains(customer_name.lower()),
        )
        .order_by(Invoice.created_at.desc())
        .first()
    )
    if not invoice:
        return f"❌ No invoice found for customer '{customer_name}'."

    return await _send_invoice_pdf(invoice, sender, db)


async def _handle_copy(sender: str, company_id: str, db: Session) -> str:
    """Send a copy of the last-sent invoice to the owner."""
    invoice_id = last_sent_invoice_by_user.get(sender)
    if not invoice_id:
        return "❌ No recent invoice found. Send an invoice first."

    invoice = (
        db.query(Invoice)
        .filter(Invoice.id == invoice_id, Invoice.company_id == company_id)
        .first()
    )
    if not invoice:
        return "❌ Invoice no longer exists."

    try:
        pdf_buffer = generate_invoice_pdf(db, invoice)
        filename = f"{invoice.invoice_number}.pdf"

        success = await send_whatsapp_document(
            to_number=sender,
            file_bytes=pdf_buffer.getvalue(),
            filename=filename,
        )
        if success:
            return "📎 Invoice copy sent to you."
        else:
            return "⚠️ Failed to send invoice copy. Try again."
    except Exception as e:
        logger.error(f"Copy send failed: {e}")
        return "⚠️ Something went wrong sending the copy."


# ── Core PDF send logic ─────────────────────────────────────────────

async def _send_invoice_pdf(
    invoice: Invoice, sender: str, db: Session
) -> str:
    """Generate PDF, send to customer, store for 'copy' command."""
    customer = invoice.customer
    if not customer:
        return "❌ Invoice has no linked customer."

    phone = customer.phone
    if not phone:
        return "❌ Customer phone number missing."

    # Ensure country code
    if not phone.startswith("91"):
        phone = f"91{phone}"

    try:
        pdf_buffer = generate_invoice_pdf(db, invoice)
        filename = f"{invoice.invoice_number}.pdf"

        success = await send_whatsapp_document(
            to_number=phone,
            file_bytes=pdf_buffer.getvalue(),
            filename=filename,
        )

        if not success:
            return "⚠️ Failed to send invoice. Try again."

        # Store for "copy" command
        last_sent_invoice_by_user[sender] = invoice.id

        logger.info(
            f"Invoice {invoice.invoice_number} sent to "
            f"{customer.name} ({phone})"
        )

        return (
            f"✅ Invoice {invoice.invoice_number} sent to {customer.name}.\n"
            f"Reply 'copy' if you want it."
        )

    except Exception as e:
        logger.error(f"Invoice PDF send failed: {e}")
        return "⚠️ Something went wrong. Please try again."
