"""
Migration: Change invoice uniqueness from invoice_number alone
           to composite (supplier_id, invoice_number).

This allows different suppliers to have invoices with the same number,
while still preventing duplicate invoices from the same supplier.
"""
from app.core.database import engine
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        # 1. Drop the old unique index on invoice_number alone
        #    SQLAlchemy named it ix_invoices_invoice_number (unique=True + index=True)
        conn.execute(text("DROP INDEX IF EXISTS ix_invoices_invoice_number"))
        print("Dropped old unique index ix_invoices_invoice_number")

        # 2. Create a regular (non-unique) index on invoice_number for query performance
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_invoices_invoice_number "
            "ON invoices (invoice_number)"
        ))
        print("Created non-unique index ix_invoices_invoice_number")

        # 3. Create the new composite unique constraint
        #    First drop it if it already exists (idempotent)
        conn.execute(text(
            "ALTER TABLE invoices "
            "DROP CONSTRAINT IF EXISTS uq_invoice_supplier_number"
        ))
        conn.execute(text(
            "ALTER TABLE invoices "
            "ADD CONSTRAINT uq_invoice_supplier_number "
            "UNIQUE (supplier_id, invoice_number)"
        ))
        print("Created composite unique constraint uq_invoice_supplier_number on (supplier_id, invoice_number)")

        conn.commit()
        print("Migration complete.")

if __name__ == "__main__":
    run()
