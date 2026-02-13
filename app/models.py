import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime,
    ForeignKey, Text, UniqueConstraint
)
from sqlalchemy.orm import relationship
from app.database import Base


def utcnow():
    return datetime.now(timezone.utc)


def generate_uuid():
    return str(uuid.uuid4())


# ── Company ──────────────────────────────────────────────────────────
class Company(Base):
    __tablename__ = "companies"

    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String(255), nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    gst_number = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    users = relationship("User", back_populates="company", cascade="all, delete-orphan")
    products = relationship("Product", back_populates="company", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="company", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="company", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="company", cascade="all, delete-orphan")
    raw_materials = relationship("RawMaterial", back_populates="company", cascade="all, delete-orphan")
    suppliers = relationship("Supplier", back_populates="company", cascade="all, delete-orphan")
    purchases = relationship("Purchase", back_populates="company", cascade="all, delete-orphan")
    production_batches = relationship("ProductionBatch", back_populates="company", cascade="all, delete-orphan")
    stock_movements = relationship("StockMovement", back_populates="company", cascade="all, delete-orphan")


# ── User ─────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    role = Column(String(20), default="owner")  # owner | staff
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="users")


# ── Product (finished goods) ─────────────────────────────────────────
class Product(Base):
    __tablename__ = "products"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    unit = Column(String(50), default="pcs")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    company = relationship("Company", back_populates="products")
    invoice_items = relationship("InvoiceItem", back_populates="product")
    production_batches = relationship("ProductionBatch", back_populates="finished_product")


# ── Customer ─────────────────────────────────────────────────────────
class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_customer_company_name"),
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="customers")
    invoices = relationship("Invoice", back_populates="customer")
    payments = relationship("Payment", back_populates="customer")


# ── Invoice ──────────────────────────────────────────────────────────
class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True, index=True)
    invoice_number = Column(String(50), nullable=False, index=True)
    customer_name = Column(String(255), nullable=False)  # denormalized cache
    customer_email = Column(String(255), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    subtotal = Column(Float, default=0.0)
    tax_percent = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    status = Column(String(20), default="unpaid")  # unpaid | partially_paid | paid | cancelled
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice")


# ── Invoice Item ─────────────────────────────────────────────────────
class InvoiceItem(Base):
    __tablename__ = "invoice_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    invoice_id = Column(String, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(String, ForeignKey("products.id"), nullable=False)
    product_name = Column(String(255), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_price = Column(Float, nullable=False)

    invoice = relationship("Invoice", back_populates="items")
    product = relationship("Product", back_populates="invoice_items")


# ═══════════════════════════════════════════════════════════════════════
# MANUFACTURING MODULE
# ═══════════════════════════════════════════════════════════════════════

# ── Raw Material ─────────────────────────────────────────────────────
class RawMaterial(Base):
    __tablename__ = "raw_materials"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    unit = Column(String(50), default="kg")
    stock_quantity = Column(Float, nullable=False, default=0)
    cost_price = Column(Float, nullable=False, default=0)
    low_stock_threshold = Column(Float, default=10)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    company = relationship("Company", back_populates="raw_materials")
    purchase_items = relationship("PurchaseItem", back_populates="raw_material")
    production_items = relationship("ProductionItem", back_populates="raw_material")


# ── Supplier ─────────────────────────────────────────────────────────
class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="suppliers")
    purchases = relationship("Purchase", back_populates="supplier")
    payments = relationship("Payment", back_populates="supplier")


# ── Purchase ─────────────────────────────────────────────────────────
class Purchase(Base):
    __tablename__ = "purchases"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=False)
    purchase_number = Column(String(50), nullable=False, index=True)
    total_amount = Column(Float, default=0.0)
    status = Column(String(20), default="unpaid")  # unpaid | partially_paid | paid
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="purchases")
    supplier = relationship("Supplier", back_populates="purchases")
    items = relationship("PurchaseItem", back_populates="purchase", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="purchase")


