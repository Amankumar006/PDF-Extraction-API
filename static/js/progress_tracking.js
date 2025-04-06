/**
 * Progress tracking functionality for PDF extraction
 */

// Poll for progress updates
function startProgressPolling(taskId, extractionType, fastMode = false) {
    // Get DOM elements for updating progress
    const progressBar = document.getElementById('processing-progress');
    const messageElement = document.getElementById('processing-message');
    const currentStepElement = document.getElementById('current-step');
    const stepPercentageElement = document.getElementById('step-percentage');
    const elapsedTimeElement = document.getElementById('elapsed-time');
    const estimatedTimeElement = document.getElementById('estimated-time');
    const optimizationLogsElement = document.getElementById('optimization-logs');
    const processingIndicator = document.getElementById('processing-indicator');
    const resultCard = document.getElementById('result-card');
    const uploadBtn = document.getElementById('upload-btn');
    
    // Initialize
    let isCompleted = false;
    let pollInterval = 1000; // Start polling every second
    
    // Function to poll for progress updates
    function pollProgress() {
        if (isCompleted) return;
        
        fetch(`/task-progress/${taskId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(progressData => {
                // Update progress display
                updateProgressDisplay(progressData);
                
                // Check if the task is complete or errored
                if (progressData.status === 'completed') {
                    isCompleted = true;
                    
                    // Show success message
                    messageElement.textContent = progressData.message || 'Extraction completed successfully!';
                    messageElement.classList.add('text-success');
                    
                    // Set progress bar to 100%
                    progressBar.style.width = '100%';
                    progressBar.classList.remove('progress-bar-animated');
                    
                    // Notify the user that processing is complete
                    showAlert('PDF extraction completed successfully!', 'success');
                    
                    // Wait 2 seconds and then redirect to the results display
                    setTimeout(() => {
                        displayTaskResults(taskId);
                    }, 2000);
                    
                    return;
                } else if (progressData.status === 'error') {
                    isCompleted = true;
                    
                    // Show error message
                    messageElement.textContent = progressData.message || 'An error occurred during extraction.';
                    messageElement.classList.add('text-danger');
                    
                    // Set progress bar to error state
                    progressBar.classList.remove('progress-bar-animated', 'bg-primary', 'bg-success');
                    progressBar.classList.add('bg-danger');
                    
                    // Hide processing indicator after a delay
                    setTimeout(() => {
                        processingIndicator.classList.add('d-none');
                        uploadBtn.disabled = false;
                    }, 3000);
                    
                    // Notify the user of the error
                    showAlert(progressData.message || 'An error occurred during extraction.', 'danger');
                    
                    return;
                }
                
                // Adjust polling frequency based on progress
                if (progressData.percentage < 20) {
                    pollInterval = 1000; // Poll faster at the beginning
                } else if (progressData.percentage < 80) {
                    pollInterval = 2000; // Poll less frequently in the middle
                } else {
                    pollInterval = 1000; // Poll faster near the end
                }
                
                // Continue polling
                setTimeout(pollProgress, pollInterval);
            })
            .catch(error => {
                console.error('Error polling for progress:', error);
                
                // Retry a few times with exponential backoff if there's a connection issue
                pollInterval = Math.min(pollInterval * 2, 10000); // Max 10s between retries
                
                setTimeout(pollProgress, pollInterval);
            });
    }
    
    // Function to update the progress display
    function updateProgressDisplay(progressData) {
        // Update progress bar
        const percentage = progressData.percentage || 0;
        progressBar.style.width = `${percentage}%`;
        
        // Update step description and percentage
        if (currentStepElement) {
            currentStepElement.textContent = progressData.step_description || `Step ${progressData.current_step} of ${progressData.total_steps}`;
        }
        
        if (stepPercentageElement) {
            stepPercentageElement.textContent = `${Math.round(percentage)}%`;
        }
        
        // Update message
        if (messageElement && progressData.message) {
            messageElement.textContent = progressData.message;
        }
        
        // Update timing information
        if (elapsedTimeElement && progressData.elapsed_time !== undefined) {
            elapsedTimeElement.textContent = `Elapsed: ${formatTime(progressData.elapsed_time)}`;
        }
        
        if (estimatedTimeElement && progressData.estimated_time_remaining !== undefined) {
            if (progressData.estimated_time_remaining !== null) {
                estimatedTimeElement.textContent = `Estimated: ${formatTime(progressData.estimated_time_remaining)} remaining`;
            } else {
                estimatedTimeElement.textContent = 'Estimated: calculating...';
            }
        }
        
        // Update optimization logs if present
        if (optimizationLogsElement && progressData.optimization_logs && progressData.optimization_logs.length > 0) {
            // Clear existing logs
            optimizationLogsElement.innerHTML = '';
            
            // Add logs in reverse order (newest first)
            for (const log of [...progressData.optimization_logs].reverse().slice(0, 5)) { // Show last 5 logs
                const logElement = document.createElement('div');
                
                // Determine log class based on type
                let logClass = 'text-info';
                if (log.type.includes('error')) {
                    logClass = 'text-danger';
                } else if (log.type.includes('warning')) {
                    logClass = 'text-warning';
                } else if (log.type.includes('optim')) {
                    logClass = 'text-success';
                }
                
                logElement.className = `${logClass} mb-1`;
                logElement.innerHTML = `<i class="fas fa-info-circle me-1"></i> ${log.message}`;
                
                optimizationLogsElement.appendChild(logElement);
            }
        }
    }
    
    // Format time in seconds to a human-readable string
    function formatTime(seconds) {
        seconds = Math.round(seconds);
        if (seconds < 60) {
            return `${seconds}s`;
        } else {
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = seconds % 60;
            return `${minutes}m ${remainingSeconds}s`;
        }
    }
    
    // Function to fetch and display the final results
    function displayTaskResults(taskId) {
        // Show loading message
        messageElement.textContent = 'Loading results...';
        
        // Make API call to get the task results
        fetch(`/task-result/${taskId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                // Hide processing indicator and enable button
                processingIndicator.classList.add('d-none');
                uploadBtn.disabled = false;
                
                // Display the results
                if (data.status === 'success' || data.content) {
                    displayResults(data);
                } else {
                    showAlert(data.message || 'An error occurred while processing the PDF', 'danger');
                }
            })
            .catch(error => {
                console.error('Error fetching task results:', error);
                
                // Since we can't get results directly, try to use the progress data itself
                processingIndicator.classList.add('d-none');
                uploadBtn.disabled = false;
                
                // Show a more specific error message
                showAlert('PDF was processed, but there was an error retrieving the full results. ' +
                          'Try uploading again or check the extracted content in the progress details.', 'warning');
            });
    }
    
    // Start polling immediately
    pollProgress();
}

// Add this function to the window object for global access
window.startProgressPolling = startProgressPolling;
