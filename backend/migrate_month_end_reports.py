"""
Migration: Create month_end_reports table.
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
    with engine.connect() as conn:
        print("Creating month_end_reports table...")
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS month_end_reports (
                id SERIAL PRIMARY KEY,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                saft_import_id INTEGER REFERENCES saft_imports(id) ON DELETE SET NULL,
                bank_statement_id INTEGER REFERENCES bank_statements(id) ON DELETE SET NULL,
                invoice_export_id INTEGER REFERENCES invoice_exports(id) ON DELETE SET NULL,
                saft_filename VARCHAR(500),
                bank_statement_filename VARCHAR(500),
                invoice_count INTEGER DEFAULT 0,
                saft_file_path VARCHAR(500),
                bank_statement_file_path VARCHAR(500),
                invoice_zip_file_path VARCHAR(500),
                status VARCHAR(50) DEFAULT 'generating',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_mer_year_month ON month_end_reports(year, month)"))
        conn.commit()
        print("✓ month_end_reports table created")


if __name__ == "__main__":
    run_migration()
