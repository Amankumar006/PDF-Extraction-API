#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting deployment process..."

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python3 is not installed. Please install Python3 first."
    echo "On macOS: brew install python3"
    echo "On Ubuntu/Debian: sudo apt-get install python3"
    echo "On Windows: Download from https://www.python.org/downloads/"
    exit 1
fi

# Check if we're on the main branch
if [ "$(git branch --show-current)" != "main" ]; then
    echo "❌ Error: You must be on the main branch to deploy"
    exit 1
fi

# Pull latest changes
echo "📥 Pulling latest changes..."
git pull origin main

# Create and activate virtual environment
echo "🔧 Setting up virtual environment..."
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Check if pip installation was successful
if [ $? -ne 0 ]; then
    echo "❌ Error: Failed to install dependencies"
    exit 1
fi

# Start the servers
echo "🚀 Starting servers..."
# Start API server in background
python3 api_server.py &
API_PID=$!

# Check if API server started successfully
sleep 2
if ! kill -0 $API_PID 2>/dev/null; then
    echo "❌ Error: Failed to start API server"
    exit 1
fi

# Start web server in background
python3 main.py &
WEB_PID=$!

# Check if web server started successfully
sleep 2
if ! kill -0 $WEB_PID 2>/dev/null; then
    echo "❌ Error: Failed to start web server"
    kill $API_PID
    exit 1
fi

echo "✅ Deployment complete!"
echo "📡 API Server running on http://localhost:8000"
echo "🌐 Web Interface running on http://localhost:5001"
echo "📝 API Documentation available at http://localhost:8000/docs"

# Function to handle cleanup
cleanup() {
    echo "🛑 Stopping servers..."
    kill $API_PID
    kill $WEB_PID
    deactivate
    exit 0
}

# Trap SIGINT and SIGTERM signals and call cleanup
trap cleanup SIGINT SIGTERM

# Keep the script running
while true; do
    sleep 1
done 