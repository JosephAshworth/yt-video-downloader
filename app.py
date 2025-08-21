from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
import tempfile
from urllib.parse import urlparse, parse_qs
import subprocess
import requests
import json
import time

app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'downloads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Environment detection
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'
IS_RENDER = os.environ.get('RENDER') == 'true'
IS_HEROKU = os.environ.get('DYNO') is not None

print(f"[Environment] Flask app initialized")
print(f"[Environment] IS_PRODUCTION: {IS_PRODUCTION}")
print(f"[Environment] IS_RENDER: {IS_RENDER}")
print(f"[Environment] IS_HEROKU: {IS_HEROKU}")
print(f"[Environment] Working directory: {os.getcwd()}")
print(f"[Environment] Downloads folder: {UPLOAD_FOLDER}")

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

def extract_video_info_direct(url):
    """Extract video info directly from YouTube without yt-dlp"""
    try:
        video_id = extract_video_id(url)
        if not video_id:
            return None, "Invalid YouTube URL"
        
        # Method 1: Try to get info from YouTube's oEmbed API
        oembed_url = f"https://www.youtube.com/oembed?url={url}&format=json"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Referer': 'https://www.youtube.com/',
        }
        
        try:
            response = requests.get(oembed_url, headers=headers, timeout=30)
            if response and response.status_code == 200:
                oembed_data = response.json()
                if isinstance(oembed_data, dict) and oembed_data.get('title'):
                    return {
                        'title': oembed_data.get('title', 'Unknown Title'),
                        'author_name': oembed_data.get('author_name', 'Unknown'),
                        'thumbnail_url': oembed_data.get('thumbnail_url', ''),
                        'video_id': video_id,
                        'method': 'oEmbed API'
                    }, None
        except Exception as e:
            print(f"[Direct] oEmbed API failed: {str(e)}")
        
        # Method 2: Try to extract from page HTML
        page_url = f"https://www.youtube.com/watch?v={video_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.youtube.com/',
        }
        
        try:
            response = requests.get(page_url, headers=headers, timeout=30)
            if response and response.status_code == 200:
                html_content = response.text
                
                # Try to extract title from HTML
                title_match = re.search(r'<title>(.*?)</title>', html_content)
                title = title_match.group(1).replace(' - YouTube', '') if title_match else 'Unknown Title'
                
                # Try to extract thumbnail
                thumbnail_match = re.search(r'"thumbnailUrl":"([^"]+)"', html_content)
                thumbnail = thumbnail_match.group(1) if thumbnail_match else f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
                
                return {
                    'title': title,
                    'author_name': 'Unknown',
                    'thumbnail_url': thumbnail,
                    'video_id': video_id,
                    'method': 'HTML extraction'
                }, None
        except Exception as e:
            print(f"[Direct] HTML extraction failed: {str(e)}")
        
        return None, "Could not extract video info"
        
    except Exception as e:
        return None, f"Error extracting video info: {str(e)}"

def get_invidious_instances():
    """Get list of working Invidious instances"""
    try:
        # Try to get instances from invidious.io
        response = requests.get('https://api.invidious.io/instances.json', timeout=10)
        if response and response.status_code == 200:
            instances = response.json()
            # Filter for working instances
            working_instances = [
                instance['uri'] for instance in instances 
                if isinstance(instance, dict) and
                instance.get('type') == 'https' and 
                instance.get('monitoring', {}).get('status') == 'healthy'
            ]
            if working_instances:
                print(f"[Invidious] Found {len(working_instances)} working instances")
                return working_instances[:5]  # Return top 5 working instances
    except Exception as e:
        print(f"[Invidious] Failed to fetch instances: {str(e)}")
    
    # Fallback instances (hardcoded reliable ones)
    fallback_instances = [
        'https://invidious.projectsegfau.lt',
        'https://invidious.slipfox.xyz',
        'https://invidious.prvcypwn.com',
        'https://invidious.snopyta.org',
        'https://invidious.kavin.rocks'
    ]
    print(f"[Invidious] Using {len(fallback_instances)} fallback instances")
    return fallback_instances

