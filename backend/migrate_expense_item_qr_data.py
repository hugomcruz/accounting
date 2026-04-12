"""
Migration: add qr_data column to expense_items so QR extraction
results are stored at item-creation time and reused at approval
instead of re-scanning the file.
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise Exception("DATABASE_URL not found in environment variables")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    conn.execute(text(
        "ALTER TABLE expense_items ADD COLUMN IF NOT EXISTS qr_data TEXT"
    ))
    conn.commit()
    print("Added qr_data column to expense_items.")
