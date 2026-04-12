# BrightWaves Accounting System

Portuguese accounting software with SAFT-PT import and invoice OCR capabilities.

## Project Structure

```
accounting/
├── backend/              # FastAPI backend
│   ├── app/
│   │   ├── api/         # API routes
│   │   ├── core/        # Core configuration
│   │   ├── models/      # Database models
│   │   ├── schemas/     # Pydantic schemas
│   │   ├── services/    # Business logic
│   │   └── storage/     # Storage abstraction (local/S3)
│   ├── requirements.txt
│   └── main.py
├── frontend/            # React + TypeScript frontend
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types/
│   └── package.json
└── docker-compose.yml
```

## Features

- 📥 SAFT-PT XML import for Portuguese tax compliance
- 📄 Invoice upload with QR code extraction (AT format)
- 🏢 Company and supplier management
- 💰 Expense tracking and categorization
- 📊 Accounting reports

## Tech Stack

### Backend
- **Python 3.11+** with FastAPI
- **PostgreSQL** database
- **SQLAlchemy** ORM
- **Pydantic** for validation
- QR code processing with `pyzbar` and `opencv-python`
- SAFT-PT XML parsing

### Frontend
- **React 18** with TypeScript
- **Vite** for build tooling
- **React Router** for navigation
- **TanStack Query** for data fetching
- **Shadcn/ui** components

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Docker & Docker Compose (optional)

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python main.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

### Docker Setup

```bash
docker-compose up -d
```

## Storage

The application uses an abstraction layer for file storage:
- **Local storage** (default) - files stored in `backend/uploads/`
- **S3 storage** (planned) - configure via environment variables

To switch storage backends, update `STORAGE_BACKEND` in `.env`.

## License

Proprietary - BrightWaves
