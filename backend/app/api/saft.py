from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
import tempfile
import os
from app.core.database import get_db
from app.storage.storage import storage, LocalStorageBackend
from app.services.saft_parser import SAFTParser
from app.schemas.schemas import SAFTImport
from app.models import models
from app.core.config import settings

router = APIRouter(prefix="/saft", tags=["saft"])


@router.post("/import", response_model=SAFTImport, status_code=201)
async def import_saft_file(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Import a SAF-T PT XML file.
    
    This will parse the XML file and import:
    - Companies (customers)
    - Sales invoices
    - Invoice line items
    """
    
    # Validate file type
    if not file.filename.lower().endswith('.xml'):
        raise HTTPException(status_code=400, detail="Only XML files are allowed for SAFT import")

    tmp_path = None
    try:
        # Save file to storage
        file_path = await storage.save(file.file, file.filename, folder="saft")

        # Get a local path for parsing (download from S3 if needed)
        if isinstance(storage, LocalStorageBackend):
            xml_path = str(storage.get_full_path(file_path))
        else:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.xml') as tmp:
                storage.client.download_fileobj(storage.bucket_name, file_path, tmp)
                tmp.flush()
                tmp_path = tmp.name
            xml_path = tmp_path

        # Parse SAFT header
        parser = SAFTParser(xml_path)
        header_data = parser.parse()

        # Create SAFT import record
        saft_import = models.SAFTImport(
            filename=file.filename,
            file_path=file_path,
            tax_registration_number=header_data.get('tax_registration_number'),
            company_name=header_data.get('company_name'),
            fiscal_year=header_data.get('fiscal_year'),
            start_date=header_data.get('start_date'),
            end_date=header_data.get('end_date'),
            status='processing'
        )
        db.add(saft_import)
        db.commit()
        db.refresh(saft_import)

        # Process import in foreground for now (can be moved to background task)
        try:
            stats = parser.import_to_database(db, saft_import.id)

            # Update import record with stats
            saft_import.total_invoices = stats['invoices_imported'] + stats['invoices_failed']
            saft_import.imported_invoices = stats['invoices_imported']
            saft_import.failed_invoices = stats['invoices_failed']
            saft_import.total_payments = stats['payments_imported'] + stats['payments_failed']
            saft_import.imported_payments = stats['payments_imported']
            saft_import.status = 'completed'
            saft_import.completed_at = datetime.utcnow()

            if stats['errors']:
                saft_import.error_message = '\n'.join(stats['errors'][:10])  # Store first 10 errors

            db.commit()
            db.refresh(saft_import)

        except Exception as e:
            saft_import.status = 'failed'
            saft_import.error_message = str(e)
            saft_import.completed_at = datetime.utcnow()
            db.commit()
            raise HTTPException(status_code=500, detail=f"Error importing SAFT data: {str(e)}")

        return saft_import

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error processing SAFT file: {str(e)}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/imports", response_model=List[SAFTImport])
def get_saft_imports(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all SAFT import records"""
    imports = db.query(models.SAFTImport).order_by(
        models.SAFTImport.created_at.desc()
    ).offset(skip).limit(limit).all()
    return imports


@router.get("/imports/{import_id}", response_model=SAFTImport)
def get_saft_import(import_id: int, db: Session = Depends(get_db)):
    """Get a specific SAFT import record"""
    saft_import = db.query(models.SAFTImport).filter(
        models.SAFTImport.id == import_id
    ).first()
    if not saft_import:
        raise HTTPException(status_code=404, detail="SAFT import not found")
    return saft_import
