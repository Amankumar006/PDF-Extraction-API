import logging
import threading
import time
from collections import defaultdict
from typing import Dict, Any, Optional, List, Callable

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global store for progress information
# Maps task_id -> progress data
progress_store = {}
active_tasks = set()

class ProgressTracker:
    """Tracks progress of PDF extraction tasks with real-time updates."""
    
    def __init__(self, task_id: str, total_steps: int = 100, 
                 step_descriptions: Optional[Dict[int, str]] = None):
        """
        Initialize a progress tracker.
        
        Args:
            task_id: Unique identifier for the task
            total_steps: Total number of steps in the process
            step_descriptions: Optional mapping of step numbers to descriptions
        """
        self.task_id = task_id
        self.total_steps = total_steps
        self.current_step = 0
        self.step_descriptions = step_descriptions or {}
        self.status = "initializing"
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.estimated_time_remaining = None
        self.performance_stats = defaultdict(float)
        self.optimization_logs = []
        
        # Register this tracker in the global store
        progress_store[task_id] = self.get_progress_data()
        active_tasks.add(task_id)
    
    def update(self, current_step: int, status: str = "processing", 
               message: Optional[str] = None) -> Dict[str, Any]:
        """
        Update the progress and return current progress data.
        
        Args:
            current_step: Current step in the process
            status: Current status (initializing, processing, optimizing, completed, error)
            message: Optional message to include
            
        Returns:
            Current progress data dictionary
        """
        self.current_step = min(current_step, self.total_steps)
        self.status = status
        current_time = time.time()
        
        # Calculate time-based metrics
        elapsed_time = current_time - self.start_time
        step_time = current_time - self.last_update_time
        self.last_update_time = current_time
        
        # Only estimate remaining time if we've made progress
        if self.current_step > 0 and self.current_step < self.total_steps:
            time_per_step = elapsed_time / self.current_step
            steps_remaining = self.total_steps - self.current_step
            self.estimated_time_remaining = time_per_step * steps_remaining
        
        # Get description for current step if available
        step_description = self.step_descriptions.get(
            self.current_step, 
            f"Step {self.current_step} of {self.total_steps}"
        )
        
        # Update progress in store
        progress_data = {
            "task_id": self.task_id,
            "current_step": self.current_step,
            "total_steps": self.total_steps,
            "percentage": round((self.current_step / self.total_steps) * 100, 1),
            "status": self.status,
            "step_description": step_description,
            "message": message,
            "elapsed_time": round(elapsed_time, 2),
            "estimated_time_remaining": (
                round(self.estimated_time_remaining, 2) 
                if self.estimated_time_remaining is not None 
                else None
            ),
            "performance_stats": dict(self.performance_stats),
            "optimization_logs": self.optimization_logs
        }
        
        # Include result_data if it exists in the current store
        current_data = progress_store.get(self.task_id, {})
        if "result_data" in current_data:
            progress_data["result_data"] = current_data["result_data"]
        
        progress_store[self.task_id] = progress_data
        
        # If task is completed or errored, remove it from active tasks after a delay
        if status in ("completed", "error"):
            threading.Timer(300, lambda: self._cleanup_task()).start()
            
        return progress_data
    
    def add_performance_stat(self, stat_name: str, value: float) -> None:
        """Add a performance statistic to the tracker."""
        self.performance_stats[stat_name] = value
    
    def add_optimization_log(self, message: str, optimization_type: str) -> None:
        """Add an optimization log entry."""
        self.optimization_logs.append({
            "time": time.time(),
            "message": message,
            "type": optimization_type
        })
    
    def set_result_data(self, result_data: Dict[str, Any]) -> None:
        """Store the final extraction result data in the progress tracker."""
        # Get current progress data from store
        current_data = progress_store.get(self.task_id, {})
        
        # Add the result data
        current_data["result_data"] = result_data
        
        # Update the store
        progress_store[self.task_id] = current_data
    
    def get_progress_data(self) -> Dict[str, Any]:
        """Get the current progress data."""
        return progress_store.get(self.task_id, {})
    
    def complete(self, message: Optional[str] = None) -> Dict[str, Any]:
        """Mark the task as completed."""
        return self.update(self.total_steps, "completed", message)
    
    def error(self, message: str) -> Dict[str, Any]:
        """Mark the task as errored."""
        return self.update(self.current_step, "error", message)
    
    def _cleanup_task(self) -> None:
        """Remove the task from active tasks after a delay."""
        if self.task_id in active_tasks:
            active_tasks.remove(self.task_id)


