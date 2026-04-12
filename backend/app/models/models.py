from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from app.core.database import Base


class InvoiceType(str, enum.Enum):
    SALE = "sale"
    PURCHASE = "purchase"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    CANCELLED = "cancelled"


class Company(Base):
    __tablename__ = "companies"
    
    id = Column(Integer, primary_key=True, index=True)
    nif = Column(String(20), unique=True, index=True, nullable=False)  # Tax ID (up to 20 chars for foreign VAT numbers)
    name = Column(String(255), nullable=False)
    address = Column(Text)
    postal_code = Column(String(20))
    city = Column(String(100))
    country = Column(String(2), default="PT")
    email = Column(String(255))
    phone = Column(String(20))
    is_customer = Column(Integer, default=0)  # Boolean: can be customer
    is_supplier = Column(Integer, default=0)  # Boolean: can be supplier
    is_enriched = Column(Integer, default=0)  # Boolean: enriched from NIF API
    enriched_at = Column(DateTime, nullable=True)  # When the company was enriched
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sales_invoices = relationship("Invoice", back_populates="customer", foreign_keys="Invoice.customer_id")
    purchase_invoices = relationship("Invoice", back_populates="supplier", foreign_keys="Invoice.supplier_id")


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint('supplier_id', 'invoice_number', name='uq_invoice_supplier_number'),)

    id = Column(Integer, primary_key=True, index=True)
    invoice_number = Column(String(50), index=True, nullable=False)
    invoice_type = Column(Enum(InvoiceType), nullable=False)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    
    # Dates
    invoice_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime)
    
    # Company references
    customer_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    supplier_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    
    # Amounts
    subtotal = Column(Float, nullable=False, default=0.0)
    tax_amount = Column(Float, nullable=False, default=0.0)
    total_amount = Column(Float, nullable=False, default=0.0)
    
    # Tax info
    tax_rate = Column(Float, default=23.0)  # Portuguese IVA standard rate
    
    # File storage
    file_path = Column(String(500))  # Path to invoice file in S3
    original_filename = Column(String(255))  # Original filename as uploaded
    
    # SAFT import tracking
    saft_import_id = Column(Integer, ForeignKey("saft_imports.id"), nullable=True)
    
    # QR Code data (for Portuguese AT invoices)
    qr_code_data = Column(Text)
    atcud = Column(String(100))  # ATCUD code (Portuguese tax authority unique document code)
    
    # Foreign currency support
    is_foreign_currency = Column(Integer, default=0)  # Boolean
    foreign_currency_code = Column(String(3))  # ISO currency code (USD, GBP, etc.)
    original_total_amount = Column(Float)  # Original amount in foreign currency
    original_tax_amount = Column(Float)  # Original tax amount in foreign currency
    exchange_rate = Column(Float)  # Exchange rate used for conversion
    
    # VAT breakdown by rate
    vat_6_base = Column(Float, default=0.0)  # Base amount for 6% VAT
    vat_6_amount = Column(Float, default=0.0)  # VAT amount at 6%
    vat_23_base = Column(Float, default=0.0)  # Base amount for 23% VAT
    vat_23_amount = Column(Float, default=0.0)  # VAT amount at 23%
    
    # Additional info
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Company", back_populates="sales_invoices", foreign_keys=[customer_id])
    supplier = relationship("Company", back_populates="purchase_invoices", foreign_keys=[supplier_id])
    saft_import = relationship("SAFTImport", back_populates="invoices")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    
    description = Column(String(500), nullable=False)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, nullable=False)
    tax_rate = Column(Float, default=23.0)
    
    line_total = Column(Float, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = relationship("Invoice", back_populates="line_items")


class SAFTImport(Base):
    __tablename__ = "saft_imports"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    
    # SAFT metadata
    tax_registration_number = Column(String(20))  # NIF / foreign VAT number
    company_name = Column(String(255))
    fiscal_year = Column(Integer)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    
    # Import stats
    total_invoices = Column(Integer, default=0)
    imported_invoices = Column(Integer, default=0)
    failed_invoices = Column(Integer, default=0)
    total_payments = Column(Integer, default=0)
    imported_payments = Column(Integer, default=0)
    
    status = Column(String(50), default="processing")  # processing, completed, failed
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    invoices = relationship("Invoice", back_populates="saft_import")
    payments = relationship("Payment", back_populates="saft_import")


class InvoiceProcessingQueue(Base):
    """Queue for tracking uploaded invoices that need processing"""
    __tablename__ = "invoice_processing_queue"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    
    # File storage paths
    local_file_path = Column(String(500))  # Local filesystem path
    s3_file_path = Column(String(500))  # S3 path (if S3 storage enabled)
    
    # Processing status
    status = Column(String(50), default="pending")  # pending, processing, completed, failed, needs_review
    error_message = Column(Text)
    
    # Extracted data (if QR code found)
    has_qr_data = Column(Integer, default=0)  # Boolean
    qr_data = Column(Text)  # JSON string of extracted QR data
    
    # Reference to created invoice (if processing completed)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    
    # Timestamps
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime)
    
    # Retry tracking
    retry_count = Column(Integer, default=0)
    last_retry_at = Column(DateTime)
    
    # Relationships
    invoice = relationship("Invoice")


