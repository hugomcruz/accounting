#!/usr/bin/env python3
"""
Migration: add linked_transaction_id to bank_transactions for inter-account transfer reconciliation.
"""
import sys
sys.path.insert(0, '/app')

from app.core.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    # Check if column already exists
    result = conn.execute(text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name='bank_transactions' AND column_name='linked_transaction_id'"
    ))
    if result.fetchone():
        print("Column linked_transaction_id already exists – skipping.")
    else:
        conn.execute(text(
            "ALTER TABLE bank_transactions "
            "ADD COLUMN linked_transaction_id INTEGER REFERENCES bank_transactions(id)"
        ))
        conn.commit()
        print("Added linked_transaction_id to bank_transactions.")

print("Done.")
