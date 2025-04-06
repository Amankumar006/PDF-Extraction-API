import os
import logging
import base64
import json
import time
import concurrent.futures
import functools
import uuid
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import tempfile
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import pdfplumber
from .ocr_service import OCRService
from .file_utils import download_file, save_upload_file_temp
from .performance_optimizer import ProgressTracker, PerformanceOptimizer, get_task_progress, get_active_tasks

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="PDF Extraction API",
    description="API for extracting structured content from PDFs",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create OCR service with parallel processing
ocr_service = OCRService(max_workers=4)

# Simple in-memory cache for extracted content
# Keys are (file_path, extraction_type, include_images, include_metadata) tuples
# Values are the extracted results
extraction_cache = {}

class PDFRequest(BaseModel):
    pdf_url: str
    extraction_type: str = "text"
    include_images: bool = False
    include_metadata: bool = False
    fast_mode: bool = False
    use_cache: bool = True

class ExtractionResult(BaseModel):
    status: str
    content: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    execution_time: Optional[float] = None

class PDFExtractor:
    def __init__(self, max_workers: int = 4):
        self.ocr_service = OCRService(max_workers=max_workers)
        self.max_workers = max_workers
    
    def extract_content(
        self, 
        pdf_path: str, 
        extraction_type: str = "text", 
        include_images: bool = False,
        include_metadata: bool = False,
        fast_mode: bool = False,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Extract content from a PDF file.
        
        Args:
            pdf_path: Path to the PDF file
            extraction_type: Type of extraction ('text', 'structured', 'ocr')
            include_images: Whether to include images in the result
            include_metadata: Whether to include metadata in the result
            fast_mode: If True, use faster but potentially less accurate processing
            use_cache: Whether to use cached results if available
            
        Returns:
            A dictionary containing the extracted content
        """
        start_time = time.time()
        logger.debug(f"Extracting content from {pdf_path} with type {extraction_type}, fast_mode={fast_mode}")
        
        # Check cache if enabled
        cache_key = (pdf_path, extraction_type, include_images, include_metadata, fast_mode)
        if use_cache and cache_key in extraction_cache:
            logger.debug(f"Using cached extraction result for {pdf_path}")
            result = extraction_cache[cache_key]
            result["execution_time"] = time.time() - start_time
            return result
        
        try:
            if extraction_type == "ocr":
                # Process the PDF as a scan (OCR)
                result = self._extract_with_ocr(pdf_path, fast_mode=fast_mode)
            else:
                # Process the PDF as text
                with pdfplumber.open(pdf_path) as pdf:
                    if extraction_type == "structured":
                        result = self._extract_structured(pdf, fast_mode=fast_mode)
                    else:  # Default to plain text
                        result = self._extract_text(pdf, fast_mode=fast_mode)
                    
                    # Add metadata if requested
                    if include_metadata:
                        result["metadata"] = self._extract_metadata(pdf)
                    
                    # Add images if requested
                    if include_images:
                        result["images"] = self._extract_images(pdf)
            
            execution_time = time.time() - start_time
            final_result = {
                "status": "success",
                "content": result,
                "execution_time": execution_time
            }
            
            # Cache the result if caching is enabled
            if use_cache:
                extraction_cache[cache_key] = final_result
                
            return final_result
            
        except Exception as e:
            logger.error(f"Error extracting content: {e}")
            return {
                "status": "error",
                "message": f"Error extracting content: {str(e)}",
                "execution_time": time.time() - start_time
            }
    
    def _process_page_text(self, page_data: Tuple[int, Any]) -> Dict[str, Any]:
        """Process a single page for text extraction."""
        i, page = page_data
        text = page.extract_text() or ""
        return {
            "page": i + 1,
            "content": text
        }
    
    def _extract_text(self, pdf, fast_mode: bool = False) -> Dict[str, Any]:
        """
        Extract plain text from a PDF using parallel processing.
        
        Args:
            pdf: pdfplumber PDF object
            fast_mode: If True, use a more efficient but potentially less accurate extraction
            
        Returns:
            Dictionary with extracted text content
        """
        # If we have many pages or fast mode is enabled, use parallel processing
        use_parallel = len(pdf.pages) > 5 or fast_mode
        
        if use_parallel:
            # Process pages in parallel
            text_content = [None] * len(pdf.pages)  # Pre-allocate list
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Create page data with indices
                page_data = [(i, page) for i, page in enumerate(pdf.pages)]
                
                # Submit all tasks and map future to index
                future_to_index = {
                    executor.submit(self._process_page_text, pd): pd[0] 
                    for pd in page_data
                }
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_index):
                    idx = future_to_index[future]
                    text_content[idx] = future.result()
        else:
            # Process pages sequentially for small documents
            text_content = []
            for i, page in enumerate(pdf.pages):
                text = page.extract_text() or ""
                text_content.append({
                    "page": i + 1,
                    "content": text
                })
        
        return {
            "type": "text",
            "pages": len(pdf.pages),
            "content": text_content
        }
    
    def _process_page_structured(self, page_data: Tuple[int, Any]) -> Dict[str, Any]:
        """Process a single page for structured extraction."""
        i, page = page_data
        
        # Extract basic text
        text = page.extract_text() or ""
        
        # Extract tables if any
        tables = []
        try:
            for table in page.extract_tables():
                if table:
                    tables.append([
                        [cell if cell is not None else "" for cell in row]
                        for row in table
                    ])
        except Exception as e:
            logger.warning(f"Error extracting tables from page {i+1}: {e}")
        
        # Simple structure detection (paragraphs, headings)
        paragraphs = []
        if text:
            paragraphs = [p for p in text.split('\n\n') if p.strip()]
        
        # Process paragraphs into elements
        elements = []
        for p in paragraphs:
            p = p.strip()
            if not p:
                continue
                
            # Simple heuristic: short lines with few words could be headings
            words = p.split()
            if len(words) <= 8 and len(p) <= 100 and p.endswith(('.', ':', '?', '!')):
                elements.append({
                    "type": "heading",
                    "content": p
                })
            else:
                elements.append({
                    "type": "paragraph",
                    "content": p
                })
        
        return {
            "page": i + 1,
            "elements": elements,
            "tables": tables,
            "raw_text": text
        }
    
    def _extract_structured(self, pdf, fast_mode: bool = False) -> Dict[str, Any]:
        """
        Extract structured content from a PDF using parallel processing.
        
        Args:
            pdf: pdfplumber PDF object
            fast_mode: If True, use a more efficient but potentially less accurate extraction
            
        Returns:
            Dictionary with structured content
        """
        # If we have many pages or fast mode is enabled, use parallel processing
        use_parallel = len(pdf.pages) > 3 or fast_mode
        
        if use_parallel:
            # Process pages in parallel
            structured_content = [None] * len(pdf.pages)  # Pre-allocate list
            with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Create page data with indices
                page_data = [(i, page) for i, page in enumerate(pdf.pages)]
                
                # Submit all tasks and map future to index
                future_to_index = {
                    executor.submit(self._process_page_structured, pd): pd[0] 
                    for pd in page_data
                }
                
                # Process results as they complete
                for future in concurrent.futures.as_completed(future_to_index):
                    idx = future_to_index[future]
                    structured_content[idx] = future.result()
        else:
            # Process pages sequentially for small documents
            structured_content = []
            for i, page in enumerate(pdf.pages):
                page_data = (i, page)
                structured_content.append(self._process_page_structured(page_data))
        
        return {
            "type": "structured",
            "pages": len(pdf.pages),
            "content": structured_content
        }
    
    def _extract_with_ocr(self, pdf_path: str, fast_mode: bool = False) -> Dict[str, Any]:
        """
        Process the PDF using OCR.
        
        Args:
            pdf_path: Path to the PDF file
            fast_mode: If True, use lower quality settings for faster processing
            
        Returns:
            Dictionary with OCR results
        """
        ocr_result = self.ocr_service.process_pdf(
            pdf_path,
            use_cache=True,
            preprocess_images=not fast_mode,  # Skip preprocessing in fast mode
            fast_mode=fast_mode
        )
        
        return {
            "type": "ocr",
            "pages": len(ocr_result),
            "content": ocr_result
        }
    
    def _extract_metadata(self, pdf) -> Dict[str, Any]:
        """Extract metadata from the PDF."""
        metadata = pdf.metadata
        return {k: v for k, v in metadata.items()} if metadata else {}
    
    def _extract_images(self, pdf) -> List[Dict[str, Any]]:
        """Extract images from the PDF (basic info only to avoid binary data)."""
        image_info = []
        
        for i, page in enumerate(pdf.pages):
            try:
                for j, img in enumerate(page.images):
                    image_info.append({
                        "page": i + 1,
                        "index": j,
                        "width": img["width"],
                        "height": img["height"],
                        "type": "image"
                    })
            except Exception as e:
                logger.warning(f"Error extracting images from page {i+1}: {e}")
        
        return image_info
    
    def clear_cache(self):
        """Clear the extraction cache to free memory."""
        global extraction_cache
        extraction_cache.clear()
        self.ocr_service.clear_cache()

# API Endpoints
@app.post("/extract", response_model=ExtractionResult)
async def extract_from_file(
    file: UploadFile = File(...),
    extraction_type: str = Form("text"),
    include_images: bool = Form(False),
    include_metadata: bool = Form(False),
    fast_mode: bool = Form(False),
    use_cache: bool = Form(True)
):
    """
    Extract content from an uploaded PDF file.
    
    - extraction_type: Type of extraction ('text', 'structured', 'ocr')
    - include_images: Whether to include image information in the result
    - include_metadata: Whether to include PDF metadata in the result
    - fast_mode: If True, use faster but potentially less accurate processing
    - use_cache: Whether to use cached results if available
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    
    # Save the uploaded file to a temporary location
    temp_file = save_upload_file_temp(file)
    
    try:
        # Process the PDF
        extractor = PDFExtractor()
        result = extractor.extract_content(
            temp_file, 
            extraction_type,
            include_images,
            include_metadata,
            fast_mode,
            use_cache
        )
        
        if result["status"] == "error":
            raise HTTPException(status_code=500, detail=result["message"])
        
        return result
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file)
        except:
            pass

