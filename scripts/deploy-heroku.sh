#!/bin/bash

# Exit on error
set -e

echo "🚀 Starting Heroku deployment..."

# Check if Heroku CLI is installed
if ! command -v heroku &> /dev/null; then
    echo "❌ Heroku CLI is not installed. Please install it first:"
    echo "https://devcenter.heroku.com/articles/heroku-cli"
    exit 1
fi

# Login to Heroku
echo "🔑 Logging in to Heroku..."
heroku login

# Create Heroku apps (one for web, one for API)
echo "📦 Creating Heroku apps..."
heroku create pdf-extractor-web
heroku create pdf-extractor-api

# Set up buildpacks
echo "⚙️ Setting up buildpacks..."
heroku buildpacks:set heroku/python -a pdf-extractor-web
heroku buildpacks:set heroku/python -a pdf-extractor-api

# Add required buildpacks for Tesseract and Poppler
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt -a pdf-extractor-web
heroku buildpacks:add --index 1 https://github.com/heroku/heroku-buildpack-apt -a pdf-extractor-api

# Create Aptfile for system dependencies
echo "📝 Creating Aptfile..."
cat > Aptfile << EOF
tesseract-ocr
poppler-utils
EOF

# Set environment variables
echo "🔧 Setting environment variables..."
heroku config:set -a pdf-extractor-web \
    FLASK_APP=app.py \
    FLASK_ENV=production \
    FLASK_DEBUG=0 \
    API_URL=https://pdf-extractor-api.herokuapp.com

heroku config:set -a pdf-extractor-api \
    FLASK_ENV=production \
    FLASK_DEBUG=0

# Deploy to Heroku
echo "🚀 Deploying to Heroku..."
git push heroku main

echo "✅ Deployment complete!"
echo "🌐 Web Interface: https://pdf-extractor-web.herokuapp.com"
echo "📡 API Endpoint: https://pdf-extractor-api.herokuapp.com"
echo "📝 API Documentation: https://pdf-extractor-api.herokuapp.com/docs" 