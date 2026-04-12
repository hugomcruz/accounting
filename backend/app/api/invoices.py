from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.auth import get_current_user
from app.schemas.schemas import Invoice, InvoiceCreate, InvoiceUpdate, InvoiceDirectPaymentCreate, InvoiceDirectPaymentOut, InvoiceCommentCreate, InvoiceCommentUpdate, InvoiceCommentOut
from app.models import models
from app.models.user import User
from app.storage.storage import storage

router = APIRouter(prefix="/invoices", tags=["invoices"])


@router.get("/count")
def count_invoices(
    invoice_type: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get total invoice count with optional filtering"""
    query = db.query(models.Invoice)
    if invoice_type:
        query = query.filter(models.Invoice.invoice_type == invoice_type)
    if status:
        query = query.filter(models.Invoice.status == status)
    return {"count": query.count()}


@router.get("/", response_model=List[Invoice])
def get_invoices(
    skip: int = 0,
    limit: int = 100,
    invoice_type: str = None,
    status: str = None,
    start_date: str = None,
    end_date: str = None,
    order_by: str = "created_at",
    reconciled_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get all invoices with optional filtering"""
    from datetime import datetime
    query = db.query(models.Invoice)
    
    if invoice_type:
        query = query.filter(models.Invoice.invoice_type == invoice_type)
    if status:
        query = query.filter(models.Invoice.status == status)
    if start_date:
        # Convert string to datetime for comparison
        start_dt = datetime.fromisoformat(start_date)
        query = query.filter(models.Invoice.invoice_date >= start_dt)
    if end_date:
        # Convert string to datetime for comparison
        end_dt = datetime.fromisoformat(end_date)
        query = query.filter(models.Invoice.invoice_date <= end_dt)

    if reconciled_only:
        bank_recon_subq = db.query(models.BankTransaction.invoice_id).filter(
            models.BankTransaction.is_reconciled == 1,
            models.BankTransaction.invoice_id.isnot(None)
        ).subquery()
        query = query.filter(
            (models.Invoice.id.in_(bank_recon_subq)) |
            (models.Invoice.status == models.InvoiceStatus.PAID)
        )

    sort_col = models.Invoice.invoice_date if order_by == "invoice_date" else models.Invoice.id
    invoices = query.order_by(sort_col.desc()).offset(skip).limit(limit).all()

    # Attach company names without requiring a schema change in the ORM model
    company_ids = set()
    for inv in invoices:
        if inv.supplier_id:
            company_ids.add(inv.supplier_id)
        if inv.customer_id:
            company_ids.add(inv.customer_id)
    companies = {}
    if company_ids:
        for c in db.query(models.Company).filter(models.Company.id.in_(company_ids)).all():
            companies[c.id] = c.name
    for inv in invoices:
        inv.supplier_name = companies.get(inv.supplier_id) if inv.supplier_id else None
        inv.customer_name = companies.get(inv.customer_id) if inv.customer_id else None

    # Attach reconciliation info
    invoice_ids = [inv.id for inv in invoices]
    # Map invoice_id -> list of linked bank transactions
    tx_map: dict = {}
    if invoice_ids:
        txs = db.query(models.BankTransaction).filter(
            models.BankTransaction.invoice_id.in_(invoice_ids),
            models.BankTransaction.is_reconciled == 1
        ).all()
        for tx in txs:
            tx_map.setdefault(tx.invoice_id, []).append(tx)
    # Map invoice_id -> list of direct payments
    payment_map: dict = {}
    if invoice_ids:
        direct_payments = db.query(models.InvoiceDirectPayment).filter(
            models.InvoiceDirectPayment.invoice_id.in_(invoice_ids)
        ).all()
        for p in direct_payments:
            payment_map.setdefault(p.invoice_id, []).append(p)
    for inv in invoices:
        linked_txs = tx_map.get(inv.id, [])
        inv_payments = payment_map.get(inv.id, [])
        direct_paid = round(sum(p.amount for p in inv_payments), 2)

        inv.is_reconciled = bool(linked_txs) or inv.status == models.InvoiceStatus.PAID or direct_paid >= inv.total_amount - 0.01
        # Prefer bank_transaction_id from direct payment (expense report path) if no direct tx link
        if linked_txs:
            inv.bank_transaction_id = linked_txs[0].id
        elif inv_payments and inv_payments[0].bank_transaction_id:
            inv.bank_transaction_id = inv_payments[0].bank_transaction_id
        else:
            inv.bank_transaction_id = None
        inv.linked_transaction_ids = [tx.id for tx in linked_txs]
        if linked_txs:
            bank_total = sum(abs(tx.amount) for tx in linked_txs)
            inv.reconciled_amount = round(bank_total, 2)
        else:
            inv.reconciled_amount = direct_paid
        inv.is_partial = inv.is_reconciled and inv.reconciled_amount > 0 and abs(inv.reconciled_amount - inv.total_amount) > 0.01
        inv.payments = inv_payments
        inv.total_paid = direct_paid
        inv.remaining_amount = round(inv.total_amount - direct_paid, 2)

    return invoices


@router.get("/{invoice_id}", response_model=Invoice)
def get_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Get a specific invoice by ID"""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    # Attach reconciliation info
    linked_txs = db.query(models.BankTransaction).filter(
        models.BankTransaction.invoice_id == invoice_id,
        models.BankTransaction.is_reconciled == 1
    ).all()
    inv_payments = db.query(models.InvoiceDirectPayment).filter(
        models.InvoiceDirectPayment.invoice_id == invoice_id
    ).order_by(models.InvoiceDirectPayment.payment_date.desc()).all()
    direct_paid = round(sum(p.amount for p in inv_payments), 2)

    invoice.is_reconciled = bool(linked_txs) or invoice.status == models.InvoiceStatus.PAID or direct_paid >= invoice.total_amount - 0.01
    if linked_txs:
        invoice.bank_transaction_id = linked_txs[0].id
    elif inv_payments and inv_payments[0].bank_transaction_id:
        invoice.bank_transaction_id = inv_payments[0].bank_transaction_id
    else:
        invoice.bank_transaction_id = None
    invoice.linked_transaction_ids = [tx.id for tx in linked_txs]
    if linked_txs:
        invoice.reconciled_amount = round(sum(abs(tx.amount) for tx in linked_txs), 2)
    else:
        invoice.reconciled_amount = direct_paid
    invoice.is_partial = invoice.is_reconciled and invoice.reconciled_amount > 0 and abs(invoice.reconciled_amount - invoice.total_amount) > 0.01
    invoice.payments = inv_payments
    invoice.total_paid = direct_paid
    invoice.remaining_amount = round(invoice.total_amount - direct_paid, 2)

    # Attach company names
    if invoice.supplier_id:
        supplier = db.query(models.Company).filter(models.Company.id == invoice.supplier_id).first()
        invoice.supplier_name = supplier.name if supplier else None
    if invoice.customer_id:
        customer = db.query(models.Company).filter(models.Company.id == invoice.customer_id).first()
        invoice.customer_name = customer.name if customer else None

    # Look up expense report if this invoice was created as an expense item
    expense_item = db.query(models.ExpenseItem).filter(
        models.ExpenseItem.invoice_id == invoice_id
    ).first()
    if expense_item:
        report = db.query(models.ExpenseReport).filter(
            models.ExpenseReport.id == expense_item.report_id
        ).first()
        if report:
            employee_name = None
            if report.employee:
                employee_name = f"{report.employee.first_name} {report.employee.last_name}"
            invoice.expense_report = type("_ER", (), {
                "id": report.id,
                "expense_id": report.expense_id,
                "title": report.title,
                "status": report.status,
                "paid_at": report.paid_at,
                "employee_name": employee_name,
            })()

    return invoice


@router.get("/{invoice_id}/file-url")
async def get_invoice_file_url(invoice_id: int, db: Session = Depends(get_db)):
    """Get a presigned/accessible URL for the invoice file"""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not invoice.file_path:
        raise HTTPException(status_code=404, detail="No file attached to this invoice")
    try:
        url = await storage.get_url(invoice.file_path)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating file URL: {str(e)}")


@router.post("/", response_model=Invoice, status_code=201)
def create_invoice(invoice: InvoiceCreate, db: Session = Depends(get_db)):
    """Create a new invoice"""
    # Check if invoice number already exists
    existing = db.query(models.Invoice).filter(
        models.Invoice.invoice_number == invoice.invoice_number
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Invoice with this number already exists")
    
    # Create invoice
    invoice_data = invoice.model_dump(exclude={'line_items'})
    db_invoice = models.Invoice(**invoice_data)
    db.add(db_invoice)
    db.flush()
    
    # Create line items
    for line_item in invoice.line_items:
        db_line = models.InvoiceLineItem(
            **line_item.model_dump(),
            invoice_id=db_invoice.id
        )
        db.add(db_line)
    
    db.commit()
    db.refresh(db_invoice)
    return db_invoice


@router.patch("/{invoice_id}", response_model=Invoice)
def update_invoice(
    invoice_id: int,
    invoice_update: InvoiceUpdate,
    db: Session = Depends(get_db)
):
    """Update an invoice"""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    update_data = invoice_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(invoice, key, value)
    
    db.commit()
    db.refresh(invoice)
    return invoice


@router.post("/{invoice_id}/attach-file")
async def attach_file_to_invoice(
    invoice_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Attach a file to an existing invoice (e.g. SAFT-imported)"""
    import os
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    allowed_exts = {'.pdf', '.png', '.jpg', '.jpeg'}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed_exts:
        raise HTTPException(status_code=400, detail="Only PDF and image files are allowed")
    try:
        file_path = await storage.save(file.file, file.filename, folder="invoices")
        invoice.file_path = file_path
        db.commit()
        url = await storage.get_url(file_path)
        return {"file_path": file_path, "url": url}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error attaching file: {str(e)}")


@router.delete("/{invoice_id}")
def delete_invoice(invoice_id: int, db: Session = Depends(get_db)):
    """Delete an invoice"""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    db.delete(invoice)
    db.commit()
    return {"message": "Invoice deleted successfully"}


@router.get("/{invoice_id}/payments", response_model=List[InvoiceDirectPaymentOut])
def get_invoice_payments(invoice_id: int, db: Session = Depends(get_db)):
    """List all direct payments for an invoice"""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return db.query(models.InvoiceDirectPayment).filter(
        models.InvoiceDirectPayment.invoice_id == invoice_id
    ).order_by(models.InvoiceDirectPayment.payment_date.desc()).all()


@router.post("/{invoice_id}/payments", response_model=InvoiceDirectPaymentOut, status_code=201)
def add_invoice_payment(
    invoice_id: int,
    payload: InvoiceDirectPaymentCreate,
    db: Session = Depends(get_db)
):
    """Add a direct payment to an invoice (cash, employee, company_account, other)"""
    invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")

    allowed_types = ('cash', 'employee', 'company_account', 'other')
    if payload.payment_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"payment_type must be one of {allowed_types}")

    employee_name = None
    if payload.payment_type == 'employee' and payload.employee_id:
        emp = db.query(models.Employee).filter(models.Employee.id == payload.employee_id).first()
        if emp:
            employee_name = f"{emp.first_name} {emp.last_name}"

    bank_transaction_id = None
    if payload.payment_type == 'company_account':
        if not payload.bank_transaction_id:
            raise HTTPException(status_code=400, detail="bank_transaction_id is required for company_account payments")
        tx = db.query(models.BankTransaction).filter(models.BankTransaction.id == payload.bank_transaction_id).first()
        if not tx:
            raise HTTPException(status_code=404, detail="Bank transaction not found")
        bank_transaction_id = tx.id
        # Also reconcile the bank transaction to this invoice
        tx.invoice_id = invoice_id
        tx.is_reconciled = 1
        if not tx.notes:
            tx.notes = f"Reconciled with invoice {invoice.invoice_number}"

    payment = models.InvoiceDirectPayment(
        invoice_id=invoice_id,
        payment_date=payload.payment_date,
        amount=payload.amount,
        payment_type=payload.payment_type,
        reference=payload.reference,
        employee_id=payload.employee_id,
        employee_name=employee_name,
        bank_transaction_id=bank_transaction_id,
        notes=payload.notes,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.delete("/{invoice_id}/payments/{payment_id}")
def delete_invoice_payment(
    invoice_id: int,
    payment_id: int,
    db: Session = Depends(get_db)
):
    """Delete a direct payment from an invoice"""
    payment = db.query(models.InvoiceDirectPayment).filter(
        models.InvoiceDirectPayment.id == payment_id,
        models.InvoiceDirectPayment.invoice_id == invoice_id,
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    db.delete(payment)
    db.commit()
    return {"message": "Payment deleted"}


# ─── Invoice Comments ─────────────────────────────────────────────────────────

@router.get("/{invoice_id}/comments", response_model=List[InvoiceCommentOut])
def get_invoice_comments(invoice_id: int, db: Session = Depends(get_db)):
    """List all comments for an invoice, oldest first."""
    return (
        db.query(models.InvoiceComment)
        .filter(models.InvoiceComment.invoice_id == invoice_id)
        .order_by(models.InvoiceComment.created_at.asc())
        .all()
    )


@router.post("/{invoice_id}/comments", response_model=InvoiceCommentOut, status_code=201)
def add_invoice_comment(
    invoice_id: int,
    payload: InvoiceCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a comment to an invoice."""
    if not db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first():
        raise HTTPException(status_code=404, detail="Invoice not found")
    comment = models.InvoiceComment(
        invoice_id=invoice_id,
        user_id=current_user.id,
        username=current_user.username,
        body=payload.body.strip(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment


@router.patch("/{invoice_id}/comments/{comment_id}", response_model=InvoiceCommentOut)
def update_invoice_comment(
    invoice_id: int,
    comment_id: int,
    payload: InvoiceCommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit your own comment."""
    comment = db.query(models.InvoiceComment).filter(
        models.InvoiceComment.id == comment_id,
        models.InvoiceComment.invoice_id == invoice_id,
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own comments")
    comment.body = payload.body.strip()
    db.commit()
    db.refresh(comment)
    return comment


@router.delete("/{invoice_id}/comments/{comment_id}")
def delete_invoice_comment(
    invoice_id: int,
    comment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete your own comment if it is less than 1 hour old."""
    comment = db.query(models.InvoiceComment).filter(
        models.InvoiceComment.id == comment_id,
        models.InvoiceComment.invoice_id == invoice_id,
    ).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")
    if comment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own comments")
    age = datetime.utcnow() - comment.created_at
    if age > timedelta(hours=1):
        raise HTTPException(status_code=403, detail="Comments can only be deleted within 1 hour of posting")
    db.delete(comment)
    db.commit()
    return {"message": "Comment deleted"}
