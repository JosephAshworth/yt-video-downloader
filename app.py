import os
import json
import time
import random
import requests
from flask import Flask, request, jsonify, send_file, render_template
import yt_dlp
from datetime import datetime, timedelta
import hashlib
import pickle

app = Flask(__name__)

# Configuration
UPLOAD_FOLDER = 'downloads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Session storage for persistent cookies and user agents
SESSIONS_FILE = 'youtube_sessions.pkl'
USER_AGENTS_FILE = 'user_agents.pkl'

# Load or create persistent sessions
def load_sessions():
    """Load persistent YouTube sessions to simulate local browser behavior"""
    try:
        if os.path.exists(SESSIONS_FILE):
            with open(SESSIONS_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Error loading sessions: {e}")
    
    # Create new session with realistic browser data
    return {
        'cookies': {},
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'last_request': None,
        'request_count': 0,
        'session_id': hashlib.md5(str(time.time()).encode()).hexdigest()[:8]
    }

def save_sessions(sessions):
    """Save persistent YouTube sessions"""
    try:
        with open(SESSIONS_FILE, 'wb') as f:
            pickle.dump(sessions, f)
    except Exception as e:
        print(f"Error saving sessions: {e}")

def load_user_agents():
    """Load realistic user agents that work locally"""
    try:
        if os.path.exists(USER_AGENTS_FILE):
            with open(USER_AGENTS_FILE, 'rb') as f:
                return pickle.load(f)
    except Exception as e:
        print(f"Error loading user agents: {e}")
    
    # Realistic user agents that work locally
    return [
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    ]

def save_user_agents(user_agents):
    """Save user agents"""
    try:
        with open(USER_AGENTS_FILE, 'wb') as f:
            pickle.dump(user_agents, f)
    except Exception as e:
        print(f"Error saving user agents: {e}")

def simulate_human_behavior():
    """Simulate human-like behavior patterns"""
    # Random delay between requests (like human browsing)
    time.sleep(random.uniform(1, 3))
    
    # Random mouse movement simulation
    mouse_x = random.randint(100, 800)
    mouse_y = random.randint(100, 600)
    
    return {
        'mouse_x': mouse_x,
        'mouse_y': mouse_y,
        'timestamp': time.time()
    }

def get_realistic_headers(sessions):
    """Get headers that exactly match local browser behavior"""
    user_agent = sessions['user_agent']
    
    # Headers that work locally
    headers = {
        'User-Agent': user_agent,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'sec-ch-ua-platform-version': '"13.0.0"',
        'sec-ch-ua-model': '""',
        'sec-ch-ua-arch': '"x86"',
        'sec-ch-ua-bitness': '"64"',
        'sec-ch-ua-full-version': '"120.0.6099.129"',
        'sec-ch-ua-full-version-list': '"Not_A Brand";v="8.0.0.0", "Chromium";v="120.0.6099.129", "Google Chrome";v="120.0.6099.129"',
        'sec-ch-ua-wow64': '?0'
    }
    
    # Add referer if we have previous requests
    if sessions.get('last_request'):
        headers['Referer'] = sessions['last_request']
    
    return headers

def create_local_like_session():
    """Create a session that behaves exactly like local browser"""
    sessions = load_sessions()
    user_agents = load_user_agents()
    
    # Use the same user agent consistently (like local browser)
    if not sessions.get('user_agent') or random.random() < 0.1:  # 10% chance to rotate
        sessions['user_agent'] = random.choice(user_agents)
        save_sessions(sessions)
    
    # Simulate human behavior
    behavior = simulate_human_behavior()
    
    # Update session
    sessions['last_request'] = 'https://www.youtube.com/'
    sessions['request_count'] += 1
    sessions['last_behavior'] = behavior
    
    save_sessions(sessions)
    return sessions

# Initialize global sessions
GLOBAL_SESSIONS = create_local_like_session()

def is_valid_youtube_url(url):
    """Check if the URL is a valid YouTube URL"""
    youtube_regex = (
        r'(https?://)?(www\.)?'
        r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
        r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})')
    
    youtube_regex_match = re.match(youtube_regex, url)
    return bool(youtube_regex_match)

