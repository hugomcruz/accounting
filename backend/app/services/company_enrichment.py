"""
Company Enrichment Service

Background service to enrich company data by querying NIF.PT API
for companies missing postal codes.
"""

import requests
from datetime import datetime
from typing import Optional, Dict, List
from sqlalchemy.orm import Session
from app.models.models import Company
from app.core.config import settings


class CompanyEnrichmentService:
    """Service to enrich company data with NIF.PT API"""
    
    API_KEY = "e81341da5ceae49adf226a5e9f3af093"
    API_URL = "https://www.nif.pt/"
    
    def __init__(self, db: Session):
        self.db = db
    
    def lookup_company_by_nif(self, nif: str) -> Optional[Dict]:
        """
        Lookup company details from NIF.PT API
        
        Args:
            nif: Portuguese Tax Identification Number
            
        Returns:
            Dictionary with company details or None if not found/error
        """
        try:
            url = f"{self.API_URL}?json=1&q={nif}&key={self.API_KEY}"
            
            print(f"🔍 Looking up NIF {nif}...")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Handle error responses
                if data.get('result') == 'error':
                    error_msg = data.get('message', 'Unknown error')
                    print(f"❌ API Error: {error_msg}")
                    
                    # If "No records found", return special marker to prevent re-querying
                    if 'No records found' in error_msg:
                        return {
                            'nif': nif,
                            'postal_code': '0000',
                            'no_records': True
                        }
                    
                    return None
                
                # Handle success response
                if data.get('result') == 'success' and data.get('records'):
                    company_info = data['records'].get(nif, {})
                    
                    if company_info:
                        # Build postal code
                        # If pc3 is missing, use only pc4
                        postal_code = ''
                        if company_info.get('pc4'):
                            if company_info.get('pc3'):
                                postal_code = f"{company_info['pc4']}-{company_info['pc3']}"
                            else:
                                postal_code = company_info['pc4']
                        
                        result = {
                            'nif': nif,
                            'name': company_info.get('title', ''),
                            'address': company_info.get('address', ''),
                            'postal_code': postal_code,
                            'city': company_info.get('city', ''),
                            'status': company_info.get('status', '')
                        }
                        
                        print(f"✅ Found: {result['name']}")
                        return result
            
            return None
            
        except requests.Timeout:
            print(f"⏱️  Timeout looking up NIF {nif}")
            return None
        except Exception as e:
            print(f"❌ Error looking up NIF {nif}: {str(e)}")
            return None
    
    def get_companies_needing_enrichment(self, limit: int = 10) -> List[Company]:
        """
        Get companies that need enrichment (missing postal code)
        Excludes companies with postal code "0000" (no records found marker)
        
        Args:
            limit: Maximum number of companies to return
            
        Returns:
            List of Company objects needing enrichment
        """
        return self.db.query(Company).filter(
            Company.is_enriched == 0
        ).limit(limit).all()
    
    def enrich_company(self, company: Company) -> bool:
        """
        Enrich a single company with data from NIF.PT API
        
        Args:
            company: Company object to enrich
            
        Returns:
            True if enrichment succeeded, False otherwise
        """
        print(f"\n📋 Enriching company: {company.name} (NIF: {company.nif})")
        
        company_data = self.lookup_company_by_nif(company.nif)
        
        if company_data:
            # Check if this is a "no records found" marker
            if company_data.get('no_records'):
                # Set postal code to 0000 to prevent re-querying
                company.postal_code = '0000'
                company.is_enriched = 1
                company.enriched_at = datetime.utcnow()
                company.updated_at = datetime.utcnow()
                self.db.commit()
                print(f"⚠️  No records found for {company.name} - marked as enriched with postal code 0000")
                return True
            
            # Update company with new data
            if company_data.get('name'):
                company.name = company_data['name']
            if company_data.get('address'):
                company.address = company_data['address']
            if company_data.get('postal_code'):
                company.postal_code = company_data['postal_code']
            if company_data.get('city'):
                company.city = company_data['city']
            
            company.country = 'PT'
            company.is_enriched = 1
            company.enriched_at = datetime.utcnow()
            company.updated_at = datetime.utcnow()
            
            self.db.commit()
            print(f"✅ Successfully enriched {company.name}")
            return True
        
        # If enrichment failed, mark as enriched to avoid repeated attempts
        company.is_enriched = 1
        company.enriched_at = datetime.utcnow()
        company.updated_at = datetime.utcnow()
        self.db.commit()
        print(f"⚠️  Could not enrich {company.name} - marked as enriched to skip future attempts")
        return False
    
    def run_enrichment_batch(self, max_companies: int = 10) -> Dict:
        """
        Run enrichment for a batch of companies
        
        Args:
            max_companies: Maximum number of companies to process
            
        Returns:
            Statistics about the enrichment run
        """
        print("\n" + "="*60)
        print("🚀 Starting Company Enrichment Batch")
        print("="*60)
        
        # Get companies needing enrichment
        companies = self.get_companies_needing_enrichment(limit=max_companies)
        
        print(f"\n🔍 Found {len(companies)} companies needing enrichment")
        
        if not companies:
            print("✨ No companies need enrichment!")
            return {
                'total_found': 0,
                'enriched': 0,
                'failed': 0
            }
        
        enriched = 0
        failed = 0
        
        for company in companies:
            # Enrich the company
            if self.enrich_company(company):
                enriched += 1
            else:
                failed += 1
        
        print("\n" + "="*60)
        print("✅ Enrichment Batch Complete")
        print(f"   Total found: {len(companies)}")
        print(f"   Enriched: {enriched}")
        print(f"   Failed: {failed}")
        print("="*60 + "\n")
        
        return {
            'total_found': len(companies),
            'enriched': enriched,
            'failed': failed
        }
