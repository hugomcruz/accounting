from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.schemas.schemas import Company, CompanyCreate, CompanyUpdate
from app.models import models
from app.services.company_enrichment import CompanyEnrichmentService

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=List[Company])
def get_companies(
    skip: int = 0,
    limit: int = 100,
    is_customer: bool = None,
    is_supplier: bool = None,
    db: Session = Depends(get_db)
):
    """Get all companies with optional filtering"""
    query = db.query(models.Company)
    
    if is_customer is not None:
        query = query.filter(models.Company.is_customer == is_customer)
    if is_supplier is not None:
        query = query.filter(models.Company.is_supplier == is_supplier)
    
    companies = query.offset(skip).limit(limit).all()
    return companies


@router.get("/{company_id}", response_model=Company)
def get_company(company_id: int, db: Session = Depends(get_db)):
    """Get a specific company by ID"""
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.get("/nif/{nif}", response_model=Company)
def get_company_by_nif(nif: str, db: Session = Depends(get_db)):
    """Get a company by NIF (Portuguese Tax ID)"""
    company = db.query(models.Company).filter(models.Company.nif == nif).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    return company


@router.post("", response_model=Company, status_code=201)
def create_company(company: CompanyCreate, db: Session = Depends(get_db)):
    """Create a new company"""
    # Check if NIF already exists
    existing = db.query(models.Company).filter(models.Company.nif == company.nif).first()
    if existing:
        raise HTTPException(status_code=400, detail="Company with this NIF already exists")
    
    db_company = models.Company(**company.model_dump())
    db.add(db_company)
    db.commit()
    db.refresh(db_company)
    return db_company


@router.patch("/{company_id}", response_model=Company)
def update_company(
    company_id: int,
    company_update: CompanyUpdate,
    db: Session = Depends(get_db)
):
    """Update a company"""
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    update_data = company_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(company, key, value)
    
    db.commit()
    db.refresh(company)
    return company


@router.delete("/{company_id}")
def delete_company(company_id: int, db: Session = Depends(get_db)):
    """Delete a company"""
    company = db.query(models.Company).filter(models.Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found")
    
    db.delete(company)
    db.commit()
    return {"message": "Company deleted successfully"}


@router.post("/enrich", status_code=200)
def enrich_companies(
    background_tasks: BackgroundTasks,
    max_companies: int = 10,
    db: Session = Depends(get_db)
):
    """
    Enrich companies with missing postal codes by querying NIF.PT API.
    
    This endpoint respects API quotas:
    - 1 request per minute
    - 6 requests per hour
    - 100 requests per day
    - 1000 requests per month
    
    Args:
        max_companies: Maximum number of companies to process (default 10)
        
    Returns:
        Enrichment statistics including quota status
    """
    enrichment_service = CompanyEnrichmentService(db)
    
    # Run enrichment synchronously (could be moved to background task if needed)
    result = enrichment_service.run_enrichment_batch(max_companies=max_companies)
    
    return {
        "message": "Company enrichment completed",
        "stats": result
    }


@router.get("/enrich/status", status_code=200)
def get_enrichment_status(db: Session = Depends(get_db)):
    """
    Get companies needing enrichment count
    
    Returns:
        Count of companies needing enrichment
    """
    companies_needing_enrichment = db.query(models.Company).filter(
        models.Company.is_enriched == 0
    ).count()
    
    return {
        "companies_needing_enrichment": companies_needing_enrichment,
        "paid_version": True
    }


