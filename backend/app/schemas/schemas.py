from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from enum import Enum


class InvoiceType(str, Enum):
    SALE = "sale"
    PURCHASE = "purchase"


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    CANCELLED = "cancelled"


# Company schemas
class CompanyBase(BaseModel):
    nif: str = Field(..., min_length=9, max_length=20)
    name: str
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    country: str = "PT"
    email: Optional[str] = None
    phone: Optional[str] = None
    is_customer: bool = False
    is_supplier: bool = False


class CompanyCreate(CompanyBase):
    pass


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    is_customer: Optional[bool] = None
    is_supplier: Optional[bool] = None


class Company(CompanyBase):
    nif: str  # override: no min_length on response (DB may have legacy short NIFs)
    id: int
    is_enriched: bool = False
    enriched_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# Invoice Line Item schemas
class InvoiceLineItemBase(BaseModel):
    description: str
    quantity: float = 1.0
    unit_price: float
    tax_rate: float = 23.0
    line_total: float


class InvoiceLineItemCreate(InvoiceLineItemBase):
    pass


class InvoiceLineItem(InvoiceLineItemBase):
    id: int
    invoice_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Invoice Direct Payment schemas
class InvoiceDirectPaymentCreate(BaseModel):
    payment_date: datetime
    amount: float
    payment_type: str  # 'cash', 'employee', 'company_account', 'other'
    reference: Optional[str] = None
    employee_id: Optional[int] = None
    bank_transaction_id: Optional[int] = None
    notes: Optional[str] = None


class InvoiceDirectPaymentOut(BaseModel):
    id: int
    invoice_id: int
    payment_date: datetime
    amount: float
    payment_type: str
    reference: Optional[str] = None
    employee_id: Optional[int] = None
    employee_name: Optional[str] = None
    bank_transaction_id: Optional[int] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class InvoiceCommentCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class InvoiceCommentUpdate(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class InvoiceCommentOut(BaseModel):
    id: int
    invoice_id: int
    user_id: Optional[int] = None
    username: str
    body: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Invoice schemas
class InvoiceBase(BaseModel):
    invoice_number: str
    invoice_type: InvoiceType
    invoice_date: datetime
    due_date: Optional[datetime] = None
    subtotal: float
    tax_amount: float
    total_amount: float
    tax_rate: float = 23.0
    notes: Optional[str] = None
    
    # Foreign currency fields
    is_foreign_currency: bool = False
    foreign_currency_code: Optional[str] = None
    original_total_amount: Optional[float] = None
    original_tax_amount: Optional[float] = None
    exchange_rate: Optional[float] = None
    
    # VAT breakdown
    vat_6_base: float = 0.0
    vat_6_amount: float = 0.0
    vat_23_base: float = 0.0
    vat_23_amount: float = 0.0


class InvoiceCreate(InvoiceBase):
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    line_items: Optional[List[InvoiceLineItemCreate]] = []


class InvoiceUpdate(BaseModel):
    status: Optional[InvoiceStatus] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    # Foreign currency fields
    is_foreign_currency: Optional[bool] = None
    foreign_currency_code: Optional[str] = None
    original_total_amount: Optional[float] = None
    original_tax_amount: Optional[float] = None
    exchange_rate: Optional[float] = None
    # EUR amounts (can be updated when converting from foreign currency)
    total_amount: Optional[float] = None
    tax_amount: Optional[float] = None
    subtotal: Optional[float] = None


class InvoiceExpenseReport(BaseModel):
    """Minimal expense report info attached to an invoice for reconciliation display."""
    id: int
    expense_id: Optional[str] = None
    title: str
    status: str
    paid_at: Optional[datetime] = None
    employee_name: Optional[str] = None

    class Config:
        from_attributes = True


class Invoice(InvoiceBase):
    id: int
    status: InvoiceStatus
    customer_id: Optional[int] = None
    supplier_id: Optional[int] = None
    file_path: Optional[str] = None
    original_filename: Optional[str] = None
    qr_code_data: Optional[str] = None
    atcud: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    line_items: List[InvoiceLineItem] = []
    supplier_name: Optional[str] = None
    customer_name: Optional[str] = None
    is_reconciled: bool = False
    bank_transaction_id: Optional[int] = None
    linked_transaction_ids: List[int] = []
    reconciled_amount: float = 0.0
    is_partial: bool = False
    payments: List[InvoiceDirectPaymentOut] = []
    total_paid: float = 0.0
    remaining_amount: float = 0.0
    expense_report: Optional[InvoiceExpenseReport] = None
    
    class Config:
        from_attributes = True


# QR Code data schema
class QRCodeData(BaseModel):
    model_config = {"extra": "ignore"}
    
    nif_emitente: Optional[str] = None
    nif_adquirente: Optional[str] = None
    pais_adquirente: Optional[str] = None
    tipo_documento: Optional[str] = None
    estado_documento: Optional[str] = None
    data_documento: Optional[str] = None
    identificacao_documento: Optional[str] = None
    atcud: Optional[str] = None
    espaco_fiscal: Optional[str] = None
    base_incidencia_iva: Optional[List[float]] = None
    total_iva: Optional[List[float]] = None
    total_impostos: Optional[float] = None
    total_documento: Optional[float] = None
    hash: Optional[str] = None
    certificado: Optional[str] = None
    outras_infos: Optional[str] = None
    is_foreign_currency: Optional[bool] = None
    foreign_currency_code: Optional[str] = None
    original_total_amount: Optional[float] = None
    exchange_rate: Optional[float] = None


# Upload response
class UploadResponse(BaseModel):
    filename: str
    file_path: str
    file_url: Optional[str] = None
    qr_data: Optional[QRCodeData] = None
    raw_qr_code: Optional[str] = None
    extraction_method: Optional[str] = None  # 'qr', 'ocr', or None
    message: str


class ProcessInvoiceRequest(BaseModel):
    file_path: str
    create_invoice: bool = True
    notes: Optional[str] = None
    qr_data: Optional[QRCodeData] = None  # User-confirmed data; skips re-parsing if provided


# SAFT Import schemas
class SAFTImportCreate(BaseModel):
    filename: str
    file_path: str


class SAFTImport(BaseModel):
    id: int
    filename: str
    tax_registration_number: Optional[str] = None
    company_name: Optional[str] = None
    fiscal_year: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    total_invoices: int
    imported_invoices: int
    failed_invoices: int
    total_payments: int = 0
    imported_payments: int = 0
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Invoice Processing Queue Schemas
class InvoiceProcessingQueueBase(BaseModel):
    filename: str
    local_file_path: Optional[str] = None
    s3_file_path: Optional[str] = None
    status: str = "pending"
    error_message: Optional[str] = None
    has_qr_data: bool = False
    qr_data: Optional[str] = None


class InvoiceProcessingQueueCreate(InvoiceProcessingQueueBase):
    pass


class InvoiceProcessingQueue(InvoiceProcessingQueueBase):
    id: int
    invoice_id: Optional[int] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    retry_count: int = 0
    last_retry_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


# Payment Schemas
class PaymentBase(BaseModel):
    payment_number: str
    payment_date: datetime
    customer_id: Optional[int] = None
    payment_amount: float
    payment_method: Optional[str] = None
    atcud: Optional[str] = None


class PaymentCreate(PaymentBase):
    pass


class Payment(PaymentBase):
    id: int
    saft_import_id: Optional[int] = None
    customer: Optional[Company] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
