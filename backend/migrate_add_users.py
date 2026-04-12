#!/usr/bin/env python3
"""
Migration script to add users table and create default admin user
"""
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.auth import get_password_hash

def migrate():
    """Add users table and create default admin"""
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        print("🔄 Creating users table...")
        
        # Drop existing enum if it exists
        try:
            conn.execute(text("DROP TYPE IF EXISTS user_role CASCADE"))
            conn.commit()
        except Exception as e:
            pass
        
        # Create user_role enum
        try:
            conn.execute(text("""
                CREATE TYPE user_role AS ENUM ('admin', 'finance', 'accounting');
            """))
            conn.commit()
            print("✅ Created user_role enum type")
        except Exception as e:
            print(f"⚠️  Error creating enum: {e}")
        
        # Create users table
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE,
                    password_hash VARCHAR(255) NOT NULL,
                    first_name VARCHAR(100) NOT NULL,
                    family_name VARCHAR(100) NOT NULL,
                    full_name VARCHAR(255) NOT NULL,
                    phone VARCHAR(20),
                    role user_role NOT NULL DEFAULT 'accounting',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login_at TIMESTAMP
                );
                
                CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
                CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            """))
            conn.commit()
            print("✅ Created users table")
        except Exception as e:
            print(f"⚠️  Table might already exist: {e}")
        
        # Create default admin user
        try:
            # Check if admin exists
            result = conn.execute(text("SELECT COUNT(*) FROM users WHERE username = 'admin'"))
            admin_exists = result.scalar() > 0
            
            if not admin_exists:
                # Hash default password: "admin123" (CHANGE THIS IN PRODUCTION!)
                password_hash = get_password_hash("admin123")
                
                conn.execute(text("""
                    INSERT INTO users (
                        username, email, password_hash, 
                        first_name, family_name, full_name, 
                        phone, role, is_active
                    ) VALUES (
                        :username, :email, :password_hash,
                        :first_name, :family_name, :full_name,
                        :phone, CAST(:role AS user_role), :is_active
                    )
                """), {
                    "username": "admin",
                    "email": "admin@brightwaves.com",
                    "password_hash": password_hash,
                    "first_name": "Admin",
                    "family_name": "User",
                    "full_name": "Admin User",
                    "phone": None,
                    "role": "admin",
                    "is_active": 1
                })
                conn.commit()
                print("✅ Created default admin user")
                print("   Username: admin")
                print("   Password: admin123")
                print("   ⚠️  PLEASE CHANGE THE DEFAULT PASSWORD AFTER FIRST LOGIN!")
            else:
                print("ℹ️  Admin user already exists")
        except Exception as e:
            print(f"❌ Error creating admin user: {e}")
        
        print("\n✅ Migration completed successfully!")
        print("\n📝 You can now login with:")
        print("   URL: http://localhost:8000/api/v1/auth/login")
        print("   Username: admin")
        print("   Password: admin123")

if __name__ == "__main__":
    migrate()
