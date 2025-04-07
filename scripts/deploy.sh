#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting deployment process..."

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
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Start the servers
echo "🚀 Starting servers..."
# Start API server in background
python3 api_server.py &
API_PID=$!

# Start web server in background
python3 main.py &
WEB_PID=$!

echo "✅ Deployment complete!"
echo "📡 API Server running on http://localhost:8000"
echo "🌐 Web Interface running on http://localhost:5001"
echo "📝 API Documentation available at http://localhost:8000/docs"

# Function to handle cleanup
cleanup() {
    echo "🛑 Stopping servers..."
    kill $API_PID
    kill $WEB_PID
    exit 0
}

# Trap SIGINT and SIGTERM signals and call cleanup
trap cleanup SIGINT SIGTERM

# Keep the script running
while true; do
    sleep 1
done 