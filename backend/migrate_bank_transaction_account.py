#!/usr/bin/env python3
"""
Migration: add bank_account_id to bank_transactions and backfill from the parent statement.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import create_engine, text
from app.core.config import settings


def migrate():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        # 1. Add column if missing
        try:
            conn.execute(text("""
                ALTER TABLE bank_transactions
                ADD COLUMN IF NOT EXISTS bank_account_id INTEGER
                    REFERENCES bank_accounts(id) ON DELETE SET NULL;
            """))
            conn.commit()
            print("✅ Added bank_account_id column to bank_transactions")
        except Exception as e:
            print(f"⚠️  Column may already exist: {e}")
            conn.rollback()

        # 2. Backfill from parent statement
        try:
            result = conn.execute(text("""
                UPDATE bank_transactions bt
                SET bank_account_id = bs.bank_account_id
                FROM bank_statements bs
                WHERE bt.statement_id = bs.id
                  AND bt.bank_account_id IS NULL
                  AND bs.bank_account_id IS NOT NULL
            """))
            conn.commit()
            print(f"✅ Backfilled bank_account_id on {result.rowcount} transactions")
        except Exception as e:
            print(f"❌ Backfill failed: {e}")
            conn.rollback()

        # 3. Create index
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_bank_transactions_bank_account_id
                ON bank_transactions(bank_account_id);
            """))
            conn.commit()
            print("✅ Created index on bank_transactions.bank_account_id")
        except Exception as e:
            print(f"⚠️  Index: {e}")


if __name__ == "__main__":
    migrate()
