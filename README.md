# YouTube Video Downloader

A Flask web application that allows users to download YouTube videos in various quality formats.

## Features

- Download YouTube videos in multiple quality options
- Automatic format detection and selection
- Clean and modern web interface
- Support for various video formats (MP4, WebM, etc.)

## Local Development

1. Clone the repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run the application:
   ```bash
   python app.py
   ```
5. Open your browser and go to `http://localhost:5000`

## Deployment on Render

### Option 1: Using render.yaml (Recommended)

1. Push your code to a GitHub repository
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New +" and select "Blueprint"
4. Connect your GitHub repository
5. Render will automatically detect the `render.yaml` file and deploy your application

### Option 2: Manual Deployment

1. Push your code to a GitHub repository
2. Go to [Render Dashboard](https://dashboard.render.com/)
3. Click "New +" and select "Web Service"
4. Connect your GitHub repository
5. Configure the service:
   - **Name**: youtube-downloader (or your preferred name)
   - **Environment**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Free (or your preferred plan)

### Environment Variables

The following environment variables are automatically set by Render:
- `PORT`: The port number (set by Render)
- `FLASK_ENV`: Set to "production"

## Important Notes

- **Free Plan Limitations**: Render's free plan has limitations on build time and runtime. For a YouTube downloader, you might want to consider a paid plan for better performance.
- **File Storage**: Downloaded files are stored temporarily on the server. Consider implementing a cleanup mechanism for production use.
- **Rate Limiting**: Be aware of YouTube's terms of service and implement appropriate rate limiting if needed.

## Dependencies

- Flask 2.3.3
- yt-dlp 2023.11.16
- requests 2.31.0
- Werkzeug 2.3.7
- gunicorn 21.2.0 (for production deployment)

## License

This project is for educational purposes. Please respect YouTube's terms of service and copyright laws. 