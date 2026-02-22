#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧠 TherapyCompanion.AI - Startup Script${NC}"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file not found. Creating from template...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}📝 Please edit .env and add your API keys:${NC}"
    echo "   - ANTHROPIC_API_KEY or OPENAI_API_KEY"
    echo "   - SECRET_KEY (generated below)"
    echo "   - ENCRYPTION_KEY (generated below)"
    echo ""
    echo -e "${GREEN}Generated secure keys:${NC}"
    python3 -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(32)); print('ENCRYPTION_KEY=' + secrets.token_urlsafe(32))"
    echo ""
    echo -e "${YELLOW}Add these to your .env file, then run this script again.${NC}"
    exit 1
fi

# Check for virtual environment
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}✓ Activating virtual environment${NC}"
source venv/bin/activate

# Install backend dependencies
echo -e "${GREEN}✓ Installing backend dependencies${NC}"
pip install -q -r requirements.txt

# Start backend
echo ""
echo -e "${BLUE}🚀 Starting Backend Server${NC}"
echo -e "${GREEN}API will be available at: http://localhost:8000${NC}"
echo -e "${GREEN}API Docs at: http://localhost:8000/docs${NC}"
echo ""

python -m app.main
