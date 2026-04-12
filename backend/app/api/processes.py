from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
import calendar
import io
import os
import uuid
import zipfile
from pathlib import Path

from app.core.database import get_db, SessionLocal
from app.models import models
from app.storage.storage import storage, LocalStorageBackend

router = APIRouter(prefix="/processes", tags=["processes"])


# ── Helpers ────────────────────────────────────────────────────────────────

def _invoice_month_range(year: int, month: int):
    start = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end = datetime(year, month, last_day, 23, 59, 59)
    return start, end


def _file_url(file_path: str):
    """Synchronously resolve a download URL for a stored file."""
    if not file_path:
        return None
    if isinstance(storage, LocalStorageBackend):
        return f"/api/v1/files/{file_path}"
    try:
        return storage.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": storage.bucket_name, "Key": file_path},
            ExpiresIn=3600,
        )
    except Exception:
        return None


def _delete_file(file_path: str):
    """Remove a file from storage (best effort, no error raised)."""
    if not file_path:
        return
    try:
        if isinstance(storage, LocalStorageBackend):
            full = storage.get_full_path(file_path)
            if full.exists():
                full.unlink()
        elif hasattr(storage, "client"):
            storage.client.delete_object(Bucket=storage.bucket_name, Key=file_path)
    except Exception:
        pass


def _report_to_dict(r: models.MonthEndReport) -> dict:
    return {
        "id": r.id,
        "year": r.year,
        "month": r.month,
        "status": r.status,
        "error_message": r.error_message,
        "saft_import_id": r.saft_import_id,
        "bank_statement_id": r.bank_statement_id,
        "invoice_export_id": r.invoice_export_id,
        "saft_filename": r.saft_filename,
        "bank_statement_filename": r.bank_statement_filename,
        "invoice_count": r.invoice_count,
        "saft_download_url": _file_url(r.saft_file_path),
        "bank_statement_download_url": _file_url(r.bank_statement_file_path),
        "invoice_zip_download_url": (
            f"/api/v1/exports/invoices/{r.invoice_export_id}/download"
            if r.invoice_export_id and r.status == "ready"
            else None
        ),
        "created_at": r.created_at,
        "completed_at": r.completed_at,
    }


# ── Background ZIP generation ──────────────────────────────────────────────

