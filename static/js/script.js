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
        } else if (e.target.id === 'download1080pBtn') {
            // This button is removed, so this block is no longer needed.
        } else if (e.target.id === 'downloadFileBtn') {
            downloadFile();
        } else if (e.target.id === 'newDownloadBtn') {
            resetApp();
        }
    });
});

// Analyze video function
async function analyzeVideo() {
    const url = videoUrlInput.value.trim();
    
    if (!url) {
        showError('Please enter a YouTube URL');
        return;
    }
    
    console.log('Analyzing URL:', url); // Debug log
    
    // Show loading state
    hideAllSections();
    showSection(loadingSection);
    
    try {
        // Try alternative method first (no yt-dlp)
        console.log('Trying alternative video analysis...');
        let response = await fetch('/get_video_info_alternative', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        console.log('Alternative response status:', response.status); // Debug log
        
        // If alternative fails, try the original route
        if (!response.ok) {
            console.log('Alternative route failed, trying original route...');
            response = await fetch('/get_video_info', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ url: url })
            });
            console.log('Original response status:', response.status); // Debug log
        }
        
        console.log('Final response status:', response.status); // Debug log
        console.log('Response headers:', response.headers); // Debug log
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            // Get the raw text to see what we're actually getting
            const rawText = await response.text();
            console.error('Non-JSON response received:', rawText);
            throw new Error(`Server returned ${contentType || 'unknown content type'}. Expected JSON.`);
        }
        
        const data = await response.json();
        console.log('Response data:', data); // Debug log
        
        if (!response.ok) {
            throw new Error(data.error || 'Failed to analyze video');
        }
        
        // Store video info
        currentVideoInfo = data;
        
        // Display video information
        displayVideoInfo(data);
        
    } catch (error) {
        console.error('Error in analyzeVideo:', error); // Debug log
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
    
    console.log('Received formats:', formats); // Debug log
    
    // If no formats provided, show default options
    if (!formats || formats.length === 0) {
        const defaultFormats = [
            { format_id: 'best', height: 720, ext: 'mp4', format_note: 'Best quality available' },
            { format_id: 'worst', height: 360, ext: 'mp4', format_note: 'Lower quality (smaller file)' }
        ];
        createFormatOptions(defaultFormats);
        return;
    }
    
    // Filter formats - be more inclusive
    const videoFormats = formats.filter(format => 
        format.height && format.format_id
    );
    
    console.log('Filtered formats:', videoFormats); // Debug log
    
    // If still no formats after filtering, use all available formats
    if (videoFormats.length === 0) {
        createFormatOptions(formats);
        return;
    }
    
    // Remove duplicates based on height and format_id
    const uniqueFormats = [];
    const seen = new Set();
    
    videoFormats.forEach(format => {
        const key = `${format.height}p_${format.format_id}`;
        if (!seen.has(key)) {
            seen.add(key);
            uniqueFormats.push(format);
        }
    });
    
    console.log('Unique formats:', uniqueFormats); // Debug log
    createFormatOptions(uniqueFormats);
}

// Helper function to create format option elements
function createFormatOptions(formats) {
    const formatOptionsContainer = document.getElementById('formatOptions');
    
    formats.forEach((format, index) => {
        const formatOption = document.createElement('div');
        formatOption.className = 'format-option';
        formatOption.dataset.formatId = format.format_id;
        
        // Add special class for 1080p
        if (format.height === 1080) {
            formatOption.classList.add('format-1080p');
        }
        
        const filesize = format.filesize ? formatFileSize(format.filesize) : 'Unknown size';
        const height = format.height || 'Unknown';
        const ext = format.ext || 'mp4';
        const formatNote = format.format_note || 'Standard quality';
        const fps = format.fps ? `${format.fps}fps` : '';
        const bitrate = format.tbr ? `${Math.round(format.tbr)}kbps` : '';
        
        // Create a more informative description
        let description = `${filesize}`;
        if (fps) description += ` • ${fps}`;
        if (bitrate) description += ` • ${bitrate}`;
        description += ` • ${formatNote}`;
        
        formatOption.innerHTML = `
            <h5>${height}p ${ext.toUpperCase()}</h5>
            <p>${description}${format.is_video_only ? ' • Video Only' : ''}</p>
        `;
        
        formatOption.addEventListener('click', () => selectFormat(formatOption, format));
        formatOptionsContainer.appendChild(formatOption);
        
        // Select the first (highest quality) format by default
        if (index === 0) {
            selectFormat(formatOption, format);
        }
    });
    
    // If no formats were created, add a default option
    if (formats.length === 0) {
        const defaultOption = document.createElement('div');
        defaultOption.className = 'format-option';
        defaultOption.dataset.formatId = 'best';
        defaultOption.innerHTML = `
            <h5>Best Quality</h5>
            <p>Unknown size • Best available quality</p>
        `;
        defaultOption.addEventListener('click', () => selectFormat(defaultOption, { format_id: 'best' }));
        formatOptionsContainer.appendChild(defaultOption);
        selectFormat(defaultOption, { format_id: 'best' });
    }
}

// Select format
function selectFormat(formatElement, format) {
    // Remove previous selection
    document.querySelectorAll('.format-option').forEach(option => {
        option.classList.remove('selected');
    });
    
    // Select new format
    formatElement.classList.add('selected');
    selectedFormat = format.format_id;
    
    // Enable download button
    const downloadBtn = document.getElementById('downloadBtn');
    downloadBtn.disabled = false;
}

// Download video
async function downloadVideo() {
    if (!currentVideoInfo || !selectedFormat) {
        showError('Please select a video format');
        return;
    }
    
    console.log('[Download] Selected format_id:', selectedFormat); // Debug log
    
    hideAllSections();
    showSection(downloadProgress);
    
    try {
        // Use alternative download method (no yt-dlp)
        console.log('Using alternative download method...');
        const response = await fetch('/download_video_alternative', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: videoUrlInput.value.trim(),
                format_id: selectedFormat
            })
        });
        
        console.log('[Download] Response status:', response.status); // Debug log
        console.log('[Download] Response headers:', response.headers); // Debug log
        
        // Check if response is JSON
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            // Get the raw text to see what we're actually getting
            const rawText = await response.text();
            console.error('[Download] Non-JSON response received:', rawText);
            throw new Error(`Server returned ${contentType || 'unknown content type'}. Expected JSON.`);
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Download failed');
        }
        
        // Show download complete
        showDownloadComplete(data);
        
    } catch (error) {
        console.error('[Download] Error:', error); // Debug log
        showError(error.message);
    }
}

// Show download complete
function showDownloadComplete(downloadData) {
    hideAllSections();
    showSection(downloadComplete);
    
    document.getElementById('downloadFileName').textContent = downloadData.filename;
    
    // Store filename for download
    document.getElementById('downloadFileBtn').dataset.filename = downloadData.filename;
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

// Add some visual feedback for better UX
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
        
        // Reset button after a delay (will be overridden by actual response)
        setTimeout(() => {
            this.innerHTML = '<i class="fas fa-search"></i> Analyze';
            this.disabled = false;
        }, 5000);
    });
}); 