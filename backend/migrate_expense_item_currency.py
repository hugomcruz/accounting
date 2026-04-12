"""
Migration: Add eur_amount and exchange_rate columns to expense_items table.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import text
from app.core.database import engine

def run():
    with engine.connect() as conn:
        print("Adding eur_amount and exchange_rate to expense_items...")
        conn.execute(text("ALTER TABLE expense_items ADD COLUMN IF NOT EXISTS eur_amount FLOAT"))
        conn.execute(text("ALTER TABLE expense_items ADD COLUMN IF NOT EXISTS exchange_rate FLOAT"))
        conn.commit()
        print("Done.")

if __name__ == "__main__":
    run()
