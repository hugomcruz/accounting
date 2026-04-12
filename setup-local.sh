#!/bin/bash

# BrightWaves Accounting - Local Development Setup (without Docker)

echo "🌊 BrightWaves Accounting - Local Development Setup"
echo "==================================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed.${NC}"
    exit 1
fi

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Python 3 and Node.js are installed${NC}"
echo ""

# Backend setup
echo "🐍 Setting up backend..."
cd backend

# Create virtual environment
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓ Created Python virtual environment${NC}"
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Create .env file
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created backend/.env${NC}"
    echo -e "${YELLOW}⚠ Please update DATABASE_URL in backend/.env to point to your PostgreSQL database${NC}"
else
    echo -e "${YELLOW}⚠ backend/.env already exists${NC}"
fi

cd ..

# Frontend setup
echo ""
echo "⚛️  Setting up frontend..."
cd frontend

# Install dependencies
echo "📦 Installing Node.js dependencies..."
npm install

# Create .env file
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo -e "${GREEN}✓ Created frontend/.env${NC}"
fi

cd ..

echo ""
echo -e "${GREEN}✅ Setup complete!${NC}"
echo ""
echo "📝 Next steps:"
echo ""
echo "1. Make sure PostgreSQL is running and create the database:"
echo "   createdb accounting_db"
echo ""
echo "2. Update backend/.env with your database credentials"
echo ""
echo "3. Start the backend:"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   python main.py"
echo ""
echo "4. In a new terminal, start the frontend:"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "5. Access the application at http://localhost:5173"
echo ""
