#!/usr/bin/env python3
"""
Migration script to add original_filename field to invoices table
"""
from sqlalchemy import create_engine, text
from app.core.config import settings

def migrate():
    """Add original_filename column to invoices table"""
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print("🔄 Adding original_filename column to invoices table...")
        
        # Add original_filename column
        try:
            conn.execute(text("""
                ALTER TABLE invoices 
                ADD COLUMN IF NOT EXISTS original_filename VARCHAR(255)
            """))
            conn.commit()
            print("✅ Added original_filename column")
        except Exception as e:
            print(f"⚠️  Column might already exist: {e}")
        
        print("\n✅ Migration completed successfully!")

if __name__ == "__main__":
    migrate()
