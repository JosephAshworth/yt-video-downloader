from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import yt_dlp
import os
import re
import tempfile
import random
import time
import json
import hashlib
from urllib.parse import urlparse, parse_qs
import subprocess
from werkzeug.security import generate_password_hash, check_password_hash
import requests
import re
import json
import base64
import urllib.parse

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Configure folders
UPLOAD_FOLDER = 'downloads'
COOKIES_FOLDER = 'cookies'
USERS_FOLDER = 'users'

for folder in [UPLOAD_FOLDER, COOKIES_FOLDER, USERS_FOLDER]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Simple user class for authentication
class User(UserMixin):
    def __init__(self, user_id, username, cookies_file=None):
        self.id = user_id
        self.username = username
        self.cookies_file = cookies_file

# In-memory user storage (in production, use a database)
users = {}

@login_manager.user_loader
def load_user(user_id):
    return users.get(user_id)

def save_user_data():
    """Save user data to file"""
    user_data = {}
    for user_id, user in users.items():
        user_data[user_id] = {
            'username': user.username,
            'cookies_file': user.cookies_file
        }
    
    with open(os.path.join(USERS_FOLDER, 'users.json'), 'w') as f:
        json.dump(user_data, f)

def load_user_data():
    """Load user data from file"""
    users_file = os.path.join(USERS_FOLDER, 'users.json')
    if os.path.exists(users_file):
        with open(users_file, 'r') as f:
            user_data = json.load(f)
            for user_id, data in user_data.items():
                users[user_id] = User(user_id, data['username'], data.get('cookies_file'))

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

def get_random_user_agent():
    """Get a random user agent to avoid detection"""
    user_agents = [
        # Chrome variants
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
        
        # Firefox variants
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7; rv:109.0) Gecko/20100101 Firefox/121.0',
        
        # Safari variants
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        
        # Edge variants
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/119.0.0.0',
        
        # Mobile variants (sometimes work better)
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 14; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
    ]
    return random.choice(user_agents)

