from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from app.models import models
import re


class BankReconciliationService:
    """Service to automatically reconcile bank transactions with invoices"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def reconcile_statement(self, statement_id: int) -> Dict[str, any]:
        """
        Reconcile all transactions in a bank statement with invoices
        
        Returns:
            Dict with reconciliation statistics
        """
        statement = self.db.query(models.BankStatement).filter(
            models.BankStatement.id == statement_id
        ).first()
        
        if not statement:
            raise ValueError(f"Statement {statement_id} not found")
        
        # Get all unreconciled transactions
        transactions = self.db.query(models.BankTransaction).filter(
            and_(
                models.BankTransaction.statement_id == statement_id,
                models.BankTransaction.is_reconciled == 0
            )
        ).all()
        
        matched = 0
        unmatched = 0
        
        for transaction in transactions:
            # Skip zero-amount transactions
            if transaction.amount == 0:
                unmatched += 1
                continue

            # Determine invoice type based on transaction direction
            # Negative = outgoing payment → match with PURCHASE invoice
            # Positive = incoming payment → match with SALE invoice
            invoice = self._find_matching_invoice(transaction, statement)

            if invoice:
                # Link transaction to invoice
                transaction.invoice_id = invoice.id
                transaction.is_reconciled = 1  # SQLite boolean as integer
                transaction.notes = f"Auto-reconciled with invoice {invoice.invoice_number}"
                # Create a company_account payment record if one doesn't exist yet
                self._ensure_company_account_payment(transaction, invoice)
                # Mark invoice as paid
                invoice.status = models.InvoiceStatus.PAID
                matched += 1
            else:
                unmatched += 1
        
        self.db.commit()
        
        return {
            "statement_id": statement_id,
            "total_transactions": len(transactions),
            "matched": matched,
            "unmatched": unmatched,
            "reconciliation_rate": (matched / len(transactions) * 100) if transactions else 0
        }
    
    def _find_matching_invoice(
        self, 
        transaction: models.BankTransaction, 
        statement: models.BankStatement
    ) -> Optional[models.Invoice]:
        """
        Find the best matching invoice for a transaction
        
        Matching criteria:
        1. Amount must match (absolute value)
        2. Invoice date should be close to transaction date (within 30 days before)
        3. Supplier name should match description (if available)
        4. Invoice type must be PURCHASE
        """
        # Determine invoice type based on transaction direction
        invoice_type = models.InvoiceType.PURCHASE if transaction.amount < 0 else models.InvoiceType.SALE
        amount = abs(transaction.amount)
        
        # Date range: transaction date and up to 30 days before
        date_start = transaction.transaction_date - timedelta(days=30)
        date_end = transaction.transaction_date + timedelta(days=5)  # Allow 5 days grace period
        
        # Build base query for invoices in date range filtered by direction
        query = self.db.query(models.Invoice).filter(
            and_(
                models.Invoice.invoice_type == invoice_type,
                models.Invoice.invoice_date >= date_start,
                models.Invoice.invoice_date <= date_end,
                # Skip invoices already paid via expense report reconciliation
                models.Invoice.status != models.InvoiceStatus.PAID,
            )
        )
        
        # Find invoices with matching amount (within 0.01 tolerance)
        matching_invoices = query.filter(
            func.abs(models.Invoice.total_amount - amount) < 0.01
        ).all()
        
        if not matching_invoices:
            return None
        
        # If only one match, return it
        if len(matching_invoices) == 1:
            return matching_invoices[0]
        
        # If multiple matches, try to match by supplier name in description
        best_match = self._find_best_supplier_match(
            transaction.description,
            matching_invoices
        )
        
        return best_match
    
    def _find_best_supplier_match(
        self,
        description: str,
        invoices: List[models.Invoice]
    ) -> Optional[models.Invoice]:
        """
        Find the best invoice match based on supplier name in transaction description
        """
        description_lower = description.lower()
        
        # Extract potential company identifiers from description
        # Common patterns: NIF, company name keywords
        nif_pattern = r'\b\d{9}\b'
        nifs_in_desc = re.findall(nif_pattern, description)
        
        for invoice in invoices:
            if not invoice.supplier:
                continue
            
            supplier_name = invoice.supplier.name.lower()
            supplier_nif = invoice.supplier.nif
            
            # Check if supplier NIF is in description
            if supplier_nif and supplier_nif in nifs_in_desc:
                return invoice
            
            # Check if supplier name (or significant parts) is in description
            # Split supplier name into words and check if any significant word matches
            supplier_words = [w for w in supplier_name.split() if len(w) > 3]
            
            for word in supplier_words:
                if word in description_lower:
                    return invoice
        
        # If no clear match, return the first one (closest date)
        return invoices[0] if invoices else None
    
    def reconcile_transaction(
        self,
        transaction_id: int,
        invoice_id: int
    ) -> models.BankTransaction:
        """
        Manually reconcile a specific transaction with an invoice
        """
        transaction = self.db.query(models.BankTransaction).filter(
            models.BankTransaction.id == transaction_id
        ).first()
        
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        invoice = self.db.query(models.Invoice).filter(
            models.Invoice.id == invoice_id
        ).first()
        
        if not invoice:
            raise ValueError(f"Invoice {invoice_id} not found")
        
        transaction.invoice_id = invoice_id
        transaction.is_reconciled = 1  # SQLite boolean as integer
        transaction.notes = f"Manually reconciled with invoice {invoice.invoice_number}"

        # Create a company_account payment record if one doesn't exist yet
        self._ensure_company_account_payment(transaction, invoice)

        # Mark invoice as paid
        invoice.status = models.InvoiceStatus.PAID

        self.db.commit()
        self.db.refresh(transaction)
        
        return transaction
    
    def unreconcile_transaction(self, transaction_id: int) -> models.BankTransaction:
        """
        Remove reconciliation from a transaction
        """
        transaction = self.db.query(models.BankTransaction).filter(
            models.BankTransaction.id == transaction_id
        ).first()

        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")

        # Remove the auto-created company_account payment record for this transaction
        self.db.query(models.InvoiceDirectPayment).filter(
            models.InvoiceDirectPayment.bank_transaction_id == transaction_id,
            models.InvoiceDirectPayment.payment_type == "company_account",
        ).delete(synchronize_session=False)

        # Revert invoice status if it was paid solely by this bank transaction
        if transaction.invoice_id:
            invoice = self.db.query(models.Invoice).filter(
                models.Invoice.id == transaction.invoice_id
            ).first()
            if invoice and invoice.status == models.InvoiceStatus.PAID:
                # Check whether any other payment records remain after deletion
                remaining = self.db.query(models.InvoiceDirectPayment).filter(
                    models.InvoiceDirectPayment.invoice_id == invoice.id,
                    models.InvoiceDirectPayment.bank_transaction_id != transaction_id,
                ).count()
                if remaining == 0:
                    invoice.status = models.InvoiceStatus.ISSUED

        transaction.invoice_id = None
        transaction.is_reconciled = 0
        transaction.notes = None

        self.db.commit()
        self.db.refresh(transaction)

        return transaction

    def _ensure_company_account_payment(
        self,
        transaction: models.BankTransaction,
        invoice: models.Invoice,
    ) -> None:
        """Create a company_account InvoiceDirectPayment linked to this bank transaction
        if one doesn't already exist."""
        existing = self.db.query(models.InvoiceDirectPayment).filter(
            models.InvoiceDirectPayment.bank_transaction_id == transaction.id,
            models.InvoiceDirectPayment.invoice_id == invoice.id,
        ).first()
        if existing:
            return
        payment = models.InvoiceDirectPayment(
            invoice_id=invoice.id,
            payment_date=transaction.transaction_date,
            amount=abs(transaction.amount),
            payment_type="company_account",
            bank_transaction_id=transaction.id,
            reference=transaction.reference if hasattr(transaction, "reference") else None,
            notes=f"Bank statement: {transaction.description}",
        )
        self.db.add(payment)
    
    def get_reconciliation_suggestions(
        self,
        transaction_id: int,
        limit: int = 5
    ) -> List[Dict]:
        """
        Get suggested invoices for a transaction
        """
        transaction = self.db.query(models.BankTransaction).filter(
            models.BankTransaction.id == transaction_id
        ).first()
        
        if not transaction:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        amount = abs(transaction.amount)
        invoice_type = models.InvoiceType.PURCHASE if transaction.amount < 0 else models.InvoiceType.SALE
        date_start = transaction.transaction_date - timedelta(days=30)
        date_end = transaction.transaction_date + timedelta(days=5)
        
        # Find invoices with similar amount
        invoices = self.db.query(models.Invoice).filter(
            and_(
                models.Invoice.invoice_type == invoice_type,
                models.Invoice.invoice_date >= date_start,
                models.Invoice.invoice_date <= date_end,
                func.abs(models.Invoice.total_amount - amount) < 1.0  # Within 1 euro
            )
        ).order_by(
            func.abs(models.Invoice.total_amount - amount)
        ).limit(limit).all()
        
        suggestions = []
        for invoice in invoices:
            match_score = self._calculate_match_score(transaction, invoice)
            suggestions.append({
                "invoice_id": invoice.id,
                "invoice_number": invoice.invoice_number,
                "supplier_name": invoice.supplier.name if invoice.supplier else None,
                "invoice_date": invoice.invoice_date,
                "amount": invoice.total_amount,
                "amount_diff": abs(invoice.total_amount - amount),
                "days_diff": abs((invoice.invoice_date - transaction.transaction_date).days),
                "match_score": match_score
            })
        
        # Sort by match score descending
        suggestions.sort(key=lambda x: x["match_score"], reverse=True)
        
        return suggestions
    
    def _calculate_match_score(
        self,
        transaction: models.BankTransaction,
        invoice: models.Invoice
    ) -> float:
        """
        Calculate a match score between 0 and 100
        """
        score = 0.0
        
        # Amount match (50 points)
        amount_diff = abs(abs(transaction.amount) - invoice.total_amount)
        if amount_diff < 0.01:
            score += 50
        elif amount_diff < 0.10:
            score += 40
        elif amount_diff < 1.0:
            score += 30
        elif amount_diff < 10.0:
            score += 20
        
        # Date proximity (30 points)
        days_diff = abs((transaction.transaction_date - invoice.invoice_date).days)
        if days_diff <= 1:
            score += 30
        elif days_diff <= 7:
            score += 20
        elif days_diff <= 14:
            score += 10
        elif days_diff <= 30:
            score += 5
        
        # Supplier name match (20 points)
        if invoice.supplier:
            description_lower = transaction.description.lower()
            supplier_name_lower = invoice.supplier.name.lower()
            supplier_words = [w for w in supplier_name_lower.split() if len(w) > 3]
            
            matches = sum(1 for word in supplier_words if word in description_lower)
            if matches > 0:
                score += min(20, matches * 10)
        
        return score
