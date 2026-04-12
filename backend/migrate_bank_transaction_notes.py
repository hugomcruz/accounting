"""Migration: create bank_transaction_notes table"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.database import engine
from sqlalchemy import text

def run():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bank_transaction_notes (
                id          SERIAL PRIMARY KEY,
                transaction_id INTEGER NOT NULL REFERENCES bank_transactions(id) ON DELETE CASCADE,
                user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
                username    VARCHAR(150) NOT NULL,
                body        TEXT NOT NULL,
                created_at  TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at  TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT NOW()
            );
        """))
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_bank_transaction_notes_transaction_id
                ON bank_transaction_notes(transaction_id);
        """))
        conn.commit()
    print("Migration complete: bank_transaction_notes table created.")

if __name__ == "__main__":
    run()
