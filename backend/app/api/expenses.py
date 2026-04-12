from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import io
import json
import os
import tempfile

from app.core.database import get_db
from app.core.auth import get_current_user
from app.models import models
from app.models.user import User, UserRole
from app.storage.storage import storage, LocalStorageBackend
from app.schemas.hr_schemas import (
    ExpenseReportCreate, ExpenseReportUpdate, ExpenseReportOut,
)
from app.services.qr_parser import PortugueseQRCodeParser

router = APIRouter(prefix="/expenses", tags=["expenses"])


def _get_user_employee(current_user: User, db: Session) -> Optional[models.Employee]:
    """Return the Employee linked to this user account, or None."""
    return db.query(models.Employee).filter(models.Employee.user_id == current_user.id).first()


def _assert_report_access(report: models.ExpenseReport, current_user: User, db: Session):
    """Raise 403 if a 'user' role tries to access a report that isn't theirs."""
    if current_user.role != UserRole.USER:
        return
    emp = _get_user_employee(current_user, db)
    if not emp or report.employee_id != emp.id:
        raise HTTPException(status_code=403, detail="Access denied")


def _serialize_report(report: models.ExpenseReport) -> dict:
    emp = report.employee
    employee_name = f"{emp.first_name} {emp.last_name}" if emp else None
    items = []
    for item in report.items:
        supplier_name = None
        invoice_number = None
        invoice_date = None
        if item.invoice:
            invoice_number = item.invoice.invoice_number
            invoice_date = item.invoice.invoice_date
            if item.invoice.supplier:
                supplier_name = item.invoice.supplier.name
            elif item.invoice.customer:
                supplier_name = item.invoice.customer.name
        items.append({
            "id": item.id,
            "report_id": item.report_id,
            "description": item.description,
            "category": item.category,
            "amount": item.amount,
            "currency": item.currency,
            "eur_amount": item.eur_amount,
            "exchange_rate": item.exchange_rate,
            "expense_date": item.expense_date,
            "file_path": item.file_path,
            "original_filename": item.original_filename,
            "notes": item.notes,
            "created_at": item.created_at,
            "invoice_id": item.invoice_id,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "supplier_name": supplier_name,
        })
    # Use eur_amount for totals when the item is in a foreign currency
    total_amount = sum(i["eur_amount"] if i["eur_amount"] is not None else i["amount"] for i in items)
    return {
        "id": report.id,
        "expense_id": report.expense_id,
        "employee_id": report.employee_id,
        "employee_name": employee_name,
        "title": report.title,
        "description": report.description,
        "status": report.status,
        "submitted_at": report.submitted_at,
        "approved_at": report.approved_at,
        "paid_at": report.paid_at,
        "bank_transaction_id": report.bank_transaction_id,
        "notes": report.notes,
        "created_at": report.created_at,
        "updated_at": report.updated_at,
        "items": items,
        "total_amount": total_amount,
    }


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def _generate_expense_id(db: Session) -> str:
    """Return the next sequential EXP-YYYY-NNN identifier."""
    from sqlalchemy import func
    year = datetime.utcnow().year
    prefix = f"EXP-{year}-"
    last = db.query(func.max(models.ExpenseReport.expense_id)).filter(
        models.ExpenseReport.expense_id.like(f"{prefix}%")
    ).scalar()
    if last:
        try:
            num = int(last.rsplit("-", 1)[-1]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    return f"{prefix}{num:03d}"

@router.get("/reports")
def list_reports(
    employee_id: Optional[int] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(models.ExpenseReport)
    if current_user.role == UserRole.USER:
        emp = _get_user_employee(current_user, db)
        if not emp:
            return []
        q = q.filter(models.ExpenseReport.employee_id == emp.id)
    elif employee_id:
        q = q.filter(models.ExpenseReport.employee_id == employee_id)
    if status:
        q = q.filter(models.ExpenseReport.status == status)
    reports = q.order_by(models.ExpenseReport.created_at.desc()).all()
    return [_serialize_report(r) for r in reports]


@router.post("/reports", status_code=201)
def create_report(
    payload: ExpenseReportCreate,
    employee_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.USER:
        emp = _get_user_employee(current_user, db)
        if not emp:
            raise HTTPException(status_code=403, detail="No employee record linked to your account")
        employee_id = emp.id
        employee = emp
    else:
        if not employee_id:
            raise HTTPException(status_code=422, detail="employee_id is required")
        employee = db.query(models.Employee).filter(models.Employee.id == employee_id).first()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

    expense_id = _generate_expense_id(db)
    report = models.ExpenseReport(
        expense_id=expense_id,
        employee_id=employee_id,
        title=payload.title,
        description=payload.description,
        notes=payload.notes,
        status="draft",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return _serialize_report(report)


@router.get("/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    _assert_report_access(report, current_user, db)
    return _serialize_report(report)


@router.patch("/reports/{report_id}")
def update_report(
    report_id: int,
    payload: ExpenseReportUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    _assert_report_access(report, current_user, db)
    if report.status != "draft":
        raise HTTPException(status_code=400, detail="Only draft reports can be edited")

    if payload.title is not None:
        report.title = payload.title
    if payload.description is not None:
        report.description = payload.description
    if payload.notes is not None:
        report.notes = payload.notes

    db.commit()
    db.refresh(report)
    return _serialize_report(report)


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    _assert_report_access(report, current_user, db)
    if report.status not in ("draft",):
        raise HTTPException(status_code=400, detail="Only draft reports can be deleted")
    db.delete(report)
    db.commit()


@router.post("/reports/{report_id}/submit")
def submit_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    _assert_report_access(report, current_user, db)
    if report.status != "draft":
        raise HTTPException(status_code=400, detail="Report is not in draft status")
    if not report.items:
        raise HTTPException(status_code=400, detail="Cannot submit a report with no expense items")

    report.status = "submitted"
    report.submitted_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return _serialize_report(report)


@router.post("/reports/{report_id}/approve")
def approve_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.USER:
        raise HTTPException(status_code=403, detail="Access denied")
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    if report.status != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted reports can be approved")

    # Move each item's receipt from temporary to permanent storage
    _TEMP_PREFIX = "expenses/temp/"
    for item in report.items:
        if item.file_path and item.file_path.startswith(_TEMP_PREFIX):
            permanent_path = "expenses/" + item.file_path[len(_TEMP_PREFIX):]
            if storage.move(item.file_path, permanent_path):
                item.file_path = permanent_path

    # Create invoices for each item
    for item in report.items:
        if not item.invoice_id:
            try:
                inv_id = _create_invoice_for_item(item, report, db)
                item.invoice_id = inv_id
            except Exception as e:
                print(f"Failed to create invoice for expense item {item.id}: {e}")

    report.status = "approved"
    report.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return _serialize_report(report)


@router.post("/reports/{report_id}/reject")
def reject_report(report_id: int, notes: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if current_user.role == UserRole.USER:
        raise HTTPException(status_code=403, detail="Access denied")
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    if report.status != "submitted":
        raise HTTPException(status_code=400, detail="Only submitted reports can be rejected")
    report.status = "rejected"
    if notes:
        report.notes = notes
    db.commit()
    db.refresh(report)
    return _serialize_report(report)


@router.post("/reports/{report_id}/revise")
def revise_report(report_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Move a rejected report back to draft so it can be edited and resubmitted."""
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    _assert_report_access(report, current_user, db)
    if report.status != "rejected":
        raise HTTPException(status_code=400, detail="Only rejected reports can be revised")
    report.status = "draft"
    db.commit()
    db.refresh(report)
    return _serialize_report(report)


from pydantic import BaseModel as _PydanticBase

class _PayPayload(_PydanticBase):
    bank_transaction_id: int

@router.post("/reports/{report_id}/pay")
def pay_report(
    report_id: int,
    payload: _PayPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark an approved expense report as PAID and link it to a bank transfer."""
    if current_user.role == UserRole.USER:
        raise HTTPException(status_code=403, detail="Access denied")
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    if report.status != "approved":
        raise HTTPException(status_code=400, detail="Only approved reports can be marked as paid")

    tx = db.query(models.BankTransaction).filter(models.BankTransaction.id == payload.bank_transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Bank transaction not found")

    report.status = "paid"
    report.paid_at = tx.transaction_date
    report.bank_transaction_id = tx.id

    # Mark the bank transaction as reconciled
    tx.is_reconciled = 1

    expense_ref = report.expense_id or f"EXP-{report.id}"

    # For each item's invoice: create a direct payment record linked to the bank
    # transaction and mark the invoice as PAID + reconciled.
    for item in report.items:
        if not item.invoice_id:
            continue
        inv = db.query(models.Invoice).filter(models.Invoice.id == item.invoice_id).first()
        if not inv:
            continue

        # Avoid duplicate payment records for this invoice+transaction pair
        existing_payment = db.query(models.InvoiceDirectPayment).filter(
            models.InvoiceDirectPayment.invoice_id == inv.id,
            models.InvoiceDirectPayment.bank_transaction_id == tx.id,
        ).first()
        if not existing_payment:
            eur_amount = item.eur_amount if item.eur_amount else item.amount
            db.add(models.InvoiceDirectPayment(
                invoice_id=inv.id,
                payment_date=tx.transaction_date,
                amount=eur_amount,
                payment_type="company_account",
                reference=expense_ref,
                bank_transaction_id=tx.id,
                notes=f"Paid via expense report {expense_ref}",
            ))

        inv.status = models.InvoiceStatus.PAID

    db.commit()
    db.refresh(report)
    return _serialize_report(report)




_ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}


def _create_invoice_for_item(
    item: models.ExpenseItem,
    report: models.ExpenseReport,
    db: Session,
) -> Optional[int]:
    """Create (or link to an existing) accounting Invoice for one expense item.

    Uses QR data already stored on the item — never re-scans the file.
    Returns the invoice id.
    """
    employee = report.employee
    emp_name = f"{employee.first_name} {employee.last_name}" if employee else "Unknown"
    expense_ref = report.expense_id or f"EXP-{report.id}"
    expense_note = f"Expense Report {expense_ref}: {report.title} — {emp_name}"

    # Use QR data stored at item-creation time — no file re-scan
    qr_data = json.loads(item.qr_data) if item.qr_data else None

    supplier: Optional[models.Company] = None
    invoice_number: str

    if qr_data:
        # Build supplier from QR NIF
        supplier_nif = qr_data.get("nif_emitente")
        if supplier_nif:
            supplier = db.query(models.Company).filter(models.Company.nif == supplier_nif).first()
            if not supplier:
                supplier = models.Company(
                    nif=supplier_nif,
                    name=f"Supplier {supplier_nif}",
                    is_supplier=True,
                    is_customer=False,
                )
                db.add(supplier)
                db.flush()

        invoice_number = qr_data.get("identificacao_documento") or f"{expense_ref}/{item.id}"

        # Deduplicate: if this invoice already exists, append note and link
        if supplier:
            existing = db.query(models.Invoice).filter(
                models.Invoice.supplier_id == supplier.id,
                models.Invoice.invoice_number == invoice_number,
            ).first()
            if existing:
                existing.notes = (
                    f"{existing.notes}\n{expense_note}"
                    if existing.notes and expense_note not in existing.notes
                    else expense_note
                )
                db.flush()
                return existing.id

        # Parse date from QR
        date_str = qr_data.get("data_documento")
        invoice_date = datetime.utcnow()
        if date_str:
            for fmt in ("%Y-%m-%d", "%Y%m%d"):
                try:
                    invoice_date = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    pass

        base_amounts = qr_data.get("base_incidencia_iva") or []
        iva_amounts = qr_data.get("total_iva") or []
        subtotal = sum(base_amounts) if base_amounts else 0.0
        tax_amount = sum(iva_amounts) if iva_amounts else float(qr_data.get("total_impostos") or 0)
        total = float(qr_data.get("total_documento") or 0) or (subtotal + tax_amount) or item.amount
    else:
        # No QR data stored — build invoice from the expense item fields directly
        invoice_number = f"{expense_ref}/{item.id}"
        invoice_date = item.expense_date
        total = item.eur_amount if item.eur_amount else item.amount
        subtotal = round(total / 1.23, 2)  # assume standard 23 % VAT
        tax_amount = round(total - subtotal, 2)

    # Use EUR equivalent as the accounting total; preserve original FC info
    eur_total = item.eur_amount if item.eur_amount else total
    invoice = models.Invoice(
        invoice_number=invoice_number,
        invoice_type=models.InvoiceType.PURCHASE,
        invoice_date=invoice_date,
        supplier_id=supplier.id if supplier else None,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=eur_total,
        is_foreign_currency=1 if item.currency != "EUR" else 0,
        foreign_currency_code=item.currency if item.currency != "EUR" else None,
        original_total_amount=item.amount if item.currency != "EUR" else None,
        exchange_rate=item.exchange_rate if item.currency != "EUR" else None,
        file_path=item.file_path,
        original_filename=item.original_filename,
        notes=expense_note,
        status=models.InvoiceStatus.DRAFT,
    )
    db.add(invoice)
    db.flush()
    return invoice.id


def _qr_extract(file_ext: str, file_path_stored: str) -> tuple:
    """Run QR extraction on a stored file. Returns (qr_data_dict | None, method | None)."""
    if file_ext not in ("pdf", "png", "jpg", "jpeg"):
        return None, None
    try:
        if isinstance(storage, LocalStorageBackend):
            full_path = str(storage.get_full_path(file_path_stored))
            parsed_data, method, _ = PortugueseQRCodeParser.extract_and_parse(
                full_path, use_ocr_fallback=True
            )
        elif hasattr(storage, "client"):
            ext_suffix = f".{file_ext}"
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext_suffix) as tmp:
                storage.client.download_fileobj(storage.bucket_name, file_path_stored, tmp)
                tmp.flush()
                parsed_data, method, _ = PortugueseQRCodeParser.extract_and_parse(
                    tmp.name, use_ocr_fallback=True
                )
            os.unlink(tmp.name)
        else:
            return None, None
        return (parsed_data, method) if parsed_data else (None, None)
    except Exception as e:
        print(f"QR extraction error: {e}")
        return None, None


@router.post("/parse-invoice")
async def parse_expense_invoice(
    file: UploadFile = File(...),
    report_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a receipt/invoice, extract QR data, and return the stored file path."""
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}"
        )

    # Determine folder: use expense_id subfolder when the report is known
    folder = "expenses/temp"
    if report_id:
        report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
        if report:
            expense_id_slug = report.expense_id or f"EXP-{report_id}"
            folder = f"expenses/temp/{expense_id_slug}"

    file_path = await storage.save(file.file, file.filename, folder=folder)
    qr_data, extraction_method = _qr_extract(ext, file_path)
    file_url = await storage.get_url(file_path)

    return {
        "file_path": file_path,
        "file_url": file_url,
        "original_filename": file.filename,
        "qr_data": qr_data,
        "extraction_method": extraction_method,
    }


@router.post("/reports/{report_id}/items", status_code=201)
async def add_expense_item(
    report_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    expense_date: str = Form(...),
    category: Optional[str] = Form(None),
    currency: str = Form("EUR"),
    eur_amount: Optional[float] = Form(None),
    exchange_rate: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    original_filename: Optional[str] = Form(None),
    qr_data_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(models.ExpenseReport).filter(models.ExpenseReport.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="Expense report not found")
    _assert_report_access(report, current_user, db)
    if report.status != "draft":
        raise HTTPException(status_code=400, detail="Items can only be added to draft reports")

    expense_id_slug = report.expense_id or f"EXP-{report_id}"
    temp_folder = f"expenses/temp/{expense_id_slug}"

    if file_path:
        # File was already uploaded via /parse-invoice — move into the report subfolder
        filename = file_path.rsplit("/", 1)[-1]
        target_path = f"{temp_folder}/{filename}"
        if file_path != target_path:
            storage.move(file_path, target_path)
            saved_path = target_path
        else:
            saved_path = file_path
        fname = original_filename or filename
    elif file:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}"
            )
        saved_path = await storage.save(file.file, file.filename, folder=temp_folder)
        fname = file.filename
    else:
        raise HTTPException(status_code=400, detail="Either file upload or file_path is required")

    try:
        parsed_date = datetime.fromisoformat(expense_date)
    except ValueError:
        parsed_date = datetime.strptime(expense_date, "%Y-%m-%d")

    # For foreign currency items: store the FC amount and EUR equivalent
    # eur_amount is None for EUR items (amount IS the EUR amount)
    effective_eur_amount = None
    effective_exchange_rate = None
    if currency != "EUR":
        effective_eur_amount = eur_amount
        if eur_amount and eur_amount > 0 and amount > 0:
            effective_exchange_rate = exchange_rate or round(amount / eur_amount, 6)

    # Use pre-parsed QR data when available (passed from /parse-invoice step);
    # only re-scan when the file was directly uploaded without pre-parsing.
    if file_path and qr_data_json is not None:
        try:
            stored_qr = json.loads(qr_data_json)
        except (json.JSONDecodeError, TypeError):
            stored_qr = None
    elif not file_path:
        # Direct file upload — scan now so approval never needs to re-scan
        file_ext_for_qr = saved_path.rsplit(".", 1)[-1].lower() if "." in saved_path else ""
        stored_qr, _ = _qr_extract(file_ext_for_qr, saved_path)
    else:
        # file_path provided but no qr_data sent — pre-parsed; QR not found
        stored_qr = None

    item = models.ExpenseItem(
        report_id=report_id,
        description=description,
        category=category,
        amount=amount,
        currency=currency,
        eur_amount=effective_eur_amount,
        exchange_rate=effective_exchange_rate,
        expense_date=parsed_date,
        file_path=saved_path,
        original_filename=fname,
        qr_data=json.dumps(stored_qr) if stored_qr else None,
        notes=notes,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "id": item.id,
        "report_id": item.report_id,
        "description": item.description,
        "category": item.category,
        "amount": item.amount,
        "currency": item.currency,
        "eur_amount": item.eur_amount,
        "exchange_rate": item.exchange_rate,
        "expense_date": item.expense_date,
        "file_path": item.file_path,
        "original_filename": item.original_filename,
        "notes": item.notes,
        "created_at": item.created_at,
    }


@router.delete("/items/{item_id}", status_code=204)
async def delete_expense_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.query(models.ExpenseItem).filter(models.ExpenseItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Expense item not found")
    _assert_report_access(item.report, current_user, db)
    if item.report.status != "draft":
        raise HTTPException(status_code=400, detail="Items can only be removed from draft reports")

    await storage.delete(item.file_path)
    db.delete(item)
    db.commit()


@router.patch("/items/{item_id}")
async def update_expense_item(
    item_id: int,
    description: str = Form(...),
    amount: float = Form(...),
    expense_date: str = Form(...),
    category: Optional[str] = Form(None),
    currency: str = Form("EUR"),
    eur_amount: Optional[float] = Form(None),
    exchange_rate: Optional[float] = Form(None),
    notes: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    file_path: Optional[str] = Form(None),
    original_filename: Optional[str] = Form(None),
    qr_data_json: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update an expense item's details. Omit file fields to keep the existing file."""
    item = db.query(models.ExpenseItem).filter(models.ExpenseItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Expense item not found")
    _assert_report_access(item.report, current_user, db)
    if item.report.status != "draft":
        raise HTTPException(status_code=400, detail="Items can only be edited on draft reports")

    item.description = description
    item.category = category or None
    item.amount = amount
    item.currency = currency
    item.notes = notes or None

    try:
        parsed_date = datetime.fromisoformat(expense_date)
    except ValueError:
        parsed_date = datetime.strptime(expense_date, "%Y-%m-%d")
    item.expense_date = parsed_date

    if currency != "EUR":
        item.eur_amount = eur_amount
        if eur_amount and eur_amount > 0 and amount > 0:
            item.exchange_rate = exchange_rate or round(amount / eur_amount, 6)
        else:
            item.exchange_rate = None
    else:
        item.eur_amount = None
        item.exchange_rate = None

    if file_path and file_path != item.file_path:
        # Pre-parsed replacement file — delete old, use new
        try:
            await storage.delete(item.file_path)
        except Exception:
            pass
        item.file_path = file_path
        item.original_filename = original_filename or file_path.rsplit("/", 1)[-1]
        if qr_data_json is not None:
            try:
                json.loads(qr_data_json)  # validate
                item.qr_data = qr_data_json
            except (json.JSONDecodeError, TypeError):
                item.qr_data = None
        else:
            item.qr_data = None
    elif file:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in _ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed: {', '.join(_ALLOWED_EXTENSIONS)}"
            )
        try:
            await storage.delete(item.file_path)
        except Exception:
            pass
        expense_id_slug = item.report.expense_id or f"EXP-{item.report_id}"
        saved_path = await storage.save(file.file, file.filename, folder=f"expenses/temp/{expense_id_slug}")
        item.file_path = saved_path
        item.original_filename = file.filename
        file_ext_for_qr = saved_path.rsplit(".", 1)[-1].lower() if "." in saved_path else ""
        stored_qr, _ = _qr_extract(file_ext_for_qr, saved_path)
        item.qr_data = json.dumps(stored_qr) if stored_qr else None
    # else: no new file provided → keep existing file_path and qr_data

    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "report_id": item.report_id,
        "description": item.description,
        "category": item.category,
        "amount": item.amount,
        "currency": item.currency,
        "eur_amount": item.eur_amount,
        "exchange_rate": item.exchange_rate,
        "expense_date": item.expense_date,
        "file_path": item.file_path,
        "original_filename": item.original_filename,
        "notes": item.notes,
        "created_at": item.created_at,
        "invoice_id": item.invoice_id,
    }


@router.get("/items/{item_id}/file")
async def download_expense_item_file(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Proxy-download the receipt/invoice file."""
    item = db.query(models.ExpenseItem).filter(models.ExpenseItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Expense item not found")
    _assert_report_access(item.report, current_user, db)
    if not storage.exists(item.file_path):
        raise HTTPException(status_code=404, detail="File not found in storage")

    filename = item.original_filename or "receipt"

    import mimetypes
    content_type, _ = mimetypes.guess_type(filename)
    content_type = content_type or "application/octet-stream"

    if isinstance(storage, LocalStorageBackend):
        full_path = storage.get_full_path(item.file_path)
        return FileResponse(str(full_path), filename=filename, media_type=content_type)
    else:
        buf = io.BytesIO()
        storage.client.download_fileobj(storage.bucket_name, item.file_path, buf)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type=content_type,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )
