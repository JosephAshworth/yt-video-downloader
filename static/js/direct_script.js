// Global variables
let currentVideoInfo = null;
let selectedFormat = null;

// DOM elements
const videoUrlInput = document.getElementById('videoUrl');
const analyzeBtn = document.getElementById('analyzeBtn');
const loadingSection = document.getElementById('loadingSection');
const errorSection = document.getElementById('errorSection');
const videoInfoSection = document.getElementById('videoInfoSection');
const downloadProgress = document.getElementById('downloadProgress');
const downloadComplete = document.getElementById('downloadComplete');

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    analyzeBtn.addEventListener('click', analyzeVideo);
    videoUrlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            analyzeVideo();
        }
    });
    
    // Download button event listener will be added dynamically
    document.addEventListener('click', function(e) {
        if (e.target.id === 'downloadBtn') {
            downloadVideo();
        } else if (e.target.id === 'downloadFileBtn') {
            downloadFile();
        } else if (e.target.id === 'newDownloadBtn') {
            resetApp();
        }
    });
});

// Analyze video function using direct method
async function analyzeVideo() {
    const url = videoUrlInput.value.trim();
    
    if (!url) {
        showError('Please enter a YouTube URL');
        return;
    }
    
    console.log('Analyzing URL with direct method:', url);
    
    // Show loading state
    hideAllSections();
    showSection(loadingSection);
    
    try {
        const response = await fetch('/get_video_info_direct', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        console.log('Response status:', response.status);
        
        const data = await response.json();
        console.log('Response data:', data);
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to analyze video');
        }
        
        // Store video info
        currentVideoInfo = data;
        
        // Display video information
        displayVideoInfo(data);
        
    } catch (error) {
        console.error('Error in analyzeVideo:', error);
        showError(error.message);
    }
}

// Display video information
function displayVideoInfo(videoInfo) {
    hideAllSections();
    showSection(videoInfoSection);
    
    // Set video details
    document.getElementById('videoTitle').textContent = videoInfo.title;
    document.getElementById('videoThumbnail').src = videoInfo.thumbnail;
    document.getElementById('videoDuration').textContent = formatDuration(videoInfo.duration);
    document.getElementById('videoId').textContent = `ID: ${videoInfo.video_id}`;
    
    // Populate format options
    populateFormatOptions(videoInfo.formats);
}

// Populate format options
function populateFormatOptions(formats) {
    const formatOptionsContainer = document.getElementById('formatOptions');
    formatOptionsContainer.innerHTML = '';
    
    if (!formats || formats.length === 0) {
        formatOptionsContainer.innerHTML = '<p class="no-formats">No video formats available</p>';
        return;
    }
    
    formats.forEach(format => {
        const formatOption = document.createElement('div');
        formatOption.className = 'format-option';
        formatOption.dataset.formatId = format.format_id;
        
        const quality = format.height ? `${format.height}p` : 'Unknown';
        const size = format.filesize ? formatFileSize(format.filesize) : 'Unknown size';
        const type = format.type || 'Unknown';
        
        formatOption.innerHTML = `
            <div class="format-info">
                <div class="format-quality">${quality}</div>
                <div class="format-details">
                    <span class="format-type">${type}</span>
                    <span class="format-size">${size}</span>
                    <span class="format-note">${format.format_note || ''}</span>
                </div>
            </div>
            <div class="format-selector">
                <input type="radio" name="format" id="format_${format.format_id}" value="${format.format_id}">
                <label for="format_${format.format_id}">Select</label>
            </div>
        `;
        
        formatOptionsContainer.appendChild(formatOption);
        
        // Add event listener for format selection
        const radio = formatOption.querySelector('input[type="radio"]');
        radio.addEventListener('change', function() {
            if (this.checked) {
                selectedFormat = format;
                document.getElementById('downloadBtn').disabled = false;
                
                // Update visual selection
                document.querySelectorAll('.format-option').forEach(opt => {
                    opt.classList.remove('selected');
                });
                formatOption.classList.add('selected');
            }
        });
    });
}

// Download video function using direct method
async function downloadVideo() {
    if (!currentVideoInfo || !selectedFormat) {
        showError('Please select a video format first');
        return;
    }
    
    console.log('Downloading with direct method:', selectedFormat.format_id);
    
    // Show download progress
    hideAllSections();
    showSection(downloadProgress);
    
    try {
        const response = await fetch('/download_video_direct', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: videoUrlInput.value.trim(),
                format_id: selectedFormat.format_id
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Download failed');
        }
        
        // Show download complete
        showDownloadComplete(data);
        
    } catch (error) {
        console.error('Error in downloadVideo:', error);
        showError(error.message);
    }
}

// Show download complete
function showDownloadComplete(data) {
    hideAllSections();
    showSection(downloadComplete);
    
    document.getElementById('downloadFileName').textContent = data.filename;
    
    // Store filename for download button
    const downloadFileBtn = document.getElementById('downloadFileBtn');
    downloadFileBtn.dataset.filename = data.filename;
}

// Download file
function downloadFile() {
    const filename = document.getElementById('downloadFileBtn').dataset.filename;
    if (filename) {
        window.open(`/download_file/${encodeURIComponent(filename)}`, '_blank');
    }
}

// Reset app
function resetApp() {
    hideAllSections();
    showSection(document.querySelector('.input-section').parentElement);
    
    // Clear form
    videoUrlInput.value = '';
    
    // Reset variables
    currentVideoInfo = null;
    selectedFormat = null;
    
    // Reset download button
    document.getElementById('downloadBtn').disabled = true;
    
    // Clear format selection
    document.querySelectorAll('.format-option').forEach(opt => {
        opt.classList.remove('selected');
    });
}

// Show error
function showError(message) {
    hideAllSections();
    showSection(errorSection);
    document.getElementById('errorMessage').textContent = message;
}

// Show section
function showSection(section) {
    section.classList.remove('hidden');
}

// Hide section
function hideSection(section) {
    section.classList.add('hidden');
}

// Hide all sections
function hideAllSections() {
    const sections = [
        loadingSection,
        errorSection,
        videoInfoSection,
        downloadProgress,
        downloadComplete
    ];
    
    sections.forEach(section => hideSection(section));
}

// Utility functions
function formatDuration(seconds) {
    if (!seconds) return 'Unknown duration';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}

function formatFileSize(bytes) {
    if (!bytes) return 'Unknown size';
    
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    
    if (i === 0) return bytes + ' ' + sizes[i];
    return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + sizes[i];
}

// Add visual feedback
document.addEventListener('DOMContentLoaded', function() {
    // Add focus effect to URL input
    videoUrlInput.addEventListener('focus', function() {
        this.parentElement.style.transform = 'scale(1.02)';
    });
    
    videoUrlInput.addEventListener('blur', function() {
        this.parentElement.style.transform = 'scale(1)';
    });
    
    // Add loading state to analyze button
    analyzeBtn.addEventListener('click', function() {
        this.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Analyzing...';
        this.disabled = true;
        
        // Reset button after a delay
        setTimeout(() => {
            this.innerHTML = '<i class="fas fa-search"></i> Analyze';
            this.disabled = false;
        }, 5000);
    });
});
