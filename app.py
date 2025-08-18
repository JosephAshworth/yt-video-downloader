from flask import Flask, render_template, request, jsonify, send_file
import yt_dlp
import os
import re
import tempfile
from urllib.parse import urlparse, parse_qs

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
        
        # Configure yt-dlp options for info extraction
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
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
        
        # Configure yt-dlp options for download
        ydl_opts = {
            'format': f'{format_id}+bestaudio/best',  # Use selected format + best audio, fallback to best
            'outtmpl': os.path.join(UPLOAD_FOLDER, '%(title)s_%(height)sp_%(format_id)s.%(ext)s'),
            'quiet': False,  # Show more output for debugging
            'no_warnings': False,  # Show warnings
            'merge_output_format': 'mp4',
            'skip': ['storyboard', 'image'],
            'extractaudio': False,
            'audioformat': None,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'verbose': True,  # Add verbose output for debugging
        }
        
        print(f"[Download] Using format_id: {format_id}")
        print(f"[Download] Full format string: {format_id}+bestaudio/best")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # First, extract info to validate the format
            info = ydl.extract_info(url, download=False)
            print(f"Video title: {info.get('title', 'Unknown')}")
            print(f"Available formats: {len(info.get('formats', []))}")
            
            # Download the video
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            
            # Check if the downloaded file is actually a video
            if os.path.exists(filename):
                # Verify it's not a storyboard by checking file size and extension
                file_size = os.path.getsize(filename)
                file_ext = os.path.splitext(filename)[1].lower()
                
                print(f"Downloaded file: {filename}, size: {file_size}, ext: {file_ext}")  # Debug print
                
                # Check for invalid file types
                invalid_extensions = ['.mhtml', '.html', '.htm', '.jpg', '.png', '.webp', '.gif']
                if file_ext in invalid_extensions:
                    os.remove(filename)  # Remove the invalid file
                    return jsonify({'error': f'Downloaded file is {file_ext.upper()}, not a video. Please try a different quality option.'}), 500
                
                # If file is too small, it might be invalid
                if file_size < 1000000:  # Less than 1MB
                    os.remove(filename)  # Remove the small file
                    return jsonify({'error': 'Downloaded file is too small to be a valid video. Please try a different quality option.'}), 500
                
                return jsonify({
                    'success': True,
                    'filename': os.path.basename(filename),
                    'filepath': filename,
                    'title': info.get('title', 'Unknown Title'),
                    'filesize': file_size
                })
            else:
                return jsonify({'error': 'Download failed - file not found'}), 500
                
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
            'outtmpl': os.path.join(UPLOAD_FOLDER, 'test_%(title)s_%(format_id)s.%(ext)s'),
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
                    'url': f.get('url', '')[:100] + '...' if f.get('url') else ''
                })
            
            return jsonify({
                'title': info.get('title', 'Unknown'),
                'formats': all_formats,
                'total_formats': len(all_formats)
            })
            
    except Exception as e:
        return jsonify({'error': f'Debug error: {str(e)}'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port) 