class PerformanceOptimizer:
    """Optimizes PDF extraction performance based on document characteristics."""
    
    def __init__(self, progress_tracker: Optional[ProgressTracker] = None, 
                 max_workers: int = 4):
        """
        Initialize the performance optimizer.
        
        Args:
            progress_tracker: Optional progress tracker for this optimization task
            max_workers: Maximum number of worker threads to use
        """
        self.progress_tracker = progress_tracker
        self.base_max_workers = max_workers
        self.optimized_workers = max_workers
        self.optimization_rules = []
    
    def analyze_document(self, page_count: int, file_size_bytes: int, 
                         has_images: bool = False, has_tables: bool = False,
                         is_scanned: bool = False) -> Dict[str, Any]:
        """
        Analyze a document and determine optimal processing parameters.
        
        Args:
            page_count: Number of pages in the document
            file_size_bytes: Size of the document in bytes
            has_images: Whether the document contains images
            has_tables: Whether the document contains tables
            is_scanned: Whether the document is likely a scanned document
            
        Returns:
            Dictionary with optimized parameters
        """
        if self.progress_tracker:
            self.progress_tracker.update(
                current_step=self.progress_tracker.current_step,
                status="optimizing",
                message="Analyzing document characteristics..."
            )
        
        # Calculate average page size
        avg_page_size = file_size_bytes / max(1, page_count)
        
        # Determine optimal number of workers based on document characteristics
        optimal_workers = self._calculate_optimal_workers(
            page_count, avg_page_size, has_images, is_scanned
        )
        
        # Determine optimal DPI for OCR
        optimal_dpi = self._calculate_optimal_dpi(
            is_scanned, has_images, avg_page_size
        )
        
        # Determine whether to preprocess images
        should_preprocess = self._should_preprocess_images(
            is_scanned, avg_page_size
        )
        
        # Determine chunking strategy
        chunk_size = self._calculate_chunk_size(page_count)
        
        # Log optimization decisions
        if self.progress_tracker:
            self.progress_tracker.add_optimization_log(
                f"Optimized worker count: {optimal_workers} (based on {page_count} pages, "
                f"{round(avg_page_size/1024, 1)}KB avg page size)",
                "worker_optimization"
            )
            
            self.progress_tracker.add_optimization_log(
                f"Optimized OCR DPI: {optimal_dpi}" +
                (" (reduced for performance)" if optimal_dpi < 300 else ""),
                "dpi_optimization"
            )
            
            self.progress_tracker.add_optimization_log(
                f"Image preprocessing: {should_preprocess}",
                "preprocessing_optimization"
            )
            
            if chunk_size > 1:
                self.progress_tracker.add_optimization_log(
                    f"Processing in chunks of {chunk_size} pages",
                    "chunking_optimization"
                )
        
        # Store the optimized worker count
        self.optimized_workers = optimal_workers
        
        # Return optimization parameters
        return {
            "max_workers": optimal_workers,
            "optimal_dpi": optimal_dpi,
            "preprocess_images": should_preprocess,
            "chunk_size": chunk_size
        }
    
    def _calculate_optimal_workers(self, page_count: int, avg_page_size: float,
                                  has_images: bool, is_scanned: bool) -> int:
        """Calculate the optimal number of worker threads."""
        base_workers = self.base_max_workers
        
        # Start with base workers
        optimal_workers = base_workers
        
        # Adjust based on page count
        if page_count < 5:
            optimal_workers = min(2, base_workers)
        elif page_count > 50:
            optimal_workers = min(base_workers + 2, 8)
        
        # Adjust for scanned documents (OCR is CPU intensive)
        if is_scanned:
            optimal_workers = max(optimal_workers, min(base_workers + 1, 6))
        
        # Reduce for very large pages to avoid memory issues
        if avg_page_size > 1024 * 1024:  # > 1MB per page
            optimal_workers = max(2, optimal_workers - 1)
        
        return optimal_workers
    
    def _calculate_optimal_dpi(self, is_scanned: bool, has_images: bool, 
                              avg_page_size: float) -> int:
        """Calculate the optimal DPI for OCR processing."""
        # Default DPI
        dpi = 300
        
        # For very large pages, reduce DPI to improve performance
        if avg_page_size > 2 * 1024 * 1024:  # > 2MB per page
            dpi = 200
        
        # For extremely large pages, reduce further
        if avg_page_size > 5 * 1024 * 1024:  # > 5MB per page
            dpi = 150
        
        return dpi
    
    def _should_preprocess_images(self, is_scanned: bool, avg_page_size: float) -> bool:
        """Determine whether to preprocess images based on document characteristics."""
        # By default, always preprocess for scanned documents
        if is_scanned:
            # Skip preprocessing only for very large scanned pages to save memory
            if avg_page_size > 4 * 1024 * 1024:  # > 4MB per page
                return False
            return True
        
        # For non-scanned documents, preprocess only if pages are reasonably sized
        return avg_page_size < 2 * 1024 * 1024  # < 2MB per page
    
    def _calculate_chunk_size(self, page_count: int) -> int:
        """Calculate the optimal chunk size for batch processing."""
        # Default: process all pages at once
        if page_count < 20:
            return page_count
        
        # For many pages, use chunks
        if page_count < 50:
            return 10
        if page_count < 100:
            return 20
        
        # For very large documents, use larger chunks
        return 30


# API to get progress for a task
def get_task_progress(task_id: str) -> Dict[str, Any]:
    """Get the progress data for a task."""
    return progress_store.get(task_id, {
        "task_id": task_id,
        "status": "not_found",
        "message": "Task not found"
    })

# API to get all active tasks
def get_active_tasks() -> List[Dict[str, Any]]:
    """Get progress data for all active tasks."""
    return [progress_store[task_id] for task_id in active_tasks 
            if task_id in progress_store]

# Cleanup old tasks periodically
def cleanup_old_tasks() -> None:
    """Remove old completed or error tasks from progress store."""
    current_time = time.time()
    tasks_to_remove = []
    
    for task_id, data in progress_store.items():
        if (data.get("status") in ("completed", "error") and 
            current_time - data.get("last_update_time", 0) > 3600):  # 1 hour
            tasks_to_remove.append(task_id)
    
    for task_id in tasks_to_remove:
        if task_id in progress_store:
            del progress_store[task_id]
        if task_id in active_tasks:
            active_tasks.remove(task_id)