# ── Purchase Item ────────────────────────────────────────────────────
class PurchaseItem(Base):
    __tablename__ = "purchase_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    purchase_id = Column(String, ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False)
    raw_material_id = Column(String, ForeignKey("raw_materials.id"), nullable=False)
    raw_material_name = Column(String(255), nullable=False)
    quantity = Column(Float, nullable=False)
    cost_price = Column(Float, nullable=False)
    total = Column(Float, nullable=False)

    purchase = relationship("Purchase", back_populates="items")
    raw_material = relationship("RawMaterial", back_populates="purchase_items")


# ── Production Batch ─────────────────────────────────────────────────
class ProductionBatch(Base):
    __tablename__ = "production_batches"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    batch_number = Column(String(50), nullable=False, index=True)
    finished_product_id = Column(String, ForeignKey("products.id"), nullable=False)
    quantity_produced = Column(Integer, nullable=False)
    total_cost = Column(Float, default=0.0)
    cost_per_unit = Column(Float, default=0.0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="production_batches")
    finished_product = relationship("Product", back_populates="production_batches")
    items = relationship("ProductionItem", back_populates="production_batch", cascade="all, delete-orphan")


# ── Production Item ──────────────────────────────────────────────────
class ProductionItem(Base):
    __tablename__ = "production_items"

    id = Column(String, primary_key=True, default=generate_uuid)
    production_batch_id = Column(String, ForeignKey("production_batches.id", ondelete="CASCADE"), nullable=False)
    raw_material_id = Column(String, ForeignKey("raw_materials.id"), nullable=False)
    raw_material_name = Column(String(255), nullable=False)
    quantity_used = Column(Float, nullable=False)

    production_batch = relationship("ProductionBatch", back_populates="items")
    raw_material = relationship("RawMaterial", back_populates="production_items")


# ═══════════════════════════════════════════════════════════════════════
# PAYMENTS & LEDGER
# ═══════════════════════════════════════════════════════════════════════

# ── Payment ──────────────────────────────────────────────────────────
class Payment(Base):
    __tablename__ = "payments"

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(String, ForeignKey("customers.id"), nullable=True, index=True)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=True, index=True)
    supplier_id = Column(String, ForeignKey("suppliers.id"), nullable=True, index=True)
    purchase_id = Column(String, ForeignKey("purchases.id"), nullable=True, index=True)
    amount = Column(Float, nullable=False)
    payment_type = Column(String(20), default="received")  # received | refund | paid | supplier_refund
    payment_method = Column(String(50), default="cash")  # cash | bank | upi | other
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    company = relationship("Company", back_populates="payments")
    customer = relationship("Customer", back_populates="payments")
    invoice = relationship("Invoice", back_populates="payments")
    supplier = relationship("Supplier", back_populates="payments")
    purchase = relationship("Purchase", back_populates="payments")


# ═══════════════════════════════════════════════════════════════════════
# STOCK MOVEMENT AUDIT TRAIL
# ═══════════════════════════════════════════════════════════════════════

class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        # XOR: either product_id or raw_material_id must be set, not both
        # Enforcement done in service layer for DB portability
    )

    id = Column(String, primary_key=True, default=generate_uuid)
    company_id = Column(String, ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(String, ForeignKey("products.id"), nullable=True, index=True)
    raw_material_id = Column(String, ForeignKey("raw_materials.id"), nullable=True, index=True)
    # purchase | production_in | production_out | sale | adjustment
    movement_type = Column(String(20), nullable=False, index=True)
    quantity_change = Column(Float, nullable=False)  # positive = in, negative = out
    reference_type = Column(String(50), nullable=False)  # purchase | production_batch | invoice
    reference_id = Column(String, nullable=False, index=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)

    company = relationship("Company", back_populates="stock_movements")
    product = relationship("Product")
    raw_material = relationship("RawMaterial")

