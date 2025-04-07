#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Railway deployment..."

# Check if Railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "❌ Railway CLI is not installed. Please install it first:"
    echo "npm i -g @railway/cli"
    exit 1
fi

# Login to Railway
echo "🔑 Logging in to Railway..."
railway login

# Initialize Railway project
echo "📦 Creating Railway project..."
railway init

# Set up environment variables
echo "🔧 Setting environment variables..."
railway variables set \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    FLASK_DEBUG=0

# Deploy to Railway
echo "🚀 Deploying to Railway..."
railway up

echo "✅ Deployment complete!"
echo "🌐 Your application will be available at the URL provided by Railway" 