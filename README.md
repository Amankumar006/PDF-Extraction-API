# PDF-Extraction-API
# PDF-Extraction-API

A Node.js based API service for extracting text and metadata from PDF files.

## Features

- Extract text content from PDF files
- Parse and structure extracted content
- RESTful API endpoints for PDF processing
- Support for multiple file uploads
- Error handling and validation

## Prerequisites

- Node.js (v14 or higher)
- MongoDB
- NPM or Yarn

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/pdf-extraction-api.git
cd pdf-extraction-api
```

2. Install dependencies:
```bash
npm install
```

3. Set up environment variables:
Create a `.env` file with:
```
PORT=3000
MONGODB_URI=your_mongodb_connection_string
```

## Usage

1. Start the server:
```bash
npm start
```

2. API Endpoints:

- `POST /api/upload` - Upload PDF file(s)
- `GET /api/extract/:id` - Get extracted content
- `GET /api/status/:id` - Check extraction status

## Error Handling

The API implements proper error handling for:
- Invalid file formats
- File size limits
- Processing errors
- Database connection issues

## Contributing

1. Fork the repository
2. Create your feature branch
3. Submit a pull request

## License

MIT License
