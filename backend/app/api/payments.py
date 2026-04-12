from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.core.database import get_db
from app.schemas.schemas import Payment as PaymentSchema
from app.models import models

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("", response_model=List[PaymentSchema])
def get_payments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all payments with optional pagination"""
    payments = db.query(models.Payment)\
        .options(joinedload(models.Payment.customer))\
        .order_by(models.Payment.payment_date.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return payments


@router.get("/{payment_id}", response_model=PaymentSchema)
def get_payment(payment_id: int, db: Session = Depends(get_db)):
    """Get a specific payment by ID"""
    payment = db.query(models.Payment)\
        .options(joinedload(models.Payment.customer))\
        .filter(models.Payment.id == payment_id)\
        .first()
    
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    
    return payment


@router.get("/customer/{customer_id}", response_model=List[PaymentSchema])
def get_customer_payments(
    customer_id: int,
    db: Session = Depends(get_db)
):
    """Get all payments for a specific customer"""
    payments = db.query(models.Payment)\
        .filter(models.Payment.customer_id == customer_id)\
        .order_by(models.Payment.payment_date.desc())\
        .all()
    
    return payments
