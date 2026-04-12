from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import List, Optional
from io import BytesIO
import os
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.auth import require_admin_or_finance, require_role, get_current_user
from app.storage.storage import storage
from app.services.bank_parser import BankStatementParser
from app.services.bank_reconciliation import BankReconciliationService
from app.schemas.bank_schemas import (
    BankStatement, BankStatementImportResponse, BankTransaction as BankTransactionSchema,
    BankAccountSchema, BankAccountUpdate, BankLogoCreate, BankLogoSchema,
    BankTransactionNoteCreate, BankTransactionNoteUpdate, BankTransactionNoteOut,
)
from app.models import models
from app.models.user import User

router = APIRouter(prefix="/bank", tags=["bank"])


# ─── Bank Accounts ────────────────────────────────────────────────────────────

@router.get("/accounts", response_model=List[BankAccountSchema])
def list_bank_accounts(db: Session = Depends(get_db)):
    return db.query(models.BankAccount).order_by(models.BankAccount.account_name).all()


@router.get("/accounts/{account_id}", response_model=BankAccountSchema)
def get_bank_account(account_id: int, db: Session = Depends(get_db)):
    acc = db.query(models.BankAccount).filter(models.BankAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Bank account not found")
    return acc


@router.patch("/accounts/{account_id}", response_model=BankAccountSchema)
def update_bank_account(
    account_id: int,
    data: BankAccountUpdate,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_finance),
):
    acc = db.query(models.BankAccount).filter(models.BankAccount.id == account_id).first()
    if not acc:
        raise HTTPException(status_code=404, detail="Bank account not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(acc, field, value)
    db.commit()
    db.refresh(acc)
    return acc


# ─── Bank Logos (CDN URL library – managed by admin) ─────────────────────────

@router.get("/logos", response_model=List[BankLogoSchema])
def list_bank_logos(db: Session = Depends(get_db)):
    return db.query(models.BankLogo).order_by(models.BankLogo.name).all()


@router.post("/logos", response_model=BankLogoSchema)
def create_bank_logo(
    data: BankLogoCreate,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    logo = models.BankLogo(name=data.name, url=data.url)
    db.add(logo)
    db.commit()
    db.refresh(logo)
    return logo


@router.delete("/logos/{logo_id}", status_code=204)
def delete_bank_logo(
    logo_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    logo = db.query(models.BankLogo).filter(models.BankLogo.id == logo_id).first()
    if not logo:
        raise HTTPException(status_code=404, detail="Logo not found")
    db.delete(logo)
    db.commit()


# ─── Import ───────────────────────────────────────────────────────────────────
@router.post("/import")
async def import_bank_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_finance),
):
    """
    Import bank statement CSV file
    
    Supports Portuguese bank formats (CGD)
    """
    
    # Validate file extension
    filename_lower = file.filename.lower()
    if not (filename_lower.endswith('.csv') or filename_lower.endswith('.xlsx')):
        raise HTTPException(status_code=400, detail="Only CSV and XLSX files are supported")
    
    try:
        # Read file content
        content = await file.read()

        # Parse according to file type
        parser = BankStatementParser()
        if filename_lower.endswith('.xlsx'):
            parsed_data = parser.parse_coverflex_xlsx(content)
        else:
            file_content = content.decode('utf-8', errors='replace')
            parsed_data = parser.parse_cgd_csv(file_content)
        
        # Validate parsed data
        if not parsed_data.get('account_info', {}).get('account_number'):
            raise HTTPException(status_code=400, detail="Could not parse account number from file")
        
        if not parsed_data.get('period', {}).get('start') or not parsed_data.get('period', {}).get('end'):
            raise HTTPException(status_code=400, detail="Could not parse statement period from file")
        
        # Save file - wrap bytes in BytesIO for file-like interface
        file_obj = BytesIO(content)
        file_path = await storage.save(file_obj, file.filename, "bank_statements")

        # Auto-upsert BankAccount record
        account_number = parsed_data['account_info'].get('account_number', '')
        bank_account = db.query(models.BankAccount).filter(
            models.BankAccount.account_number == account_number
        ).first()
        if not bank_account:
            bank_account = models.BankAccount(
                account_number=account_number,
                account_name=parsed_data['account_info'].get('company_name'),
                currency=parsed_data['account_info'].get('currency', 'EUR'),
            )
            db.add(bank_account)
            db.flush()

        # ── Duplicate detection ──────────────────────────────────────────────
        # Build a set of (date, amount, description) tuples from the incoming file
        incoming = [
            (
                t['transaction_date'].date() if hasattr(t['transaction_date'], 'date') else t['transaction_date'],
                round(t['amount'], 2),
                t['description'].strip(),
            )
            for t in parsed_data['transactions']
        ]
        if incoming:
            # Look for existing transactions on the same account that match ANY incoming row
            existing_stmts = db.query(models.BankStatement.id).filter(
                models.BankStatement.bank_account_id == bank_account.id
            ).subquery()
            existing_txs = db.query(
                models.BankTransaction.transaction_date,
                models.BankTransaction.amount,
                models.BankTransaction.description,
            ).filter(
                models.BankTransaction.statement_id.in_(existing_stmts)
            ).all()
            existing_set = {
                (
                    r.transaction_date.date() if hasattr(r.transaction_date, 'date') else r.transaction_date,
                    round(r.amount, 2),
                    r.description.strip(),
                )
                for r in existing_txs
            }
            duplicates = [row for row in incoming if row in existing_set]
            if duplicates:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Statement rejected: {len(duplicates)} duplicate transaction(s) already exist "
                        f"for account {account_number}. "
                        f"First duplicate: {duplicates[0][2]} on {duplicates[0][0]} ({duplicates[0][1]:.2f})"
                    ),
                )

        # Create bank statement record
        statement = models.BankStatement(
            filename=file.filename,
            file_path=file_path,
            account_number=account_number,
            account_currency=parsed_data['account_info'].get('currency', 'EUR'),
            company_name=parsed_data['account_info'].get('company_name'),
            company_nif=parsed_data['account_info'].get('nif'),
            period_start=parsed_data['period']['start'],
            period_end=parsed_data['period']['end'],
            opening_balance=parsed_data['balances'].get('opening_balance'),
            closing_balance=parsed_data['balances'].get('closing_balance'),
            available_balance=parsed_data['balances'].get('available_balance'),
            total_transactions=len(parsed_data['transactions']),
            bank_account_id=bank_account.id,
            status='processing'
        )
        
        db.add(statement)
        db.flush()
        
        # Import transactions
        imported = 0
        failed = 0
        
        for trans_data in parsed_data['transactions']:
            try:
                category = parser.categorize_transaction(trans_data['description'])
                
                transaction = models.BankTransaction(
                    statement_id=statement.id,
                    bank_account_id=bank_account.id,
                    transaction_date=trans_data['transaction_date'],
                    value_date=trans_data['value_date'],
                    description=trans_data['description'],
                    amount=trans_data['amount'],
                    balance_after=trans_data.get('balance_after'),
                    category=category,
                    is_reconciled=0  # SQLite boolean as integer
                )
                
                db.add(transaction)
                imported += 1
                
            except Exception as e:
                print(f"Error importing transaction: {str(e)}")
                failed += 1
                continue
        
        # Update statement
        statement.imported_transactions = imported
        statement.failed_transactions = failed
        statement.status = 'completed' if failed == 0 else 'completed_with_errors'
        statement.completed_at = datetime.utcnow()
        
        db.commit()
        db.refresh(statement)
        
        return BankStatementImportResponse(
            message="Bank statement imported successfully",
            statement_id=statement.id,
            account_number=statement.account_number,
            period_start=statement.period_start,
            period_end=statement.period_end,
            total_transactions=statement.total_transactions,
            imported_transactions=statement.imported_transactions,
            failed_transactions=statement.failed_transactions,
            opening_balance=statement.opening_balance,
            closing_balance=statement.closing_balance
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing bank statement: {str(e)}")


@router.get("/statements", response_model=List[BankStatement])
def get_statements(
    skip: int = 0,
    limit: int = 100,
    account_number: str = None,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_finance),
):
    """Get all bank statements"""
    query = db.query(models.BankStatement)
    
    if account_number:
        query = query.filter(models.BankStatement.account_number == account_number)
    
    statements = query.order_by(models.BankStatement.period_start.desc()).offset(skip).limit(limit).all()
    return statements


