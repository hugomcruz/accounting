from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import json
import os
from app.core.database import get_db
from app.storage.storage import storage, LocalStorageBackend
from app.services.qr_parser import PortugueseQRCodeParser
from app.schemas.schemas import InvoiceProcessingQueue, InvoiceProcessingQueueCreate
from app.models import models
from app.core.config import settings

router = APIRouter(prefix="/queue", tags=["invoice-queue"])


def _extract_qr_from_stored_file(file_path: str, file_ext: str):
    """Extract QR data from a stored file (works for both local and S3 storage)."""
    parsed_data = None
    try:
        if isinstance(storage, LocalStorageBackend):
            full_path = str(storage.get_full_path(file_path))
            parsed_data, _, _ = PortugueseQRCodeParser.extract_and_parse(full_path, use_ocr_fallback=True)
        elif hasattr(storage, 'client'):
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                storage.client.download_fileobj(storage.bucket_name, file_path, tmp_file)
                tmp_file.flush()
                parsed_data, _, _ = PortugueseQRCodeParser.extract_and_parse(tmp_file.name, use_ocr_fallback=True)
            os.unlink(tmp_file.name)
    except Exception as e:
        print(f"QR extraction error for {file_path}: {e}")
    return parsed_data


_REQUIRED_QR_FIELDS = ('nif_emitente', 'identificacao_documento', 'data_documento', 'total_documento')


def _auto_process_item(item: models.InvoiceProcessingQueue, db: Session) -> dict:
    """
    Create invoice and company records from a queue item that has complete QR data.
    Raises on failure; caller should handle exceptions.
    """
    item.status = "processing"
    db.commit()

    qr_data = json.loads(item.qr_data) if item.qr_data else {}
    invoice_number = qr_data.get('identificacao_documento', f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}")

    # Find or create supplier first (needed for the composite uniqueness check)
    supplier_nif = qr_data.get('nif_emitente')
    supplier = db.query(models.Company).filter(models.Company.nif == supplier_nif).first()
    if not supplier:
        supplier = models.Company(
            nif=supplier_nif,
            name=f"Supplier {supplier_nif}",
            is_supplier=True,
            is_customer=False
        )
        db.add(supplier)
        db.flush()

    # If invoice already exists for this supplier, link to it and complete without re-inserting
    existing_invoice = db.query(models.Invoice).filter(
        models.Invoice.supplier_id == supplier.id,
        models.Invoice.invoice_number == invoice_number
    ).first()
    if existing_invoice:
        item.status = "completed"
        item.invoice_id = existing_invoice.id
        item.processed_at = datetime.utcnow()
        db.commit()
        return {'invoice_id': existing_invoice.id, 'duplicate': True}

    # Parse date
    invoice_date = datetime.now()
    if qr_data.get('data_documento'):
        try:
            invoice_date = datetime.strptime(qr_data['data_documento'], '%Y-%m-%d')
        except ValueError:
            pass

    # Calculate amounts
    base_amounts = qr_data.get('base_incidencia_iva', [])
    iva_amounts = qr_data.get('total_iva', [])
    subtotal = sum(base_amounts) if base_amounts else 0
    tax_amount = sum(iva_amounts) if iva_amounts else qr_data.get('total_impostos', 0)
    total_amount = qr_data.get('total_documento', subtotal + tax_amount)

    vat_6_base = base_amounts[0] if len(base_amounts) > 1 else 0
    vat_6_amount = iva_amounts[0] if len(iva_amounts) > 1 else 0
    vat_23_base = base_amounts[1] if len(base_amounts) > 1 else (base_amounts[0] if base_amounts else 0)
    vat_23_amount = iva_amounts[1] if len(iva_amounts) > 1 else (iva_amounts[0] if iva_amounts else 0)

    # Move file from staging to processed folder
    year = invoice_date.year
    month = f"{invoice_date.month:02d}"
    dest_path = f"processed/fy-{year}/invoices/{month}/{item.filename}"
    try:
        if hasattr(storage, 'client'):
            copy_source = {'Bucket': storage.bucket_name, 'Key': item.s3_file_path}
            storage.client.copy_object(CopySource=copy_source, Bucket=storage.bucket_name, Key=dest_path)
            storage.client.delete_object(Bucket=storage.bucket_name, Key=item.s3_file_path)
        elif isinstance(storage, LocalStorageBackend):
            import shutil as _shutil
            src = storage.get_full_path(item.s3_file_path)
            dst_dir = storage.base_path / f"processed/fy-{year}/invoices/{month}"
            dst_dir.mkdir(parents=True, exist_ok=True)
            dst = dst_dir / item.filename
            _shutil.copy2(src, dst)
            src.unlink(missing_ok=True)
            dest_path = f"processed/fy-{year}/invoices/{month}/{item.filename}"
    except Exception as e:
        print(f"Warning: could not move file to processed folder: {e}")
        dest_path = item.s3_file_path

    # Foreign currency support: stored in extra keys alongside QR data
    is_foreign = bool(qr_data.get('is_foreign_currency'))
    fc_code = qr_data.get('foreign_currency_code') or None
    original_total = qr_data.get('original_total_amount')
    fc_exchange_rate = qr_data.get('exchange_rate')

    invoice = models.Invoice(
        invoice_number=invoice_number,
        invoice_type=models.InvoiceType.PURCHASE,
        invoice_date=invoice_date,
        supplier_id=supplier.id,
        subtotal=subtotal,
        tax_amount=tax_amount,
        total_amount=total_amount,
        vat_6_base=vat_6_base,
        vat_6_amount=vat_6_amount,
        vat_23_base=vat_23_base,
        vat_23_amount=vat_23_amount,
        is_foreign_currency=1 if is_foreign else 0,
        foreign_currency_code=fc_code if is_foreign else None,
        original_total_amount=float(original_total) if is_foreign and original_total else None,
        exchange_rate=float(fc_exchange_rate) if is_foreign and fc_exchange_rate else None,
        file_path=dest_path,
        original_filename=item.filename,
        qr_code_data=item.qr_data,
        atcud=qr_data.get('atcud'),
        status=models.InvoiceStatus.DRAFT
    )
    db.add(invoice)
    db.flush()

    item.status = "completed"
    item.invoice_id = invoice.id
    item.processed_at = datetime.utcnow()
    db.commit()

    return {'invoice_id': invoice.id}