def extract_video_info_invidious(url):
    """Extract video info using Invidious API"""
    video_id = extract_video_id(url)
    if not video_id:
        return None, "Invalid YouTube URL"
    
    instances = get_invidious_instances()
    
    for instance in instances:
        try:
            api_url = f"{instance}/api/v1/videos/{video_id}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'application/json',
            }
            
            response = requests.get(api_url, headers=headers, timeout=15)
            if response and response.status_code == 200:
                data = response.json()
                
                # Validate required fields
                if not isinstance(data, dict) or 'title' not in data:
                    continue
                
                # Get available formats
                formats = []
                if 'formatStreams' in data and isinstance(data['formatStreams'], list):
                    for fmt in data['formatStreams']:
                        if isinstance(fmt, dict) and fmt.get('height') and fmt.get('url'):
                            formats.append({
                                'format_id': fmt.get('itag', 'unknown'),
                                'height': fmt.get('height', 0),
                                'ext': 'mp4',
                                'url': fmt.get('url'),
                                'filesize': fmt.get('contentLength', 0),
                                'format_note': f"Invidious {fmt.get('height')}p",
                                'method': 'Invidious'
                            })
                
                # Sort by quality
                formats.sort(key=lambda x: x['height'], reverse=True)
                
                # Ensure thumbnail is valid
                thumbnail = ""
                if 'videoThumbnails' in data and isinstance(data['videoThumbnails'], list) and len(data['videoThumbnails']) > 0:
                    first_thumb = data['videoThumbnails'][0]
                    if isinstance(first_thumb, dict) and first_thumb.get('url'):
                        thumbnail = first_thumb['url']
                
                return {
                    'title': data.get('title', 'Unknown Title'),
                    'duration': data.get('lengthSeconds', 0),
                    'thumbnail': thumbnail,
                    'formats': formats,
                    'video_id': video_id,
                    'method': 'Invidious API'
                }, None
        except Exception as e:
            print(f"[Invidious] Instance {instance} failed: {str(e)}")
            continue
    
    return None, "All Invidious instances failed"

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