@app.post("/extract-url", response_model=ExtractionResult)
async def extract_from_url(request: PDFRequest):
    """
    Extract content from a PDF at the specified URL.
    
    - extraction_type: Type of extraction ('text', 'structured', 'ocr')
    - include_images: Whether to include image information in the result
    - include_metadata: Whether to include PDF metadata in the result
    - fast_mode: If True, use faster but potentially less accurate processing
    - use_cache: Whether to use cached results if available
    """
    try:
        # Download the PDF from the URL
        temp_file = download_file(request.pdf_url)
        
        try:
            # Process the PDF
            extractor = PDFExtractor()
            result = extractor.extract_content(
                temp_file, 
                request.extraction_type,
                request.include_images,
                request.include_metadata,
                request.fast_mode,
                request.use_cache
            )
            
            if result["status"] == "error":
                raise HTTPException(status_code=500, detail=result["message"])
            
            return result
        finally:
            # Clean up the temporary file
            try:
                os.unlink(temp_file)
            except:
                pass
    except Exception as e:
        logger.error(f"Error processing PDF from URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "pdf-extraction-api"}

@app.post("/clear-cache")
async def clear_cache():
    """Clear all caches to free memory."""
    try:
        extractor = PDFExtractor()
        extractor.clear_cache()
        return {"status": "success", "message": "All caches cleared successfully"}
    except Exception as e:
        logger.error(f"Error clearing caches: {e}")
        raise HTTPException(status_code=500, detail=str(e))
