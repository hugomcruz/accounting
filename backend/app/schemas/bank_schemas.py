from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class BankLogoCreate(BaseModel):
    name: str
    url: str


class BankLogoSchema(BaseModel):
    id: int
    name: str
    url: str
    created_at: datetime

    class Config:
        from_attributes = True


class BankAccountUpdate(BaseModel):
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    iban: Optional[str] = None
    currency: Optional[str] = None
    logo_path: Optional[str] = None
    notes: Optional[str] = None


class BankAccountSchema(BaseModel):
    id: int
    account_number: str
    account_name: Optional[str] = None
    bank_name: Optional[str] = None
    iban: Optional[str] = None
    currency: str = "EUR"
    logo_path: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BankStatementCreate(BaseModel):
    """Schema for creating bank statement"""
    filename: str
    account_number: str
    account_currency: str = "EUR"
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    period_start: datetime
    period_end: datetime
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    available_balance: Optional[float] = None


class BankTransaction(BaseModel):
    """Schema for bank transaction"""
    id: int
    statement_id: int
    transaction_date: datetime
    value_date: datetime
    description: str
    amount: float
    balance_after: Optional[float] = None
    category: Optional[str] = None
    is_reconciled: bool = False
    invoice_id: Optional[int] = None
    payment_id: Optional[int] = None
    linked_transaction_id: Optional[int] = None
    notes: Optional[str] = None
    note_count: int = 0
    created_at: datetime
    # Derived from statement → bank_account
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    # Direct FK to bank account (denormalized)
    bank_account_id: Optional[int] = None
    # Populated when this tx was used to pay an expense report
    expense_report_id: Optional[int] = None

    class Config:
        from_attributes = True


class BankTransactionNoteCreate(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class BankTransactionNoteUpdate(BaseModel):
    body: str = Field(..., min_length=1, max_length=4000)


class BankTransactionNoteOut(BaseModel):
    id: int
    transaction_id: int
    user_id: Optional[int] = None
    username: str
    body: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class BankStatement(BaseModel):
    """Schema for bank statement"""
    id: int
    filename: str
    file_path: Optional[str] = None
    account_number: str
    account_currency: str
    company_name: Optional[str] = None
    company_nif: Optional[str] = None
    period_start: datetime
    period_end: datetime
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
    available_balance: Optional[float] = None
    total_transactions: int
    imported_transactions: int
    failed_transactions: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    transactions: List[BankTransaction] = []
    
    class Config:
        from_attributes = True


class BankStatementImportResponse(BaseModel):
    """Response for bank statement import"""
    message: str
    statement_id: int
    account_number: str
    period_start: datetime
    period_end: datetime
    total_transactions: int
    imported_transactions: int
    failed_transactions: int
    opening_balance: Optional[float] = None
    closing_balance: Optional[float] = None
