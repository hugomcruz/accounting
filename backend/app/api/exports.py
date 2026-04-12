from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
import io
import os
import uuid
import zipfile
import calendar
from pathlib import Path

from app.core.database import get_db, SessionLocal
from app.models import models
from app.storage.storage import storage, LocalStorageBackend

router = APIRouter(prefix="/exports", tags=["exports"])


def _save_zip_sync(buf: io.BytesIO, year: int, month: int) -> str:
    """Save a ZIP buffer to storage synchronously and return the stored path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    filename = f"{timestamp}_{unique_id}_invoices_{year}_{month:02d}.zip"

    if isinstance(storage, LocalStorageBackend):
        folder_path = storage.base_path / "exports"
        folder_path.mkdir(parents=True, exist_ok=True)
        dest = folder_path / filename
        with open(dest, "wb") as f:
            f.write(buf.getvalue())
        return str(Path("exports") / filename)
    else:
        # S3 — upload directly without going through the async wrapper
        key = f"exports/{filename}"
        buf.seek(0)
        storage.client.upload_fileobj(buf, storage.bucket_name, key)
        return key


def _generate_zip(export_id: int, year: int, month: int):
    """
    Plain sync function — FastAPI's BackgroundTasks runs this in a thread-pool
    executor so it never blocks the event loop.
    """
    db = SessionLocal()
    export = None
    try:
        export = db.query(models.InvoiceExport).filter(models.InvoiceExport.id == export_id).first()
        if not export:
            return

        export.status = "processing"
        db.commit()

        start = datetime(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        end = datetime(year, month, last_day, 23, 59, 59)

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
        seen: dict[str, int] = {}

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for inv in invoices:
                try:
                    safe_num = inv.invoice_number.replace("/", "_").replace(" ", "_")
                    base_name = inv.original_filename or Path(inv.file_path).name
                    arcname = f"{safe_num}_{base_name}"

                    # Deduplicate names inside the archive
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
                    pass  # skip individual files that cannot be read

        zip_path = _save_zip_sync(zip_buffer, year, month)

        export.file_path = zip_path
        export.invoice_count = count
        export.status = "completed"
        export.completed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        if export:
            export.status = "failed"
            export.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/invoices")
async def trigger_invoice_export(
    year: int,
    month: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Start a background job to build a ZIP of all invoices for a given year/month."""
    if month < 1 or month > 12:
        raise HTTPException(status_code=400, detail="Month must be between 1 and 12")

    export = models.InvoiceExport(year=year, month=month, status="pending")
    db.add(export)
    db.commit()
    db.refresh(export)

    background_tasks.add_task(_generate_zip, export.id, year, month)

    return {
        "id": export.id,
        "year": export.year,
        "month": export.month,
        "status": export.status,
        "invoice_count": export.invoice_count,
        "created_at": export.created_at,
        "completed_at": export.completed_at,
        "error_message": export.error_message,
    }


@router.get("/invoices")
def list_invoice_exports(db: Session = Depends(get_db)):
    """List all invoice export jobs, newest first."""
    rows = (
        db.query(models.InvoiceExport)
        .order_by(models.InvoiceExport.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "year": r.year,
            "month": r.month,
            "status": r.status,
            "invoice_count": r.invoice_count,
            "created_at": r.created_at,
            "completed_at": r.completed_at,
            "error_message": r.error_message,
        }
        for r in rows
    ]


@router.get("/invoices/{export_id}")
def get_invoice_export(export_id: int, db: Session = Depends(get_db)):
    """Get a single export record (used for status polling)."""
    export = db.query(models.InvoiceExport).filter(models.InvoiceExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    return {
        "id": export.id,
        "year": export.year,
        "month": export.month,
        "status": export.status,
        "invoice_count": export.invoice_count,
        "created_at": export.created_at,
        "completed_at": export.completed_at,
        "error_message": export.error_message,
    }


@router.delete("/invoices/{export_id}", status_code=204)
def delete_invoice_export(export_id: int, db: Session = Depends(get_db)):
    """Delete an invoice export record and remove the ZIP file from storage."""
    export = db.query(models.InvoiceExport).filter(models.InvoiceExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")

    # Remove the ZIP file from storage (best effort)
    if export.file_path:
        try:
            if isinstance(storage, LocalStorageBackend):
                full = storage.get_full_path(export.file_path)
                if full.exists():
                    full.unlink()
            elif hasattr(storage, "client"):
                storage.client.delete_object(Bucket=storage.bucket_name, Key=export.file_path)
        except Exception:
            pass

    db.delete(export)
    db.commit()


@router.get("/invoices/{export_id}/download")
async def download_export(export_id: int, db: Session = Depends(get_db)):
    """Proxy-download the ZIP file through the server (works for both local and S3 storage)."""
    export = db.query(models.InvoiceExport).filter(models.InvoiceExport.id == export_id).first()
    if not export:
        raise HTTPException(status_code=404, detail="Export not found")
    if export.status != "completed":
        raise HTTPException(status_code=400, detail="Export is not ready yet")
    if not export.file_path or not storage.exists(export.file_path):
        raise HTTPException(status_code=404, detail="Export file not found in storage")

    filename = f"invoices_{export.year}_{export.month:02d}.zip"

    if isinstance(storage, LocalStorageBackend):
        full_path = storage.get_full_path(export.file_path)
        return FileResponse(
            str(full_path),
            media_type="application/zip",
            filename=filename,
        )
    else:
        # Stream from S3 without exposing a presigned URL
        obj_buf = io.BytesIO()
        storage.client.download_fileobj(storage.bucket_name, export.file_path, obj_buf)
        obj_buf.seek(0)
        return StreamingResponse(
            obj_buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