def extract_video_id(url):
    """Extract video ID from YouTube URL"""
    parsed_url = urlparse(url)
    if parsed_url.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed_url.path == '/watch':
            return parse_qs(parsed_url.query)['v'][0]
    elif parsed_url.hostname == 'youtu.be':
        return parsed_url.path[1:]
    return None

def convert_mp4_to_mov(input_file):
    """Convert MP4 file to MOV format using FFmpeg"""
    try:
        # Create output filename
        output_file = input_file.replace('.mp4', '.mov')
        
        # FFmpeg command to convert MP4 to MOV (preserves quality)
        cmd = [
            'ffmpeg', '-i', input_file, 
            '-c', 'copy',  # Copy streams without re-encoding (preserves quality)
            '-f', 'mov',   # Force MOV format
            output_file
        ]
        
        print(f"[Conversion] Converting {input_file} to {output_file}...")
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode == 0:
            # Remove the original MP4 file
            os.remove(input_file)
            print(f"[Conversion] Successfully converted to {output_file}")
            return output_file
        else:
            print(f"[Conversion] FFmpeg conversion failed: {result.stderr}")
            return input_file  # Return original file if conversion fails
            
    except FileNotFoundError:
        print("[Conversion] FFmpeg not found - keeping original MP4 file")
        return input_file
    except Exception as e:
        print(f"[Conversion] Conversion error: {str(e)}")
        return input_file

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    """Extract video information from YouTube URL using local-like behavior"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url or not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        # Use local-like session (same as what works locally)
        sessions = create_local_like_session()
        print(f"[LOCAL MODE] Using session ID: {sessions['session_id']}")
        print(f"[LOCAL MODE] User Agent: {sessions['user_agent']}")
        print(f"[LOCAL MODE] Request count: {sessions['request_count']}")
        
        # Method 1: Local-like approach (replicates exact local behavior)
        try:
            print(f"[LOCAL MODE] Method 1: Local browser simulation...")
            ydl_opts = {
                'quiet': False,  # Show output like local
                'no_warnings': False,  # Show warnings like local
                'extract_flat': False,
                # Use exact same settings that work locally
                'nocheckcertificate': False,  # Don't skip certs like local
                'no_check_certificate': False,
                'ignoreerrors': False,
                'extractor_retries': 1,  # Minimal retries like local
                'retries': 1,
                'fragment_retries': 1,
                'http_chunk_size': 1048576,  # Small chunks like local
                'sleep_interval': 0,  # No artificial delays like local
                'max_sleep_interval': 0,
                # Use the exact user agent that works locally
                'user_agent': sessions['user_agent'],
                # Use realistic headers that work locally
                'http_headers': get_realistic_headers(sessions),
                # Don't use aggressive bypass - use normal approach like local
                'cookiefile': None,
                'cookiesfrombrowser': None,
                # Use normal extractor settings like local
                'extractor_args': {
                    'youtube': {
                        'skip': ['storyboard', 'image'],  # Only skip obvious non-video
                        'player_client': ['web'],  # Use web client like local
                        'player_skip': [],  # Don't skip anything like local
                    }
                },
                # Use normal format selection like local
                'format': 'best[ext=mp4]/best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and info.get('title'):
                    print(f"[LOCAL MODE] Success! Title: {info.get('title')}")
                    # Update session with successful request
                    sessions['last_request'] = url
                    sessions['successful_requests'] = sessions.get('successful_requests', 0) + 1
                    save_sessions(sessions)
                    return _process_video_info(info, url)
                    
        except Exception as e:
            print(f"[LOCAL MODE] Method 1 failed: {str(e)}")
            print(f"[LOCAL MODE] Error type: {type(e).__name__}")
        
        # Method 2: Fallback to local browser cookies approach
        try:
            print(f"[LOCAL MODE] Method 2: Browser cookies simulation...")
            ydl_opts = {
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                # Use browser-like settings
                'nocheckcertificate': False,
                'no_check_certificate': False,
                'ignoreerrors': False,
                'extractor_retries': 1,
                'retries': 1,
                'fragment_retries': 1,
                'http_chunk_size': 1048576,
                'sleep_interval': 0,
                'max_sleep_interval': 0,
                # Use consistent user agent
                'user_agent': sessions['user_agent'],
                # Use realistic headers
                'http_headers': get_realistic_headers(sessions),
                # Try to use browser cookies (like local)
                'cookiesfrombrowser': ('chrome', 'firefox', 'safari'),
                'cookiefile': None,
                # Normal extractor settings
                'extractor_args': {
                    'youtube': {
                        'skip': ['storyboard', 'image'],
                        'player_client': ['web'],
                        'player_skip': [],
                    }
                },
                'format': 'best[ext=mp4]/best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and info.get('title'):
                    print(f"[LOCAL MODE] Method 2 successful: {info.get('title')}")
                    sessions['last_request'] = url
                    sessions['successful_requests'] = sessions.get('successful_requests', 0) + 1
                    save_sessions(sessions)
                    return _process_video_info(info, url)
                    
        except Exception as e:
            print(f"[LOCAL MODE] Method 2 failed: {str(e)}")
            print(f"[LOCAL MODE] Error type: {type(e).__name__}")
        
        # Method 3: Minimal local approach (like when local fails)
        try:
            print(f"[LOCAL MODE] Method 3: Minimal local approach...")
            ydl_opts = {
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                # Minimal settings like local
                'nocheckcertificate': False,
                'no_check_certificate': False,
                'ignoreerrors': False,
                'extractor_retries': 1,
                'retries': 1,
                'fragment_retries': 1,
                'http_chunk_size': 1048576,
                'sleep_interval': 0,
                'max_sleep_interval': 0,
                # Keep same user agent
                'user_agent': sessions['user_agent'],
                # Minimal headers
                'http_headers': {
                    'User-Agent': sessions['user_agent'],
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.youtube.com/',
                },
                'cookiefile': None,
                'cookiesfrombrowser': None,
                # Very basic format
                'format': 'best',
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info and info.get('title'):
                    print(f"[LOCAL MODE] Method 3 successful: {info.get('title')}")
                    sessions['last_request'] = url
                    sessions['successful_requests'] = sessions.get('successful_requests', 0) + 1
                    save_sessions(sessions)
                    return _process_video_info(info, url)
                    
        except Exception as e:
            print(f"[LOCAL MODE] Method 3 failed: {str(e)}")
            print(f"[LOCAL MODE] Error type: {type(e).__name__}")
        
        # All local methods failed - this is unusual
        print(f"[LOCAL MODE] All local simulation methods failed for URL: {url}")
        print(f"[LOCAL MODE] This suggests YouTube may have updated their system")
        
        # Update session with failure
        sessions['failed_requests'] = sessions.get('failed_requests', 0) + 1
        sessions['last_error'] = str(e)
        save_sessions(sessions)
        
        return jsonify({
            'error': 'Local simulation methods failed. This is unusual and may indicate YouTube has updated their system.',
            'suggestion': 'Try again in a few minutes or check if YouTube is experiencing issues',
            'session_info': {
                'session_id': sessions['session_id'],
                'user_agent': sessions['user_agent'],
                'successful_requests': sessions.get('successful_requests', 0),
                'failed_requests': sessions.get('failed_requests', 0),
                'total_requests': sessions['request_count']
            },
            'debug_info': {
                'url': url,
                'video_id': extract_video_id(url),
                'timestamp': datetime.now().isoformat()
            }
        }), 500
        
    except Exception as e:
        print(f"Error in get_video_info: {str(e)}")
        return jsonify({'error': f'Error extracting video info: {str(e)}'}), 500

def _process_video_info(info, url):
    """Process extracted video info and return formatted response"""
    try:
        # Get available formats and filter for actual video formats
        formats = []
        for f in info.get('formats', []):
            # Include all video formats (both with and without audio)
            if (f.get('height') and f.get('ext') and 
                f.get('vcodec') and f.get('vcodec') != 'none' and
                f.get('height') >= 144 and  # Minimum reasonable video height
                f.get('protocol') != 'mhtml' and  # Skip MHTML formats
                not f.get('ext') in ['html', 'htm', 'mhtml'] and
                f.get('ext') in ['mp4', 'webm', 'mkv', 'avi', 'mov']):  # Only video formats
                
                # Check if this is video-only (no audio)
                is_video_only = f.get('acodec') == 'none' or not f.get('acodec')
                
                formats.append({
                    'format_id': f.get('format_id', ''),
                    'height': f.get('height', 0),
                    'ext': f.get('ext', ''),
                    'filesize': f.get('filesize', 0),
                    'format_note': f.get('format_note', ''),
                    'vcodec': f.get('vcodec', ''),
                    'acodec': f.get('acodec', ''),
                    'fps': f.get('fps', 0),
                    'tbr': f.get('tbr', 0),  # Total bitrate
                    'protocol': f.get('protocol', ''),
                    'is_video_only': is_video_only
                })
        
        # If no video formats found, try to get best available
        if not formats:
            # Look for any format with video
            for f in info.get('formats', []):
                if (f.get('height') and f.get('vcodec') and 
                    f.get('vcodec') != 'none' and f.get('height') >= 144 and
                    f.get('protocol') != 'mhtml'):
                    formats.append({
                        'format_id': f.get('format_id', ''),
                        'height': f.get('height', 0),
                        'ext': f.get('ext', 'mp4'),
                        'filesize': f.get('filesize', 0),
                        'format_note': f.get('format_note', 'Video format'),
                        'vcodec': f.get('vcodec', ''),
                        'acodec': f.get('acodec', ''),
                        'fps': f.get('fps', 0),
                        'tbr': f.get('tbr', 0),
                        'protocol': f.get('protocol', '')
                    })
        
        # Sort formats by height (quality) and then by bitrate
        formats.sort(key=lambda x: (x['height'], x.get('tbr', 0)), reverse=True)
        
        # Remove duplicates based on height, but keep the best quality for each height
        unique_formats = []
        seen_heights = set()
        for f in formats:
            if f['height'] not in seen_heights:
                seen_heights.add(f['height'])
                unique_formats.append(f)
        
        # Ensure we have at least one format - use yt-dlp's best format
        if not unique_formats:
            unique_formats = [{
                'format_id': 'best[ext=mp4]/best',  # Prefer MP4, fallback to best
                'height': 720,
                'ext': 'mp4',
                'filesize': 0,
                'format_note': 'Best available quality (auto-selected)',
                'vcodec': 'unknown',
                'acodec': 'unknown',
                'fps': 0,
                'tbr': 0,
                'protocol': 'unknown'
            }]
        
        print(f"Found {len(unique_formats)} video formats")
        for f in unique_formats:
            print(f"  - {f['height']}p {f['ext']} ({f['format_id']})")
        
        return jsonify({
            'title': info.get('title', 'Unknown Title'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'formats': unique_formats,
            'video_id': extract_video_id(url)
        })
        
    except Exception as e:
        print(f"Error processing video info: {str(e)}")
        return jsonify({'error': f'Error processing video info: {str(e)}'}), 500

@app.route('/download_video', methods=['POST'])
def download_video():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        format_id = data.get('format_id', 'best')
        print(f"[Backend] Received format_id: {format_id}")  # Debug log
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        # Configure yt-dlp options for download using local-like behavior
        sessions = create_local_like_session()
        print(f"[LOCAL MODE] Download using session ID: {sessions['session_id']}")
        
        ydl_opts = {
            'format': f'{format_id}+bestaudio/best',  # Use selected format + best audio
            'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s_%(format_id)s.mp4'),  # Output as MP4
            'quiet': False,  # Show output like local
            'no_warnings': False,  # Show warnings like local
            'merge_output_format': 'mp4',  # Force MP4 output
            'skip': ['storyboard', 'image'],
            'extractaudio': False,
            'audioformat': None,
            'nocheckcertificate': False,  # Don't skip certs like local
            'ignoreerrors': False,
            'verbose': True,  # Add verbose output for debugging
            # Use local-like settings
            'user_agent': sessions['user_agent'],
            'http_headers': get_realistic_headers(sessions),
            'retries': 1,  # Minimal retries like local
            'fragment_retries': 1,
            'http_chunk_size': 1048576,  # Small chunks like local
            'sleep_interval': 0,  # No artificial delays like local
            'max_sleep_interval': 0,
            # Better format handling
            'prefer_ffmpeg': True,  # Use FFmpeg for better merging
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',  # Ensure proper MP4 output
            }],
        }
        
        print(f"[Download] Using format_id: {format_id}")
        print(f"[Download] Full format string: {format_id}+bestaudio/best")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First, extract info to validate the format
            info = ydl.extract_info(url, download=False)
            print(f"Video title: {info.get('title', 'Unknown')}")
            print(f"Available formats: {len(info.get('formats', []))}")
            
            # Download the video with the selected format
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            print(f"[Download] Expected filename: {filename}")
            print(f"[Download] Selected format_id: {format_id}")
            
            # Verify the downloaded format matches what was requested
            downloaded_info = ydl.extract_info(url, download=False)
            selected_format = None
            for f in downloaded_info.get('formats', []):
                if f.get('format_id') == format_id:
                    selected_format = f
                    break
            
            if selected_format:
                print(f"[Download] Selected format details: {selected_format.get('height')}p, {selected_format.get('ext')}, {selected_format.get('format_note', '')}")
                print(f"[Download] Selected format bitrate: {selected_format.get('tbr', 'Unknown')} kbps")
                print(f"[Download] Selected format filesize: {selected_format.get('filesize', 'Unknown')} bytes")
            else:
                print(f"[Download] WARNING: Could not find format_id {format_id} in available formats")
            
            # Check if the downloaded file is actually a video
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                file_ext = os.path.splitext(filename)[1].lower()
                
                print(f"Downloaded file: {filename}, size: {file_size}, ext: {file_ext}")
                print(f"[Download] File size comparison: Downloaded={file_size}, Expected={selected_format.get('filesize', 'Unknown') if selected_format else 'Unknown'}")
                
                # Check for invalid file types
                invalid_extensions = ['.mhtml', '.html', '.htm', '.jpg', '.png', '.webp', '.gif']
                if file_ext in invalid_extensions:
                    os.remove(filename)
                    return jsonify({'error': f'Downloaded file is {file_ext.upper()}, not a video. Please try a different quality option.'}), 500
                
                # If file is too small, it might be invalid
                if file_size < 1000000:  # Less than 1MB
                    os.remove(filename)
                    return jsonify({'error': 'Downloaded file is too small to be a valid video. Please try a different quality option.'}), 500
                
                # Check if file size is much smaller than expected (quality issue)
                if selected_format and selected_format.get('filesize'):
                    expected_size = selected_format.get('filesize')
                    size_ratio = file_size / expected_size
                    print(f"[Download] Size ratio: Downloaded/Expected = {size_ratio:.2f}")
                    if size_ratio < 0.5:  # If downloaded file is less than 50% of expected size
                        print(f"[Download] WARNING: Downloaded file is much smaller than expected - quality may be compromised")
                
                return jsonify({
                    'success': True,
                    'filename': os.path.basename(filename),
                    'filepath': filename,
                    'title': info.get('title', 'Unknown Title'),
                    'filesize': file_size,
                    'selected_quality': f"{selected_format.get('height', 'Unknown')}p" if selected_format else 'Unknown',
                    'expected_size': selected_format.get('filesize', 'Unknown') if selected_format else 'Unknown'
                })
            else:
                # Try fallback download with simpler format
                print(f"[Download] First attempt failed, trying fallback download...")
                fallback_opts = {
                    'format': 'best[ext=mp4]/best',  # Simpler format selection
                    'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s_fallback.mp4'),
                    'quiet': False,
                    'verbose': True,
                }
                
                with yt_dlp.YoutubeDL(fallback_opts) as fallback_ydl:
                    fallback_info = fallback_ydl.extract_info(url, download=True)
                    fallback_filename = fallback_ydl.prepare_filename(fallback_info)
                    
                    if os.path.exists(fallback_filename):
                        file_size = os.path.getsize(fallback_filename)
                        print(f"[Download] Fallback successful: {fallback_filename}, size: {file_size}")
                        return jsonify({
                            'success': True,
                            'filename': os.path.basename(fallback_filename),
                            'filepath': fallback_filename,
                            'title': info.get('title', 'Unknown Title'),
                            'filesize': file_size,
                            'selected_quality': 'Fallback quality (best available)',
                            'expected_size': 'Unknown'
                        })
                    else:
                        return jsonify({'error': 'Both download attempts failed'}), 500
                
    except Exception as e:
        print(f"Error in download_video: {str(e)}")  # Debug print
        return jsonify({'error': f'Error downloading video: {str(e)}'}), 500

@app.route('/download_1080p', methods=['POST'])
def download_1080p():
    """Specific route for 1080p downloads"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        # Configure yt-dlp options specifically for 1080p
        ydl_opts = {
            'format': 'best[height<=1080][ext=mp4]/best[height<=1080]/best[ext=mp4]/best',
            'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s_1080p.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'skip': ['storyboard', 'image'],
            'extractaudio': False,
            'audioformat': None,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'format_sort': ['res:1080', 'res:720', 'res:480'],
            'format_sort_force': True,
        }
        
        print(f"Downloading 1080p version of: {url}")  # Debug print
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First, extract info to validate the format
            info = ydl.extract_info(url, download=False)
            print(f"Video title: {info.get('title', 'Unknown')}")
            
            # Check if 1080p is available
            formats = info.get('formats', [])
            has_1080p = any(f.get('height') == 1080 for f in formats)
            print(f"1080p available: {has_1080p}")
            
            # Download the video
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Check if the downloaded file is actually a video
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                file_ext = os.path.splitext(filename)[1].lower()
                
                print(f"Downloaded file: {filename}, size: {file_size}, ext: {file_ext}")
                
                # Check for invalid file types
                invalid_extensions = ['.mhtml', '.html', '.htm', '.jpg', '.png', '.webp', '.gif']
                if file_ext in invalid_extensions:
                    os.remove(filename)
                    return jsonify({'error': f'Downloaded file is {file_ext.upper()}, not a video.'}), 500
                
                # If file is too small, it might be invalid
                if file_size < 1000000:  # Less than 1MB
                    os.remove(filename)
                    return jsonify({'error': 'Downloaded file is too small to be a valid video.'}), 500
                
                return jsonify({
                    'success': True,
                    'filename': os.path.basename(filename),
                    'filepath': filename,
                    'title': info.get('title', 'Unknown Title'),
                    'filesize': file_size,
                    'quality': '1080p' if has_1080p else 'Best available'
                })
            else:
                return jsonify({'error': 'Download failed - file not found'}), 500
                
    except Exception as e:
        print(f"Error in download_1080p: {str(e)}")
        return jsonify({'error': f'Error downloading 1080p video: {str(e)}'}), 500