def download_video_direct(url, format_info, output_path):
    """Download video directly using the stream URL"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Referer': 'https://www.youtube.com/',
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=300)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    
                    # Progress logging
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        if downloaded % (1024 * 1024) == 0:  # Log every MB
                            print(f"Downloaded: {downloaded / (1024 * 1024):.1f}MB / {total_size / (1024 * 1024):.1f}MB ({progress:.1f}%)")
        
        return True, "Download completed successfully"
        
    except Exception as e:
        return False, f"Download error: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test')
def test():
    """Simple test route to check if the app is working"""
    try:
        return jsonify({
            'status': 'ok',
            'message': 'YouTube Downloader is running',
            'timestamp': '2024-01-18',
            'environment': {
                'python_version': os.sys.version,
                'yt_dlp_version': yt_dlp.version.__version__,
                'flask_version': Flask.__version__,
                'working_directory': os.getcwd(),
                'downloads_folder': UPLOAD_FOLDER,
                'downloads_exists': os.path.exists(UPLOAD_FOLDER),
                'downloads_writable': os.access(UPLOAD_FOLDER, os.W_OK) if os.path.exists(UPLOAD_FOLDER) else False
            }
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': '2024-01-18'
        }), 500

@app.route('/test_yt_dlp')
def test_yt_dlp():
    """Test yt-dlp functionality with a simple URL"""
    try:
        test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
        
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(test_url, download=False)
            
            return jsonify({
                'status': 'ok',
                'message': 'yt-dlp is working',
                'test_url': test_url,
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'formats_count': len(info.get('formats', [])),
                'timestamp': '2024-01-18'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'error_type': str(type(e)),
            'timestamp': '2024-01-18'
        }), 500

@app.route('/debug')
def debug():
    """Debug route to check server status and configuration"""
    try:
        import sys
        import platform
        
        debug_info = {
            'server_status': 'running',
            'timestamp': '2024-01-18',
            'environment': {
                'python_version': sys.version,
                'python_executable': sys.executable,
                'platform': platform.platform(),
                'architecture': platform.architecture(),
                'machine': platform.machine(),
                'processor': platform.processor(),
                'working_directory': os.getcwd(),
                'downloads_folder': UPLOAD_FOLDER,
                'downloads_exists': os.path.exists(UPLOAD_FOLDER),
                'downloads_writable': os.access(UPLOAD_FOLDER, os.W_OK) if os.path.exists(UPLOAD_FOLDER) else False,
                'downloads_contents': os.listdir(UPLOAD_FOLDER) if os.path.exists(UPLOAD_FOLDER) else []
            },
            'dependencies': {
                'yt_dlp_version': yt_dlp.version.__version__,
                'flask_version': Flask.__version__,
                'yt_dlp_available': 'yt_dlp' in sys.modules,
                'flask_available': 'flask' in sys.modules
            },
            'deployment': {
                'is_production': IS_PRODUCTION,
                'is_render': IS_RENDER,
                'is_heroku': IS_HEROKU,
                'flask_env': os.environ.get('FLASK_ENV'),
                'port': os.environ.get('PORT'),
                'host': os.environ.get('HOST', '0.0.0.0')
            }
        }
        
        return jsonify(debug_info)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': '2024-01-18'
        }), 500

@app.route('/get_video_info', methods=['POST'])
def get_video_info():
    try:
        print(f"[DEBUG] get_video_info called")
        print(f"[DEBUG] Request data: {request.get_json()}")
        
        data = request.get_json()
        url = data.get('url', '').strip()
        
        print(f"[DEBUG] URL received: {url}")
        
        if not url:
            print(f"[DEBUG] No URL provided")
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            print(f"[DEBUG] Invalid YouTube URL: {url}")
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        print(f"[DEBUG] URL validation passed")
        
        # Check environment and dependencies
        print(f"[DEBUG] Python version: {os.sys.version}")
        print(f"[DEBUG] Current working directory: {os.getcwd()}")
        print(f"[DEBUG] yt-dlp version: {yt_dlp.version.__version__}")
        print(f"[DEBUG] Flask version: {Flask.__version__}")
        
        # Check if downloads folder exists and is writable
        try:
            if not os.path.exists(UPLOAD_FOLDER):
                os.makedirs(UPLOAD_FOLDER)
                print(f"[DEBUG] Created downloads folder: {UPLOAD_FOLDER}")
            else:
                print(f"[DEBUG] Downloads folder exists: {UPLOAD_FOLDER}")
            
            # Test write access
            test_file = os.path.join(UPLOAD_FOLDER, 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"[DEBUG] Downloads folder is writable")
        except Exception as e:
            print(f"[DEBUG] Downloads folder error: {str(e)}")
            return jsonify({'error': f'Server configuration error: {str(e)}'}), 500
        
        # Configure yt-dlp options for info extraction
        ydl_opts = {
            'quiet': False,  # Changed to False for debugging
            'no_warnings': False,  # Changed to False for debugging
            'extract_flat': False,
            'verbose': True,  # Added verbose output
        }
        
        # Add deployment-specific options
        if IS_PRODUCTION or IS_RENDER or IS_HEROKU:
            print(f"[DEBUG] Running in production environment, adding deployment options")
            ydl_opts.update({
                'nocheckcertificate': True,
                'ignoreerrors': False,
                'retries': 5,
                'fragment_retries': 5,
                'http_chunk_size': 10485760,  # 10MB chunks
                'sleep_interval': 2,
                'max_sleep_interval': 10,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
        
        print(f"[DEBUG] yt-dlp options: {ydl_opts}")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"[DEBUG] yt-dlp instance created successfully")
                
                # Test basic yt-dlp functionality
                print(f"[DEBUG] Testing yt-dlp with URL: {url}")
                
                info = ydl.extract_info(url, download=False)
                print(f"[DEBUG] yt-dlp extract_info completed")
                print(f"[DEBUG] Video title: {info.get('title', 'Unknown')}")
                print(f"[DEBUG] Available formats count: {len(info.get('formats', []))}")
                
                # Get available formats and filter for actual video formats (allow video-only for higher qualities)
                formats = []
                raw_formats = info.get('formats', [])
                print(f"[DEBUG] Processing {len(raw_formats)} raw formats")
                
                for i, f in enumerate(raw_formats):
                    print(f"[DEBUG] Format {i}: {f}")
                    
                    # Include all video formats (both with and without audio)
                    if (f.get('height') and f.get('ext') and 
                        f.get('vcodec') and f.get('vcodec') != 'none' and
                        f.get('height') >= 144 and  # Minimum reasonable video height
                        f.get('protocol') != 'mhtml' and  # Skip MHTML formats
                        not f.get('ext') in ['html', 'htm', 'mhtml'] and
                        f.get('ext') in ['mp4', 'webm', 'mkv', 'avi', 'mov']):  # Only video formats
                        
                        # Check if this is video-only (no audio)
                        is_video_only = f.get('acodec') == 'none' or not f.get('acodec')
                        
                        format_info = {
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
                        }
                        
                        formats.append(format_info)
                        print(f"[DEBUG] Added format: {format_info}")
                    else:
                        print(f"[DEBUG] Skipped format {i}: height={f.get('height')}, ext={f.get('ext')}, vcodec={f.get('vcodec')}, protocol={f.get('protocol')}")
                
                print(f"[DEBUG] Filtered formats count: {len(formats)}")
                
                # If no video formats found, try to get best available
                if not formats:
                    print(f"[DEBUG] No formats found, trying fallback...")
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
                            print(f"[DEBUG] Added fallback format: {f.get('format_id')} {f.get('height')}p")
                
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
                    print(f"[DEBUG] No unique formats, using default")
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
                
                print(f"[DEBUG] Final formats count: {len(unique_formats)}")
                for f in unique_formats:
                    print(f"[DEBUG] Final format: {f['height']}p {f['ext']} ({f['format_id']})")
                
                response_data = {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', ''),
                    'formats': unique_formats,
                    'video_id': extract_video_id(url)
                }
                
                print(f"[DEBUG] Returning response with {len(unique_formats)} formats")
                return jsonify(response_data)
                
        except Exception as yt_dlp_error:
            print(f"[DEBUG] yt-dlp error: {str(yt_dlp_error)}")
            print(f"[DEBUG] Error type: {type(yt_dlp_error)}")
            import traceback
            print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
            
            # Return detailed error for debugging
            return jsonify({
                'error': f'yt-dlp error: {str(yt_dlp_error)}',
                'error_type': str(type(yt_dlp_error)),
                'debug_info': {
                    'python_version': os.sys.version,
                    'yt_dlp_version': yt_dlp.version.__version__,
                    'working_directory': os.getcwd(),
                    'downloads_folder': UPLOAD_FOLDER
                }
            }), 500
        
    except Exception as e:
        print(f"[DEBUG] General error in get_video_info: {str(e)}")
        import traceback
        print(f"[DEBUG] Full traceback: {traceback.format_exc()}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500

@app.route('/get_video_info_alternative', methods=['POST'])
def get_video_info_alternative():
    """Get video info using alternative methods (no yt-dlp)"""
    try:
        print(f"[Alternative] get_video_info_alternative called")
        data = request.get_json()
        url = data.get('url', '').strip()
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        print(f"[Alternative] Trying Invidious API first...")
        
        # Try Invidious first (most reliable alternative)
        info, error = extract_video_info_invidious(url)
        if info and not error:
            print(f"[Alternative] Invidious API successful: {len(info.get('formats', []))} formats")
            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'duration': info.get('duration', 0),
                'thumbnail': info.get('thumbnail', ''),
                'formats': info.get('formats', []),
                'video_id': info.get('video_id'),
                'method': 'Invidious API',
                'warning': 'Using alternative method - some features may be limited'
            })
        
        print(f"[Alternative] Invidious failed, trying direct YouTube extraction...")
        
        # Fallback to direct YouTube extraction
        info, error = extract_video_info_direct(url)
        if info and not error:
            # Create a basic format list since direct extraction doesn't give formats
            basic_formats = [
                {
                    'format_id': 'best',
                    'height': 720,
                    'ext': 'mp4',
                    'format_note': 'Best available (direct extraction)',
                    'method': 'Direct',
                    'url': None  # No direct URL available
                }
            ]
            
            print(f"[Alternative] Direct YouTube extraction successful")
            return jsonify({
                'title': info.get('title', 'Unknown Title'),
                'duration': 0,
                'thumbnail': info.get('thumbnail_url', ''),
                'formats': basic_formats,
                'video_id': info.get('video_id'),
                'method': 'Direct YouTube',
                'warning': 'Using basic extraction - limited format options'
            })
        
        print(f"[Alternative] All alternative methods failed")
        return jsonify({'error': 'All alternative methods failed. Please try again later.'}), 500
        
    except Exception as e:
        print(f"[Alternative] Error in get_video_info_alternative: {str(e)}")
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
        
        # Configure yt-dlp options for download
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
            # Add options to handle 403 errors
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'retries': 3,  # Retry failed downloads
            'fragment_retries': 3,  # Retry fragment downloads
            'http_chunk_size': 10485760,  # 10MB chunks
            'sleep_interval': 1,  # Sleep between requests
            'max_sleep_interval': 5,  # Maximum sleep interval
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

@app.route('/download_video_alternative', methods=['POST'])
def download_video_alternative():
    """Download video using alternative methods (no yt-dlp)"""
    try:
        print(f"[Alternative] download_video_alternative called")
        data = request.get_json()
        url = data.get('url', '').strip()
        format_id = data.get('format_id', 'best')
        
        if not url:
            return jsonify({'error': 'Please provide a YouTube URL'}), 400
        
        if not is_valid_youtube_url(url):
            return jsonify({'error': 'Please provide a valid YouTube URL'}), 400
        
        print(f"[Alternative] Trying Invidious download...")
        
        # Try Invidious first
        info, error = extract_video_info_invidious(url)
        if info and not error:
            # Find the requested format
            selected_format = None
            for fmt in info.get('formats', []):
                if str(fmt.get('format_id')) == str(format_id) or format_id == 'best':
                    selected_format = fmt
                    if format_id == 'best':
                        break  # Use first (highest quality) format
            
            if selected_format and selected_format.get('url'):
                # Generate filename
                safe_title = "".join(c for c in info.get('title', 'Unknown') if c.isalnum() or c in (' ', '-', '_')).rstrip()
                filename = f"{safe_title}_{selected_format.get('height', 'unknown')}p.mp4"
                output_path = os.path.join(UPLOAD_FOLDER, filename)
                
                print(f"[Alternative] Downloading {filename} from Invidious...")
                
                # Download the video
                success, message = download_video_direct(selected_format['url'], selected_format, output_path)
                
                if success:
                    file_size = os.path.getsize(output_path)
                    print(f"[Alternative] Download successful: {filename}, size: {file_size}")
                    return jsonify({
                        'success': True,
                        'filename': filename,
                        'filepath': output_path,
                        'title': info.get('title', 'Unknown Title'),
                        'filesize': file_size,
                        'selected_quality': f"{selected_format.get('height', 'Unknown')}p",
                        'method': 'Invidious API',
                        'message': message
                    })
                else:
                    print(f"[Alternative] Download failed: {message}")
                    return jsonify({'error': f'Download failed: {message}'}), 500
            else:
                print(f"[Alternative] Selected format not available")
                return jsonify({'error': 'Selected format not available'}), 400
        
        print(f"[Alternative] Invidious failed, trying direct YouTube...")
        
        # Fallback to direct YouTube (limited format options)
        info, error = extract_video_info_direct(url)
        if info and not error:
            # For direct extraction, we can only get basic info
            safe_title = "".join(c for c in info.get('title', 'Unknown') if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title}_basic.mp4"
            output_path = os.path.join(UPLOAD_FOLDER, filename)
            
            print(f"[Alternative] Direct YouTube extraction only provides basic info")
            return jsonify({
                'success': False,
                'error': 'Direct YouTube extraction only provides basic info. Please use Invidious method or try again later.',
                'available_info': info
            }), 400
        
        print(f"[Alternative] All alternative methods failed")
        return jsonify({'error': 'All alternative methods failed. Please try again later.'}), 500
        
    except Exception as e:
        print(f"[Alternative] Error in download_video_alternative: {str(e)}")
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

@app.route('/test_alternative_methods')
def test_alternative_methods():
    """Test only alternative methods (no yt-dlp)"""
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll for testing
    
    results = []
    
    # Test 1: Direct YouTube extraction
    try:
        info, error = extract_video_info_direct(test_url)
        if error:
            results.append({
                'method': 'Direct YouTube',
                'success': False,
                'error': error
            })
        else:
            results.append({
                'method': 'Direct YouTube',
                'success': True,
                'title': info.get('title', 'Unknown'),
                'method_used': info.get('method', 'Unknown')
            })
    except Exception as e:
        results.append({
            'method': 'Direct YouTube',
            'success': False,
            'error': str(e)
        })
    
    # Test 2: Invidious API
    try:
        info, error = extract_video_info_invidious(test_url)
        if error:
            results.append({
                'method': 'Invidious API',
                'success': False,
                'error': error
            })
        else:
            results.append({
                'method': 'Invidious API',
                'success': True,
                'title': info.get('title', 'Unknown'),
                'formats': len(info.get('formats', [])),
                'method_used': info.get('method', 'Unknown')
            })
    except Exception as e:
        results.append({
            'method': 'Invidious API',
            'success': False,
            'error': str(e)
        })
    
    return jsonify({
        'status': 'ok',
        'message': 'Alternative methods test results (no yt-dlp)',
        'results': results,
        'timestamp': '2024-01-18'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 