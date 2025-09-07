from flask import Flask, render_template, request, jsonify, session, send_file
from datetime import datetime
import requests
import uuid
import os
from pdf_generator import generate_chat_pdf

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Change this in production

# Configuration
FASTAPI_URL = "http://127.0.0.1:8000"
UPLOAD_FOLDER = 'exports'

# Ensure exports directory exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    """Main chat interface"""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    if 'chat_history' not in session:
        session['chat_history'] = []
    
    return render_template('chat.html', 
                         session_id=session['session_id'],
                         chat_history=session['chat_history'])

@app.route('/send_message', methods=['POST'])
def send_message():
    """Send message to FastAPI and return response"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        session_id = session.get('session_id')
        
        if not user_message.strip():
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        # Record start time for API call
        start_time = datetime.now()
        
        # Call FastAPI endpoint
        payload = {
            'session_id': session_id,
            'message': user_message
        }
        
        response = requests.post(f"{FASTAPI_URL}/chat", 
                               json=payload, 
                               timeout=30)
        
        # Calculate response time
        end_time = datetime.now()
        response_time = (end_time - start_time).total_seconds()
        
        if response.status_code == 200:
            api_response = response.json()
            
            # Store in session history
            chat_entry = {
                'user_message': user_message,
                'ai_response': api_response.get('response', ''),
                'timestamp': datetime.now().isoformat(),
                'response_time': round(response_time, 2),
                'input_tokens': api_response.get('input_tokens', 0),
                'output_tokens': api_response.get('output_tokens', 0)
            }
            
            if 'chat_history' not in session:
                session['chat_history'] = []
            session['chat_history'].append(chat_entry)
            session.modified = True
            
            return jsonify({
                'success': True,
                'response': api_response.get('response', ''),
                'response_time': round(response_time, 2),
                'input_tokens': api_response.get('input_tokens', 0),
                'output_tokens': api_response.get('output_tokens', 0),
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'error': f'API Error: {response.status_code}',
                'message': response.text
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Request timeout. Please try again.'}), 408
    except requests.exceptions.ConnectionError:
        return jsonify({'error': 'Could not connect to chat API. Please ensure the API is running.'}), 503
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500

@app.route('/export_pdf')
def export_pdf():
    """Export chat history as PDF"""
    try:
        chat_history = session.get('chat_history', [])
        session_id = session.get('session_id', 'unknown')
        
        if not chat_history:
            return jsonify({'error': 'No chat history to export'}), 400
        
        # Generate PDF
        pdf_path = generate_chat_pdf(chat_history, session_id)
        
        return send_file(pdf_path, 
                        as_attachment=True, 
                        download_name=f'chat_export_{session_id[:8]}.pdf',
                        mimetype='application/pdf')
                        
    except Exception as e:
        return jsonify({'error': f'Failed to generate PDF: {str(e)}'}), 500

@app.route('/clear_chat', methods=['POST'])
def clear_chat():
    """Clear current chat session"""
    session['chat_history'] = []
    session.modified = True
    return jsonify({'success': True})

@app.route('/get_current_time')
def get_current_time():
    """Get current time for header display"""
    now = datetime.now()
    return jsonify({
        'time': now.strftime('%H:%M:%S'),
        'date': now.strftime('%Y-%m-%d'),
        'timezone': now.astimezone().tzname()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)