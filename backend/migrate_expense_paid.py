"""
Migration: add paid_at and bank_transaction_id columns to expense_reports table.
Run once inside the backend container or with the project venv active.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import engine
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        # Add paid_at column
        try:
            conn.execute(text("ALTER TABLE expense_reports ADD COLUMN paid_at TIMESTAMP"))
            print("Added paid_at column")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("paid_at already exists — skipped")
            else:
                raise

        # Add bank_transaction_id column
        try:
            conn.execute(text(
                "ALTER TABLE expense_reports "
                "ADD COLUMN bank_transaction_id INTEGER REFERENCES bank_transactions(id)"
            ))
            print("Added bank_transaction_id column")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate column" in str(e).lower():
                print("bank_transaction_id already exists — skipped")
            else:
                raise

        conn.commit()
    print("Migration complete.")

if __name__ == "__main__":
    run()
