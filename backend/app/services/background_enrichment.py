"""
Background task for continuous company enrichment

Runs periodically to enrich all companies missing postal codes
by querying the NIF.PT API.
"""

import asyncio
import time
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.services.company_enrichment import CompanyEnrichmentService
from app.models.models import Company, AppSettings


def is_nif_api_enabled(db: Session) -> bool:
    """Check if NIF API is enabled in settings"""
    setting = db.query(AppSettings).filter(AppSettings.key == "nif_api_enabled").first()
    if not setting:
        # Default to enabled if setting doesn't exist
        return True
    return setting.value == "true"


class BackgroundEnrichmentTask:
    """Background task that runs company enrichment in batches"""
    
    def __init__(self):
        self.running = False
        self.task = None
    
    async def run_continuous_enrichment(self):
        """
        Main loop that checks for companies needing enrichment and processes all of them
        """
        print("\n" + "="*70)
        print("🚀 Starting Background Company Enrichment Service")
        print("="*70)
        print("⏰ Will check for companies needing enrichment every 5 minutes")
        print("💳 Using paid NIF.PT API - no rate limiting")
        print("="*70 + "\n")
        
        self.running = True
        
        while self.running:
            db: Session = SessionLocal()
            
            try:
                # Check if NIF API is enabled
                if not is_nif_api_enabled(db):
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏸️  NIF API is disabled in settings. Waiting 5 minutes...")
                    await asyncio.sleep(300)  # 5 minutes
                    continue
                
                # Get count of companies needing enrichment
                companies_needing_enrichment = db.query(Company).filter(
                    Company.is_enriched == 0
                ).count()
                
                if companies_needing_enrichment == 0:
                    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✨ No companies need enrichment. Waiting 5 minutes...")
                    await asyncio.sleep(300)  # 5 minutes
                    continue
                
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🔍 Found {companies_needing_enrichment} companies needing enrichment")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚀 Starting batch enrichment...")
                
                # Create enrichment service and run batch enrichment
                enrichment_service = CompanyEnrichmentService(db)
                result = enrichment_service.run_enrichment_batch(max_companies=companies_needing_enrichment)
                
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✅ Batch complete: {result['enriched']} enriched, {result['failed']} failed")
                
                # Wait 5 minutes before next check
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏳ Waiting 5 minutes before next check...")
                await asyncio.sleep(300)  # 5 minutes
                
            except Exception as e:
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ Error in enrichment loop: {str(e)}")
                print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ⏳ Waiting 5 minutes before retry...")
                await asyncio.sleep(300)  # 5 minutes
                
            finally:
                db.close()
    
    def start(self):
        """Start the background enrichment task"""
        if not self.running:
            self.task = asyncio.create_task(self.run_continuous_enrichment())
            print("🟢 Background enrichment task started")
    
    async def stop(self):
        """Stop the background enrichment task"""
        if self.running:
            print("\n🛑 Stopping background enrichment task...")
            self.running = False
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    pass
            print("🔴 Background enrichment task stopped\n")


# Global instance
background_enrichment_task = BackgroundEnrichmentTask()
