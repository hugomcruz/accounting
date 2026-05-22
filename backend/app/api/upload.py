from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
import os
import tempfile
from datetime import datetime
from app.core.database import get_db
from app.storage.storage import storage, LocalStorageBackend
from app.services.qr_parser import PortugueseQRCodeParser
from app.services.openai_parser import OpenAIInvoiceParser
from app.schemas.schemas import UploadResponse, QRCodeData, ProcessInvoiceRequest
from app.models import models
from app.core.config import settings

router = APIRouter(prefix="/upload", tags=["upload"])


def validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed"""
    ext = filename.split('.')[-1].lower()
    return ext in settings.allowed_extensions_list


def validate_file_size(file: UploadFile) -> bool:
    """Check if file size is within limit"""
    file.file.seek(0, 2)  # Seek to end
    size = file.file.tell()
    file.file.seek(0)  # Reset to start
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    return size <= max_size


@router.post("/invoice", response_model=UploadResponse)
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload an invoice file (PDF or image) and extract QR code data if available.
    
    The file will be stored and QR code will be parsed for Portuguese AT invoices.
    """
    
    # Validate file
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed types: {', '.join(settings.allowed_extensions_list)}"
        )
    
    if not validate_file_size(file):
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE_MB}MB"
        )
    
    try:
        # Save file to storage
        file_path = await storage.save(file.file, file.filename, folder="invoices")
        
        # Try to extract QR code data (for images and PDFs)
        qr_raw_dict = None
        raw_qr_code = None
        extraction_method = None
        ai_extracted = False

        file_ext = os.path.splitext(file.filename)[1].lower()

        # ── Step 1: obtain a local path to the file for analysis ──────────
        local_path: Optional[str] = None
        _tmp_path: Optional[str] = None
        try:
            if file_ext in ('.png', '.jpg', '.jpeg', '.pdf'):
                if isinstance(storage, LocalStorageBackend):
                    local_path = str(storage.get_full_path(file_path))
                elif hasattr(storage, 'client'):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                        storage.client.download_fileobj(storage.bucket_name, file_path, tmp_file)
                        tmp_file.flush()
                        _tmp_path = tmp_file.name
                    local_path = _tmp_path
        except Exception as e:
            print(f"File download for analysis error: {e}")

        # ── Step 2: QR / ATCUD parsing ─────────────────────────────────────
        if local_path:
            try:
                qr_raw_dict, extraction_method, raw_qr_code = PortugueseQRCodeParser.extract_and_parse(
                    local_path, use_ocr_fallback=True
                )
            except Exception as e:
                print(f"QR extraction error: {e}")

        # ── Step 3: OpenAI vision parsing ──────────────────────────────────
        ai_raw_dict = None
        if local_path and settings.OPENAI_API_KEY:
            try:
                ai_raw_dict = OpenAIInvoiceParser.parse(
                    file_path=local_path,
                    qr_data=qr_raw_dict,
                    api_key=settings.OPENAI_API_KEY,
                )
            except Exception as e:
                print(f"OpenAI parsing error: {e}")

        # Clean up temp file after analysis
        if _tmp_path:
            try:
                os.unlink(_tmp_path)
            except OSError:
                pass

        # ── Step 4: merge results ──────────────────────────────────────────
        merged_dict: Optional[dict] = None
        if ai_raw_dict or qr_raw_dict:
            merged_dict = OpenAIInvoiceParser.merge(ai_raw_dict, qr_raw_dict)
            ai_extracted = ai_raw_dict is not None

        qr_data = QRCodeData(**merged_dict) if merged_dict else None

        # Update extraction_method label to reflect AI involvement
        if ai_extracted:
            extraction_method = f"{extraction_method}+ai" if extraction_method else "ai"

        # ── Step 5: build response message ────────────────────────────────
        message = "File uploaded successfully"
        if qr_data:
            if "qr" in (extraction_method or ""):
                message += " - QR/ATCUD code detected and parsed"
            elif "ocr" in (extraction_method or ""):
                message += " - QR not found, data extracted via OCR"
            if ai_extracted:
                message += " with AI enrichment"

        file_url = await storage.get_url(file_path)

        return UploadResponse(
            filename=file.filename,
            file_path=file_path,
            file_url=file_url,
            qr_data=qr_data,
            raw_qr_code=raw_qr_code,
            extraction_method=extraction_method,
            ai_extracted=ai_extracted,
            message=message,
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")


@router.post("/invoice/process")
async def process_uploaded_invoice(
    request: ProcessInvoiceRequest,
    db: Session = Depends(get_db)
):
    """
    Process an already uploaded invoice file to create invoice and company records.

    Pass qr_data in the request body to use user-confirmed (possibly edited) data
    directly, skipping re-parsing of the file.
    """
    file_path = request.file_path
    create_invoice = request.create_invoice
    notes = request.notes

    try:
        # Check if file exists
        if not storage.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        parsed_data = None
        source = 'none'
        raw_qr_string = None

        if request.qr_data:
            # Use the data the user already reviewed / edited — no re-parsing needed
            parsed_data = request.qr_data.model_dump(exclude_none=True)
            source = 'user_confirmed'
            raw_qr_string = None
        else:
            # Fall back to extracting QR from the file
            file_ext = os.path.splitext(file_path)[1].lower()
            try:
                if isinstance(storage, LocalStorageBackend):
                    full_path = str(storage.get_full_path(file_path))
                    parsed_data, source, raw_qr_string = PortugueseQRCodeParser.extract_and_parse(full_path, use_ocr_fallback=True)
                elif hasattr(storage, 'client'):
                    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
                        storage.client.download_fileobj(storage.bucket_name, file_path, tmp_file)
                        tmp_file.flush()
                        parsed_data, source, raw_qr_string = PortugueseQRCodeParser.extract_and_parse(tmp_file.name, use_ocr_fallback=True)
                    os.unlink(tmp_file.name)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"QR extraction failed: {e}")

        if not parsed_data:
            raise HTTPException(status_code=400, detail="No QR code or invoice data found in file")
        
        result = {
            'qr_data': parsed_data,
            'extraction_method': source,
            'raw_qr_code': raw_qr_string,
            'supplier_created': False,
            'invoice_created': False
        }
        
        if create_invoice:
            # Find or create supplier company
            supplier_nif = parsed_data.get('nif_emitente')
            
            if not supplier_nif:
                raise HTTPException(status_code=400, detail="Missing supplier NIF in invoice data")
            
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
                result['supplier_created'] = True
            
            # Parse date
            invoice_date = None
            if parsed_data.get('data_documento'):
                try:
                    invoice_date = datetime.strptime(parsed_data.get('data_documento'), '%Y-%m-%d')
                except ValueError:
                    invoice_date = datetime.now()
            else:
                invoice_date = datetime.now()
            
            # Calculate amounts
            base_amounts = parsed_data.get('base_incidencia_iva', [])
            iva_amounts = parsed_data.get('total_iva', [])
            
            subtotal = sum(base_amounts) if base_amounts else 0
            tax_amount = sum(iva_amounts) if iva_amounts else parsed_data.get('total_impostos', 0)
            total_amount = parsed_data.get('total_documento', subtotal + tax_amount)
            
            invoice_number = parsed_data.get('identificacao_documento', f"INV-{datetime.now().strftime('%Y%m%d%H%M%S')}")

            # If invoice already exists for this supplier, update file/QR data and return it
            existing_invoice = db.query(models.Invoice).filter(
                models.Invoice.supplier_id == supplier.id,
                models.Invoice.invoice_number == invoice_number
            ).first()
            if existing_invoice:
                existing_invoice.file_path = file_path
                existing_invoice.qr_code_data = raw_qr_string
                if parsed_data.get('atcud'):
                    existing_invoice.atcud = parsed_data.get('atcud')
                if notes:
                    existing_invoice.notes = notes
                db.commit()
                result['invoice_created'] = False
                result['invoice_updated'] = True
                result['invoice_id'] = existing_invoice.id
                result['invoice_number'] = invoice_number
                result['supplier_name'] = supplier.name
                return result

            # Create invoice
            invoice = models.Invoice(
                invoice_number=invoice_number,
                invoice_type=models.InvoiceType.PURCHASE,
                invoice_date=invoice_date,
                supplier_id=supplier.id,
                subtotal=subtotal,
                tax_amount=tax_amount,
                total_amount=total_amount,
                file_path=file_path,
                qr_code_data=raw_qr_string,
                atcud=parsed_data.get('atcud'),
                notes=notes,
                status=models.InvoiceStatus.DRAFT,
                is_foreign_currency=1 if parsed_data.get('is_foreign_currency') else 0,
                foreign_currency_code=parsed_data.get('foreign_currency_code') or None,
                original_total_amount=parsed_data.get('original_total_amount'),
                exchange_rate=parsed_data.get('exchange_rate'),
            )
            db.add(invoice)
            db.commit()
            db.refresh(invoice)
            
            result['invoice_created'] = True
            result['invoice_id'] = invoice.id
            result['invoice_number'] = invoice_number
            result['supplier_name'] = supplier.name
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing invoice: {str(e)}")