def get_headers_for_user_agent(user_agent):
    """Get appropriate headers for a given user agent"""
    if 'Chrome' in user_agent:
        return {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
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
            'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'Sec-Ch-Ua-Mobile': '?0',
            'Sec-Ch-Ua-Platform': '"Windows"',
        }
    elif 'Firefox' in user_agent:
        return {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
        }
    else:  # Safari/Edge fallback
        return {
            'User-Agent': user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

def generate_fake_cookies():
    """Generate fake cookies to appear more like a real browser session"""
    import hashlib
    import time
    
    # Generate fake session ID
    session_id = hashlib.md5(str(time.time()).encode()).hexdigest()[:16]
    
    # Generate fake visitor data
    visitor_id = hashlib.md5(f"visitor_{time.time()}".encode()).hexdigest()[:20]
    
    cookies = {
        'VISITOR_INFO1_LIVE': visitor_id,
        'LOGIN_INFO': f'AFmmF2swRQKj{hashlib.md5(session_id.encode()).hexdigest()[:20]}',
        'SID': session_id,
        'HSID': hashlib.md5(f"hsid_{time.time()}".encode()).hexdigest()[:20],
        'SSID': hashlib.md5(f"ssid_{time.time()}".encode()).hexdigest()[:20],
        'APISID': hashlib.md5(f"apisid_{time.time()}".encode()).hexdigest()[:20],
        'SAPISID': hashlib.md5(f"sapisid_{time.time()}".encode()).hexdigest()[:20],
        '__Secure-1PSID': hashlib.md5(f"1psid_{time.time()}".encode()).hexdigest()[:20],
        '__Secure-3PSID': hashlib.md5(f"3psid_{time.time()}".encode()).hexdigest()[:20],
    }
    
    return cookies

def get_enhanced_headers_for_user_agent(user_agent):
    """Get enhanced headers with cookies and additional bot avoidance"""
    base_headers = get_headers_for_user_agent(user_agent)
    
    # Add fake cookies
    cookies = generate_fake_cookies()
    cookie_string = '; '.join([f'{k}={v}' for k, v in cookies.items()])
    
    # Enhanced headers
    enhanced_headers = base_headers.copy()
    enhanced_headers.update({
        'Cookie': cookie_string,
        'Referer': 'https://www.youtube.com/',
        'Origin': 'https://www.youtube.com',
        'Sec-Fetch-Site': 'same-origin',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Dest': 'empty',
        'X-Requested-With': 'XMLHttpRequest',
        'X-Client-Data': 'CIa2yQEIo7bJAQipncoBCKijygEIkqHLAQiFoM0BCJyrzQEI8KvNAQj4q80BCIqszQEIq6zNAQ==',
    })
    
    return enhanced_headers

def simulate_human_behavior():
    """Simulate human-like behavior with random delays and patterns"""
    # Random delay between 1-5 seconds
    delay = random.uniform(1, 5)
    time.sleep(delay)
    
    # Sometimes add extra delay (20% chance)
    if random.random() < 0.2:
        extra_delay = random.uniform(2, 8)
        time.sleep(extra_delay)
    
    # Return a random "thinking time" for the next request
    return random.uniform(0.5, 3.0)

def get_yt_dlp_options_with_advanced_bot_avoidance():
    """Get yt-dlp options with the most advanced bot avoidance techniques"""
    user_agent = get_random_user_agent()
    headers = get_enhanced_headers_for_user_agent(user_agent)
    
    # Simulate human behavior
    simulate_human_behavior()
    
    return {
        'user_agent': user_agent,
        'http_headers': headers,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'retries': 15,  # More aggressive retries
        'fragment_retries': 15,
        'sleep_interval': 5,  # Longer delays
        'max_sleep_interval': 15,
        'sleep_interval_requests': 3,
        'socket_timeout': 45,  # Longer timeout
        'extractor_retries': 8,
        'http_chunk_size': 5242880,  # Smaller chunks (5MB)
        'buffersize': 1024,  # Smaller buffer
        'prefer_ffmpeg': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        # Additional bot avoidance
        'no_color': True,  # Less suspicious output
        'quiet': False,
        'verbose': False,  # Less verbose to avoid detection
        'no_warnings': True,
        'extract_flat': False,
        'force_generic_extractor': False,
        'allow_unplayable_formats': False,
        'ignore_no_formats_error': False,
        'extractor_args': {
            'youtube': {
                'skip': ['dash', 'live_chat'],
                'player_client': ['android', 'web'],
                'player_skip': ['webpage', 'configs'],
            }
        }
    }

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

@app.route('/test')
def test():
    """Test route to check if the app is working"""
    return jsonify({
        'status': 'ok',
        'message': 'YouTube Downloader is running',
        'timestamp': '2024-01-18'
    })

@app.route('/test_bot_avoidance')
def test_bot_avoidance():
    """Test route to check bot avoidance techniques"""
    user_agent = get_random_user_agent()
    headers = get_headers_for_user_agent(user_agent)
    enhanced_headers = get_enhanced_headers_for_user_agent(user_agent)
    
    return jsonify({
        'status': 'ok',
        'message': 'Bot avoidance test',
        'user_agent': user_agent,
        'basic_headers': headers,
        'enhanced_headers': enhanced_headers,
        'timestamp': '2024-01-18'
    })

@app.route('/test_youtube_access')
def test_youtube_access():
    """Test different YouTube access methods"""
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
    
    results = []
    
    # Test 1: Direct stream extraction (no yt-dlp, no cookies)
    try:
        video_info, error = extract_video_streams_direct(test_url)
        if error:
            results.append({
                'method': 'Direct Stream Extraction',
                'success': False,
                'error': error
            })
        else:
            results.append({
                'method': 'Direct Stream Extraction',
                'success': True,
                'title': video_info.get('title', 'Unknown'),
                'duration': video_info.get('duration', 0),
                'formats': len(video_info.get('formats', []))
            })
    except Exception as e:
        results.append({
            'method': 'Direct Stream Extraction',
            'success': False,
            'error': str(e)
        })
    
    # Test 2: Basic yt-dlp approach
    try:
        basic_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        with yt_dlp.YoutubeDL(basic_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            results.append({
                'method': 'Basic yt-dlp',
                'success': True,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0)
            })
    except Exception as e:
        results.append({
            'method': 'Basic yt-dlp',
            'success': False,
            'error': str(e)
        })
    
    # Test 3: Advanced bot avoidance
    try:
        advanced_opts = get_yt_dlp_options_with_advanced_bot_avoidance()
        advanced_opts['extract_flat'] = True
        with yt_dlp.YoutubeDL(advanced_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            results.append({
                'method': 'Advanced Bot Avoidance',
                'success': True,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0)
            })
    except Exception as e:
        results.append({
            'method': 'Advanced Bot Avoidance',
            'success': False,
            'error': str(e)
        })
    
    return jsonify({
        'status': 'ok',
        'message': 'YouTube access test results',
        'results': results,
        'timestamp': '2024-01-18'
    })

@app.route('/auth_status')
def auth_status():
    """Check authentication status"""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'username': current_user.username,
            'has_cookies': bool(current_user.cookies_file and os.path.exists(current_user.cookies_file)),
            'cookies_file': current_user.cookies_file
        })
    else:
        return jsonify({
            'authenticated': False,
            'message': 'User not authenticated'
        })