@router.get("/statements/{statement_id}", response_model=BankStatement)
def get_statement(statement_id: int, db: Session = Depends(get_db), _: None = Depends(require_admin_or_finance)):
    """Get specific bank statement with transactions"""
    statement = db.query(models.BankStatement).options(
        joinedload(models.BankStatement.transactions)
    ).filter(models.BankStatement.id == statement_id).first()
    
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")
    
    return statement


@router.get("/transactions", response_model=List[BankTransactionSchema])
def get_transactions(
    skip: int = 0,
    limit: int = 100,
    statement_id: int = None,
    category: str = None,
    is_reconciled: bool = None,
    start_date: str = None,
    end_date: str = None,
    month: int = None,
    year: int = None,
    search: str = None,
    account_number: str = None,
    db: Session = Depends(get_db)
):
    """Get bank transactions with filtering"""
    from sqlalchemy import or_
    query = db.query(models.BankTransaction).options(
        joinedload(models.BankTransaction.statement).joinedload(models.BankStatement.bank_account)
    )

    if statement_id:
        query = query.filter(models.BankTransaction.statement_id == statement_id)

    if account_number:
        query = query.join(models.BankTransaction.statement).filter(
            models.BankStatement.account_number == account_number
        )

    if category:
        query = query.filter(models.BankTransaction.category == category)

    if is_reconciled is not None:
        query = query.filter(models.BankTransaction.is_reconciled == (1 if is_reconciled else 0))

    if search:
        query = query.filter(models.BankTransaction.description.ilike(f"%{search}%"))

    # Date range filtering
    if start_date:
        query = query.filter(models.BankTransaction.transaction_date >= start_date)

    if end_date:
        query = query.filter(models.BankTransaction.transaction_date <= end_date)
    
    # Month/Year filtering
    if year:
        if month:
            # Filter by specific month and year
            from datetime import datetime
            start_of_month = datetime(year, month, 1)
            if month == 12:
                end_of_month = datetime(year + 1, 1, 1)
            else:
                end_of_month = datetime(year, month + 1, 1)
            query = query.filter(
                models.BankTransaction.transaction_date >= start_of_month,
                models.BankTransaction.transaction_date < end_of_month
            )
        else:
            # Filter by year only
            from datetime import datetime
            query = query.filter(
                models.BankTransaction.transaction_date >= datetime(year, 1, 1),
                models.BankTransaction.transaction_date < datetime(year + 1, 1, 1)
            )
    
    transactions = query.order_by(models.BankTransaction.transaction_date.desc()).offset(skip).limit(limit).all()

    # Build note_count map in one query
    tx_ids = [tx.id for tx in transactions]
    note_counts: dict[int, int] = {}
    if tx_ids:
        rows = (
            db.query(models.BankTransactionNote.transaction_id, func.count().label("cnt"))
            .filter(models.BankTransactionNote.transaction_id.in_(tx_ids))
            .group_by(models.BankTransactionNote.transaction_id)
            .all()
        )
        note_counts = {r.transaction_id: r.cnt for r in rows}

    # Enrich with account info from the linked statement → bank_account
    # Also resolve expense_report_id: bank txs used to pay expense reports
    er_map: dict[int, int] = {}
    if tx_ids:
        er_rows = db.query(
            models.ExpenseReport.bank_transaction_id,
            models.ExpenseReport.id,
        ).filter(
            models.ExpenseReport.bank_transaction_id.in_(tx_ids)
        ).all()
        er_map = {row.bank_transaction_id: row.id for row in er_rows}

    result = []
    for tx in transactions:
        d = BankTransactionSchema.model_validate(tx)
        d.note_count = note_counts.get(tx.id, 0)
        d.expense_report_id = er_map.get(tx.id)
        if tx.statement:
            d.account_number = tx.statement.account_number
            if tx.statement.bank_account:
                d.account_name = (
                    tx.statement.bank_account.account_name
                    or tx.statement.bank_account.account_number
                )
            else:
                d.account_name = tx.statement.company_name or tx.statement.account_number
        result.append(d)
    return result


