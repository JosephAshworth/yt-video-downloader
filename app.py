from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
import tempfile
import random
import time
from urllib.parse import urlparse, parse_qs
import subprocess

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'downloads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

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
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
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
    
    return jsonify({
        'status': 'ok',
        'message': 'Bot avoidance test',
        'user_agent': user_agent,
        'headers': headers,
        'timestamp': '2024-01-18'
    })

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    try:
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        # Configure yt-dlp options for info extraction with bot avoidance
        user_agent = get_random_user_agent()
        headers = get_headers_for_user_agent(user_agent)
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            # Bot avoidance for info extraction
            'user_agent': user_agent,
            'http_headers': headers,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'retries': 5,
            'fragment_retries': 5,
            'sleep_interval': 2,
            'max_sleep_interval': 8,
        }
        
        # Retry mechanism with exponential backoff for bot detection
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    break  # Success, exit retry loop
            except Exception as e:
                error_msg = str(e).lower()
                if 'bot' in error_msg or 'sign in' in error_msg or '403' in error_msg:
                    print(f"[Bot Detection] Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        print(f"[Bot Detection] Waiting {retry_delay} seconds before retry...")
                        time.sleep(retry_delay)
                        # Rotate user agent for next attempt
                        user_agent = get_random_user_agent()
                        headers = get_headers_for_user_agent(user_agent)
                        ydl_opts['user_agent'] = user_agent
                        ydl_opts['http_headers'] = headers
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        print(f"[Bot Detection] All retry attempts failed")
                        return jsonify({'error': 'YouTube is blocking automated access. Please try again later or use a different video.'}), 429
                else:
                    # Non-bot related error, don't retry
                    raise e
        
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
        
        # Configure yt-dlp options for download with advanced bot avoidance
        user_agent = get_random_user_agent()
        headers = get_headers_for_user_agent(user_agent)
        
        ydl_opts = {
            'format': f'{format_id}+bestaudio/best',  # Use selected format + best audio, more reliable
            'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s_%(format_id)s.mp4'),  # Output as MP4
            'quiet': False,  # Show more output for debugging
            'no_warnings': False,  # Show warnings
            'merge_output_format': 'mp4',  # Force MP4 output
            'skip': ['storyboard', 'image'],
            'extractaudio': False,
            'audioformat': None,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'verbose': True,  # Add verbose output for debugging
            
            # Advanced bot avoidance techniques
            'user_agent': user_agent,
            'http_headers': headers,
            
            # Enhanced retry and delay settings
            'retries': 10,  # More retries for bot detection
            'fragment_retries': 10,  # More fragment retries
            'http_chunk_size': 10485760,  # 10MB chunks
            'sleep_interval': 3,  # Longer sleep between requests
            'max_sleep_interval': 10,  # Maximum sleep interval
            'sleep_interval_requests': 2,  # Sleep between requests
            
            # Additional bot avoidance
            'socket_timeout': 30,  # Longer socket timeout
            'extractor_retries': 5,  # Retry extractor failures
            
            # Better format handling
            'prefer_ffmpeg': True,  # Use FFmpeg for better merging
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',  # Ensure proper MP4 output
            }],
        }
        
        print(f"[Download] Using format_id: {format_id}")
        print(f"[Download] Full format string: {format_id}+bestaudio/best")
        
        # Retry mechanism with exponential backoff for bot detection during download
        max_retries = 3
        retry_delay = 3
        
        for attempt in range(max_retries):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    # First, extract info to validate the format
                    info = ydl.extract_info(url, download=False)
                    print(f"Video title: {info.get('title', 'Unknown')}")
                    print(f"Available formats: {len(info.get('formats', []))}")
                    
                    # Download the video with the selected format
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    break  # Success, exit retry loop
            except Exception as e:
                error_msg = str(e).lower()
                if 'bot' in error_msg or 'sign in' in error_msg or '403' in error_msg:
                    print(f"[Download Bot Detection] Attempt {attempt + 1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        print(f"[Download Bot Detection] Waiting {retry_delay} seconds before retry...")
                        time.sleep(retry_delay)
                        # Rotate user agent for next attempt
                        user_agent = get_random_user_agent()
                        headers = get_headers_for_user_agent(user_agent)
                        ydl_opts['user_agent'] = user_agent
                        ydl_opts['http_headers'] = headers
                        retry_delay *= 2  # Exponential backoff
                        continue
                    else:
                        print(f"[Download Bot Detection] All retry attempts failed")
                        return jsonify({'error': 'YouTube is blocking downloads. Please try again later or use a different video.'}), 429
                else:
                    # Non-bot related error, don't retry
                    raise e
            
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

if __name__ == '__main__':
    # Use environment variables for production deployment
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    app.run(
        debug=debug,
        host='0.0.0.0',  # Allow external connections
        port=port
    ) 