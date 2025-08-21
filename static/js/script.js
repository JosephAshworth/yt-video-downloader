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

// Authentication elements
const cookiesFileInput = document.getElementById('cookiesFile');
const uploadCookiesBtn = document.getElementById('uploadCookiesBtn');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const setCredentialsBtn = document.getElementById('setCredentialsBtn');
const checkAuthBtn = document.getElementById('checkAuthBtn');
const clearAuthBtn = document.getElementById('clearAuthBtn');
const cookiesStatus = document.getElementById('cookiesStatus');
const credentialsStatus = document.getElementById('credentialsStatus');

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    analyzeBtn.addEventListener('click', analyzeVideo);
    videoUrlInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            analyzeVideo();
        }
    });
    
    // Authentication event listeners
    uploadCookiesBtn.addEventListener('click', uploadCookies);
    setCredentialsBtn.addEventListener('click', setCredentials);
    checkAuthBtn.addEventListener('click', checkAuthStatus);
    clearAuthBtn.addEventListener('click', clearAuth);
    
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
    
    // Check authentication status on page load
    checkAuthStatus();
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
        const response = await fetch('/get_video_info', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ url: url })
        });
        
        console.log('Response status:', response.status); // Debug log
        
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
        const response = await fetch('/download_video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                url: videoUrlInput.value.trim(),
                format_id: selectedFormat
            })
        });
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || 'Download failed');
        }
        
        // Show download complete
        showDownloadComplete(data);
        
    } catch (error) {
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

// Authentication functions
async function uploadCookies() {
    const file = cookiesFileInput.files[0];
    if (!file) {
        showAuthStatus(cookiesStatus, 'Please select a cookies file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('cookies_file', file);
    
    try {
        uploadCookiesBtn.disabled = true;
        uploadCookiesBtn.textContent = 'Uploading...';
        
        const response = await fetch('/upload_cookies', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAuthStatus(cookiesStatus, data.message, 'success');
            checkAuthStatus(); // Refresh status
        } else {
            showAuthStatus(cookiesStatus, data.error, 'error');
        }
    } catch (error) {
        showAuthStatus(cookiesStatus, 'Upload failed: ' + error.message, 'error');
    } finally {
        uploadCookiesBtn.disabled = false;
        uploadCookiesBtn.innerHTML = '<i class="fas fa-upload"></i> Upload Cookies';
    }
}

async function setCredentials() {
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    
    if (!username || !password) {
        showAuthStatus(credentialsStatus, 'Please enter both username and password', 'error');
        return;
    }
    
    try {
        setCredentialsBtn.disabled = true;
        setCredentialsBtn.textContent = 'Setting...';
        
        const response = await fetch('/set_credentials', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAuthStatus(credentialsStatus, data.message, 'success');
            usernameInput.value = '';
            passwordInput.value = '';
            checkAuthStatus(); // Refresh status
        } else {
            showAuthStatus(credentialsStatus, data.error, 'error');
        }
    } catch (error) {
        showAuthStatus(credentialsStatus, 'Failed to set credentials: ' + error.message, 'error');
    } finally {
        setCredentialsBtn.disabled = false;
        setCredentialsBtn.innerHTML = '<i class="fas fa-save"></i> Set Credentials';
    }
}

async function checkAuthStatus() {
    try {
        const response = await fetch('/auth_status');
        const data = await response.json();
        
        if (response.ok) {
            updateAuthUI(data);
        } else {
            console.error('Failed to check auth status:', data.error);
        }
    } catch (error) {
        console.error('Error checking auth status:', error);
    }
}

async function clearAuth() {
    if (!confirm('Are you sure you want to clear all authentication data?')) {
        return;
    }
    
    try {
        clearAuthBtn.disabled = true;
        clearAuthBtn.textContent = 'Clearing...';
        
        const response = await fetch('/clear_auth', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showAuthStatus(cookiesStatus, 'Cookies cleared', 'success');
            showAuthStatus(credentialsStatus, 'Credentials cleared', 'success');
            checkAuthStatus(); // Refresh status
        } else {
            console.error('Failed to clear auth:', data.error);
        }
    } catch (error) {
        console.error('Error clearing auth:', error);
    } finally {
        clearAuthBtn.disabled = false;
        clearAuthBtn.innerHTML = '<i class="fas fa-trash"></i> Clear Auth';
    }
}

function updateAuthUI(authData) {
    // Update cookies status
    if (authData.cookies_configured) {
        showAuthStatus(cookiesStatus, '✅ Cookies configured and working', 'success');
    } else {
        showAuthStatus(cookiesStatus, '❌ No cookies configured', 'info');
    }
    
    // Update credentials status
    if (authData.credentials_configured) {
        showAuthStatus(credentialsStatus, '✅ Credentials configured', 'success');
    } else {
        showAuthStatus(credentialsStatus, '❌ No credentials configured', 'info');
    }
    
    // Update overall auth status
    if (authData.authenticated) {
        document.querySelector('.auth-section').classList.add('authenticated');
    } else {
        document.querySelector('.auth-section').classList.remove('authenticated');
    }
}

function showAuthStatus(element, message, type) {
    element.textContent = message;
    element.className = `auth-status ${type}`;
    
    // Auto-clear success messages after 5 seconds
    if (type === 'success') {
        setTimeout(() => {
            element.textContent = '';
            element.className = 'auth-status';
        }, 5000);
    }
} 