from lxml import etree
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import Company, Invoice, InvoiceLineItem, SAFTImport, InvoiceType, InvoiceStatus, Payment, InvoicePayment


class SAFTParser:
    """
    Parser for SAF-T PT (Portuguese Standard Audit File for Tax purposes)
    
    Based on SAF-T PT version 1.04_01
    """
    
    NAMESPACE = {
        'ns': 'urn:OECD:StandardAuditFile-Tax:PT_1.04_01'
    }
    
    def __init__(self, xml_path: str):
        self.xml_path = xml_path
        self.tree = None
        self.root = None
    
    def parse(self) -> Dict:
        """Parse SAFT XML file and extract header information"""
        try:
            self.tree = etree.parse(self.xml_path)
            self.root = self.tree.getroot()
            
            header = self._parse_header()
            return header
        except Exception as e:
            raise Exception(f"Error parsing SAFT file: {str(e)}")
    
    def _parse_header(self) -> Dict:
        """Extract header information from SAFT file"""
        header = {}
        
        # Get Header element
        header_elem = self.root.find('.//ns:Header', self.NAMESPACE)
        
        if header_elem is not None:
            # Tax Registration Number (NIF)
            nif = header_elem.find('ns:TaxRegistrationNumber', self.NAMESPACE)
            if nif is not None:
                header['tax_registration_number'] = nif.text
            
            # Company Name
            company_name = header_elem.find('ns:CompanyName', self.NAMESPACE)
            if company_name is not None:
                header['company_name'] = company_name.text
            
            # Fiscal Year
            fiscal_year = header_elem.find('ns:FiscalYear', self.NAMESPACE)
            if fiscal_year is not None:
                header['fiscal_year'] = int(fiscal_year.text)
            
            # Start Date
            start_date = header_elem.find('ns:StartDate', self.NAMESPACE)
            if start_date is not None:
                header['start_date'] = datetime.fromisoformat(start_date.text)
            
            # End Date
            end_date = header_elem.find('ns:EndDate', self.NAMESPACE)
            if end_date is not None:
                header['end_date'] = datetime.fromisoformat(end_date.text)
        
        return header
    
    def get_customers(self) -> List[Dict]:
        """Extract customer data from SAFT file"""
        customers = []
        
        customer_elems = self.root.findall('.//ns:Customer', self.NAMESPACE)
        
        for customer in customer_elems:
            customer_data = {}
            
            # Customer ID
            customer_id = customer.find('ns:CustomerID', self.NAMESPACE)
            if customer_id is not None:
                customer_data['customer_id'] = customer_id.text
            
            # Tax ID (NIF)
            tax_id = customer.find('ns:CustomerTaxID', self.NAMESPACE)
            if tax_id is not None:
                customer_data['nif'] = tax_id.text
            
            # Company Name
            name = customer.find('ns:CompanyName', self.NAMESPACE)
            if name is not None:
                customer_data['name'] = name.text
            
            # Billing Address
            billing_address = customer.find('ns:BillingAddress', self.NAMESPACE)
            if billing_address is not None:
                address_detail = billing_address.find('ns:AddressDetail', self.NAMESPACE)
                if address_detail is not None:
                    customer_data['address'] = address_detail.text
                
                city = billing_address.find('ns:City', self.NAMESPACE)
                if city is not None:
                    customer_data['city'] = city.text
                
                postal_code = billing_address.find('ns:PostalCode', self.NAMESPACE)
                if postal_code is not None:
                    customer_data['postal_code'] = postal_code.text
                
                country = billing_address.find('ns:Country', self.NAMESPACE)
                if country is not None:
                    customer_data['country'] = country.text
            
            customer_data['is_customer'] = True
            customer_data['is_supplier'] = False
            
            customers.append(customer_data)
        
        return customers
    
    def get_invoices(self) -> List[Dict]:
        """Extract invoice data from SAFT file"""
        invoices = []
        
        # Sales invoices are in SourceDocuments/SalesInvoices/Invoice
        invoice_elems = self.root.findall('.//ns:SourceDocuments/ns:SalesInvoices/ns:Invoice', self.NAMESPACE)
        
        for invoice in invoice_elems:
            invoice_data = {}
            
            # Invoice Number
            invoice_no = invoice.find('ns:InvoiceNo', self.NAMESPACE)
            if invoice_no is not None:
                invoice_data['invoice_number'] = invoice_no.text
            
            # ATCUD
            atcud = invoice.find('ns:ATCUD', self.NAMESPACE)
            if atcud is not None:
                invoice_data['atcud'] = atcud.text
            
            # Customer ID
            customer_id = invoice.find('ns:CustomerID', self.NAMESPACE)
            if customer_id is not None:
                invoice_data['customer_reference'] = customer_id.text
            
            # Invoice Date
            invoice_date = invoice.find('ns:InvoiceDate', self.NAMESPACE)
            if invoice_date is not None:
                invoice_data['invoice_date'] = datetime.fromisoformat(invoice_date.text)
            
            # Invoice Type
            invoice_type = invoice.find('ns:InvoiceType', self.NAMESPACE)
            if invoice_type is not None:
                invoice_data['document_type'] = invoice_type.text
            
            # Status
            status = invoice.find('ns:InvoiceStatus', self.NAMESPACE)
            if status is not None:
                status_code = status.find('ns:InvoiceStatusCode', self.NAMESPACE)
                if status_code is not None:
                    invoice_data['status'] = status_code.text
            
            # Document Totals
            doc_totals = invoice.find('ns:DocumentTotals', self.NAMESPACE)
            if doc_totals is not None:
                net_total = doc_totals.find('ns:NetTotal', self.NAMESPACE)
                if net_total is not None:
                    invoice_data['subtotal'] = float(net_total.text)
                
                tax_payable = doc_totals.find('ns:TaxPayable', self.NAMESPACE)
                if tax_payable is not None:
                    invoice_data['tax_amount'] = float(tax_payable.text)
                
                gross_total = doc_totals.find('ns:GrossTotal', self.NAMESPACE)
                if gross_total is not None:
                    invoice_data['total_amount'] = float(gross_total.text)
            
            # Line items
            lines = invoice.findall('ns:Line', self.NAMESPACE)
            invoice_data['line_items'] = []
            
            for line in lines:
                line_data = {}
                
                description = line.find('ns:Description', self.NAMESPACE)
                if description is not None:
                    line_data['description'] = description.text
                
                quantity = line.find('ns:Quantity', self.NAMESPACE)
                if quantity is not None:
                    line_data['quantity'] = float(quantity.text)
                
                unit_price = line.find('ns:UnitPrice', self.NAMESPACE)
                if unit_price is not None:
                    line_data['unit_price'] = float(unit_price.text)
                
                # Tax
                tax = line.find('ns:Tax', self.NAMESPACE)
                if tax is not None:
                    tax_percentage = tax.find('ns:TaxPercentage', self.NAMESPACE)
                    if tax_percentage is not None:
                        line_data['tax_rate'] = float(tax_percentage.text)
                
                # Credit/Debit Amount
                credit_amount = line.find('ns:CreditAmount', self.NAMESPACE)
                debit_amount = line.find('ns:DebitAmount', self.NAMESPACE)
                
                if credit_amount is not None:
                    line_data['line_total'] = float(credit_amount.text)
                elif debit_amount is not None:
                    line_data['line_total'] = float(debit_amount.text)
                
                invoice_data['line_items'].append(line_data)
            
            invoice_data['invoice_type'] = InvoiceType.SALE
            invoices.append(invoice_data)
        
        return invoices
    
    def get_payments(self) -> List[Dict]:
        """Extract payment/receipt data from SAFT file (WorkingDocuments)"""
        payments = []
        
        # Payments/Receipts are in SourceDocuments/WorkingDocuments/WorkDocument
        payment_elems = self.root.findall('.//ns:SourceDocuments/ns:WorkingDocuments/ns:WorkDocument', self.NAMESPACE)
        
        for payment in payment_elems:
            payment_data = {}
            
            # Check if this is a receipt (RG or similar)
            doc_type = payment.find('ns:WorkType', self.NAMESPACE)
            if doc_type is not None and 'RG' not in doc_type.text:
                continue  # Skip non-receipt documents
            
            # Document Number
            doc_no = payment.find('ns:DocumentNumber', self.NAMESPACE)
            if doc_no is not None:
                payment_data['payment_number'] = doc_no.text
            
            # ATCUD
            atcud = payment.find('ns:ATCUD', self.NAMESPACE)
            if atcud is not None:
                payment_data['atcud'] = atcud.text
            
            # Customer ID
            customer_id = payment.find('ns:CustomerID', self.NAMESPACE)
            if customer_id is not None:
                payment_data['customer_reference'] = customer_id.text
            
            # Document Date
            doc_date = payment.find('ns:WorkDate', self.NAMESPACE)
            if doc_date is not None:
                payment_data['payment_date'] = datetime.fromisoformat(doc_date.text)
            
            # Document Totals
            doc_totals = payment.find('ns:DocumentTotals', self.NAMESPACE)
            if doc_totals is not None:
                gross_total = doc_totals.find('ns:GrossTotal', self.NAMESPACE)
                if gross_total is not None:
                    payment_data['payment_amount'] = float(gross_total.text)
            
            # Payment method (if available)
            payment_method = payment.find('ns:PaymentMechanism', self.NAMESPACE)
            if payment_method is not None:
                payment_data['payment_method'] = payment_method.text
            
            # Related invoices (DocumentReferences)
            invoice_refs = []
            for line in payment.findall('ns:Line', self.NAMESPACE):
                doc_ref = line.find('ns:References/ns:Reference', self.NAMESPACE)
                if doc_ref is not None:
                    ref_number = doc_ref.text
                    if ref_number:
                        # Get the amount for this specific invoice reference
                        credit_amount = line.find('ns:CreditAmount', self.NAMESPACE)
                        debit_amount = line.find('ns:DebitAmount', self.NAMESPACE)
                        
                        amount = 0.0
                        if credit_amount is not None:
                            amount = float(credit_amount.text)
                        elif debit_amount is not None:
                            amount = float(debit_amount.text)
                        
                        invoice_refs.append({
                            'invoice_number': ref_number,
                            'amount': amount
                        })
            
            payment_data['invoice_references'] = invoice_refs
            payments.append(payment_data)
        
        return payments
    
    def import_to_database(self, db: Session, saft_import_id: int) -> Dict:
        """Import SAFT data into database"""
        stats = {
            'customers_imported': 0,
            'invoices_imported': 0,
            'invoices_failed': 0,
            'payments_imported': 0,
            'payments_failed': 0,
            'errors': []
        }
        
        try:
            # Import customers
            customers = self.get_customers()
            customer_map = {}  # Map SAFT customer ID to DB ID
            
            for customer_data in customers:
                try:
                    # Check if customer already exists by NIF
                    nif = customer_data.get('nif')
                    if nif:
                        existing = db.query(Company).filter(Company.nif == nif).first()
                        if existing:
                            customer_map[customer_data.get('customer_id')] = existing.id
                            continue
                    
                    # Create new company
                    company = Company(
                        nif=customer_data.get('nif', '999999990'),
                        name=customer_data.get('name', 'Unknown'),
                        address=customer_data.get('address'),
                        city=customer_data.get('city'),
                        postal_code=customer_data.get('postal_code'),
                        country=customer_data.get('country', 'PT'),
                        is_customer=True,
                        is_supplier=False
                    )
                    db.add(company)
                    db.flush()
                    
                    customer_map[customer_data.get('customer_id')] = company.id
                    stats['customers_imported'] += 1
                    
                except Exception as e:
                    stats['errors'].append(f"Customer import error: {str(e)}")
            
            db.commit()
            
            # Import invoices
            invoices = self.get_invoices()
            invoice_map = {}  # Map invoice_number to DB invoice ID
            
            for invoice_data in invoices:
                try:
                    # Get customer ID from map
                    customer_ref = invoice_data.get('customer_reference')
                    customer_id = customer_map.get(customer_ref)
                    
                    # Create invoice
                    invoice = Invoice(
                        invoice_number=invoice_data['invoice_number'],
                        invoice_type=invoice_data['invoice_type'],
                        invoice_date=invoice_data['invoice_date'],
                        customer_id=customer_id,
                        subtotal=invoice_data.get('subtotal', 0),
                        tax_amount=invoice_data.get('tax_amount', 0),
                        total_amount=invoice_data.get('total_amount', 0),
                        atcud=invoice_data.get('atcud'),
                        status=InvoiceStatus.ISSUED,
                        saft_import_id=saft_import_id
                    )
                    db.add(invoice)
                    db.flush()
                    
                    # Store invoice mapping for payment linking
                    invoice_map[invoice_data['invoice_number']] = invoice.id
                    
                    # Add line items
                    for line_data in invoice_data.get('line_items', []):
                        line = InvoiceLineItem(
                            invoice_id=invoice.id,
                            description=line_data.get('description', ''),
                            quantity=line_data.get('quantity', 1.0),
                            unit_price=line_data.get('unit_price', 0),
                            tax_rate=line_data.get('tax_rate', 23.0),
                            line_total=line_data.get('line_total', 0)
                        )
                        db.add(line)
                    
                    stats['invoices_imported'] += 1
                    
                except Exception as e:
                    stats['invoices_failed'] += 1
                    stats['errors'].append(f"Invoice {invoice_data.get('invoice_number')}: {str(e)}")
            
            db.commit()
            
            # Import payments/receipts
            payments = self.get_payments()
            
            for payment_data in payments:
                try:
                    # Get customer ID from map
                    customer_ref = payment_data.get('customer_reference')
                    customer_id = customer_map.get(customer_ref)
                    
                    # Create payment
                    payment = Payment(
                        payment_number=payment_data['payment_number'],
                        payment_date=payment_data['payment_date'],
                        customer_id=customer_id,
                        payment_amount=payment_data.get('payment_amount', 0),
                        payment_method=payment_data.get('payment_method'),
                        atcud=payment_data.get('atcud'),
                        saft_import_id=saft_import_id
                    )
                    db.add(payment)
                    db.flush()
                    
                    # Link payment to invoices if references exist
                    for invoice_ref in payment_data.get('invoice_references', []):
                        invoice_number = invoice_ref.get('invoice_number')
                        amount = invoice_ref.get('amount', 0)
                        
                        # Try to find invoice in the map first (from this import)
                        invoice_id = invoice_map.get(invoice_number)
                        
                        # If not found in map, search database
                        if not invoice_id:
                            existing_invoice = db.query(Invoice).filter(
                                Invoice.invoice_number == invoice_number
                            ).first()
                            if existing_invoice:
                                invoice_id = existing_invoice.id
                        
                        # Create payment-invoice link
                        if invoice_id and amount > 0:
                            invoice_payment = InvoicePayment(
                                invoice_id=invoice_id,
                                payment_id=payment.id,
                                amount=amount
                            )
                            db.add(invoice_payment)
                    
                    stats['payments_imported'] += 1
                    
                except Exception as e:
                    stats['payments_failed'] += 1
                    stats['errors'].append(f"Payment {payment_data.get('payment_number')}: {str(e)}")
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise Exception(f"Database import error: {str(e)}")
        
        return stats
