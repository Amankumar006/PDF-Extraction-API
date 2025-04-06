import os
import logging
import tempfile
import uuid
import time
import io
from typing import Optional, Tuple
import requests
from fastapi import UploadFile

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Simple download cache
# Keys are URLs, values are (file_path, timestamp) tuples
download_cache = {}
CACHE_TTL = 3600  # Cache downloads for 1 hour

def save_upload_file_temp(upload_file: UploadFile) -> str:
    """
    Save an uploaded file to a temporary file using efficient buffering.
    
    Args:
        upload_file: FastAPI UploadFile
        
    Returns:
        Path to the temporary file
    """
    try:
        # Get file extension
        suffix = os.path.splitext(upload_file.filename)[1]
        
        # Use a larger buffer for better performance
        buffer_size = 1024 * 1024  # 1MB buffer
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
            # Use buffered reading for better performance
            for chunk in iter(lambda: upload_file.file.read(buffer_size), b''):
                if not chunk:
                    break
                temp.write(chunk)
                
        return temp.name
    except Exception as e:
        logger.error(f"Error saving uploaded file: {e}")
        raise e

def download_file(url: str, use_cache: bool = True) -> str:
    """
    Download a file from a URL and save it to a temporary file with caching.
    
    Args:
        url: URL of the file to download
        use_cache: Whether to use cached downloads
        
    Returns:
        Path to the temporary file
    """
    # Check cache first if enabled
    if use_cache:
        cached = _get_cached_download(url)
        if cached:
            logger.debug(f"Using cached download for {url}")
            return cached
    
    try:
        # Set up headers for the request
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
        }
        
        # Download the file with optimized settings
        logger.debug(f"Downloading file from {url}")
        response = requests.get(
            url, 
            stream=True, 
            headers=headers,
            timeout=30,  # Add a timeout
            allow_redirects=True  # Allow redirects
        )
        response.raise_for_status()  # Raise an exception for HTTP errors
        
        # Determine file extension from content-type or URL
        content_type = response.headers.get('content-type', '')
        extension = '.pdf'  # Default to PDF
        
        # Create a temporary file with an optimized buffer
        buffer_size = 1024 * 1024  # 1MB buffer
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as temp:
            # Write the file content with a larger chunk size for efficiency
            for chunk in response.iter_content(chunk_size=buffer_size):
                if not chunk:
                    break
                temp.write(chunk)
        
        # Cache the download if caching is enabled
        if use_cache:
            _cache_download(url, temp.name)
                
        return temp.name
    except Exception as e:
        logger.error(f"Error downloading file from {url}: {e}")
        raise e

def _get_cached_download(url: str) -> Optional[str]:
    """
    Get a cached download if it exists and is still valid.
    
    Args:
        url: URL of the downloaded file
        
    Returns:
        Path to the cached file or None if not found or expired
    """
    if url in download_cache:
        file_path, timestamp = download_cache[url]
        
        # Check if the file still exists and is not too old
        if os.path.exists(file_path) and (time.time() - timestamp) < CACHE_TTL:
            return file_path
        
        # Remove expired or missing file from cache
        del download_cache[url]
    
    return None

def _cache_download(url: str, file_path: str) -> None:
    """
    Cache a downloaded file.
    
    Args:
        url: URL of the downloaded file
        file_path: Path to the downloaded file
    """
    download_cache[url] = (file_path, time.time())

def clean_expired_cache() -> int:
    """
    Clean expired entries from the download cache.
    
    Returns:
        Number of entries removed
    """
    count = 0
    current_time = time.time()
    urls_to_remove = []
    
    # Find expired entries
    for url, (file_path, timestamp) in download_cache.items():
        if not os.path.exists(file_path) or (current_time - timestamp) >= CACHE_TTL:
            urls_to_remove.append(url)
            
            # Try to remove the file if it exists
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except:
                pass
    
    # Remove expired entries
    for url in urls_to_remove:
        del download_cache[url]
        count += 1
    
    return count