class Payment(Base):
    __tablename__ = "payments"
    
    id = Column(Integer, primary_key=True, index=True)
    payment_number = Column(String(50), unique=True, index=True, nullable=False)
    payment_date = Column(DateTime, nullable=False)
    
    # Company reference
    customer_id = Column(Integer, ForeignKey("companies.id"), nullable=True)
    
    # Amount
    payment_amount = Column(Float, nullable=False, default=0.0)
    
    # Payment method
    payment_method = Column(String(50))  # Cash, Check, Transfer, etc.
    
    # SAFT import tracking
    saft_import_id = Column(Integer, ForeignKey("saft_imports.id"), nullable=True)
    
    # ATCUD for receipts
    atcud = Column(String(100))
    
    # Additional info
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Company")
    saft_import = relationship("SAFTImport", back_populates="payments")
    invoice_payments = relationship("InvoicePayment", back_populates="payment", cascade="all, delete-orphan")


class InvoicePayment(Base):
    """Link table between invoices and payments"""
    __tablename__ = "invoice_payments"
    
    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    invoice = relationship("Invoice")
    payment = relationship("Payment", back_populates="invoice_payments")


class InvoiceDirectPayment(Base):
    """Direct payments applied to invoices (cash, employee account, company bank account, other)"""
    __tablename__ = "invoice_direct_payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=False)
    payment_date = Column(DateTime, nullable=False)
    amount = Column(Float, nullable=False)
    payment_type = Column(String(50), nullable=False)  # cash, employee, company_account, other
    reference = Column(String(200), nullable=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    employee_name = Column(String(200), nullable=True)
    bank_transaction_id = Column(Integer, ForeignKey("bank_transactions.id"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice")
    employee = relationship("Employee")
    bank_transaction = relationship("BankTransaction")


class NifApiQuota(Base):
    """Track NIF.PT API usage quotas"""
    __tablename__ = "nif_api_quotas"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Quota counters
    minute_count = Column(Integer, default=0)
    hour_count = Column(Integer, default=0)
    day_count = Column(Integer, default=0)
    month_count = Column(Integer, default=0)
    
    # Timestamps for tracking when to reset counters
    minute_reset_at = Column(DateTime, default=datetime.utcnow)
    hour_reset_at = Column(DateTime, default=datetime.utcnow)
    day_reset_at = Column(DateTime, default=datetime.utcnow)
    month_reset_at = Column(DateTime, default=datetime.utcnow)
    
    # Track last successful API call
    last_request_at = Column(DateTime)
    
    # API credits info from last response
    credits_left_month = Column(Integer)
    credits_left_day = Column(Integer)
    credits_left_hour = Column(Integer)
    credits_left_minute = Column(Integer)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BankAccount(Base):
    """Known bank account – created automatically on first import, editable by users."""
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(String(50), unique=True, index=True, nullable=False)
    account_name = Column(String(255))       # friendly name, e.g. "CGD – Operations"
    bank_name = Column(String(255))          # e.g. "Caixa Geral de Depósitos"
    iban = Column(String(34))
    currency = Column(String(3), default="EUR")
    logo_path = Column(String(1000))         # CDN URL of the selected logo
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    statements = relationship("BankStatement", back_populates="bank_account")


class BankLogo(Base):
    """Admin-managed bank logo library – each entry is a CDN URL."""
    __tablename__ = "bank_logos"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(1000), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class InvoiceComment(Base):
    """User comment/note attached to an invoice – displayed as a chat thread."""
    __tablename__ = "invoice_comments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(150), nullable=False)   # stored so it survives user deletion
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    invoice = relationship("Invoice")


class BankTransactionNote(Base):
    """User note attached to a bank transaction – displayed as a chat thread."""
    __tablename__ = "bank_transaction_notes"

    id = Column(Integer, primary_key=True, index=True)
    transaction_id = Column(Integer, ForeignKey("bank_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(150), nullable=False)   # stored so it survives user deletion
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    transaction = relationship("BankTransaction", foreign_keys=[transaction_id], back_populates="notes_thread")


class BankStatement(Base):
    """Bank statement import record"""
    __tablename__ = "bank_statements"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500))
    
    # Account information
    account_number = Column(String(50), nullable=False, index=True)
    account_currency = Column(String(3), default="EUR")
    company_name = Column(String(255))
    company_nif = Column(String(20))
    # Link to the BankAccount record (auto-created on import)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=True)
    
    # Statement period
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    
    # Balances
    opening_balance = Column(Float)
    closing_balance = Column(Float)
    available_balance = Column(Float)
    
    # Import stats
    total_transactions = Column(Integer, default=0)
    imported_transactions = Column(Integer, default=0)
    failed_transactions = Column(Integer, default=0)
    
    status = Column(String(50), default="processing")  # processing, completed, failed
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)
    
    # Relationships
    transactions = relationship("BankTransaction", back_populates="statement", cascade="all, delete-orphan")
    bank_account = relationship("BankAccount", back_populates="statements")


class BankTransaction(Base):
    """Bank transaction from statement"""
    __tablename__ = "bank_transactions"
    
    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=False)
    # Denormalized for fast filtering without joining statements
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=True, index=True)
    
    # Transaction details
    transaction_date = Column(DateTime, nullable=False, index=True)
    value_date = Column(DateTime, nullable=False)
    description = Column(Text, nullable=False)
    amount = Column(Float, nullable=False)
    balance_after = Column(Float)
    
    # Categorization
    category = Column(String(100))  # e.g., 'transfer', 'payment', 'purchase', 'salary'
    is_reconciled = Column(Integer, default=0)  # Boolean: matched with invoice/payment
    
    # References
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)
    payment_id = Column(Integer, ForeignKey("payments.id"), nullable=True)
    # Inter-account transfer link: points to the counterpart transaction in another statement
    linked_transaction_id = Column(Integer, ForeignKey("bank_transactions.id"), nullable=True)

    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    statement = relationship("BankStatement", back_populates="transactions")
    bank_account = relationship("BankAccount")
    invoice = relationship("Invoice")
    payment = relationship("Payment")
    linked_transaction = relationship("BankTransaction", foreign_keys=[linked_transaction_id], remote_side="BankTransaction.id")
    notes_thread = relationship("BankTransactionNote", back_populates="transaction", cascade="all, delete-orphan")


