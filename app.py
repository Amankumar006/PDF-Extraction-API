import os
import logging
import uuid
import tempfile
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from werkzeug.utils import secure_filename
import requests
from api.pdf_extractor import PDFExtractor

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Define the API endpoint
API_URL = "http://localhost:8000"

# Create uploads directory if it doesn't exist
UPLOAD_FOLDER = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size

# Create a FastAPI app instance to handle PDF extraction
pdf_extractor = PDFExtractor()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api-docs')
def api_docs():
    return redirect('http://localhost:8000/docs')

@app.route('/extract', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('index'))
    
    file = request.files['file']
    
    if file.filename == '':
        flash('No file selected', 'danger')
        return redirect(url_for('index'))
    
    if file and file.filename.lower().endswith('.pdf'):
        try:
            # Get form parameters
            extraction_type = request.form.get('extraction_type', 'text')
            include_images = request.form.get('include_images') == 'true'
            include_metadata = request.form.get('include_metadata') == 'true'
            fast_mode = request.form.get('fast_mode') == 'true'
            use_cache = request.form.get('use_cache') == 'true'
            
            logger.debug(f"Extracting content with type={extraction_type}, fast_mode={fast_mode}, use_cache={use_cache}")
            
            # Forward the request to FastAPI endpoint
            files = {'file': (file.filename, file.read(), 'application/pdf')}
            api_response = requests.post(
                f"{API_URL}/extract",
                files=files,
                data={
                    'extraction_type': extraction_type,
                    'include_images': str(include_images).lower(),
                    'include_metadata': str(include_metadata).lower(),
                    'fast_mode': str(fast_mode).lower(),
                    'use_cache': str(use_cache).lower()
                }
            )
            
            # Check if the request was successful
            api_response.raise_for_status()
            
            # Return the response as JSON
            return api_response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error forwarding request to API: {e}")
            return jsonify({
                "status": "error",
                "message": f"API service error: {str(e)}"
            }), 500
        except Exception as e:
            logger.error(f"Error processing PDF: {e}")
            return jsonify({
                "status": "error",
                "message": str(e)
            }), 500
    else:
        flash('Only PDF files are allowed', 'danger')
        return redirect(url_for('index'))

@app.route('/extract-url', methods=['POST'])
def process_remote_pdf():
    data = request.json
    if not data or 'pdf_url' not in data:
        return jsonify({
            "status": "error",
            "message": "PDF URL is required"
        }), 400
    
    try:
        # Forward the request to FastAPI endpoint
        api_response = requests.post(
            f"{API_URL}/extract-url",
            json=data  # Forward the entire JSON payload
        )
        
        # Check if the request was successful
        api_response.raise_for_status()
        
        # Return the response as JSON
        return api_response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request to API: {e}")
        return jsonify({
            "status": "error",
            "message": f"API service error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Error processing remote PDF: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# Add a route to clear the cache
@app.route('/clear-cache', methods=['POST'])
def clear_cache():
    try:
        # Forward the request to FastAPI endpoint
        api_response = requests.post(f"{API_URL}/clear-cache")
        
        # Check if the request was successful
        api_response.raise_for_status()
        
        # Return the response as JSON
        return api_response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request to API: {e}")
        return jsonify({
            "status": "error",
            "message": f"API service error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/extract-optimized', methods=['POST'])
def extract_optimized():
    """Extract content with progress tracking and performance optimization."""
    if 'file' not in request.files and not request.json:
        return jsonify({
            "status": "error",
            "message": "Either a file upload or a JSON payload with pdf_url is required"
        }), 400
    
    try:
        if 'file' in request.files:
            # Handle file upload
            file = request.files['file']
            
            if file.filename == '':
                return jsonify({
                    "status": "error",
                    "message": "No file selected"
                }), 400
            
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({
                    "status": "error",
                    "message": "Only PDF files are supported"
                }), 400
            
            # Set up the multipart form data
            files = {'file': (file.filename, file.read(), 'application/pdf')}
            
            # Extract form parameters
            extraction_type = request.form.get('extraction_type', 'text')
            include_images = request.form.get('include_images') == 'true'
            include_metadata = request.form.get('include_metadata') == 'true'
            fast_mode = request.form.get('fast_mode') == 'true'
            use_cache = request.form.get('use_cache', 'true') == 'true'
            optimize_performance = request.form.get('optimize_performance', 'true') == 'true'
            
            # Call the optimized extraction endpoint
            api_response = requests.post(
                f"{API_URL}/extract-optimized",
                files=files,
                data={
                    'extraction_type': extraction_type,
                    'include_images': str(include_images).lower(),
                    'include_metadata': str(include_metadata).lower(),
                    'fast_mode': str(fast_mode).lower(),
                    'use_cache': str(use_cache).lower(),
                    'optimize_performance': str(optimize_performance).lower()
                }
            )
        else:
            # Handle JSON payload with URL
            data = request.json
            if not data.get('pdf_url'):
                return jsonify({
                    "status": "error",
                    "message": "PDF URL is required in the JSON payload"
                }), 400
            
            # Call the optimized extraction endpoint
            api_response = requests.post(
                f"{API_URL}/extract-optimized",
                json=data
            )
        
        # Check if the request was successful
        api_response.raise_for_status()
        
        # Return the task ID and status
        return api_response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request to API: {e}")
        return jsonify({
            "status": "error",
            "message": f"API service error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Error in optimized extraction: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/task-progress/<task_id>', methods=['GET'])
def get_task_progress(task_id):
    """Get the progress of a PDF extraction task."""
    try:
        # Forward the request to FastAPI endpoint
        api_response = requests.get(f"{API_URL}/task-progress/{task_id}")
        
        # Check if the request was successful
        api_response.raise_for_status()
        
        # Return the response as JSON
        return api_response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request to API: {e}")
        return jsonify({
            "status": "error",
            "message": f"API service error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Error getting task progress: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/active-tasks', methods=['GET'])
def list_active_tasks():
    """List all active extraction tasks."""
    try:
        # Forward the request to FastAPI endpoint
        api_response = requests.get(f"{API_URL}/active-tasks")
        
        # Check if the request was successful
        api_response.raise_for_status()
        
        # Return the response as JSON
        return api_response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request to API: {e}")
        return jsonify({
            "status": "error",
            "message": f"API service error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Error listing active tasks: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/task-result/<task_id>', methods=['GET'])
def get_task_result(task_id):
    """Get the result of a completed extraction task."""
    try:
        # Forward the request to FastAPI endpoint
        api_response = requests.get(f"{API_URL}/task-result/{task_id}")
        
        # Check if the request was successful
        api_response.raise_for_status()
        
        # Return the response as JSON
        return api_response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error forwarding request to API: {e}")
        return jsonify({
            "status": "error",
            "message": f"API service error: {str(e)}"
        }), 500
    except Exception as e:
        logger.error(f"Error getting task result: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

# The FastAPI server is now started from main.py