@router.post("/upload-bulk")
async def upload_invoices_bulk(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload multiple invoice files at once and add them to processing queue.
    
    Files are stored locally (and to S3 if configured) and added to the queue
    for background processing.
    """
    
    results = []
    
    # Get next running number for today
    today = datetime.now().strftime('%Y%m%d')
    today_items = db.query(models.InvoiceProcessingQueue).filter(
        models.InvoiceProcessingQueue.s3_file_path.like(f'staging/review-invoices/{today}-%')
    ).count()
    running_number = today_items + 1
    
    for file in files:
        try:
            # Validate file
            if not file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.pdf')):
                results.append({
                    'filename': file.filename,
                    'status': 'error',
                    'message': 'Invalid file type'
                })
                continue
            
            # Generate new filename: YYYYMMDD-001.ext, YYYYMMDD-002.ext, etc.
            file_ext = os.path.splitext(file.filename)[1]
            new_filename = f"{today}-{running_number:03d}{file_ext}"
            
            # Save file to S3 staging folder with new filename
            file_path = await storage.save(file.file, new_filename, folder="staging/review-invoices")
            running_number += 1
            
            # Try to extract QR data from the stored file
            parsed_data = _extract_qr_from_stored_file(file_path, file_ext)
            has_qr = bool(parsed_data)
            qr_data_str = json.dumps(parsed_data) if has_qr else None

            # Check whether all required fields are present for auto-processing
            can_auto_process = has_qr and all(parsed_data.get(f) for f in _REQUIRED_QR_FIELDS)

            # Add to processing queue
            queue_item = models.InvoiceProcessingQueue(
                filename=file.filename,
                local_file_path=None,
                s3_file_path=file_path,
                status="pending" if can_auto_process else "needs_review",
                has_qr_data=1 if has_qr else 0,
                qr_data=qr_data_str
            )
            db.add(queue_item)
            db.commit()
            db.refresh(queue_item)

            # Auto-process items whose QR data is complete
            auto_processed = False
            invoice_id = None
            if can_auto_process:
                try:
                    result = _auto_process_item(queue_item, db)
                    auto_processed = True
                    invoice_id = result.get('invoice_id')
                except Exception as e:
                    db.rollback()
                    print(f"Auto-processing failed for {file.filename}: {e}")
                    queue_item.status = "needs_review"
                    queue_item.error_message = str(e)
                    db.commit()

            results.append({
                'filename': file.filename,
                'status': 'success',
                'queue_id': queue_item.id,
                'has_qr_data': has_qr,
                'auto_processed': auto_processed,
                'invoice_id': invoice_id,
                'message': (
                    'QR code detected and invoice created automatically' if auto_processed
                    else 'QR code detected but has missing fields - needs review' if has_qr
                    else 'No QR code found - needs manual review'
                )
            })
            
        except Exception as e:
            results.append({
                'filename': file.filename,
                'status': 'error',
                'message': str(e)
            })
            continue
    
    return {
        'total_files': len(files),
        'successful': sum(1 for r in results if r['status'] == 'success'),
        'auto_processed': sum(1 for r in results if r.get('auto_processed')),
        'needs_review': sum(1 for r in results if r['status'] == 'success' and not r.get('auto_processed')),
        'failed': sum(1 for r in results if r['status'] == 'error'),
        'results': results
    }


@router.get("", response_model=List[InvoiceProcessingQueue])
def get_queue_items(
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get items from the invoice processing queue"""
    query = db.query(models.InvoiceProcessingQueue)
    
    if status:
        query = query.filter(models.InvoiceProcessingQueue.status == status)
    
    items = query.order_by(models.InvoiceProcessingQueue.uploaded_at.desc()).offset(skip).limit(limit).all()
    return items


@router.get("/{queue_id}", response_model=InvoiceProcessingQueue)
def get_queue_item(queue_id: int, db: Session = Depends(get_db)):
    """Get a specific queue item"""
    item = db.query(models.InvoiceProcessingQueue).filter(models.InvoiceProcessingQueue.id == queue_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    return item


@router.put("/{queue_id}")
async def update_queue_item(
    queue_id: int,
    qr_data: dict,
    db: Session = Depends(get_db)
):
    """Update queue item's QR data (for manual entry)"""
    item = db.query(models.InvoiceProcessingQueue).filter(models.InvoiceProcessingQueue.id == queue_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    # Update QR data
    item.qr_data = json.dumps(qr_data)
    item.has_qr_data = 1
    
    db.commit()
    db.refresh(item)
    
    return item


@router.post("/{queue_id}/process")
async def process_queue_item(
    queue_id: int,
    db: Session = Depends(get_db)
):
    """
    Process a specific queue item to create invoice and company records.
    """
    item = db.query(models.InvoiceProcessingQueue).filter(models.InvoiceProcessingQueue.id == queue_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    if item.status == "completed":
        raise HTTPException(status_code=400, detail="Item already processed")

    # Validate required fields before attempting to process
    qr_data = json.loads(item.qr_data) if item.qr_data else {}
    missing_fields = [label for field, label in [
        ('nif_emitente', 'Supplier NIF'),
        ('identificacao_documento', 'Invoice Number'),
        ('data_documento', 'Invoice Date'),
        ('total_documento', 'Total Amount'),
    ] if not qr_data.get(field)]

    if missing_fields:
        item.status = "needs_review"
        item.error_message = f"Missing required fields: {', '.join(missing_fields)}"
        db.commit()
        raise HTTPException(
            status_code=400,
            detail=f"Missing required fields: {', '.join(missing_fields)}. Please fill in all required data before processing."
        )

    try:
        result = _auto_process_item(item, db)
        return {
            'message': 'Invoice processed successfully',
            'queue_id': queue_id,
            'invoice_id': result['invoice_id']
        }
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        item.status = "failed"
        item.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error processing invoice: {str(e)}")


@router.get("/{queue_id}/file-url")
async def get_queue_item_file_url(queue_id: int, db: Session = Depends(get_db)):
    """Get presigned URL for the queue item's file.
    For processed items the file has been moved; use the linked invoice's file_path.
    """
    item = db.query(models.InvoiceProcessingQueue).filter(models.InvoiceProcessingQueue.id == queue_id).first()

    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")

    # Determine which path to serve
    file_path = item.s3_file_path

    # If the item has been processed, the file was moved — prefer the invoice's path
    if item.invoice_id:
        invoice = db.query(models.Invoice).filter(models.Invoice.id == item.invoice_id).first()
        if invoice and invoice.file_path:
            file_path = invoice.file_path

    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")

    # For local storage, fall back to staging path if the processed file doesn't exist
    if isinstance(storage, LocalStorageBackend):
        if not storage.get_full_path(file_path).exists() and item.s3_file_path:
            file_path = item.s3_file_path

    try:
        url = await storage.get_url(file_path)
        return {'url': url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating file URL: {str(e)}")


@router.delete("/{queue_id}")
def delete_queue_item(queue_id: int, db: Session = Depends(get_db)):
    """Delete a queue item"""
    item = db.query(models.InvoiceProcessingQueue).filter(models.InvoiceProcessingQueue.id == queue_id).first()
    
    if not item:
        raise HTTPException(status_code=404, detail="Queue item not found")
    
    db.delete(item)
    db.commit()
    
    return {'message': 'Queue item deleted'}
