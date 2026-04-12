from sqlalchemy import Column, Integer, String, DateTime, Enum
from datetime import datetime
import enum
from app.core.database import Base


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    ACCOUNTING = "accounting"
    FINANCE = "finance"  # kept for backward compatibility


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Personal information
    first_name = Column(String(100), nullable=False)
    family_name = Column(String(100), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20))
    
    # Role and status
    role = Column(Enum(UserRole), default=UserRole.ACCOUNTING, nullable=False)
    is_active = Column(Integer, default=1)  # Boolean
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login_at = Column(DateTime)
