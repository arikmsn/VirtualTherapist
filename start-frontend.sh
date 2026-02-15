#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}🎨 TherapyCompanion.AI - Frontend Startup${NC}"
echo ""

cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo -e "${YELLOW}Installing frontend dependencies...${NC}"
    npm install
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating frontend .env...${NC}"
    cp .env.example .env
fi

# Start frontend
echo ""
echo -e "${BLUE}🚀 Starting Frontend Server${NC}"
echo -e "${GREEN}Web interface will be available at: http://localhost:3000${NC}"
echo ""

npm run dev
