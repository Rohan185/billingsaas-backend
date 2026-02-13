from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


# ── Auth / User ──────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    company_name: str
    full_name: str
    email: EmailStr
    password: str
    company_address: Optional[str] = None
    company_phone: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    company_id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Product ──────────────────────────────────────────────────────────
class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    stock: int = 0
    unit: str = "pcs"


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    unit: Optional[str] = None
    is_active: Optional[bool] = None


class ProductOut(BaseModel):
    id: str
    company_id: str
    name: str
    description: Optional[str]
    price: float
    stock: int
    unit: str
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Invoice ──────────────────────────────────────────────────────────
class InvoiceItemCreate(BaseModel):
    product_id: str
    quantity: int


class InvoiceCreate(BaseModel):
    customer_name: str
    customer_id: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    tax_percent: float = 0.0
    discount: float = 0.0
    notes: Optional[str] = None
    items: list[InvoiceItemCreate]


class InvoiceItemOut(BaseModel):
    id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price: float
    total_price: float

    class Config:
        from_attributes = True


class InvoiceOut(BaseModel):
    id: str
    company_id: str
    customer_id: Optional[str] = None
    invoice_number: str
    customer_name: str
    customer_email: Optional[str]
    customer_phone: Optional[str]
    subtotal: float
    tax_percent: float
    tax_amount: float
    discount: float
    total: float
    status: str
    notes: Optional[str]
    created_at: datetime
    items: list[InvoiceItemOut]

    class Config:
        from_attributes = True


# ── Dashboard ────────────────────────────────────────────────────────
class LowStockItem(BaseModel):
    id: str
    name: str
    stock: int
    unit: str

    class Config:
        from_attributes = True


class DashboardSummary(BaseModel):
    today_revenue: float
    monthly_revenue: float
    total_invoices_today: int
    total_invoices_month: int
    low_stock_items: list[LowStockItem]


# ═══════════════════════════════════════════════════════════════════════
# MANUFACTURING MODULE
# ═══════════════════════════════════════════════════════════════════════

# ── Raw Material ─────────────────────────────────────────────────────
class RawMaterialCreate(BaseModel):
    name: str
    unit: str = "kg"
    stock_quantity: float = 0
    cost_price: float = 0
    low_stock_threshold: float = 10


class RawMaterialUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    cost_price: Optional[float] = None
    low_stock_threshold: Optional[float] = None
    is_active: Optional[bool] = None


class RawMaterialOut(BaseModel):
    id: str
    company_id: str
    name: str
    unit: str
    stock_quantity: float
    cost_price: float
    low_stock_threshold: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# ── Supplier ─────────────────────────────────────────────────────────
class SupplierCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    is_active: Optional[bool] = None


class SupplierOut(BaseModel):
    id: str
    company_id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Purchase ─────────────────────────────────────────────────────────
class PurchaseItemCreate(BaseModel):
    raw_material_id: str
    quantity: float
    cost_price: float


class PurchaseCreate(BaseModel):
    supplier_id: str
    notes: Optional[str] = None
    items: list[PurchaseItemCreate]


class PurchaseItemOut(BaseModel):
    id: str
    raw_material_id: str
    raw_material_name: str
    quantity: float
    cost_price: float
    total: float

    class Config:
        from_attributes = True


class PurchaseOut(BaseModel):
    id: str
    company_id: str
    purchase_number: str
    supplier_id: str
    total_amount: float
    notes: Optional[str]
    created_at: datetime
    items: list[PurchaseItemOut]

    class Config:
        from_attributes = True


# ── Production Batch ─────────────────────────────────────────────────
class ProductionItemCreate(BaseModel):
    raw_material_id: str
    quantity_used: float


class ProductionBatchCreate(BaseModel):
    finished_product_id: str
    quantity_produced: int
    notes: Optional[str] = None
    items: list[ProductionItemCreate]


class ProductionItemOut(BaseModel):
    id: str
    raw_material_id: str
    raw_material_name: str
    quantity_used: float

    class Config:
        from_attributes = True


class ProductionBatchOut(BaseModel):
    id: str
    company_id: str
    batch_number: str
    finished_product_id: str
    quantity_produced: int
    total_cost: float
    cost_per_unit: float = 0.0
    notes: Optional[str]
    created_at: datetime
    items: list[ProductionItemOut]

    class Config:
        from_attributes = True


# ═══════════════════════════════════════════════════════════════════════
# CUSTOMER & PAYMENT MODULE
# ═══════════════════════════════════════════════════════════════════════

# ── Customer ─────────────────────────────────────────────────────────
class CustomerCreate(BaseModel):
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None


class CustomerOut(BaseModel):
    id: str
    company_id: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class CustomerWithBalance(CustomerOut):
    total_invoiced: float = 0
    total_paid: float = 0
    outstanding: float = 0


# ── Payment ─────────────────────────────────────────────────────────
class PaymentCreate(BaseModel):
    customer_id: str
    invoice_id: Optional[str] = None
    amount: float
    payment_type: str = "received"  # received | refund
    payment_method: str = "cash"  # cash | bank | upi | other
    notes: Optional[str] = None


class PaymentOut(BaseModel):
    id: str
    company_id: str
    customer_id: Optional[str] = None
    invoice_id: Optional[str] = None
    supplier_id: Optional[str] = None
    purchase_id: Optional[str] = None
    amount: float
    payment_type: str
    payment_method: str
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Supplier Payment ─────────────────────────────────────────────────
class SupplierPaymentCreate(BaseModel):
    supplier_id: str
    purchase_id: Optional[str] = None
    amount: float
    payment_method: str = "bank"  # cash | bank | upi | other
    notes: Optional[str] = None
