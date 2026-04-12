from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import Depends
from contextlib import asynccontextmanager
from app.core.config import settings
from app.core.database import Base, engine
from app.core.auth import require_staff, require_admin_or_finance
from app.api import companies, invoices, upload, saft, payments, bank, hr, settings as settings_router, invoice_queue, auth, exports, expenses, processes
from app.services.background_enrichment import background_enrichment_task
import os
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import engine
from app.models.user import User

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Create database tables
Base.metadata.create_all(bind=engine)


def run_migrations():
    """Apply lightweight column-level migrations that create_all doesn't handle."""
    with engine.connect() as conn:
        # linked_transaction_id on bank_transactions
        r = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='bank_transactions' AND column_name='linked_transaction_id'"
        ))
        if not r.fetchone():
            conn.execute(text(
                "ALTER TABLE bank_transactions "
                "ADD COLUMN linked_transaction_id INTEGER REFERENCES bank_transactions(id)"
            ))
            conn.commit()
            print("✅ Migration: added linked_transaction_id to bank_transactions")

        # bank_account_id on bank_statements
        r2 = conn.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='bank_statements' AND column_name='bank_account_id'"
        ))
        if not r2.fetchone():
            conn.execute(text(
                "ALTER TABLE bank_statements "
                "ADD COLUMN bank_account_id INTEGER REFERENCES bank_accounts(id)"
            ))
            conn.commit()
            print("✅ Migration: added bank_account_id to bank_statements")


def seed_admin():
    """Ensure the default admin user exists with password admin1234."""
    # bcrypt hash for 'admin1234'
    ADMIN_PASSWORD_HASH = '$2b$12$6WD22DmmX0wv3kDDKeFuNOcEarDXXFnNZAlbh6PaI/1MrSeJKp1Me'
    with Session(engine) as db:
        existing = db.query(User).filter(User.username == 'admin').first()
        if existing:
            existing.password_hash = ADMIN_PASSWORD_HASH
            existing.is_active = 1
            db.commit()
            print('✅ Admin user updated (admin / admin1234)')
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
            print('✅ Admin user created (admin / admin1234)')


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup: run migrations, seed default admin, start background enrichment task
    print("\n🚀 Starting application...")
    run_migrations()
    seed_admin()
    background_enrichment_task.start()
    
    yield
    
    # Shutdown: Stop background enrichment task
    print("\n🛑 Shutting down application...")
    await background_enrichment_task.stop()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# auth router: no role restrictions (login, /me, password change, user CRUD)
app.include_router(auth.router, prefix="/api/v1")

# Staff-only routers (blocks 'user' role; admin/accounting/finance allowed)
_staff = [Depends(require_staff)]
app.include_router(companies.router, prefix="/api/v1", dependencies=_staff)
app.include_router(invoices.router, prefix="/api/v1", dependencies=_staff)
app.include_router(payments.router, prefix="/api/v1", dependencies=_staff)
app.include_router(bank.router, prefix="/api/v1", dependencies=_staff)
app.include_router(hr.router, prefix="/api/v1", dependencies=_staff)
app.include_router(settings_router.router, prefix="/api/v1", dependencies=_staff)
app.include_router(exports.router, prefix="/api/v1", dependencies=_staff)
app.include_router(processes.router, prefix="/api/v1", dependencies=_staff)

# Import/upload routers: admin and finance only (blocks 'user' AND 'accounting')
_admin_finance = [Depends(require_admin_or_finance)]
app.include_router(upload.router, prefix="/api/v1", dependencies=_admin_finance)
app.include_router(invoice_queue.router, prefix="/api/v1", dependencies=_admin_finance)
app.include_router(saft.router, prefix="/api/v1", dependencies=_admin_finance)

# Expenses: no router-level restriction; role filtering is handled inside each endpoint
app.include_router(expenses.router, prefix="/api/v1")

# Serve uploaded files (for local storage)
if settings.STORAGE_BACKEND == "local":
    os.makedirs(settings.LOCAL_STORAGE_PATH, exist_ok=True)
    app.mount(
        "/api/v1/files",
        StaticFiles(directory=settings.LOCAL_STORAGE_PATH),
        name="files"
    )


@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG
    )
