from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
import csv
import io
from datetime import datetime
from app.core.database import get_db
from app.schemas.hr_schemas import (
    Employee, EmployeeCreate, EmployeeUpdate,
    BenefitType, BenefitTypeCreate, BenefitTypeUpdate,
    EmployeeCompensation, EmployeeCompensationCreate, EmployeeCompensationUpdate,
    PayrollPeriod, PayrollPeriodCreate, PayrollPeriodUpdate,
    PayrollEntry, PayrollEntryCreate, PayrollEntryUpdate,
    PayrollUploadEntry
)
from app.models import models

router = APIRouter(prefix="/hr", tags=["hr"])


# ========== BENEFIT TYPES ENDPOINTS ==========

@router.get("/benefit-types", response_model=List[BenefitType])
def get_benefit_types(
    skip: int = 0,
    limit: int = 100,
    is_active: int = None,
    db: Session = Depends(get_db)
):
    """Get all benefit types"""
    query = db.query(models.BenefitType)
    
    if is_active is not None:
        query = query.filter(models.BenefitType.is_active == is_active)
    
    types = query.order_by(models.BenefitType.name).offset(skip).limit(limit).all()
    return types


@router.post("/benefit-types", response_model=BenefitType, status_code=201)
def create_benefit_type(benefit_type: BenefitTypeCreate, db: Session = Depends(get_db)):
    """Create a new benefit type"""
    # Check if code already exists
    existing = db.query(models.BenefitType).filter(
        models.BenefitType.code == benefit_type.code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Benefit type code already exists")
    
    db_type = models.BenefitType(**benefit_type.model_dump())
    db.add(db_type)
    db.commit()
    db.refresh(db_type)
    return db_type


@router.patch("/benefit-types/{type_id}", response_model=BenefitType)
def update_benefit_type(
    type_id: int,
    type_update: BenefitTypeUpdate,
    db: Session = Depends(get_db)
):
    """Update a benefit type"""
    benefit_type = db.query(models.BenefitType).filter(models.BenefitType.id == type_id).first()
    if not benefit_type:
        raise HTTPException(status_code=404, detail="Benefit type not found")
    
    update_data = type_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(benefit_type, key, value)
    
    db.commit()
    db.refresh(benefit_type)
    return benefit_type


# ========== EMPLOYEE ENDPOINTS ==========

@router.get("/employees", response_model=List[Employee])
def get_employees(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Get all employees (profile only, no salary)"""
    query = db.query(models.Employee)
    
    if is_active is not None:
        query = query.filter(models.Employee.is_active == (1 if is_active else 0))
    
    employees = query.order_by(models.Employee.last_name, models.Employee.first_name).offset(skip).limit(limit).all()
    return employees


@router.get("/employees/{employee_id}", response_model=Employee)
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    """Get a specific employee by ID"""
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    return employee


@router.post("/employees", response_model=Employee, status_code=201)
def create_employee(employee: EmployeeCreate, db: Session = Depends(get_db)):
    """Create a new employee (profile only)"""
    # Check if employee_id already exists
    existing = db.query(models.Employee).filter(
        models.Employee.employee_id == employee.employee_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Employee ID already exists")
    
    # Check if NIF already exists (if provided)
    if employee.nif:
        existing_nif = db.query(models.Employee).filter(
            models.Employee.nif == employee.nif
        ).first()
        if existing_nif:
            raise HTTPException(status_code=400, detail="NIF already exists")
    
    db_employee = models.Employee(**employee.model_dump())
    db.add(db_employee)
    db.commit()
    db.refresh(db_employee)
    return db_employee


@router.patch("/employees/{employee_id}", response_model=Employee)
def update_employee(
    employee_id: int,
    employee_update: EmployeeUpdate,
    db: Session = Depends(get_db)
):
    """Update an employee profile"""
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    update_data = employee_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(employee, key, value)
    
    db.commit()
    db.refresh(employee)
    return employee


@router.delete("/employees/{employee_id}")
def remove_employee(employee_id: int, db: Session = Depends(get_db)):
    """Mark employee as removed (soft delete)"""
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    employee.is_active = 0
    today = datetime.utcnow()
    employee.termination_date = datetime(today.year, today.month, today.day)
    db.commit()
    
    return {"message": "Employee marked as inactive", "id": employee_id}


# ========== EMPLOYEE COMPENSATION ENDPOINTS ==========

@router.get("/employees/{employee_id}/compensations", response_model=List[EmployeeCompensation])
def get_employee_compensations(employee_id: int, db: Session = Depends(get_db)):
    """Get all compensations for an employee"""
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    compensations = db.query(models.EmployeeCompensation).filter(
        models.EmployeeCompensation.employee_id == employee_id
    ).all()
    return compensations


@router.post("/employees/{employee_id}/compensations", response_model=EmployeeCompensation, status_code=201)
def add_employee_compensation(
    employee_id: int,
    compensation: EmployeeCompensationCreate,
    db: Session = Depends(get_db)
):
    """Add compensation/benefit to an employee"""
    employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    # Check if benefit type exists
    benefit_type = db.query(models.BenefitType).filter(
        models.BenefitType.id == compensation.benefit_type_id
    ).first()
    if not benefit_type:
        raise HTTPException(status_code=404, detail="Benefit type not found")
    
    db_compensation = models.EmployeeCompensation(
        **compensation.model_dump(),
        employee_id=employee_id
    )
    db.add(db_compensation)
    db.commit()
    db.refresh(db_compensation)
    return db_compensation


@router.patch("/compensations/{compensation_id}", response_model=EmployeeCompensation)
def update_compensation(
    compensation_id: int,
    compensation_update: EmployeeCompensationUpdate,
    db: Session = Depends(get_db)
):
    """Update an employee compensation"""
    compensation = db.query(models.EmployeeCompensation).filter(
        models.EmployeeCompensation.id == compensation_id
    ).first()
    if not compensation:
        raise HTTPException(status_code=404, detail="Compensation not found")
    
    update_data = compensation_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(compensation, key, value)
    
    db.commit()
    db.refresh(compensation)
    return compensation


@router.delete("/compensations/{compensation_id}")
def delete_compensation(compensation_id: int, db: Session = Depends(get_db)):
    """Delete an employee compensation"""
    compensation = db.query(models.EmployeeCompensation).filter(
        models.EmployeeCompensation.id == compensation_id
    ).first()
    if not compensation:
        raise HTTPException(status_code=404, detail="Compensation not found")
    
    db.delete(compensation)
    db.commit()
    return {"message": "Compensation deleted", "id": compensation_id}


# ========== PAYROLL PERIOD ENDPOINTS ==========

@router.get("/payroll/periods", response_model=List[PayrollPeriod])
def get_payroll_periods(
    skip: int = 0,
    limit: int = 100,
    year: int = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get all payroll periods with optional filtering"""
    query = db.query(models.PayrollPeriod)
    
    if year:
        query = query.filter(models.PayrollPeriod.year == year)
    if status:
        query = query.filter(models.PayrollPeriod.status == status)
    
    periods = query.order_by(models.PayrollPeriod.year.desc(), models.PayrollPeriod.month.desc()).offset(skip).limit(limit).all()
    return periods


@router.get("/payroll/periods/{period_id}", response_model=PayrollPeriod)
def get_payroll_period(period_id: int, db: Session = Depends(get_db)):
    """Get a specific payroll period by ID"""
    period = db.query(models.PayrollPeriod).filter(models.PayrollPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    return period


@router.post("/payroll/periods", response_model=PayrollPeriod, status_code=201)
def create_payroll_period(period: PayrollPeriodCreate, db: Session = Depends(get_db)):
    """Create a new payroll period"""
    # Check if period already exists
    existing = db.query(models.PayrollPeriod).filter(
        models.PayrollPeriod.year == period.year,
        models.PayrollPeriod.month == period.month
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Payroll period already exists for this month")
    
    db_period = models.PayrollPeriod(**period.model_dump())
    db.add(db_period)
    db.commit()
    db.refresh(db_period)
    return db_period


@router.patch("/payroll/periods/{period_id}", response_model=PayrollPeriod)
def update_payroll_period(
    period_id: int,
    period_update: PayrollPeriodUpdate,
    db: Session = Depends(get_db)
):
    """Update a payroll period"""
    period = db.query(models.PayrollPeriod).filter(models.PayrollPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    
    update_data = period_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(period, key, value)
    
    db.commit()
    db.refresh(period)
    return period


@router.post("/payroll/periods/{period_id}/process")
def process_payroll(period_id: int, db: Session = Depends(get_db)):
    """Process payroll for a period - create entries for all active employees"""
    period = db.query(models.PayrollPeriod).filter(models.PayrollPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    
    if period.status != "draft":
        raise HTTPException(status_code=400, detail="Payroll period is not in draft status")
    
    # Get all active employees
    employees = db.query(models.Employee).filter(models.Employee.is_active == 1).all()
    
    total_gross = 0.0
    total_net = 0.0
    
    for employee in employees:
        # Get active compensations
        compensations = db.query(models.EmployeeCompensation).filter(
            models.EmployeeCompensation.employee_id == employee.id,
            models.EmployeeCompensation.is_active == 1,
            models.EmployeeCompensation.end_date.is_(None)
        ).all()
        
        # Calculate base salary and benefits
        base_salary = 0.0
        benefits_total = 0.0
        
        for comp in compensations:
            if comp.benefit_type.code == 'base_salary':
                base_salary = comp.amount
            else:
                benefits_total += comp.amount
        
        gross_salary = base_salary + benefits_total
        # For now, no deductions calculation - can be enhanced later
        net_salary = gross_salary
        
        # Create payroll entry
        entry = models.PayrollEntry(
            period_id=period.id,
            employee_id=employee.id,
            base_salary=base_salary,
            benefits_total=benefits_total,
            gross_salary=gross_salary,
            deductions=0.0,
            net_salary=net_salary
        )
        db.add(entry)
        
        total_gross += gross_salary
        total_net += net_salary
    
    # Update period totals and status
    period.total_gross = total_gross
    period.total_net = total_net
    period.status = "processed"
    period.processed_date = datetime.utcnow()
    
    db.commit()
    db.refresh(period)
    
    return {
        "message": "Payroll processed successfully",
        "period_id": period.id,
        "employees_count": len(employees),
        "total_gross": total_gross,
        "total_net": total_net
    }


@router.post("/payroll/periods/{period_id}/upload")
async def upload_payroll_file(
    period_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload CSV file with employee payroll data (employee_id, net_amount)"""
    period = db.query(models.PayrollPeriod).filter(models.PayrollPeriod.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Payroll period not found")
    
    # Read CSV file
    contents = await file.read()
    csv_data = contents.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(csv_data))
    
    updated_count = 0
    errors = []
    
    for row in csv_reader:
        try:
            employee_id_str = row.get('employee_id', '').strip()
            net_amount = float(row.get('net_amount', 0))
            
            # Find employee
            employee = db.query(models.Employee).filter(
                models.Employee.employee_id == employee_id_str
            ).first()
            
            if not employee:
                errors.append(f"Employee {employee_id_str} not found")
                continue
            
            # Find or create payroll entry
            entry = db.query(models.PayrollEntry).filter(
                models.PayrollEntry.period_id == period_id,
                models.PayrollEntry.employee_id == employee.id
            ).first()
            
            if entry:
                # Update existing entry
                entry.net_salary = net_amount
            else:
                # Create new entry
                entry = models.PayrollEntry(
                    period_id=period_id,
                    employee_id=employee.id,
                    base_salary=0.0,
                    benefits_total=0.0,
                    gross_salary=net_amount,
                    deductions=0.0,
                    net_salary=net_amount
                )
                db.add(entry)
            
            updated_count += 1
            
        except Exception as e:
            errors.append(f"Error processing row {row}: {str(e)}")
    
    # Recalculate period totals
    entries = db.query(models.PayrollEntry).filter(
        models.PayrollEntry.period_id == period_id
    ).all()
    
    period.total_gross = sum(entry.gross_salary for entry in entries)
    period.total_net = sum(entry.net_salary for entry in entries)
    
    db.commit()
    
    return {
        "message": "Payroll file uploaded successfully",
        "updated_count": updated_count,
        "errors": errors
    }


# ========== PAYROLL ENTRY ENDPOINTS ==========

@router.get("/payroll/entries", response_model=List[PayrollEntry])
def get_payroll_entries(
    period_id: int = None,
    employee_id: int = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get payroll entries with optional filtering"""
    query = db.query(models.PayrollEntry)
    
    if period_id:
        query = query.filter(models.PayrollEntry.period_id == period_id)
    if employee_id:
        query = query.filter(models.PayrollEntry.employee_id == employee_id)
    
    entries = query.offset(skip).limit(limit).all()
    return entries


@router.patch("/payroll/entries/{entry_id}", response_model=PayrollEntry)
def update_payroll_entry(
    entry_id: int,
    entry_update: PayrollEntryUpdate,
    db: Session = Depends(get_db)
):
    """Update a payroll entry"""
    entry = db.query(models.PayrollEntry).filter(models.PayrollEntry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Payroll entry not found")
    
    update_data = entry_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)
    
    db.commit()
    db.refresh(entry)
    return entry