@app.route('/direct')
def direct_download():
    """Direct download page (no authentication required)"""
    return render_template('direct_download.html')

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if user exists
        user = None
        for u in users.values():
            if u.username == username:
                user = u
                break
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # Check if username already exists
        for u in users.values():
            if u.username == username:
                flash('Username already exists')
                return render_template('register.html')
        
        # Create new user
        user_id = str(len(users) + 1)
        password_hash = generate_password_hash(password)
        user = User(user_id, username)
        user.password_hash = password_hash
        users[user_id] = user
        
        save_user_data()
        flash('Registration successful! Please log in.')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/upload_cookies', methods=['GET', 'POST'])
@login_required
def upload_cookies():
    if request.method == 'POST':
        if 'cookies_file' not in request.files:
            flash('No file selected')
            return redirect(request.url)
        
        file = request.files['cookies_file']
        if file.filename == '':
            flash('No file selected')
            return redirect(request.url)
        
        if file and file.filename.endswith('.txt'):
            # Save cookies file
            filename = f"cookies_{current_user.username}.txt"
            filepath = os.path.join(COOKIES_FOLDER, filename)
            file.save(filepath)
            
            # Update user's cookies file
            current_user.cookies_file = filepath
            save_user_data()
            
            flash('Cookies uploaded successfully!')
            return redirect(url_for('index'))
        else:
            flash('Please upload a .txt file')
    
    return render_template('upload_cookies.html')

@app.route('/get_video_info', methods=['POST'])
@login_required
def get_video_info():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        # Check if user has cookies
        if not current_user.cookies_file or not os.path.exists(current_user.cookies_file):
            return jsonify({'error': 'Please upload your YouTube cookies first. Go to Upload Cookies in the menu.'}), 401
        
        # Use user's cookies for authentication
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'cookiefile': current_user.cookies_file,  # Use user's cookies
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'nocheckcertificate': True,
            'ignoreerrors': False,
        }
        
        # Extract video info using user's cookies
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            print(f"Error extracting video info: {str(e)}")
            if 'cookies' in str(e).lower() or 'authentication' in str(e).lower():
                return jsonify({'error': 'Your cookies may have expired. Please re-upload your YouTube cookies.'}), 401
            else:
                return jsonify({'error': f'Error extracting video info: {str(e)}'}), 500
        
        # Get available formats and filter for actual video formats (allow video-only for higher qualities)
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
            
            print(f"Found {len(unique_formats)} video formats")  # Debug print
            for f in unique_formats:
                print(f"  - {f['height']}p {f['ext']} ({f['format_id']})")  # Debug print
            
            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'formats': unique_formats,
                'video_id': extract_video_id(url)
            })
            
    except Exception as e:
        print(f"Error in get_video_info: {str(e)}")  # Debug print
        return jsonify({'error': f'Error extracting video info: {str(e)}'}), 500

@app.route('/download_video', methods=['POST'])
@login_required
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
        
        # Check if user has cookies
        if not current_user.cookies_file or not os.path.exists(current_user.cookies_file):
            return jsonify({'error': 'Please upload your YouTube cookies first. Go to Upload Cookies in the menu.'}), 401
        
        # Use user's cookies for authentication
        ydl_opts = {
            'format': f'{format_id}+bestaudio/best',  # Use selected format + best audio, more reliable
            'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s_%(format_id)s.mp4'),  # Output as MP4
            'quiet': False,  # Show more output for debugging
            'no_warnings': False,  # Show warnings
            'verbose': True,  # Add verbose output for debugging
            'merge_output_format': 'mp4',  # Force MP4 output
            'skip': ['storyboard', 'image'],
            'extractaudio': False,
            'audioformat': None,
            'cookiefile': current_user.cookies_file,  # Use user's cookies
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'retries': 3,
            'fragment_retries': 3,
            'prefer_ffmpeg': True,
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        print(f"[Download] Using format_id: {format_id}")
        print(f"[Download] Full format string: {format_id}+bestaudio/best")
        
        # Download video using user's cookies
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # First, extract info to validate the format
                info = ydl.extract_info(url, download=False)
                print(f"Video title: {info.get('title', 'Unknown')}")
                print(f"Available formats: {len(info.get('formats', []))}")
                
                # Download the video with the selected format
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
        except Exception as e:
            print(f"Error downloading video: {str(e)}")
            if 'cookies' in str(e).lower() or 'authentication' in str(e).lower():
                return jsonify({'error': 'Your cookies may have expired. Please re-upload your YouTube cookies.'}), 401
            else:
                return jsonify({'error': f'Error downloading video: {str(e)}'}), 500
            
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

