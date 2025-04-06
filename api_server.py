import uvicorn
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("Starting FastAPI server...")
    uvicorn.run("api.pdf_extractor:app", host="0.0.0.0", port=8000)