class Employee(Base):
    """Employee profile - personal and employment information only"""
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(String(50), unique=True, index=True, nullable=False)  # Internal employee ID
    
    # Personal information
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    nif = Column(String(20), unique=True, index=True)  # Tax ID (up to 20 chars for foreign VAT numbers)
    social_security_number = Column(String(11), unique=True, index=True)  # Portuguese NISS
    email = Column(String(255))
    phone = Column(String(20))
    address = Column(Text)
    date_of_birth = Column(DateTime)
    
    # Employment details
    position = Column(String(100))
    department = Column(String(100))
    hire_date = Column(DateTime, nullable=False)
    termination_date = Column(DateTime, nullable=True)
    is_active = Column(Integer, default=1)  # Boolean: 1=active, 0=inactive/removed
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Optional link to a User account (for "user" role self-service expense reports)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, unique=True)

    # Relationships
    compensations = relationship("EmployeeCompensation", back_populates="employee", cascade="all, delete-orphan")
    payroll_entries = relationship("PayrollEntry", back_populates="employee")


class BenefitType(Base):
    """Configurable benefit types with taxation rules"""
    __tablename__ = "benefit_types"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)  # e.g., 'base_salary', 'meal_allowance'
    name = Column(String(100), nullable=False)  # e.g., 'Base Salary', 'Meal Allowance'
    description = Column(Text)
    
    # Taxation configuration (can be expanded in the future)
    is_taxable = Column(Integer, default=1)  # Boolean
    tax_exemption_limit = Column(Float, nullable=True)  # Maximum amount exempt from tax
    requires_receipt = Column(Integer, default=0)  # Boolean: requires documentation
    
    is_active = Column(Integer, default=1)  # Boolean
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    compensations = relationship("EmployeeCompensation", back_populates="benefit_type")


