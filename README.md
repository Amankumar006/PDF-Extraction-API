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

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Amankumar006/PDF-Extraction-API.git
cd PDF-Extraction-API
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

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

## API Endpoints

- `POST /extract` - Upload and extract content from a PDF file
- `POST /extract-url` - Extract content from a PDF URL
- `POST /extract-optimized` - Extract content with performance optimization
- `POST /clear-cache` - Clear the extraction cache

## Error Handling

The API implements proper error handling for:
- Invalid file formats
- File size limits
- Processing errors
- Network issues
- OCR failures

## Contributing

1. Fork the repository
2. Create your feature branch
3. Submit a pull request

## License

MIT License