@app.route('/download_file/<filename>')
def download_file(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error serving file: {str(e)}'}), 500

@app.route('/cleanup/<filename>', methods=['DELETE'])
def cleanup_file(filename):
    try:
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error deleting file: {str(e)}'}), 500

@app.route('/test_download', methods=['POST'])
def test_download():
    """Test route to download with simple format selection"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        format_id = data.get('format_id', 'best')
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        # Simple format selection
        ydl_opts = {
            'format': format_id,
            'outtmpl': os.path.join(UPLOAD_FOLDER, 'test_%(title)s_%(format_id)s.mov'),
            'merge_output_format': 'mov',
            'quiet': False,
            'no_warnings': False,
        }
        
        print(f"[Test Download] Using format_id: {format_id}")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            if os.path.exists(filename):
                file_size = os.path.getsize(filename)
                return jsonify({
                    'success': True,
                    'filename': os.path.basename(filename),
                    'filesize': file_size,
                    'format_id': format_id
                })
            else:
                return jsonify({'error': 'Test download failed'}), 500
                
    except Exception as e:
        print(f"Error in test_download: {str(e)}")
        return jsonify({'error': f'Test download error: {str(e)}'}), 500

@app.route('/test_format', methods=['POST'])
def test_format():
    """Test route to download with a specific format and show detailed information"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        format_id = data.get('format_id', 'best')
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        print(f"[Test Format] Testing format_id: {format_id}")
        
        # First, get format info
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Find the specific format
            target_format = None
            for f in info.get('formats', []):
                if f.get('format_id') == format_id:
                    target_format = f
                    break
            
            if not target_format:
                return jsonify({'error': f'Format {format_id} not found'})
            
            print(f"[Test Format] Found format: {target_format.get('height')}p, {target_format.get('ext')}, {target_format.get('format_note', '')}")
            print(f"[Test Format] Bitrate: {target_format.get('tbr', 'Unknown')} kbps")
            print(f"[Test Format] Filesize: {target_format.get('filesize', 'Unknown')} bytes")
            print(f"[Test Format] Codec: {target_format.get('vcodec', 'Unknown')}")
            
            # Try to download just this format
            test_ydl_opts = {
                'format': format_id,
                'outtmpl': os.path.join(UPLOAD_FOLDER, 'test_%(title)s_%(format_id)s.%(ext)s'),
                'quiet': False,
                'verbose': True,
            }
            
            with yt_dlp.YoutubeDL(test_ydl_opts) as test_ydl:
                test_info = test_ydl.extract_info(url, download=True)
                test_filename = test_ydl.prepare_filename(test_info)
                
                if os.path.exists(test_filename):
                    file_size = os.path.getsize(test_filename)
                    return jsonify({
                        'success': True,
                        'filename': os.path.basename(test_filename),
                        'filesize': file_size,
                        'format_info': {
                            'height': target_format.get('height'),
                            'ext': target_format.get('ext'),
                            'bitrate': target_format.get('tbr'),
                            'expected_size': target_format.get('filesize'),
                            'codec': target_format.get('vcodec')
                        }
                    })
                else:
                    return jsonify({'error': 'Test download failed'})
                    
    except Exception as e:
        print(f"Error in test_format: {str(e)}")
        return jsonify({'error': f'Test format error: {str(e)}'}), 500

@app.route('/debug_formats', methods=['POST'])
def debug_formats():
    """Debug route to see all available formats for a URL"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            all_formats = []
            for f in info.get('formats', []):
                all_formats.append({
                    'format_id': f.get('format_id', ''),
                    'height': f.get('height', 0),
                    'ext': f.get('ext', ''),
                    'filesize': f.get('filesize', 0),
                    'format_note': f.get('format_note', ''),
                    'vcodec': f.get('vcodec', ''),
                    'acodec': f.get('acodec', ''),
                    'protocol': f.get('protocol', ''),
                    'url': f.get('url', '')[:100] + '...' if f.get('url') else '',
                    'is_video_only': f.get('acodec') == 'none' or not f.get('acodec'),
                    'tbr': f.get('tbr', 0),
                    'fps': f.get('fps', 0)
                })
            
            # Sort by height for easier reading
            all_formats.sort(key=lambda x: x['height'], reverse=True)
            
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'formats': all_formats,
                'total_formats': len(all_formats),
                'video_id': extract_video_id(url)
            })
            
    except Exception as e:
        return jsonify({'error': f'Debug error: {str(e)}'}), 500

@app.route('/test_auth_bypass')
def test_auth_bypass():
    """Test authentication bypass methods"""
    try:
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
        
        print(f"[Auth Test] Testing authentication bypass with URL: {test_url}")
        
        # Test 1: Standard method
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'nocheckcertificate': True,
                'no_check_certificate': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.youtube.com/',
                },
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
                if info and info.get('title'):
                    print(f"[Auth Test] Standard method successful: {info.get('title')}")
                    return jsonify({
                        'status': 'success',
                        'message': 'Authentication bypass is working',
                        'method': 'Standard with headers',
                        'title': info.get('title', 'Unknown'),
                        'formats_count': len(info.get('formats', [])),
                        'timestamp': '2024-01-18'
                    })
        except Exception as e:
            print(f"[Auth Test] Standard method failed: {str(e)}")
        
        # Test 2: Mobile user agent
        try:
            mobile_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'nocheckcertificate': True,
                'no_check_certificate': True,
                'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Referer': 'https://www.youtube.com/',
                },
            }
            
            with yt_dlp.YoutubeDL(mobile_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
                if info and info.get('title'):
                    print(f"[Auth Test] Mobile method successful: {info.get('title')}")
                    return jsonify({
                        'status': 'success',
                        'message': 'Mobile authentication bypass is working',
                        'method': 'Mobile user agent',
                        'title': info.get('title', 'Unknown'),
                        'formats_count': len(info.get('formats', [])),
                        'timestamp': '2024-01-18'
                    })
        except Exception as e:
            print(f"[Auth Test] Mobile method failed: {str(e)}")
        
        # Test 3: Linux user agent
        try:
            linux_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'nocheckcertificate': True,
                'no_check_certificate': True,
                'user_agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': '*/*',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Referer': 'https://www.youtube.com/',
                },
            }
            
            with yt_dlp.YoutubeDL(linux_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
                if info and info.get('title'):
                    print(f"[Auth Test] Linux method successful: {info.get('title')}")
                    return jsonify({
                        'status': 'success',
                        'message': 'Linux authentication bypass is working',
                        'method': 'Linux user agent',
                        'title': info.get('title', 'Unknown'),
                        'formats_count': len(info.get('formats', [])),
                        'timestamp': '2024-01-18'
                    })
        except Exception as e:
            print(f"[Auth Test] Linux method failed: {str(e)}")
        
        return jsonify({
            'status': 'failed',
            'message': 'All authentication bypass methods failed',
            'methods_tried': ['Standard', 'Mobile', 'Linux'],
            'suggestion': 'YouTube may have updated their anti-bot measures',
            'timestamp': '2024-01-18'
        }), 500
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': '2024-01-18'
        }), 500

@app.route('/session_status')
def session_status():
    """View current session status and debug information"""
    try:
        sessions = load_sessions()
        user_agents = load_user_agents()
        
        return jsonify({
            'status': 'success',
            'current_session': {
                'session_id': sessions.get('session_id', 'Unknown'),
                'user_agent': sessions.get('user_agent', 'Unknown'),
                'request_count': sessions.get('request_count', 0),
                'successful_requests': sessions.get('successful_requests', 0),
                'failed_requests': sessions.get('failed_requests', 0),
                'last_request': sessions.get('last_request', 'None'),
                'last_error': sessions.get('last_error', 'None'),
                'last_behavior': sessions.get('last_behavior', {}),
                'created_at': sessions.get('created_at', 'Unknown')
            },
            'available_user_agents': user_agents,
            'session_file': SESSIONS_FILE,
            'user_agents_file': USER_AGENTS_FILE,
            'timestamp': datetime.now().isoformat(),
            'local_mode': True
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/reset_session')
def reset_session():
    """Reset the current session to start fresh"""
    try:
        # Remove session files
        if os.path.exists(SESSIONS_FILE):
            os.remove(SESSIONS_FILE)
        if os.path.exists(USER_AGENTS_FILE):
            os.remove(USER_AGENTS_FILE)
        
        # Create new session
        global GLOBAL_SESSIONS
        GLOBAL_SESSIONS = create_local_like_session()
        
        return jsonify({
            'status': 'success',
            'message': 'Session reset successfully',
            'new_session_id': GLOBAL_SESSIONS['session_id'],
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 