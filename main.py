from app import app
import subprocess
import sys
import logging
import signal
import time
import threading

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Variable to track the FastAPI process
fastapi_process = None

def start_fastapi_server():
    global fastapi_process
    try:
        # Start the FastAPI server
        fastapi_process = subprocess.Popen([
            sys.executable, "-m", "uvicorn", 
            "api.pdf_extractor:app", "--host", "0.0.0.0", 
            "--port", "8000"
        ])
        logger.info("Started FastAPI server on port 8000")
        return True
    except Exception as e:
        logger.error(f"Error starting FastAPI server: {e}")
        return False

def cleanup_on_exit(signum, frame):
    """Clean up resources before exiting."""
    logger.info("Cleaning up before exit...")
    if fastapi_process:
        logger.info("Terminating FastAPI server...")
        fastapi_process.terminate()
        fastapi_process.wait()
    sys.exit(0)

# Register signal handlers for graceful shutdown
signal.signal(signal.SIGINT, cleanup_on_exit)
signal.signal(signal.SIGTERM, cleanup_on_exit)

if __name__ == "__main__":
    try:
        # Start FastAPI server
        if start_fastapi_server():
            # Give FastAPI a moment to start
            time.sleep(2)
            
            # Start the Flask app
            app.run(host="0.0.0.0", port=5001, debug=True)
    except Exception as e:
        logger.error(f"Error starting servers: {e}")
        if fastapi_process:
            fastapi_process.terminate()
            fastapi_process.wait()
