# Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### Using Docker (Easiest)

```bash
# 1. Navigate to project
cd /Users/hcruz/myfiles/coding/brightwaves/accounting

# 2. Run setup script
./setup.sh

# 3. Access the app
open http://localhost:5173
```

That's it! The script will:
- ✅ Create environment files
- ✅ Start PostgreSQL database
- ✅ Start backend API server
- ✅ Start frontend development server

### URLs
- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Database**: localhost:5432 (user: accounting, password: accounting123)

## 📝 Common Tasks

### Upload an Invoice
1. Go to "Upload Invoice" in the sidebar
2. Drag & drop a Portuguese invoice image (with QR code)
3. System automatically extracts data
4. Click "Save to Database" to create invoice record

### Import SAFT File
1. Go to "SAFT Import" in the sidebar
2. Upload your SAF-T PT XML file
3. System automatically imports customers and invoices
4. View import results and statistics

### View Data
- **Dashboard**: See overview and statistics
- **Invoices**: View all invoices (from uploads and SAFT)
- **Companies**: View all customers and suppliers

## 🔧 Development Commands

### Docker
```bash
# View logs
docker-compose logs -f

# Stop everything
docker-compose down

# Restart services
docker-compose restart

# Rebuild containers
docker-compose up -d --build
```

### Backend Only (without Docker)
```bash
cd backend
source venv/bin/activate
python main.py
```

### Frontend Only (without Docker)
```bash
cd frontend
npm run dev
```

## 📦 Switching to S3 Storage

1. Edit `backend/.env`:
```env
STORAGE_BACKEND=s3
S3_BUCKET_NAME=your-bucket-name
S3_REGION=eu-west-1
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
```

2. Restart backend:
```bash
docker-compose restart backend
```

No code changes needed! The storage abstraction handles everything.

## 🐛 Troubleshooting

### Frontend errors about missing modules
```bash
cd frontend
npm install
docker-compose restart frontend
```

### Backend errors about missing packages
```bash
cd backend
source venv/bin/activate  # if not using Docker
pip install -r requirements.txt
docker-compose restart backend  # if using Docker
```

### Database connection errors
```bash
# Check if PostgreSQL is running
docker-compose ps

# View PostgreSQL logs
docker-compose logs postgres

# Restart database
docker-compose restart postgres
```

### Port already in use
```bash
# Find process using port 8000
lsof -i :8000

# Kill process (replace PID)
kill -9 PID

# Or change port in docker-compose.yml
```

## 📚 Testing the Application

### Test SAFT Import
1. Get a SAF-T PT XML file (sample or real)
2. Go to SAFT Import page
3. Upload the file
4. Check the import results
5. View imported invoices in "Invoices" page

### Test Invoice Upload with QR
1. Get a Portuguese invoice image with QR code
2. Go to Upload Invoice page
3. Drop the image
4. See extracted data (NIF, amounts, date, ATCUD)
5. Save to database
6. Check "Invoices" page

## 🎯 Project Structure Quick Reference

```
backend/
├── app/api/          → API endpoints (companies, invoices, upload, saft)
├── app/services/     → Business logic (QR parser, SAFT parser)
├── app/storage/      → Storage abstraction (local/S3)
├── app/models/       → Database models
└── main.py           → Entry point

frontend/
├── src/pages/        → Pages (Dashboard, Upload, SAFT, etc.)
├── src/components/   → Reusable UI components
├── src/services/     → API client
└── src/types/        → TypeScript types
```

## 💡 Tips

- **QR Code Detection**: Works best with clear, high-resolution images
- **SAFT Files**: Tested with SAF-T PT version 1.04_01
- **File Limits**: Default max upload size is 10MB (configurable in `.env`)
- **Storage**: Starts with local storage, easy to switch to S3 later
- **API Docs**: FastAPI auto-generates interactive docs at `/docs`

## 🔐 Default Credentials

### Database
- Host: localhost:5432
- Database: accounting_db
- User: accounting
- Password: accounting123

### Notes
- Change these in production!
- Set strong SECRET_KEY in backend/.env for production

## 📞 Need Help?

1. Check the logs: `docker-compose logs -f`
2. View API docs: http://localhost:8000/docs
3. Read PROJECT_OVERVIEW.md for detailed documentation
4. Check the README.md for setup instructions
