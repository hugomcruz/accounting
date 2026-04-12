# BrightWaves Accounting System - Project Overview

## 🎯 Project Summary

A modern, single-tenant accounting software built specifically for Portuguese companies with features to:
- Import SAFT-PT (Portuguese Standard Audit File for Tax) XML files
- Upload and process expense invoices with automatic QR code extraction (Portuguese AT format)
- Manage companies (customers/suppliers)
- Track invoices and financial data

## 🏗️ Architecture

### Technology Stack

**Backend:**
- **Python 3.11+** with **FastAPI** framework
- **PostgreSQL** database with **SQLAlchemy** ORM
- **Pydantic** for data validation
- **pyzbar** + **opencv-python** for QR code extraction
- **lxml** for SAFT XML parsing
- Modular storage abstraction (Local filesystem / AWS S3)

**Frontend:**
- **React 18** with **TypeScript**
- **Vite** for fast builds
- **TanStack Query (React Query)** for server state management
- **React Router** for navigation
- **Tailwind CSS** for styling
- **Lucide React** for icons

**Infrastructure:**
- **Docker** and **Docker Compose** for containerization
- **PostgreSQL 15** for database

### Project Structure

```
accounting/
├── backend/                    # Python FastAPI backend
│   ├── app/
│   │   ├── api/               # API route handlers
│   │   │   ├── companies.py   # Company CRUD endpoints
│   │   │   ├── invoices.py    # Invoice CRUD endpoints
│   │   │   ├── upload.py      # File upload & QR processing
│   │   │   └── saft.py        # SAFT import endpoints
│   │   ├── core/              # Core configuration
│   │   │   ├── config.py      # Settings management
│   │   │   └── database.py    # Database connection
│   │   ├── models/            # Database models
│   │   │   └── models.py      # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   │   └── schemas.py     # Request/response models
│   │   ├── services/          # Business logic
│   │   │   ├── qr_parser.py   # Portuguese QR code parser
│   │   │   └── saft_parser.py # SAFT XML parser
│   │   └── storage/           # Storage abstraction
│   │       └── storage.py     # Local/S3 storage backends
│   ├── main.py                # FastAPI application entry point
│   ├── requirements.txt       # Python dependencies
│   ├── Dockerfile            # Docker configuration
│   └── .env.example          # Environment variables template
│
├── frontend/                  # React TypeScript frontend
│   ├── src/
│   │   ├── components/        # Reusable components
│   │   │   ├── ui/           # UI components (Button, Card)
│   │   │   └── Layout.tsx    # Main layout with navigation
│   │   ├── pages/            # Page components
│   │   │   ├── Dashboard.tsx      # Dashboard overview
│   │   │   ├── UploadInvoice.tsx  # Invoice upload with QR
│   │   │   ├── InvoiceList.tsx    # Invoice listing
│   │   │   ├── SAFTImport.tsx     # SAFT import interface
│   │   │   └── CompanyList.tsx    # Company management
│   │   ├── services/         # API client
│   │   │   ├── api.ts        # Axios configuration
│   │   │   └── queries.ts    # API endpoints
│   │   ├── types/            # TypeScript types
│   │   │   └── index.ts      # Type definitions
│   │   ├── lib/              # Utilities
│   │   │   └── utils.ts      # Helper functions
│   │   ├── App.tsx           # Main app component
│   │   ├── main.tsx          # React entry point
│   │   └── index.css         # Global styles
│   ├── package.json          # Node dependencies
│   ├── vite.config.ts        # Vite configuration
│   ├── tailwind.config.js    # Tailwind CSS config
│   └── Dockerfile            # Docker configuration
│
├── docker-compose.yml        # Multi-container setup
├── setup.sh                  # Docker setup script
├── setup-local.sh            # Local development setup
├── README.md                 # Project documentation
└── .gitignore               # Git ignore rules
```

## 🔑 Key Features

### 1. SAFT-PT Import
- Parse SAF-T PT (Portuguese Standard Audit File for Tax) XML files
- Automatic extraction of:
  - Company information
  - Customer data
  - Sales invoices with line items
- Import tracking and status monitoring
- Error handling and reporting

### 2. Invoice Upload with QR Code Processing
- Drag-and-drop file upload (PDF, PNG, JPG)
- Automatic QR code detection and parsing
- Extract Portuguese AT (Autoridade Tributária) invoice data:
  - Supplier NIF (Tax ID)
  - Buyer NIF
  - Invoice number and date
  - Total amounts and tax
  - ATCUD code
- Automatic company and invoice creation from QR data

### 3. Storage Abstraction Layer
**Modular design supporting multiple backends:**

**Local Storage (Default):**
- Files stored in `backend/uploads/` directory
- Organized by folder (invoices, saft)
- Unique filename generation with timestamps

**S3 Storage (Ready to use):**
- AWS S3 integration via boto3
- Presigned URLs for secure access
- Simple configuration via environment variables
- Switch storage backend by changing `STORAGE_BACKEND` in `.env`

**Implementation:**
```python
# Storage backend interface
class StorageBackend(ABC):
    async def save(file, filename, folder) -> str
    async def delete(file_path) -> bool
    async def get_url(file_path) -> str
    def exists(file_path) -> bool

# Easy to add new backends (Azure Blob, Google Cloud Storage, etc.)
```

