# YouTube Video Downloader

A modern, Flask-based web application that allows users to download YouTube videos with quality selection. Built with Python, Flask, and yt-dlp for reliable video extraction and downloading.

## ✨ Features

- **Quality Selection**: Choose from available video qualities (144p to 1080p+)
- **Multiple Formats**: Support for MP4, WebM, MKV, AVI, and MOV formats
- **Smart Fallback**: Automatic fallback to best available quality if selected quality fails
- **Modern UI**: Clean, responsive web interface
- **Error Handling**: Robust error handling with helpful user feedback
- **File Validation**: Ensures downloaded files are valid videos, not corrupted

## 🚀 Live Demo

[View Live Demo](https://your-deployment-url.com) *(Coming Soon)*

## 🛠️ Technology Stack

- **Backend**: Python Flask
- **Video Processing**: yt-dlp (YouTube-DL successor)
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **File Handling**: FFmpeg for video processing
- **Deployment**: Ready for Heroku, Railway, or any Python hosting

## 📋 Prerequisites

- Python 3.8 or higher
- FFmpeg (for video processing)
- Git

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/JosephAshworth/yt-video-downloader.git
cd yt-video-downloader
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install FFmpeg

**macOS (using Homebrew):**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows:**
Download from [FFmpeg official website](https://ffmpeg.org/download.html)

### 5. Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

## 🎯 Usage

### 1. Open the Web Interface
Navigate to `http://localhost:5000` in your browser

### 2. Enter YouTube URL
Paste any YouTube video URL into the input field

### 3. Select Quality
Choose your preferred video quality from the available options

### 4. Download
Click the download button and wait for the process to complete

### 5. Access Your File
Downloaded videos are saved in the `downloads/` folder

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
FLASK_ENV=development
PORT=5000
UPLOAD_FOLDER=downloads
```

### Custom Settings

Modify `app.py` to customize:
- Download folder location
- Maximum file size
- Allowed video formats
- Quality preferences

## 📁 Project Structure

```
yt-video-downloader/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── templates/
│   └── index.html        # Main web interface
├── static/
│   ├── css/
│   │   └── style.css     # Styling
│   └── js/
│       └── script.js     # Frontend logic
├── downloads/            # Downloaded videos folder
├── .gitignore           # Git ignore rules
└── README.md            # This file
```

## 🚀 Deployment

### Heroku

1. **Install Heroku CLI**
```bash
curl https://cli-assets.heroku.com/install.sh | sh
```

2. **Login to Heroku**
```bash
heroku login
```

3. **Create Heroku App**
```bash
heroku create your-app-name
```

4. **Add FFmpeg Buildpack**
```bash
heroku buildpacks:add https://github.com/heroku/heroku-buildpack-ffmpeg-latest.git
heroku buildpacks:add heroku/python
```

5. **Deploy**
```bash
git push heroku main
```

### Railway

1. Connect your GitHub repository to Railway
2. Railway will automatically detect Python and install dependencies
3. Add environment variables as needed
4. Deploy automatically on every push

### Docker

1. **Build Image**
```bash
docker build -t youtube-downloader .
```

2. **Run Container**
```bash
docker run -p 5000:5000 youtube-downloader
```

## 🐛 Troubleshooting

### Common Issues

**"No module named 'flask'"**
- Ensure virtual environment is activated: `source venv/bin/activate`

**"FFmpeg not found"**
- Install FFmpeg using your system's package manager
- Verify installation: `ffmpeg -version`

**"Download failed - file not found"**
- Check if the selected quality is available for the video
- Try a different quality option
- Check the terminal for detailed error messages

**"Video quality doesn't match selection"**
- YouTube sometimes provides different qualities than requested
- Use the debug routes to see available formats: `/debug_formats`

### Debug Routes

- `/debug_formats` - View all available video formats
- `/test_download` - Test download functionality
- `/test_format` - Test specific format download

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit your changes: `git commit -am 'Add feature'`
4. Push to the branch: `git push origin feature-name`
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This tool is for educational and personal use only. Please respect YouTube's Terms of Service and only download videos you have permission to download. The developers are not responsible for any misuse of this application.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube video downloader
- [Flask](https://flask.palletsprojects.com/) - Web framework
- [FFmpeg](https://ffmpeg.org/) - Multimedia processing

## 📞 Support

If you encounter any issues or have questions:

1. Check the [Issues](https://github.com/JosephAshworth/yt-video-downloader/issues) page
2. Create a new issue with detailed information
3. Include error messages and steps to reproduce

---

**Star this repository if it helped you! ⭐** 