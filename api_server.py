import uvicorn
import logging
import sys

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # This script is dedicated to running just the FastAPI server for PDF extraction
    logger.info("Starting FastAPI server on port 8000...")
    try:
        uvicorn.run("api.pdf_extractor:app", host="0.0.0.0", port=8000)
    except Exception as e:
        logger.error(f"Error starting FastAPI server: {e}")
        sys.exit(1)