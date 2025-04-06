document.addEventListener('DOMContentLoaded', function() {
    // Get the elements we need to interact with
    const form = document.getElementById('upload-form');
    const copyBtn = document.getElementById('copy-results');
    
    // Form submission handler
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const formData = new FormData(form);
        const extractionType = formData.get('extraction_type') || 'text';
        const file = formData.get('file');
        const fastMode = formData.get('fast_mode') === 'true';
        const useCache = formData.get('use_cache') === 'true';
        const includeMetadata = formData.get('include_metadata') === 'true';
        const includeImages = formData.get('include_images') === 'true';
        const optimizePerformance = formData.get('optimize_performance') === 'true';
        
        if (!file || file.name === '') {
            showAlert('Please select a PDF file to upload', 'warning');
            return;
        }
        
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            showAlert('Only PDF files are supported', 'warning');
            return;
        }
        
        // Show the processing indicator with the appropriate animation
        const processingIndicator = document.getElementById('processing-indicator');
        const resultCard = document.getElementById('result-card');
        const uploadBtn = document.getElementById('upload-btn');
        const animationContainer = document.getElementById('pdf-animation-container');
        const progressDetails = document.getElementById('progress-details');
        
        // Set animation class based on extraction type
        animationContainer.className = 'pdf-animation-container animation-' + extractionType;
        if (fastMode) {
            animationContainer.classList.add('fast-mode');
        }
        
        // Hide previous results and show processing animation
        if (resultCard) resultCard.classList.add('d-none');
        processingIndicator.classList.remove('d-none');
        uploadBtn.disabled = true;
        
        // Make sure we have all the options in the form data
        if (fastMode) formData.set('fast_mode', 'true');
        formData.set('use_cache', useCache ? 'true' : 'false');
        formData.set('include_metadata', includeMetadata ? 'true' : 'false');
        formData.set('include_images', includeImages ? 'true' : 'false');
        formData.set('optimize_performance', optimizePerformance ? 'true' : 'false');
        
        // Determine if we should use the optimized endpoint with progress tracking
        const useOptimizedEndpoint = optimizePerformance;
        
        // Check if we're using the optimized extraction with progress tracking
        if (useOptimizedEndpoint) {
            // Use the optimized endpoint with progress tracking
            fetch('/extract-optimized', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Server responded with ${response.status}: ${response.statusText}`);
                }
                return response.json();
            })
            .then(data => {
                if (data.status === 'processing' && data.task_id) {
                    // Show progress details for real-time tracking
                    progressDetails.classList.remove('d-none');
                    
                    // Start polling for progress updates
                    startProgressPolling(data.task_id, extractionType, fastMode);
                } else if (data.status === 'error') {
                    // Handle immediate error
                    throw new Error(data.message || 'An error occurred while starting the extraction process');
                } else {
                    // Handle unexpected response
                    throw new Error('Invalid response from server');
                }
            })
            .catch(error => {
                console.error('Error starting optimized extraction:', error);
                processingIndicator.classList.add('d-none');
                progressDetails.classList.add('d-none');
                uploadBtn.disabled = false;
                showAlert(`Error: ${error.message || 'An error occurred while starting the extraction process'}`, 'danger');
            });
        } else {
            // Use the regular endpoint without progress tracking
            // Start the progress animation (simulated)
            startProgressAnimation(extractionType, fastMode);
            
            // Cycle through fun messages during processing
            startMessageCycling(extractionType, fastMode);
            
            // Send the request to the API endpoint
            fetch('/extract', {
                method: 'POST',
                body: formData
            })
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
                console.error('Error uploading file:', error);
                processingIndicator.classList.add('d-none');
                uploadBtn.disabled = false;
                showAlert(`Error: ${error.message || 'An error occurred while uploading the file'}`, 'danger');
            });
        }
    });
    
    // Copy button handler
    if (copyBtn) {
        copyBtn.addEventListener('click', function() {
            const resultsElement = document.getElementById('results');
            if (resultsElement) {
                try {
                    // Create a temporary text area to copy from
                    const textarea = document.createElement('textarea');
                    textarea.value = resultsElement.textContent;
                    document.body.appendChild(textarea);
                    textarea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textarea);
                    
                    // Show success message
                    showAlert('Results copied to clipboard!', 'success');
                } catch (e) {
                    console.error('Error copying text:', e);
                    showAlert('Failed to copy results', 'danger');
                }
            }
        });
    }
    
    // Function to display alerts
    window.showAlert = function(message, type = 'info') {
        const alertsContainer = document.getElementById('alerts-container') || createAlertsContainer();
        
        // Create the alert element
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        // Add the alert to the container
        alertsContainer.appendChild(alert);
        
        // Remove the alert after 5 seconds
        setTimeout(function() {
            if (alert.parentNode) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        }, 5000);
    };
    
    // Create alerts container if it doesn't exist
    function createAlertsContainer() {
        const container = document.createElement('div');
        container.id = 'alerts-container';
        container.className = 'position-fixed top-0 end-0 p-3';
        container.style.zIndex = '5000';
        document.body.appendChild(container);
        return container;
    }
    
    // Function to display the results
    window.displayResults = function(data) {
        const resultCard = document.getElementById('result-card');
        const resultsElement = document.getElementById('results');
        const executionTimeElement = document.getElementById('execution-time');
        
        if (resultCard && resultsElement) {
            // Format the content for display
            let formattedContent;
            
            try {
                if (typeof data.content === 'object') {
                    formattedContent = JSON.stringify(data.content, null, 2);
                } else if (typeof data.content === 'string') {
                    formattedContent = data.content;
                } else {
                    formattedContent = JSON.stringify(data, null, 2);
                }
            } catch (e) {
                console.error('Error formatting content:', e);
                formattedContent = String(data.content || 'Error formatting content');
            }
            
            // Set the content
            resultsElement.textContent = formattedContent;
            
            // Set execution time if available
            if (executionTimeElement && data.execution_time) {
                executionTimeElement.textContent = `Processing time: ${data.execution_time.toFixed(2)}s`;
            } else if (executionTimeElement) {
                executionTimeElement.textContent = '';
            }
            
            // Show the result card
            resultCard.classList.remove('d-none');
            
            // Scroll to the results
            resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    };
    
    // Function to start the simulated progress animation
    window.startProgressAnimation = function(extractionType, fastMode) {
        const progressBar = document.getElementById('processing-progress');
        
        if (progressBar) {
            progressBar.style.width = '0%';
            
            const duration = fastMode ? 1500 : 3000; // Fast mode is faster
            const steps = 100;
            const interval = duration / steps;
            
            let current = 0;
            
            const animation = setInterval(() => {
                current += 1;
                
                // Simulate a non-linear progress
                let progress;
                if (current <= 20) {
                    // Start slow (initial loading)
                    progress = current * 0.5;
                } else if (current <= 80) {
                    // Middle is faster (processing)
                    progress = 10 + (current - 20) * 1.0;
                } else {
                    // End slows down again (saving results)
                    progress = 70 + (current - 80) * 0.3;
                }
                
                // Max progress is 90% for simulated animation
                // The last 10% is added when we get the result
                progress = Math.min(progress, 90);
                
                progressBar.style.width = `${progress}%`;
                
                if (current >= steps) {
                    clearInterval(animation);
                }
            }, interval);
        }
    };
    
    // Function to cycle through fun messages during processing
    window.startMessageCycling = function(extractionType, fastMode) {
        const messageElement = document.getElementById('processing-message');
        
        // Different message sets based on extraction type
        const messages = {
            text: [
                "Scanning those tiny letters...",
                "Reading between the lines...",
                "Extracting all the words...",
                "Finding those important paragraphs...",
                "Organizing the text content..."
            ],
            structured: [
                "Analyzing document structure...",
                "Detecting headings and sections...",
                "Identifying tables and lists...",
                "Mapping document hierarchy...",
                "Building structured content..."
            ],
            ocr: [
                "Warming up the OCR engine...",
                "Teaching the computer to read...",
                "Converting images to text...",
                "Deciphering those scanned pages...",
                "Recognizing characters and words..."
            ]
        };
        
        // Choose the right message set
        const messageSet = messages[extractionType] || messages.text;
        
        // Set initial message
        if (messageElement) {
            messageElement.textContent = messageSet[0];
            
            // Determine cycle speed based on fast mode
            const interval = fastMode ? 2000 : 3500;
            
            let index = 1;
            
            // Cycle through messages
            const messageInterval = setInterval(() => {
                if (index < messageSet.length) {
                    messageElement.textContent = messageSet[index];
                    index++;
                } else {
                    // Stop cycling after going through all messages once
                    clearInterval(messageInterval);
                }
            }, interval);
            
            // Store the interval ID on the window to clear it later if needed
            window.currentMessageInterval = messageInterval;
        }
    };
});
