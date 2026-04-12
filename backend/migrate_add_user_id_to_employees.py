"""
Migration: Add user_id FK column to employees table.

This links an Employee record to a User account, enabling the 'user' role
to access only their own expense reports.

Run with:
    docker exec brightwaves_backend python3 /app/migrate_add_user_id_to_employees.py
"""

import sys
import os
sys.path.insert(0, '/app')

from sqlalchemy import text
from app.core.database import engine


def run():
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='employees' AND column_name='user_id'"
        ))
        if result.fetchone():
            print("Column 'user_id' already exists in employees table — skipping.")
            return

        print("Adding 'user_id' column to employees table...")
        conn.execute(text(
            "ALTER TABLE employees ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"
        ))
        # Unique constraint: one employee per user account
        conn.execute(text(
            "CREATE UNIQUE INDEX idx_employees_user_id ON employees(user_id) WHERE user_id IS NOT NULL"
        ))
        conn.commit()
        print("Migration complete.")


if __name__ == "__main__":
    run()
