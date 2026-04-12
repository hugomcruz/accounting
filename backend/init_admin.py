#!/usr/bin/env python3
import sys
sys.path.insert(0, '/app')

from app.core.database import engine, Base
from app.models.user import User
from sqlalchemy.orm import Session

Base.metadata.create_all(bind=engine)

# Pre-computed bcrypt hash for 'admin1234'
ADMIN_PASSWORD_HASH = '$2b$12$6WD22DmmX0wv3kDDKeFuNOcEarDXXFnNZAlbh6PaI/1MrSeJKp1Me'

with Session(engine) as db:
    existing = db.query(User).filter(User.username == 'admin').first()
    if existing:
        existing.password_hash = ADMIN_PASSWORD_HASH
        existing.is_active = 1
        db.commit()
        print('Updated existing admin user')
    else:
        user = User(
            username='admin',
            email='admin@brightwaves.com',
            password_hash=ADMIN_PASSWORD_HASH,
            first_name='Admin',
            family_name='User',
            full_name='Admin User',
            role='admin',
            is_active=1,
        )
        db.add(user)
        db.commit()
        print('Created admin user')

print('Done - login with admin / admin1234')
