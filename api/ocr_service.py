import os
import logging
import tempfile
import concurrent.futures
import functools
from typing import List, Dict, Any, Optional, Tuple
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageFilter

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Simple in-memory cache using a dictionary
# Keys are (file_path, dpi, language, preprocess) tuples
# Values are the processed results
ocr_cache = {}

class OCRService:
    """Service for performing OCR on PDFs and images with parallel processing and caching."""
    
    def __init__(self, dpi: int = 300, language: str = 'eng', max_workers: int = 4):
        """
        Initialize the OCR service.
        
        Args:
            dpi: DPI to use when converting PDF to images
            language: OCR language (default: 'eng' for English)
            max_workers: Maximum number of parallel workers for OCR processing
        """
        self.dpi = dpi
        self.language = language
        self.max_workers = max_workers
    
    def process_pdf(self, pdf_path: str, use_cache: bool = True, 
                   preprocess_images: bool = True, fast_mode: bool = False) -> List[Dict[str, Any]]:
        """
        Process a PDF file using OCR with parallel processing.
        
        Args:
            pdf_path: Path to the PDF file
            use_cache: Whether to use cache for previously processed PDFs
            preprocess_images: Whether to preprocess images to improve OCR
            fast_mode: If True, uses lower quality settings for faster processing
            
        Returns:
            A list of dictionaries, each containing the text for a page
        """
        logger.debug(f"Processing PDF at {pdf_path} with OCR (fast_mode={fast_mode})")
        
        # Set DPI based on mode
        current_dpi = 150 if fast_mode else self.dpi
        
        # Check cache first if enabled
        cache_key = (pdf_path, current_dpi, self.language, preprocess_images)
        if use_cache and cache_key in ocr_cache:
            logger.debug(f"Using cached OCR result for {pdf_path}")
            return ocr_cache[cache_key]
        
        # Create a temporary directory for the images
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Convert PDF to images
                logger.debug(f"Converting PDF to images with DPI={current_dpi}")
                images = convert_from_path(
                    pdf_path, 
                    dpi=current_dpi, 
                    output_folder=temp_dir,
                    fmt="jpeg",
                    thread_count=2  # Use 2 threads for conversion
                )
                
                # Process images in parallel using ThreadPoolExecutor
                logger.debug(f"Processing {len(images)} images with {self.max_workers} workers")
                
                # Create a partial function with the preprocessing flag
                process_func = functools.partial(
                    self._process_image_with_index, 
                    preprocess=preprocess_images
                )
                
                # Process images in parallel
                results = [None] * len(images)  # Pre-allocate results list
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    # Submit all tasks and map future to index
                    future_to_index = {
                        executor.submit(process_func, i, img): i 
                        for i, img in enumerate(images)
                    }
                    
                    # Process results as they complete
                    for future in concurrent.futures.as_completed(future_to_index):
                        idx, text = future.result()
                        results[idx] = {
                            "page": idx + 1,
                            "content": text
                        }
                
                # Cache the result if caching is enabled
                if use_cache:
                    ocr_cache[cache_key] = results
                    
                return results
                
            except Exception as e:
                logger.error(f"Error in OCR processing: {e}")
                raise Exception(f"OCR processing failed: {str(e)}")
    
    def _process_image_with_index(self, idx: int, image: Image.Image, preprocess: bool = True) -> Tuple[int, str]:
        """Process an image and return its index with the result."""
        return idx, self._process_image(image, preprocess)
    
    def _process_image(self, image: Image.Image, preprocess: bool = True) -> str:
        """
        Process a single image with OCR.
        
        Args:
            image: PIL Image object
            preprocess: Whether to preprocess the image to improve OCR results
            
        Returns:
            Extracted text
        """
        try:
            # Preprocess the image if enabled
            if preprocess:
                image = self._preprocess_image(image)
            
            # Perform OCR on the image
            text = pytesseract.image_to_string(image, lang=self.language)
            return text
        except Exception as e:
            logger.error(f"Error in OCR image processing: {e}")
            return ""
    
    def _preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Preprocess image to improve OCR quality.
        
        Args:
            image: Original PIL Image
            
        Returns:
            Preprocessed PIL Image
        """
        # Convert to grayscale
        img_gray = image.convert('L')
        
        # Apply mild Gaussian blur to reduce noise
        img_blur = img_gray.filter(ImageFilter.GaussianBlur(radius=1))
        
        # Apply threshold to make text more prominent
        threshold = 200
        img_threshold = img_blur.point(lambda x: 255 if x > threshold else 0)
        
        return img_threshold
    
    def process_image_file(self, image_path: str, preprocess: bool = True) -> str:
        """
        Process an image file with OCR.
        
        Args:
            image_path: Path to the image file
            preprocess: Whether to preprocess the image
            
        Returns:
            Extracted text
        """
        try:
            # Open the image
            with Image.open(image_path) as img:
                # Perform OCR
                return self._process_image(img, preprocess)
        except Exception as e:
            logger.error(f"Error processing image file: {e}")
            raise Exception(f"Image OCR processing failed: {str(e)}")
            
    def clear_cache(self):
        """Clear the OCR cache to free memory."""
        global ocr_cache
        ocr_cache.clear()