@router.get("/transactions/{transaction_id}", response_model=BankTransactionSchema)
def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Get specific bank transaction"""
    transaction = db.query(models.BankTransaction).filter(
        models.BankTransaction.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")

    d = BankTransactionSchema.model_validate(transaction)
    d.note_count = db.query(func.count(models.BankTransactionNote.id)).filter(
        models.BankTransactionNote.transaction_id == transaction_id
    ).scalar() or 0
    # Resolve expense_report_id
    er = db.query(models.ExpenseReport).filter(
        models.ExpenseReport.bank_transaction_id == transaction_id
    ).first()
    if er:
        d.expense_report_id = er.id
    # Populate account info
    if transaction.statement:
        d.account_number = transaction.statement.account_number
        if transaction.statement.bank_account:
            d.account_name = (
                transaction.statement.bank_account.account_name
                or transaction.statement.bank_account.account_number
            )
        else:
            d.account_name = transaction.statement.company_name or transaction.statement.account_number
    return d


@router.patch("/transactions/{transaction_id}/reconcile")
def reconcile_transaction(
    transaction_id: int,
    invoice_id: int = None,
    payment_id: int = None,
    db: Session = Depends(get_db)
):
    """Mark transaction as reconciled with invoice or payment"""
    transaction = db.query(models.BankTransaction).filter(
        models.BankTransaction.id == transaction_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    transaction.is_reconciled = 1  # SQLite boolean as integer
    if invoice_id:
        transaction.invoice_id = invoice_id
        # Mark linked invoice as paid
        invoice = db.query(models.Invoice).filter(models.Invoice.id == invoice_id).first()
        if invoice:
            invoice.status = models.InvoiceStatus.PAID
    if payment_id:
        transaction.payment_id = payment_id
    
    db.commit()
    db.refresh(transaction)
    
    return {"message": "Transaction reconciled successfully", "transaction_id": transaction_id}


@router.delete("/statements/{statement_id}")
def delete_statement(
    statement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """Delete bank statement and its transactions (admin only; blocked if any transaction has relations)"""
    statement = db.query(models.BankStatement).filter(
        models.BankStatement.id == statement_id
    ).first()
    
    if not statement:
        raise HTTPException(status_code=404, detail="Bank statement not found")

    # Block deletion if any transaction is reconciled or linked to invoices/expense reports
    blocked = db.query(models.BankTransaction).filter(
        models.BankTransaction.statement_id == statement_id,
        (
            (models.BankTransaction.is_reconciled == 1) |
            (models.BankTransaction.invoice_id.isnot(None)) |
            (models.BankTransaction.payment_id.isnot(None)) |
            (models.BankTransaction.linked_transaction_id.isnot(None))
        )
    ).first()
    if blocked:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete: one or more transactions are reconciled or linked to invoices/payments.",
        )
    # Also block if an expense report references any transaction in this statement
    tx_ids = [tx.id for tx in db.query(models.BankTransaction.id).filter(
        models.BankTransaction.statement_id == statement_id
    ).all()]
    if tx_ids:
        er_link = db.query(models.ExpenseReport).filter(
            models.ExpenseReport.bank_transaction_id.in_(tx_ids)
        ).first()
        if er_link:
            raise HTTPException(
                status_code=409,
                detail="Cannot delete: a transaction in this statement is linked to an expense report.",
            )
    
    # Delete file if exists
    if statement.file_path:
        try:
            storage.delete(statement.file_path)
        except:
            pass
    
    db.delete(statement)
    db.commit()
    
    return {"message": "Bank statement deleted successfully"}


@router.post("/statements/{statement_id}/reconcile")
def auto_reconcile_statement(
    statement_id: int,
    db: Session = Depends(get_db)
):
    """
    Automatically reconcile all transactions in a statement with invoices
    
    Matches transactions with purchase invoices based on:
    - Amount (exact match within 0.01 tolerance)
    - Date proximity (invoice date within 30 days before transaction)
    - Supplier name in transaction description
    """
    try:
        reconciliation_service = BankReconciliationService(db)
        result = reconciliation_service.reconcile_statement(statement_id)
        
        return {
            "message": "Reconciliation completed",
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


@router.get("/transactions/{transaction_id}/suggestions")
def get_reconciliation_suggestions(
    transaction_id: int,
    limit: int = 5,
    db: Session = Depends(get_db)
):
    """Get suggested invoices for manual reconciliation"""
    try:
        reconciliation_service = BankReconciliationService(db)
        suggestions = reconciliation_service.get_reconciliation_suggestions(
            transaction_id, 
            limit
        )
        
        return {
            "transaction_id": transaction_id,
            "suggestions": suggestions
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/transactions/{transaction_id}/reconcile-manual")
def manual_reconcile_transaction(
    transaction_id: int,
    invoice_id: int,
    db: Session = Depends(get_db)
):
    """Manually reconcile a transaction with a specific invoice"""
    try:
        reconciliation_service = BankReconciliationService(db)
        transaction = reconciliation_service.reconcile_transaction(
            transaction_id,
            invoice_id
        )
        
        return {
            "message": "Transaction reconciled successfully",
            "transaction_id": transaction.id,
            "invoice_id": invoice_id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/transactions/{transaction_id}/reconcile")
def unreconcile_transaction(
    transaction_id: int,
    db: Session = Depends(get_db)
):
    """Remove reconciliation from a transaction"""
    try:
        reconciliation_service = BankReconciliationService(db)
        transaction = reconciliation_service.unreconcile_transaction(transaction_id)
        
        return {
            "message": "Transaction unreconciled successfully",
            "transaction_id": transaction.id
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/transactions/{transaction_id}/link-transfer")
def link_transfer(
    transaction_id: int,
    counterpart_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_finance),
):
    """
    Link two transactions as an inter-account transfer and mark both as reconciled.
    One should be a debit (negative) and the other a credit (positive) of the same amount.
    """
    tx_a = db.query(models.BankTransaction).filter(models.BankTransaction.id == transaction_id).first()
    tx_b = db.query(models.BankTransaction).filter(models.BankTransaction.id == counterpart_id).first()

    if not tx_a:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")
    if not tx_b:
        raise HTTPException(status_code=404, detail=f"Transaction {counterpart_id} not found")
    if tx_a.statement_id == tx_b.statement_id:
        raise HTTPException(status_code=400, detail="Both transactions belong to the same statement")

    # Link both ways
    tx_a.linked_transaction_id = tx_b.id
    tx_b.linked_transaction_id = tx_a.id

    # Mark both as reconciled
    tx_a.is_reconciled = 1
    tx_b.is_reconciled = 1

    tx_a.notes = (tx_a.notes or '') + f" [Transfer ↔ tx#{tx_b.id}]"
    tx_b.notes = (tx_b.notes or '') + f" [Transfer ↔ tx#{tx_a.id}]"

    db.commit()
    return {"message": "Transfer linked and both transactions reconciled", "transaction_id": transaction_id, "counterpart_id": counterpart_id}


@router.delete("/transactions/{transaction_id}/link-transfer")
def unlink_transfer(
    transaction_id: int,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin_or_finance),
):
    """Unlink an inter-account transfer and mark both transactions as unreconciled."""
    tx_a = db.query(models.BankTransaction).filter(models.BankTransaction.id == transaction_id).first()
    if not tx_a:
        raise HTTPException(status_code=404, detail=f"Transaction {transaction_id} not found")

    counterpart_id = tx_a.linked_transaction_id
    tx_a.linked_transaction_id = None
    tx_a.is_reconciled = 0

    if counterpart_id:
        tx_b = db.query(models.BankTransaction).filter(models.BankTransaction.id == counterpart_id).first()
        if tx_b and tx_b.linked_transaction_id == tx_a.id:
            tx_b.linked_transaction_id = None
            tx_b.is_reconciled = 0

    db.commit()
    return {"message": "Transfer unlinked", "transaction_id": transaction_id}


# ─── Transaction Notes (chat thread) ─────────────────────────────────────────

@router.get("/transactions/{transaction_id}/notes", response_model=List[BankTransactionNoteOut])
def get_transaction_notes(transaction_id: int, db: Session = Depends(get_db)):
    """List all notes for a transaction, oldest first."""
    tx = db.query(models.BankTransaction).filter(models.BankTransaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return (
        db.query(models.BankTransactionNote)
        .filter(models.BankTransactionNote.transaction_id == transaction_id)
        .order_by(models.BankTransactionNote.created_at.asc())
        .all()
    )


@router.post("/transactions/{transaction_id}/notes", response_model=BankTransactionNoteOut, status_code=201)
def add_transaction_note(
    transaction_id: int,
    payload: BankTransactionNoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Add a note to a transaction."""
    tx = db.query(models.BankTransaction).filter(models.BankTransaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    note = models.BankTransactionNote(
        transaction_id=transaction_id,
        user_id=current_user.id,
        username=current_user.username,
        body=payload.body,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/transactions/{transaction_id}/notes/{note_id}", response_model=BankTransactionNoteOut)
def update_transaction_note(
    transaction_id: int,
    note_id: int,
    payload: BankTransactionNoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Edit own note (any time)."""
    note = db.query(models.BankTransactionNote).filter(
        models.BankTransactionNote.id == note_id,
        models.BankTransactionNote.transaction_id == transaction_id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot edit another user's note")
    note.body = payload.body
    note.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(note)
    return note


@router.delete("/transactions/{transaction_id}/notes/{note_id}", status_code=204)
def delete_transaction_note(
    transaction_id: int,
    note_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete own note within 1 hour of posting."""
    note = db.query(models.BankTransactionNote).filter(
        models.BankTransactionNote.id == note_id,
        models.BankTransactionNote.transaction_id == transaction_id,
    ).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    if note.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Cannot delete another user's note")
    if datetime.utcnow() - note.created_at > timedelta(hours=1):
        raise HTTPException(status_code=403, detail="Cannot delete a note older than 1 hour")
    db.delete(note)
    db.commit()