def extract_video_streams_direct(url):
    """Extract video streams directly from YouTube without yt-dlp"""
    try:
        # Get the video page
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        # Extract video info from the page
        html_content = response.text
        
        # Find ytInitialPlayerResponse
        player_response_match = re.search(r'ytInitialPlayerResponse\s*=\s*({.+?});', html_content)
        if not player_response_match:
            return None, "Could not find video player response"
        
        player_response = json.loads(player_response_match.group(1))
        
        # Extract video details
        video_details = player_response.get('videoDetails', {})
        streaming_data = player_response.get('streamingData', {})
        
        if not streaming_data:
            return None, "No streaming data available"
        
        # Get available formats
        formats = []
        
        # Add progressive formats (video + audio combined)
        if 'formats' in streaming_data:
            for fmt in streaming_data['formats']:
                if fmt.get('url') and fmt.get('height'):
                    formats.append({
                        'format_id': fmt.get('itag', 'unknown'),
                        'height': fmt.get('height', 0),
                        'ext': 'mp4',
                        'filesize': fmt.get('contentLength', 0),
                        'format_note': f"Progressive {fmt.get('height')}p",
                        'url': fmt.get('url'),
                        'type': 'progressive'
                    })
        
        # Add adaptive formats (separate video/audio)
        if 'adaptiveFormats' in streaming_data:
            for fmt in streaming_data['adaptiveFormats']:
                if fmt.get('url') and fmt.get('height') and fmt.get('mimeType', '').startswith('video/'):
                    formats.append({
                        'format_id': fmt.get('itag', 'unknown'),
                        'height': fmt.get('height', 0),
                        'ext': 'mp4',
                        'filesize': fmt.get('contentLength', 0),
                        'format_note': f"Adaptive {fmt.get('height')}p",
                        'url': fmt.get('url'),
                        'type': 'adaptive'
                    })
        
        # Sort by height
        formats.sort(key=lambda x: x['height'], reverse=True)
        
        return {
            'title': video_details.get('title', 'Unknown Title'),
            'duration': int(video_details.get('lengthSeconds', 0)),
            'thumbnail': f"https://i.ytimg.com/vi/{extract_video_id(url)}/maxresdefault.jpg",
            'formats': formats,
            'video_id': extract_video_id(url)
        }, None
        
    except Exception as e:
        return None, f"Error extracting streams: {str(e)}"

def download_video_direct(url, format_id, output_path):
    """Download video directly using the stream URL"""
    try:
        # First get the video info
        video_info, error = extract_video_streams_direct(url)
        if error:
            return False, error
        
        # Find the requested format
        selected_format = None
        for fmt in video_info['formats']:
            if str(fmt['format_id']) == str(format_id):
                selected_format = fmt
                break
        
        if not selected_format:
            return False, f"Format {format_id} not found"
        
        # Download the video
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        }
        
        response = requests.get(selected_format['url'], headers=headers, stream=True, timeout=300)
        response.raise_for_status()
        
        # Save the file
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        return True, "Download completed successfully"
        
    except Exception as e:
        return False, f"Download error: {str(e)}"

@app.route('/get_video_info_direct', methods=['POST'])
def get_video_info_direct():
    """Get video info using direct stream extraction"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        # Extract video info directly
        video_info, error = extract_video_streams_direct(url)
        
        if error:
            return jsonify({'error': error}), 500
        
        return jsonify(video_info)
        
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500

@app.route('/download_video_direct', methods=['POST'])
def download_video_direct_route():
    """Download video using direct stream extraction"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        format_id = data.get('format_id', 'best')
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        # Create output filename
        video_info, error = extract_video_streams_direct(url)
        if error:
            return jsonify({'error': error}), 500
        
        # Find the selected format
        selected_format = None
        for fmt in video_info['formats']:
            if str(fmt['format_id']) == str(format_id):
                selected_format = fmt
                break
        
        if not selected_format:
            return jsonify({'error': f'Format {format_id} not found'}), 400
        
        # Generate filename
        safe_title = "".join(c for c in video_info['title'] if c.isalnum() or c in (' ', '-', '_')).rstrip()
        filename = f"{safe_title}_{format_id}.mp4"
        output_path = os.path.join(UPLOAD_FOLDER, filename)
        
        # Download the video
        success, message = download_video_direct(url, format_id, output_path)
        
        if success:
            file_size = os.path.getsize(output_path)
            return jsonify({
                'success': True,
                'filename': filename,
                'filepath': output_path,
                'title': video_info['title'],
                'filesize': file_size,
                'selected_quality': f"{selected_format['height']}p",
                'message': message
            })
        else:
            return jsonify({'error': message}), 500
        
    except Exception as e:
        return jsonify({'error': f'Error: {str(e)}'}), 500

if __name__ == '__main__':
    # Load user data on startup
    load_user_data()
    
    # Use environment variables for production deployment
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(
        debug=debug,
        host='0.0.0.0',  # Allow external connections
        port=port
    ) 