class EmployeeCompensation(Base):
    """Employee compensation - salary and benefits"""
    __tablename__ = "employee_compensations"
    
    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    benefit_type_id = Column(Integer, ForeignKey("benefit_types.id"), nullable=False)
    
    amount = Column(Float, nullable=False)
    effective_date = Column(DateTime, default=datetime.utcnow)  # When this compensation starts
    end_date = Column(DateTime, nullable=True)  # When this compensation ends (null = ongoing)
    is_active = Column(Integer, default=1)  # Boolean
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    employee = relationship("Employee", back_populates="compensations")
    benefit_type = relationship("BenefitType", back_populates="compensations")


class PayrollPeriod(Base):
    """Monthly payroll processing period"""
    __tablename__ = "payroll_periods"
    
    id = Column(Integer, primary_key=True, index=True)
    
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)  # 1-12
    
    status = Column(String(20), default="draft")  # draft, processed, paid, closed
    processed_date = Column(DateTime)
    paid_date = Column(DateTime)
    
    total_gross = Column(Float, default=0.0)
    total_net = Column(Float, default=0.0)
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    entries = relationship("PayrollEntry", back_populates="period", cascade="all, delete-orphan")


class PayrollEntry(Base):
    """Individual employee payroll entry for a period"""
    __tablename__ = "payroll_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("payroll_periods.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False)
    
    # Salary components
    base_salary = Column(Float, nullable=False)
    benefits_total = Column(Float, default=0.0)
    gross_salary = Column(Float, nullable=False)  # base + benefits
    
    # Deductions (taxes, social security, etc.)
    deductions = Column(Float, default=0.0)
    
    # Final amount
    net_salary = Column(Float, nullable=False)  # Amount to be paid
    
    # Payment tracking
    is_paid = Column(Integer, default=0)  # Boolean
    payment_date = Column(DateTime)
    bank_transaction_id = Column(Integer, ForeignKey("bank_transactions.id"), nullable=True)  # Link to bank statement
    
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    period = relationship("PayrollPeriod", back_populates="entries")
    employee = relationship("Employee", back_populates="payroll_entries")
    bank_transaction = relationship("BankTransaction")