### 4. Company Management
- Customer and supplier tracking
- NIF-based identification
- Automatic creation during invoice processing
- Full CRUD operations

### 5. Invoice Management
- Support for sales and purchase invoices
- Status tracking (draft, issued, paid, cancelled)
- Line items with tax calculations
- File attachment support
- SAFT import tracking

## 🚀 Getting Started

### Option 1: Docker Setup (Recommended)

```bash
# Clone and navigate to project
cd accounting

# Run setup script
./setup.sh

# Access the application
# Frontend: http://localhost:5173
# Backend API: http://localhost:8000
# API Docs: http://localhost:8000/docs
```

### Option 2: Local Development Setup

**Prerequisites:**
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+

```bash
# Run local setup script
./setup-local.sh

# Create PostgreSQL database
createdb accounting_db

# Update backend/.env with database credentials

# Start backend
cd backend
source venv/bin/activate
python main.py

# Start frontend (in new terminal)
cd frontend
npm run dev
```

## 📊 Database Schema

### Main Tables

**companies**
- Company/supplier/customer information
- NIF (Portuguese Tax ID)
- Contact details
- Type flags (is_customer, is_supplier)

**invoices**
- Invoice header information
- Type (sale/purchase)
- Status (draft/issued/paid/cancelled)
- Amounts and tax
- File reference
- QR code data
- SAFT import tracking

**invoice_line_items**
- Line-level invoice details
- Description, quantity, unit price
- Tax calculations

**saft_imports**
- SAFT import tracking
- Company metadata
- Import statistics
- Error logging

## 🔐 Configuration

### Backend Environment Variables

```env
# Database
DATABASE_URL=postgresql://user:password@host:port/dbname

# Storage Backend
STORAGE_BACKEND=local  # or 's3'
LOCAL_STORAGE_PATH=./uploads

# S3 Configuration (if using S3)
S3_BUCKET_NAME=your-bucket
S3_REGION=eu-west-1
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key

# Security
SECRET_KEY=your-secret-key
```

### Frontend Environment Variables

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

## 🎨 UI Features

- **Dashboard**: Overview with statistics and recent activity
- **Invoice Upload**: Drag-and-drop with automatic QR processing
- **Invoice List**: Tabular view with filtering
- **SAFT Import**: Upload and track SAFT file imports
- **Company List**: Manage customers and suppliers
- **Responsive Design**: Works on desktop and mobile
- **Modern UI**: Clean, professional interface with Tailwind CSS

## 🔧 API Endpoints

### Companies
- `GET /api/v1/companies` - List companies
- `GET /api/v1/companies/{id}` - Get company by ID
- `GET /api/v1/companies/nif/{nif}` - Get company by NIF
- `POST /api/v1/companies` - Create company
- `PATCH /api/v1/companies/{id}` - Update company
- `DELETE /api/v1/companies/{id}` - Delete company

### Invoices
- `GET /api/v1/invoices` - List invoices
- `GET /api/v1/invoices/{id}` - Get invoice by ID
- `POST /api/v1/invoices` - Create invoice
- `PATCH /api/v1/invoices/{id}` - Update invoice
- `DELETE /api/v1/invoices/{id}` - Delete invoice

### Upload
- `POST /api/v1/upload/invoice` - Upload invoice file
- `POST /api/v1/upload/invoice/process` - Process uploaded invoice

### SAFT
- `POST /api/v1/saft/import` - Import SAFT XML file
- `GET /api/v1/saft/imports` - List SAFT imports
- `GET /api/v1/saft/imports/{id}` - Get SAFT import details

## 🧪 Portuguese QR Code Format

The system parses Portuguese AT (Autoridade Tributária) invoice QR codes with the following fields:

- **A**: NIF Emitente (Issuer Tax ID)
- **B**: NIF Adquirente (Buyer Tax ID)
- **C**: País Adquirente (Buyer Country)
- **D**: Tipo Documento (Document Type)
- **E**: Estado (Status)
- **F**: Data (Date YYYYMMDD)
- **G**: Identificação Documento (Document ID)
- **H**: ATCUD (Unique Document Code)
- **I**: Espaço Fiscal (Tax Region)
- **J**: Base Incidência IVA (Tax Base)
- **K**: Total IVA (VAT Total)
- **L**: Total Impostos (Total Taxes)
- **M**: Total Documento (Document Total)
- **N**: Hash
- **O**: Nº Certificado (Certificate Number)

## 📈 Future Enhancements

- User authentication and authorization
- Multi-tenant support
- Invoice PDF generation
- Advanced reporting and analytics
- Export functionality
- Email notifications
- OCR for non-QR invoices (Tesseract)
- Expense categorization
- Budget tracking
- Chart of accounts
- Double-entry bookkeeping
- Bank reconciliation

## 🛠️ Development

### Adding a New Storage Backend

1. Create a new class implementing `StorageBackend` interface
2. Add configuration in `config.py`
3. Update factory function in `storage.py`
4. Update documentation

### Running Tests

```bash
# Backend tests (to be implemented)
cd backend
pytest

# Frontend tests (to be implemented)
cd frontend
npm test
```

## 📝 License

Proprietary - BrightWaves

## 👥 Support

For questions or support, please contact the development team.

---

**Built with ❤️ for Portuguese accounting compliance**
