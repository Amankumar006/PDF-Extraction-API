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

# Add new endpoints for progress tracking and optimized extraction

class OptimizedExtractionRequest(BaseModel):
    """Request model for optimized extraction."""
    pdf_url: Optional[str] = None
    extraction_type: str = "text"
    include_images: bool = False
    include_metadata: bool = False
    fast_mode: bool = False
    use_cache: bool = True
    optimize_performance: bool = True

class TaskProgressResponse(BaseModel):
    """Response model for task progress."""
    task_id: str
    current_step: int
    total_steps: int
    percentage: float
    status: str
    step_description: Optional[str] = None
    message: Optional[str] = None
    elapsed_time: Optional[float] = None
    estimated_time_remaining: Optional[float] = None
    performance_stats: Optional[Dict[str, Any]] = None
    optimization_logs: Optional[List[Dict[str, Any]]] = None

@app.post("/extract-optimized", response_model=Dict[str, Any])
async def extract_optimized(
    background_tasks: BackgroundTasks,
    file: Optional[UploadFile] = None,
    request: OptimizedExtractionRequest = None
):
    """
    Extract content from a PDF file with optimized performance and real-time progress tracking.
    
    Returns a task_id that can be used to poll for progress updates.
    """
    # Generate a unique task ID
    task_id = str(uuid.uuid4())
    
    if file and file.filename:
        # Save the uploaded file to a temporary location
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")
        
        temp_file = save_upload_file_temp(file)
        
        # Set up extraction parameters from form data or defaults
        extraction_params = {
            "extraction_type": request.extraction_type if request else "text",
            "include_images": request.include_images if request else False,
            "include_metadata": request.include_metadata if request else False,
            "fast_mode": request.fast_mode if request else False,
            "use_cache": request.use_cache if request else True,
            "optimize_performance": request.optimize_performance if request else True
        }
        
        # Start the extraction process in a background task
        background_tasks.add_task(
            process_pdf_with_progress,
            task_id=task_id,
            pdf_path=temp_file,
            is_temp_file=True,
            **extraction_params
        )
    
    elif request and request.pdf_url:
        # Process PDF from URL
        # Download will happen in the background task
        background_tasks.add_task(
            process_pdf_from_url_with_progress,
            task_id=task_id,
            pdf_url=request.pdf_url,
            extraction_type=request.extraction_type,
            include_images=request.include_images,
            include_metadata=request.include_metadata,
            fast_mode=request.fast_mode,
            use_cache=request.use_cache,
            optimize_performance=request.optimize_performance
        )
    
    else:
        raise HTTPException(
            status_code=400, 
            detail="Either a file upload or a PDF URL must be provided"
        )
    
    # Create initial progress tracker
    progress_tracker = ProgressTracker(
        task_id=task_id,
        total_steps=100,
        step_descriptions={
            0: "Initializing extraction process",
            20: "Analyzing document characteristics",
            40: "Optimizing extraction parameters",
            60: "Processing document content",
            90: "Finalizing extraction",
            100: "Extraction complete"
        }
    )
    
    # Return the task ID for progress tracking
    return {
        "task_id": task_id,
        "status": "processing",
        "message": "Extraction started. Use the /task-progress/{task_id} endpoint to track progress."
    }