class AppSettings(Base):
    __tablename__ = "app_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    value = Column(String(255), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InvoiceExport(Base):
    """Monthly invoice ZIP export jobs"""
    __tablename__ = "invoice_exports"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)          # 1–12
    status = Column(String(50), default="pending")   # pending | processing | completed | failed
    file_path = Column(String(500), nullable=True)   # path to ZIP in storage
    invoice_count = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class MonthEndReport(Base):
    """
    A generated end-of-month closing report.
    The report records which SAF-T import, bank statement and invoice ZIP
    were included.  It can only be created when all three are available.
    The linked invoice ZIP (InvoiceExport) is owned by this record —
    deleting the report also removes the ZIP file from storage.
    """
    __tablename__ = "month_end_reports"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    month = Column(Integer, nullable=False, index=True)          # 1-12

    # Foreign keys to other records (nullable so records can be deleted independently)
    saft_import_id = Column(Integer, ForeignKey("saft_imports.id"), nullable=True)
    bank_statement_id = Column(Integer, ForeignKey("bank_statements.id"), nullable=True)
    invoice_export_id = Column(Integer, ForeignKey("invoice_exports.id"), nullable=True)

    # Denormalised snapshot info (kept even if originals are deleted)
    saft_filename = Column(String(500), nullable=True)
    bank_statement_filename = Column(String(500), nullable=True)
    invoice_count = Column(Integer, default=0)

    # Paths – so we can clean up files on delete
    saft_file_path = Column(String(500), nullable=True)
    bank_statement_file_path = Column(String(500), nullable=True)
    invoice_zip_file_path = Column(String(500), nullable=True)

    status = Column(String(50), default="generating")  # generating | ready | failed
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships (optional – just for convenience)
    saft_import = relationship("SAFTImport", foreign_keys=[saft_import_id])
    bank_statement = relationship("BankStatement", foreign_keys=[bank_statement_id])
    invoice_export = relationship("InvoiceExport", foreign_keys=[invoice_export_id])


# ---------------------------------------------------------------------------
# Employee Expense Reports
# ---------------------------------------------------------------------------

class ExpenseReport(Base):
    """An employee's expense claim, grouping one or more expense items."""
    __tablename__ = "expense_reports"

    id = Column(Integer, primary_key=True, index=True)
    expense_id = Column(String(50), unique=True, index=True, nullable=True)  # Human-readable ID, e.g. EXP-2026-001
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    # draft → submitted → approved | rejected → paid
    status = Column(String(50), default="draft", nullable=False, index=True)
    submitted_at = Column(DateTime, nullable=True)
    approved_at = Column(DateTime, nullable=True)
    paid_at = Column(DateTime, nullable=True)
    bank_transaction_id = Column(Integer, ForeignKey("bank_transactions.id"), nullable=True)
    notes = Column(Text, nullable=True)   # reviewer notes
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = relationship("Employee", backref="expense_reports")
    items = relationship("ExpenseItem", back_populates="report", cascade="all, delete-orphan")
    bank_transaction = relationship("BankTransaction", foreign_keys=[bank_transaction_id])


class ExpenseItem(Base):
    """A single line in an expense report with a mandatory invoice file."""
    __tablename__ = "expense_items"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("expense_reports.id"), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    category = Column(String(100), nullable=True)   # travel, meals, accommodation, other …
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR")
    eur_amount = Column(Float, nullable=True)    # EUR equivalent when currency != EUR
    exchange_rate = Column(Float, nullable=True) # rate: 1 EUR = X foreign currency
    expense_date = Column(DateTime, nullable=False)
    # Mandatory invoice/receipt file
    file_path = Column(String(500), nullable=False)
    original_filename = Column(String(255), nullable=True)
    qr_data = Column(Text, nullable=True)  # JSON-encoded QR extraction result
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Accounting invoice created when the report is approved
    invoice_id = Column(Integer, ForeignKey("invoices.id"), nullable=True)

    report = relationship("ExpenseReport", back_populates="items")
    invoice = relationship("Invoice")
