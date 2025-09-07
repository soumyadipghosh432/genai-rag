# 🤖 AI Assistant Chat UI

A professional, responsive chat interface built with Flask that integrates seamlessly with FastAPI backends. Features a modern white and purple theme with real-time messaging, PDF export, and comprehensive chat management.

![Chat UI Preview](https://img.shields.io/badge/Status-Production%20Ready-brightgreen) ![Python](https://img.shields.io/badge/Python-3.7+-blue) ![Flask](https://img.shields.io/badge/Flask-2.3+-red) ![License](https://img.shields.io/badge/License-MIT-yellow)

## ✨ Features

- 🎨 **Professional Design** - Clean white/purple theme with smooth animations
- 💬 **Real-time Chat** - Seamless integration with FastAPI endpoints
- ⏱️ **Live Header** - Real-time clock with timezone display
- 📋 **Copy to Clipboard** - One-click copy for all AI responses
- 📄 **PDF Export** - Export entire chat sessions with formatting
- 🔢 **Token Tracking** - Display input/output token counts
- ⚡ **Response Timing** - Show API response times
- 📱 **Responsive Design** - Optimized for mobile and desktop
- 🔄 **Session Management** - Persistent chat history during session
- 🚀 **Loading States** - Professional loading animations

## 📁 Project Structure

```
ChatUI/
├── app.py                          # Main Flask application
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── static/
│   ├── css/
│   │   └── style.css              # Main stylesheet
│   ├── js/
│   │   └── chat.js                # Chat functionality
│   └── images/
│       ├── logo.png               # Company logo (add your own)
│       ├── user-avatar.png        # User avatar (optional)
│       └── ai-avatar.png          # AI avatar (optional)
├── templates/
│   └── chat.html                  # Main chat interface template
├── utils/
│   └── pdf_generator.py           # PDF export functionality
└── exports/                       # Generated PDF files (auto-created)
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.7 or higher
- FastAPI server running with a `/chat` endpoint
- pip (Python package manager)

### 2. Installation

```bash
# Navigate to your FastAPI project directory
cd /path/to/your/fastapi-project

# Create ChatUI directory
mkdir ChatUI && cd ChatUI

# Create required subdirectories
mkdir -p static/css static/js static/images templates utils exports

# Copy all the provided files into their respective directories
# (See file contents below)

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Configuration

Update `app.py` with your settings:

```python
# Change the secret key for production
app.secret_key = 'your-unique-secret-key-here'

# Update FastAPI URL if different
FASTAPI_URL = "http://127.0.0.1:8000"
```

### 4. Running the Application

**Terminal 1 - Start FastAPI server:**
```bash
uvicorn main:app --host 127.0.0.1 --port 8000
```

**Terminal 2 - Start Flask Chat UI:**
```bash
cd ChatUI
python app.py
```

**Access the application:**
Open your browser and navigate to `http://localhost:5000`

## ⚙️ FastAPI Integration

### Required Endpoint Format

Your FastAPI server must have a `/chat` endpoint that accepts POST requests:

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str
    input_tokens: int
    output_tokens: int

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    # Your AI processing logic here
    ai_response = process_message(request.message, request.session_id)
    
    return ChatResponse(
        response=ai_response,
        input_tokens=150,  # Calculate actual input tokens
        output_tokens=200  # Calculate actual output tokens
    )
```

### Request Format (Sent by Flask UI)
```json
{
    "session_id": "unique-session-id-string",
    "message": "User's message text"
}
```

### Response Format (Expected by Flask UI)
```json
{
    "response": "AI assistant's response text",
    "input_tokens": 150,
    "output_tokens": 200
}
```

## 📦 Dependencies

```txt
Flask==2.3.3
requests==2.31.0
reportlab==4.0.4
Werkzeug==2.3.7
Jinja2==3.1.2
itsdangerous==2.1.2
click==8.1.7
MarkupSafe==2.1.3
Pillow==10.0.1
```

## 🎨 Customization

### 1. Branding

**Update company information in `templates/chat.html`:**
```html
<h1 class="company-name">Your Company Name</h1>
```

**Add your logo to `static/images/logo.png` (recommended size: 40x40px)**

### 2. Colors and Theme

**Modify CSS variables in `static/css/style.css`:**
```css
:root {
    --primary-purple: #8B5CF6;
    --secondary-purple: #6366F1;
    --accent-blue: #667eea;
    --success-green: #10B981;
    --error-red: #EF4444;
}
```

### 3. Welcome Message

**Update the welcome message in `templates/chat.html`:**
```html
<div class="message-text">
    Welcome to [Your Company]! How can I assist you today?
</div>
```

## 🔧 Advanced Configuration

### Environment Variables

For production deployments, use environment variables:

```python
import os

app.secret_key = os.getenv('FLASK_SECRET_KEY', 'fallback-secret-key')
FASTAPI_URL = os.getenv('FASTAPI_URL', 'http://127.0.0.1:8000')
```

### Custom Ports

```python
if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
```

## 📱 Mobile Responsiveness

The chat UI automatically adapts to different screen sizes:

- **Desktop**: Full-width layout with sidebar controls
- **Tablet**: Optimized button sizes and spacing
- **Mobile**: Stacked layout with touch-friendly elements

## 🔒 Security Considerations

### For Production Deployment:

1. **Change Secret Key**: Use a strong, unique secret key
2. **HTTPS Only**: Always use SSL/TLS in production
3. **Input Validation**: Validate and sanitize user inputs
4. **Rate Limiting**: Implement request rate limiting
5. **CORS Policy**: Configure proper CORS headers
6. **Error Handling**: Don't expose internal error details

### Security Headers Example:
```python
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

@app.after_request
def after_request(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response
```

## 🚀 Production Deployment

### Using Gunicorn (Recommended)

```bash
# Install Gunicorn
pip install gunicorn

# Run with multiple workers
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# Or with configuration file
gunicorn -c gunicorn.conf.py app:app
```

### Sample `gunicorn.conf.py`:
```python
bind = "0.0.0.0:5000"
workers = 4
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2
max_requests = 1000
max_requests_jitter = 50
preload_app = True
```

### Nginx Configuration Example:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/ChatUI/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
}
```

## 🐛 Troubleshooting

### Common Issues and Solutions:

#### 1. **Connection Error to FastAPI**
```
Error: Could not connect to chat API
```
**Solution:**
- Verify FastAPI server is running: `curl http://127.0.0.1:8000/docs`
- Check `FASTAPI_URL` in `app.py`
- Ensure `/chat` endpoint exists and accepts POST requests

#### 2. **PDF Export Issues**
```
Error: Failed to generate PDF
```
**Solution:**
```bash
pip install reportlab Pillow
mkdir exports
chmod 755 exports
```

#### 3. **Missing Static Files**
```
404 Error on CSS/JS files
```
**Solution:**
```bash
# Verify directory structure
ls -la static/css/style.css
ls -la static/js/chat.js
```

#### 4. **Session Issues**
```
Chat history not persisting
```
**Solution:**
- Check Flask secret key is set
- Verify session configuration
- Clear browser cookies and try again

#### 5. **Port Already in Use**
```
Address already in use
```
**Solution:**
```bash
# Find process using port 5000
lsof -i :5000
kill -9 [PID]

# Or use different port
python app.py --port 5001
```

## 📊 Performance Optimization

### For High Traffic:

1. **Use Redis for Sessions**:
```python
from flask_session import Session
import redis

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_REDIS'] = redis.from_url('redis://localhost:6379')
```

2. **Enable Gzip Compression**:
```python
from flask_compress import Compress
Compress(app)
```

3. **Add Caching Headers**:
```python
@app.after_request
def add_header(response):
    if request.path.startswith('/static'):
        response.cache_control.max_age = 31536000  # 1 year
    return response
```

## 📈 Monitoring and Analytics

### Adding Request Logging:
```python
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.before_request
def log_request_info():
    logger.info('Request: %s %s', request.method, request.url)

@app.after_request
def log_response_info(response):
    logger.info('Response: %s', response.status_code)
    return response
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built with [Flask](https://flask.palletsprojects.com/)
- Styled with modern CSS3 and animations
- Icons by [Font Awesome](https://fontawesome.com/)
- Typography by [Inter Font](https://rsms.me/inter/)


**Made with ❤️ for seamless AI chat experiences**