async def process_pdf_with_progress(
    task_id: str,
    pdf_path: str,
    is_temp_file: bool = False,
    extraction_type: str = "text",
    include_images: bool = False,
    include_metadata: bool = False,
    fast_mode: bool = False,
    use_cache: bool = True,
    optimize_performance: bool = True
):
    """
    Process a PDF file with progress tracking.
    
    Args:
        task_id: Unique identifier for the task
        pdf_path: Path to the PDF file
        is_temp_file: Whether to delete the file after processing
        extraction_type: Type of extraction
        include_images: Whether to include images in the result
        include_metadata: Whether to include metadata in the result
        fast_mode: Whether to use fast mode
        use_cache: Whether to use cache
        optimize_performance: Whether to optimize performance
    """
    # Create progress tracker
    progress_tracker = ProgressTracker(
        task_id=task_id,
        total_steps=100,
        step_descriptions={
            0: "Initializing extraction process",
            20: "Analyzing document characteristics",
            40: "Optimizing extraction parameters",
            60: "Processing document content",
            90: "Finalizing extraction",
            100: "Extraction complete"
        }
    )
    
    try:
        # Update progress to initializing
        progress_tracker.update(
            current_step=0,
            status="initializing",
            message="Loading PDF and analyzing its structure..."
        )
        
        # Initial analysis of the PDF
        try:
            with pdfplumber.open(pdf_path) as pdf:
                page_count = len(pdf.pages)
                file_size = os.path.getsize(pdf_path)
                
                # Detect if the PDF contains images
                has_images = False
                has_tables = False
                first_page_text = ""
                
                # Check first few pages for images and tables
                for i, page in enumerate(pdf.pages):
                    if i >= 3:  # Limit to first 3 pages for performance
                        break
                    
                    if hasattr(page, 'images') and page.images:
                        has_images = True
                    
                    if i == 0:
                        first_page_text = page.extract_text() or ""
                    
                    try:
                        tables = page.extract_tables()
                        if tables and any(tables):
                            has_tables = True
                    except Exception:
                        pass
                
                # Heuristic to detect if this is a scanned document
                is_scanned = has_images and (not first_page_text or len(first_page_text) < 100)
                
                # Update progress to analysis complete
                progress_tracker.update(
                    current_step=20,
                    status="analyzing",
                    message=f"Analysis complete: {page_count} pages, {file_size/1024:.1f}KB, "
                            f"{'scanned' if is_scanned else 'digital'} document"
                )
                
                # Optimize extraction parameters if requested
                if optimize_performance:
                    # Create performance optimizer
                    optimizer = PerformanceOptimizer(progress_tracker=progress_tracker)
                    
                    # Get optimized parameters
                    optimization_params = optimizer.analyze_document(
                        page_count=page_count,
                        file_size_bytes=file_size,
                        has_images=has_images,
                        has_tables=has_tables,
                        is_scanned=is_scanned
                    )
                    
                    # Update progress
                    progress_tracker.update(
                        current_step=40,
                        status="optimizing",
                        message=f"Optimized extraction parameters for best performance"
                    )
                    
                    # Apply optimized parameters
                    max_workers = optimization_params["max_workers"]
                    optimal_dpi = optimization_params["optimal_dpi"]
                    preprocess_images = optimization_params["preprocess_images"]
                else:
                    # Use default parameters
                    max_workers = 4
                    optimal_dpi = 300
                    preprocess_images = not fast_mode
                
                # Create extractor with optimized parameters
                extractor = PDFExtractor(max_workers=max_workers)
                
                # Update progress to extraction start
                progress_tracker.update(
                    current_step=60,
                    status="processing",
                    message=f"Extracting content with optimized parameters..."
                )
                
                # Perform the extraction
                if extraction_type == "ocr":
                    # Set OCR parameters
                    extractor.ocr_service = OCRService(
                        dpi=optimal_dpi,
                        max_workers=max_workers
                    )
                
                # Process the document
                result = {}
                total_steps = 30  # Allocate 30% of the progress bar for processing
                update_interval = max(1, page_count // 10)  # Update progress every ~10% of pages
                
                # Extract content with progress tracking
                result = extractor.extract_content(
                    pdf_path, 
                    extraction_type,
                    include_images,
                    include_metadata,
                    fast_mode,
                    use_cache
                )
                
                # Update progress to completion
                progress_tracker.update(
                    current_step=90,
                    status="finalizing",
                    message="Finalizing extraction results..."
                )
                
                # Store the result in the progress data for retrieval
                progress_tracker.add_performance_stat("execution_time", result.get("execution_time", 0))
                progress_tracker.add_performance_stat("page_count", page_count)
                
                # Store the extraction result data for later retrieval
                progress_tracker.set_result_data(result)
                
                # Mark as complete
                progress_tracker.complete(
                    message=f"Successfully extracted content from {page_count} pages "
                            f"({result.get('execution_time', 0):.2f}s)"
                )
                
        except Exception as e:
            logger.error(f"Error during PDF analysis: {e}")
            progress_tracker.error(f"Error analyzing PDF: {str(e)}")
            raise
            
    except Exception as e:
        logger.error(f"Error processing PDF: {e}")
        progress_tracker.error(f"Error processing PDF: {str(e)}")
    
    finally:
        # Clean up the temporary file if needed
        if is_temp_file:
            try:
                os.unlink(pdf_path)
                logger.debug(f"Removed temporary file: {pdf_path}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file {pdf_path}: {e}")

async def process_pdf_from_url_with_progress(
    task_id: str,
    pdf_url: str,
    extraction_type: str = "text",
    include_images: bool = False,
    include_metadata: bool = False,
    fast_mode: bool = False,
    use_cache: bool = True,
    optimize_performance: bool = True
):
    """Process a PDF from a URL with progress tracking."""
    # Create progress tracker
    progress_tracker = ProgressTracker(
        task_id=task_id,
        total_steps=100,
        step_descriptions={
            0: "Initializing extraction process",
            10: "Downloading PDF from URL",
            30: "Analyzing document characteristics",
            50: "Optimizing extraction parameters",
            60: "Processing document content",
            90: "Finalizing extraction",
            100: "Extraction complete"
        }
    )
    
    try:
        # Update progress to downloading
        progress_tracker.update(
            current_step=0,
            status="initializing",
            message=f"Downloading PDF from {pdf_url}..."
        )
        
        # Download the PDF
        try:
            temp_file = download_file(pdf_url)
            
            # Update progress
            progress_tracker.update(
                current_step=20,
                status="downloaded",
                message="PDF downloaded successfully. Starting analysis..."
            )
            
            # Process the PDF with progress tracking
            await process_pdf_with_progress(
                task_id=task_id,
                pdf_path=temp_file,
                is_temp_file=True,
                extraction_type=extraction_type,
                include_images=include_images,
                include_metadata=include_metadata,
                fast_mode=fast_mode,
                use_cache=use_cache,
                optimize_performance=optimize_performance
            )
            
        except Exception as e:
            logger.error(f"Error downloading PDF from URL: {e}")
            progress_tracker.error(f"Error downloading PDF: {str(e)}")
    
    except Exception as e:
        logger.error(f"Error in URL extraction process: {e}")
        progress_tracker.error(f"Error processing PDF from URL: {str(e)}")

@app.get("/task-progress/{task_id}", response_model=TaskProgressResponse)
async def get_progress(task_id: str):
    """
    Get the progress of a PDF extraction task.
    
    Args:
        task_id: ID of the task to get progress for
        
    Returns:
        Progress information for the task
    """
    progress_data = get_task_progress(task_id)
    
    if progress_data.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Task with ID {task_id} not found"
        )
    
    return progress_data

@app.get("/active-tasks")
async def list_active_tasks():
    """
    List all active extraction tasks.
    
    Returns:
        List of active task IDs and their status
    """
    return {"active_tasks": get_active_tasks()}

@app.get("/task-result/{task_id}")
async def get_task_result(task_id: str):
    """
    Get the results of a completed PDF extraction task.
    
    Args:
        task_id: ID of the task to get results for
        
    Returns:
        The extracted content if available
    """
    progress_data = get_task_progress(task_id)
    
    if progress_data.get("status") == "not_found":
        raise HTTPException(
            status_code=404,
            detail=f"Task with ID {task_id} not found"
        )
    
    # Check if the task is completed
    if progress_data.get("status") != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Task with ID {task_id} is not completed yet"
        )
    
    # Get performance stats and result data
    performance_stats = progress_data.get("performance_stats", {})
    result_data = progress_data.get("result_data", {})
    
    # Return a formatted response with the necessary data
    return {
        "status": "success",
        "task_id": task_id,
        "content": result_data,  # Include the actual content
        "execution_time": performance_stats.get("execution_time"),
        "message": progress_data.get("message"),
        "optimization_logs": progress_data.get("optimization_logs")
    }
