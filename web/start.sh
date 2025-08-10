#!/bin/bash

# Trading Bot Web UI Startup Script

echo "🚀 Starting Trading Bot Web UI..."
echo "================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check if a port is in use
port_in_use() {
    lsof -i:$1 >/dev/null 2>&1
}

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Check Python
if ! command_exists python3; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Python 3 found${NC}"

# Check Node.js
if ! command_exists node; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi
echo -e "${GREEN}✅ Node.js found${NC}"

# Check PostgreSQL
if ! command_exists psql; then
    echo -e "${YELLOW}⚠️  PostgreSQL client not found (dashboard will work with limited functionality)${NC}"
else
    echo -e "${GREEN}✅ PostgreSQL found${NC}"
fi

# Navigate to web directory
cd "$(dirname "$0")"

# Install backend dependencies
echo -e "\n${YELLOW}Installing backend dependencies...${NC}"
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
echo -e "${GREEN}✅ Backend dependencies installed${NC}"

# Install frontend dependencies
echo -e "\n${YELLOW}Installing frontend dependencies...${NC}"
cd ../frontend
if [ ! -d "node_modules" ]; then
    npm install
    echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
else
    echo -e "${GREEN}✅ Frontend dependencies already installed${NC}"
fi

# Check if ports are available
if port_in_use 8000; then
    echo -e "${YELLOW}⚠️  Port 8000 is in use. Killing existing process...${NC}"
    kill $(lsof -t -i:8000) 2>/dev/null
fi

if port_in_use 5174; then
    echo -e "${YELLOW}⚠️  Port 5174 is in use. Killing existing process...${NC}"
    kill $(lsof -t -i:5174) 2>/dev/null
fi

# Start backend server
echo -e "\n${YELLOW}Starting backend API server...${NC}"
cd ../backend
source venv/bin/activate
python api_server.py &
BACKEND_PID=$!
echo -e "${GREEN}✅ Backend server started (PID: $BACKEND_PID)${NC}"

# Wait for backend to be ready
echo -e "${YELLOW}Waiting for backend to be ready...${NC}"
sleep 3

# Start frontend dev server
echo -e "\n${YELLOW}Starting frontend development server...${NC}"
cd ../frontend
npm run dev &
FRONTEND_PID=$!
echo -e "${GREEN}✅ Frontend server started (PID: $FRONTEND_PID)${NC}"

# Function to cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}✅ Servers stopped${NC}"
    exit 0
}

# Set up trap to cleanup on script exit
trap cleanup EXIT INT TERM

# Display access information
echo -e "\n================================"
echo -e "${GREEN}🎉 Trading Bot Web UI is running!${NC}"
echo -e "================================"
echo -e "\n📊 Dashboard URL: ${GREEN}http://localhost:5174${NC}"
echo -e "📡 API Documentation: ${GREEN}http://localhost:8000/docs${NC}"
echo -e "\n${YELLOW}Press Ctrl+C to stop all servers${NC}\n"

# Keep script running
wait