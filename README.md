# PDF-Extraction-API

A Python-based API service for extracting text, images, and metadata from PDF files.

## Features

- Extract text content from PDF files
- Extract images from PDF files
- Extract metadata from PDF files
- OCR capabilities for scanned PDFs
- Performance optimization options
- Caching capabilities
- RESTful API endpoints for PDF processing
- Web interface for easy file uploads
- Error handling and validation

## Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Tesseract OCR (for OCR functionality)
- Poppler (for PDF to image conversion)

### System Dependencies

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
sudo apt-get install poppler-utils
```

#### macOS
```bash
brew install tesseract
brew install poppler
```

#### Windows
- Download and install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki
- Download and install Poppler from: https://github.com/oschwartz10612/poppler-windows/releases

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Amankumar006/PDF-Extraction-API.git
cd PDF-Extraction-API
```

2. Create and activate a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create a `.env` file in the root directory with the following variables:

```env
# Server Configuration
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SESSION_SECRET=your_secret_key_here

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
WEB_PORT=5001

# OCR Configuration
TESSERACT_CMD=/usr/bin/tesseract  # Path to tesseract executable
TESSERACT_LANG=eng  # Default language for OCR

# Cache Configuration
CACHE_ENABLED=true
CACHE_DIR=./cache
CACHE_TTL=3600  # Cache time-to-live in seconds

# Performance Configuration
MAX_WORKERS=4
CHUNK_SIZE=1024
```

### Configuration Options

The application can be configured through environment variables or directly in the code:

1. **Server Configuration**
   - `FLASK_APP`: Main application file
   - `FLASK_ENV`: Environment (development/production)
   - `FLASK_DEBUG`: Debug mode (0/1)

2. **API Configuration**
   - `API_HOST`: Host address for the API server
   - `API_PORT`: Port for the API server
   - `WEB_PORT`: Port for the web interface

3. **OCR Configuration**
   - `TESSERACT_CMD`: Path to Tesseract executable
   - `TESSERACT_LANG`: Default language for OCR

4. **Cache Configuration**
   - `CACHE_ENABLED`: Enable/disable caching
   - `CACHE_DIR`: Directory for cache files
   - `CACHE_TTL`: Cache expiration time

5. **Performance Configuration**
   - `MAX_WORKERS`: Maximum number of worker processes
   - `CHUNK_SIZE`: Size of chunks for processing large files

## Usage

### Starting the Servers

1. Start the API server:
```bash
python3 api_server.py
```

2. Start the web server:
```bash
python3 main.py
```

3. Access the application:
- Web Interface: http://localhost:5001
- API Documentation: http://localhost:8000/docs

### API Usage Examples

#### 1. Extract Text from PDF File

```bash
curl -X POST "http://localhost:8000/extract" \
  -H "accept: application/json" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "extraction_type=text" \
  -F "include_images=false" \
  -F "include_metadata=true"
```

#### 2. Extract Content from PDF URL

```bash
curl -X POST "http://localhost:8000/extract-url" \
  -H "Content-Type: application/json" \
  -d '{
    "pdf_url": "https://example.com/document.pdf",
    "extraction_type": "text",
    "include_images": true,
    "include_metadata": true
  }'
```

#### 3. Optimized Extraction

```bash
curl -X POST "http://localhost:8000/extract-optimized" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@document.pdf" \
  -F "fast_mode=true" \
  -F "use_cache=true" \
  -F "optimize_performance=true"
```

#### 4. Clear Cache

```bash
curl -X POST "http://localhost:8000/clear-cache"
```

### Web Interface Usage

1. Open http://localhost:5001 in your browser
2. Click "Choose File" to select a PDF
3. Configure extraction options:
   - Extraction Type (text/images/metadata)
   - Include Images (yes/no)
   - Include Metadata (yes/no)
   - Fast Mode (yes/no)
   - Use Cache (yes/no)
4. Click "Upload" to process the PDF
5. View and download the extracted content

## Troubleshooting Guide

### Common Issues and Solutions

1. **OCR Not Working**
   - Ensure Tesseract OCR is installed correctly
   - Verify TESSERACT_CMD path in .env file
   - Check if the language pack is installed
   - Solution: Install required language pack:
     ```bash
     sudo apt-get install tesseract-ocr-[lang]  # Ubuntu/Debian
     brew install tesseract-lang  # macOS
     ```

2. **PDF to Image Conversion Failing**
   - Verify Poppler installation
   - Check file permissions
   - Solution: Reinstall Poppler and verify path

3. **Memory Issues with Large PDFs**
   - Enable fast mode
   - Use chunk processing
   - Solution: Adjust MAX_WORKERS and CHUNK_SIZE in .env

4. **API Connection Errors**
   - Check if both servers are running
   - Verify port configurations
   - Solution: Ensure API_PORT and WEB_PORT are not in use

5. **Cache Issues**
   - Clear the cache using the API endpoint
   - Check CACHE_DIR permissions
   - Solution: Run clear-cache endpoint and verify directory permissions

### Logging

The application logs to the console and can be configured for file logging. Check the logs for detailed error messages and debugging information.

## Contributing

1. Fork the repository
2. Create your feature branch
3. Submit a pull request

## License

MIT License