def _generate_zip_for_report(report_id: int, year: int, month: int):
    """
    Build an invoice ZIP export tied to a MonthEndReport.
    Runs in a background thread (FastAPI BackgroundTasks).
    """
    db = SessionLocal()
    try:
        report = db.query(models.MonthEndReport).filter(models.MonthEndReport.id == report_id).first()
        if not report:
            return

        start, end = _invoice_month_range(year, month)

        # Create an InvoiceExport record to reuse the existing download endpoint
        export = models.InvoiceExport(year=year, month=month, status="processing")
        db.add(export)
        db.flush()

        invoices = (
            db.query(models.Invoice)
            .filter(
                models.Invoice.invoice_date >= start,
                models.Invoice.invoice_date <= end,
                models.Invoice.file_path.isnot(None),
            )
            .all()
        )

        zip_buffer = io.BytesIO()
        count = 0
        seen: dict = {}

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for inv in invoices:
                try:
                    safe_num = (inv.invoice_number or "unknown").replace("/", "_").replace(" ", "_")
                    base_name = inv.original_filename or Path(inv.file_path).name
                    arcname = f"{safe_num}_{base_name}"
                    if arcname in seen:
                        seen[arcname] += 1
                        stem, ext = os.path.splitext(arcname)
                        arcname = f"{stem}_{seen[arcname]}{ext}"
                    else:
                        seen[arcname] = 0

                    if isinstance(storage, LocalStorageBackend):
                        full_path = storage.get_full_path(inv.file_path)
                        if full_path.exists():
                            zf.write(str(full_path), arcname)
                            count += 1
                    elif hasattr(storage, "client"):
                        obj_buf = io.BytesIO()
                        storage.client.download_fileobj(storage.bucket_name, inv.file_path, obj_buf)
                        obj_buf.seek(0)
                        zf.writestr(arcname, obj_buf.read())
                        count += 1
                except Exception:
                    pass

        # Save ZIP
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = str(uuid.uuid4())[:8]
        filename = f"{timestamp}_{uid}_invoices_{year}_{month:02d}.zip"

        if isinstance(storage, LocalStorageBackend):
            folder_path = storage.base_path / "exports"
            folder_path.mkdir(parents=True, exist_ok=True)
            dest = folder_path / filename
            with open(dest, "wb") as f:
                f.write(zip_buffer.getvalue())
            zip_path = str(Path("exports") / filename)
        else:
            zip_path = f"exports/{filename}"
            zip_buffer.seek(0)
            storage.client.upload_fileobj(zip_buffer, storage.bucket_name, zip_path)

        export.status = "completed"
        export.file_path = zip_path
        export.invoice_count = count
        export.completed_at = datetime.utcnow()

        report.invoice_export_id = export.id
        report.invoice_zip_file_path = zip_path
        report.invoice_count = count
        report.status = "ready"
        report.completed_at = datetime.utcnow()
        db.commit()

    except Exception as exc:
        try:
            report = db.query(models.MonthEndReport).filter(models.MonthEndReport.id == report_id).first()
            if report:
                report.status = "failed"
                report.error_message = str(exc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/month-end/available")
def get_available_assets(year: int, month: int, db: Session = Depends(get_db)):
    """
    Return the available SAF-T files and bank statements for a given month
    so the user can pick which ones to include in the report.
    """
    start, end = _invoice_month_range(year, month)

    saft_rows = (
        db.query(models.SAFTImport)
        .filter(
            models.SAFTImport.start_date <= end,
            models.SAFTImport.end_date >= start,
        )
        .order_by(models.SAFTImport.created_at.desc())
        .all()
    )
    saft_files = [
        {
            "id": s.id,
            "filename": s.filename,
            "company_name": s.company_name,
            "fiscal_year": s.fiscal_year,
            "start_date": s.start_date,
            "end_date": s.end_date,
        }
        for s in saft_rows
    ]

    stmt_rows = (
        db.query(models.BankStatement)
        .filter(
            models.BankStatement.period_start <= end,
            models.BankStatement.period_end >= start,
        )
        .order_by(models.BankStatement.period_start.asc())
        .all()
    )
    bank_statements = [
        {
            "id": bs.id,
            "filename": bs.filename,
            "account_number": bs.account_number,
            "company_name": bs.company_name,
            "period_start": bs.period_start,
            "period_end": bs.period_end,
            "opening_balance": bs.opening_balance,
            "closing_balance": bs.closing_balance,
        }
        for bs in stmt_rows
    ]

    invoice_count = (
        db.query(models.Invoice)
        .filter(
            models.Invoice.invoice_date >= start,
            models.Invoice.invoice_date <= end,
        )
        .count()
    )

    return {
        "saft_files": saft_files,
        "bank_statements": bank_statements,
        "invoice_count": invoice_count,
    }


@router.post("/month-end/reports", status_code=201)
def create_month_end_report(
    payload: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Generate a new month-end report. Only year and month are required;
    the most recent SAF-T and the matching bank statement are auto-selected.
    A background task builds the invoice ZIP and marks the report ready.
    """
    year: int = payload.get("year")
    month: int = payload.get("month")

    if not all([year, month]):
        raise HTTPException(status_code=422, detail="year and month are required")

    start, end = _invoice_month_range(year, month)

    # Auto-select the most recently uploaded SAF-T that covers the period
    saft = (
        db.query(models.SAFTImport)
        .filter(models.SAFTImport.start_date <= end, models.SAFTImport.end_date >= start)
        .order_by(models.SAFTImport.created_at.desc())
        .first()
    )
    if not saft:
        raise HTTPException(status_code=422, detail="No SAF-T file found for this period")

    # Auto-select the earliest bank statement that covers the period
    bank = (
        db.query(models.BankStatement)
        .filter(models.BankStatement.period_start <= end, models.BankStatement.period_end >= start)
        .order_by(models.BankStatement.period_start.asc())
        .first()
    )
    if not bank:
        raise HTTPException(status_code=422, detail="No bank statement found for this period")

    invoice_count_check = (
        db.query(models.Invoice)
        .filter(
            models.Invoice.invoice_date >= start,
            models.Invoice.invoice_date <= end,
        )
        .count()
    )
    if invoice_count_check == 0:
        raise HTTPException(status_code=422, detail="No invoices found for this month")

    report = models.MonthEndReport(
        year=year,
        month=month,
        saft_import_id=saft.id,
        bank_statement_id=bank.id,
        saft_filename=saft.filename,
        saft_file_path=saft.file_path,
        bank_statement_filename=bank.filename,
        bank_statement_file_path=bank.file_path,
        status="generating",
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    background_tasks.add_task(_generate_zip_for_report, report.id, year, month)

    return _report_to_dict(report)


@router.get("/month-end/reports")
def list_month_end_reports(db: Session = Depends(get_db)):
    """Return all month-end reports, newest first."""
    rows = (
        db.query(models.MonthEndReport)
        .order_by(
            models.MonthEndReport.year.desc(),
            models.MonthEndReport.month.desc(),
            models.MonthEndReport.created_at.desc(),
        )
        .all()
    )
    return [_report_to_dict(r) for r in rows]


@router.get("/month-end/reports/{report_id}")
def get_month_end_report(report_id: int, db: Session = Depends(get_db)):
    """Return a single month-end report."""
    row = db.query(models.MonthEndReport).filter(models.MonthEndReport.id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")
    return _report_to_dict(row)


@router.delete("/month-end/reports/{report_id}", status_code=204)
def delete_month_end_report(report_id: int, db: Session = Depends(get_db)):
    """
    Delete a month-end report and remove its associated invoice ZIP file
    from storage.  The original SAF-T and bank statement files are NOT
    deleted — they belong to their own sections.
    """
    row = db.query(models.MonthEndReport).filter(models.MonthEndReport.id == report_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Report not found")

    # Delete the invoice ZIP file from storage
    _delete_file(row.invoice_zip_file_path)

    # Delete the associated InvoiceExport record as well
    if row.invoice_export_id:
        export = db.query(models.InvoiceExport).filter(
            models.InvoiceExport.id == row.invoice_export_id
        ).first()
        if export:
            db.delete(export)

    db.delete(row)
    db.commit()
