from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


# Benefit Type Schemas
class BenefitTypeBase(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    is_taxable: int = 1
    tax_exemption_limit: Optional[float] = None
    requires_receipt: int = 0


class BenefitTypeCreate(BenefitTypeBase):
    pass


class BenefitTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_taxable: Optional[int] = None
    tax_exemption_limit: Optional[float] = None
    requires_receipt: Optional[int] = None
    is_active: Optional[int] = None


class BenefitType(BenefitTypeBase):
    id: int
    is_active: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Employee Compensation Schemas
class EmployeeCompensationBase(BaseModel):
    benefit_type_id: int
    amount: float
    effective_date: Optional[date] = None
    notes: Optional[str] = None


class EmployeeCompensationCreate(EmployeeCompensationBase):
    pass


class EmployeeCompensationUpdate(BaseModel):
    amount: Optional[float] = None
    end_date: Optional[date] = None
    is_active: Optional[int] = None
    notes: Optional[str] = None


class EmployeeCompensation(EmployeeCompensationBase):
    id: int
    employee_id: int
    end_date: Optional[date] = None
    is_active: int
    created_at: datetime
    updated_at: datetime
    benefit_type: Optional[BenefitType] = None

    class Config:
        from_attributes = True


# Employee Schemas (no salary information)
class EmployeeBase(BaseModel):
    employee_id: str
    first_name: str
    last_name: str
    nif: Optional[str] = None
    social_security_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    position: Optional[str] = None
    department: Optional[str] = None
    hire_date: date
    notes: Optional[str] = None
    user_id: Optional[int] = None


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    nif: Optional[str] = None
    social_security_number: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    date_of_birth: Optional[date] = None
    position: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[int] = None
    termination_date: Optional[datetime] = None
    notes: Optional[str] = None
    user_id: Optional[int] = None


class Employee(EmployeeBase):
    id: int
    is_active: int
    termination_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    compensations: List[EmployeeCompensation] = []

    class Config:
        from_attributes = True


# Payroll Schemas
class PayrollEntryBase(BaseModel):
    employee_id: int
    base_salary: float
    benefits_total: float = 0.0
    gross_salary: float
    deductions: float = 0.0
    net_salary: float
    notes: Optional[str] = None


class PayrollEntryCreate(PayrollEntryBase):
    pass


class PayrollEntryUpdate(BaseModel):
    net_salary: Optional[float] = None
    is_paid: Optional[int] = None
    payment_date: Optional[datetime] = None
    bank_transaction_id: Optional[int] = None
    notes: Optional[str] = None


class PayrollEntry(PayrollEntryBase):
    id: int
    period_id: int
    is_paid: int
    payment_date: Optional[datetime] = None
    bank_transaction_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    employee: Optional[Employee] = None

    class Config:
        from_attributes = True


class PayrollPeriodBase(BaseModel):
    year: int
    month: int
    notes: Optional[str] = None


class PayrollPeriodCreate(PayrollPeriodBase):
    pass


class PayrollPeriodUpdate(BaseModel):
    status: Optional[str] = None
    processed_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    notes: Optional[str] = None


class PayrollPeriod(PayrollPeriodBase):
    id: int
    status: str
    processed_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    total_gross: float
    total_net: float
    created_at: datetime
    updated_at: datetime
    entries: List[PayrollEntry] = []

    class Config:
        from_attributes = True


# Upload schema for payroll file
class PayrollUploadEntry(BaseModel):
    employee_id: str
    net_amount: float


# ---------------------------------------------------------------------------
# Expense Report Schemas
# ---------------------------------------------------------------------------

class ExpenseItemOut(BaseModel):
    id: int
    report_id: int
    description: str
    category: Optional[str] = None
    amount: float
    currency: str
    expense_date: datetime
    file_path: str
    original_filename: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ExpenseReportCreate(BaseModel):
    title: str
    description: Optional[str] = None
    notes: Optional[str] = None


class ExpenseReportUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    notes: Optional[str] = None


class ExpenseReportOut(BaseModel):
    id: int
    employee_id: int
    employee_name: Optional[str] = None
    title: str
    description: Optional[str] = None
    status: str
    submitted_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[ExpenseItemOut] = []
    total_amount: float = 0.0

    class Config:
        from_attributes = True
