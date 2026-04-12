"""
Database migration script to add new features:
- Invoice processing queue table
- Foreign currency fields in invoices
- VAT breakdown fields in invoices
- Social security number field in employees
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in environment variables")

engine = create_engine(DATABASE_URL)


def run_migration():
    """Run the database migration"""
    
    with engine.connect() as conn:
        print("Starting database migration...")
        
        # 1. Create invoice_processing_queue table
        print("\n1. Creating invoice_processing_queue table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS invoice_processing_queue (
                id SERIAL PRIMARY KEY,
                filename VARCHAR(255) NOT NULL,
                local_file_path VARCHAR(500),
                s3_file_path VARCHAR(500),
                status VARCHAR(50) DEFAULT 'pending',
                error_message TEXT,
                has_qr_data INTEGER DEFAULT 0,
                qr_data TEXT,
                invoice_id INTEGER REFERENCES invoices(id),
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                retry_count INTEGER DEFAULT 0,
                last_retry_at TIMESTAMP
            )
        """))
        print("✓ invoice_processing_queue table created")
        
        # 2. Add foreign currency fields to invoices
        print("\n2. Adding foreign currency fields to invoices...")
        try:
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS is_foreign_currency INTEGER DEFAULT 0"))
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS foreign_currency_code VARCHAR(3)"))
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS original_total_amount FLOAT"))
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS original_tax_amount FLOAT"))
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS exchange_rate FLOAT"))
            print("✓ Foreign currency fields added to invoices")
        except Exception as e:
            print(f"⚠ Foreign currency fields may already exist: {e}")
        
        # 3. Add VAT breakdown fields to invoices
        print("\n3. Adding VAT breakdown fields to invoices...")
        try:
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS vat_6_base FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS vat_6_amount FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS vat_23_base FLOAT DEFAULT 0"))
            conn.execute(text("ALTER TABLE invoices ADD COLUMN IF NOT EXISTS vat_23_amount FLOAT DEFAULT 0"))
            print("✓ VAT breakdown fields added to invoices")
        except Exception as e:
            print(f"⚠ VAT fields may already exist: {e}")
        
        # 4. Add social security number to employees
        print("\n4. Adding social security number to employees...")
        try:
            conn.execute(text("ALTER TABLE employees ADD COLUMN IF NOT EXISTS social_security_number VARCHAR(11) UNIQUE"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_employees_social_security_number ON employees(social_security_number)"))
            print("✓ Social security number field added to employees")
        except Exception as e:
            print(f"⚠ Social security number field may already exist: {e}")
        
        # Commit changes
        conn.commit()
        
        print("\n✅ Migration completed successfully!")
        print("\nNew features added:")
        print("  • Bulk invoice upload with processing queue")
        print("  • Review Invoices page for manual processing")
        print("  • Foreign currency support in invoices")
        print("  • VAT 6% and 23% breakdown in invoices")
        print("  • Social Security Number (NISS) for employees")


if __name__ == "__main__":
    run_migration()
