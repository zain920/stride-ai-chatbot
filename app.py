from flask import Flask, request, jsonify, render_template, send_file
import requests
import json
import io
import base64
from datetime import datetime
import time
import os
import re
import hashlib
import uuid

app = Flask(__name__)
app.secret_key = 'stride-secret-key-2026'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Create folders
UPLOAD_FOLDER = 'uploads'
CHAT_HISTORY_FOLDER = 'chat_history'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CHAT_HISTORY_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Groq API Configuration
GROQ_API_KEY = "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"
API_URL = "https://api.groq.com/openai/v1/chat/completions"
VISION_URL = "https://api.groq.com/openai/v1/chat/completions"

# Available Models
AVAILABLE_MODELS = {
    "llama-3.3-70b-versatile": "Llama 3.3 70B (Best Quality)",
    "llama-3.1-8b-instant": "Llama 3.1 8B (Fastest)"
}

THEMES = {
    "default": "Default Purple",
    "midnight": "Midnight Dark",
    "ocean": "Ocean Blue",
    "forest": "Forest Green",
    "sunset": "Sunset Orange"
}

# Quiz Questions
CAREER_QUIZ = [
    {"q": "Do you enjoy solving complex problems?", "options": ["Yes", "Sometimes", "No"], "careers": {"Yes": "engineer", "Sometimes": "analyst", "No": "manager"}},
    {"q": "Do you prefer working with people or technology?", "options": ["People", "Both", "Technology"], "careers": {"People": "doctor", "Both": "manager", "Technology": "engineer"}},
    {"q": "Are you more creative or analytical?", "options": ["Creative", "Balanced", "Analytical"], "careers": {"Creative": "designer", "Balanced": "marketer", "Analytical": "scientist"}},
    {"q": "Do you like leading teams?", "options": ["Yes", "Maybe", "No"], "careers": {"Yes": "manager", "Maybe": "analyst", "No": "specialist"}},
    {"q": "Do you prefer routine or variety?", "options": ["Routine", "Balanced", "Variety"], "careers": {"Routine": "accountant", "Balanced": "teacher", "Variety": "entrepreneur"}}
]

def ask_groq(prompt, model="llama-3.3-70b-versatile", conversation_history=None):
    """Send prompt to Groq API and get response with token counting"""
    
    messages = [
        {
            "role": "system",
            "content": "You are Stride AI, a helpful career assistant. You can understand and respond in multiple languages. Respond in the same language the user speaks. Give practical, concise advice."
        }
    ]
    
    if conversation_history:
        for msg in conversation_history[-10:]:
            if msg.get('role') in ['user', 'assistant']:
                messages.append({
                    "role": msg.get('role'),
                    "content": msg.get('content', '')
                })
    
    messages.append({"role": "user", "content": prompt})
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 800
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            tokens_used = result.get('usage', {}).get('total_tokens', 0)
            return result['choices'][0]['message']['content'], tokens_used
        else:
            return "Sorry, I encountered an error. Please try again.", 0
            
    except Exception as e:
        return f"Sorry, something went wrong. Please try again.", 0

def analyze_image_with_groq(image_base64, prompt="Describe this image and give career advice if relevant."):
    """Analyze image using Groq's vision capabilities"""
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        if ',' in image_base64:
            image_base64 = image_base64.split(',')[1]
        
        data = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}}
                    ]
                }
            ],
            "max_tokens": 500
        }
        
        response = requests.post(VISION_URL, headers=headers, json=data, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            return result['choices'][0]['message']['content']
        else:
            return "Could not analyze the image. Please try again."
            
    except Exception as e:
        return f"Error analyzing image: {str(e)[:100]}"

@app.route('/')
def index():
    return render_template('index.html', models=AVAILABLE_MODELS, themes=THEMES, quiz=CAREER_QUIZ)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_message = data.get('message', '')
    model = data.get('model', 'llama-3.3-70b-versatile')
    conversation_history = data.get('history', [])
    
    formatted_history = []
    for msg in conversation_history:
        role = msg.get('role', '')
        content = msg.get('content', '')
        if role in ['user', 'assistant'] and content:
            formatted_history.append({"role": role, "content": content})
    
    start_time = time.time()
    ai_response, tokens_used = ask_groq(user_message, model, formatted_history)
    end_time = time.time()
    
    response_time = round((end_time - start_time), 2)
    
    return jsonify({
        'response': ai_response,
        'model': model,
        'response_time': response_time,
        'tokens_used': tokens_used
    })

@app.route('/analyze_image', methods=['POST'])
def analyze_image_route():
    data = request.json
    image_base64 = data.get('image', '')
    prompt = data.get('prompt', 'What do you see in this image? Describe it and give career advice if relevant.')
    
    if not image_base64:
        return jsonify({'error': 'No image provided'}), 400
    
    result = analyze_image_with_groq(image_base64, prompt)
    
    return jsonify({
        'analysis': result,
        'status': 'success'
    })

@app.route('/save_chat', methods=['POST'])
def save_chat():
    data = request.json
    chat_id = data.get('chat_id', str(uuid.uuid4()))
    conversation = data.get('conversation', [])
    title = data.get('title', f"Chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    
    chat_data = {
        'id': chat_id,
        'title': title,
        'conversation': conversation,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    
    filepath = os.path.join(CHAT_HISTORY_FOLDER, f"{chat_id}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(chat_data, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True, 'chat_id': chat_id})

@app.route('/load_chats', methods=['GET'])
def load_chats():
    chats = []
    for filename in os.listdir(CHAT_HISTORY_FOLDER):
        if filename.endswith('.json'):
            filepath = os.path.join(CHAT_HISTORY_FOLDER, filename)
            with open(filepath, 'r', encoding='utf-8') as f:
                chat_data = json.load(f)
                chats.append({
                    'id': chat_data['id'],
                    'title': chat_data['title'],
                    'created_at': chat_data['created_at']
                })
    
    chats.sort(key=lambda x: x['created_at'], reverse=True)
    return jsonify({'chats': chats})

@app.route('/load_chat/<chat_id>', methods=['GET'])
def load_chat(chat_id):
    filepath = os.path.join(CHAT_HISTORY_FOLDER, f"{chat_id}.json")
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            chat_data = json.load(f)
        return jsonify({'success': True, 'chat': chat_data})
    return jsonify({'error': 'Chat not found'}), 404

@app.route('/delete_chat/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    filepath = os.path.join(CHAT_HISTORY_FOLDER, f"{chat_id}.json")
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({'success': True})
    return jsonify({'error': 'Chat not found'}), 404

@app.route('/export_pdf', methods=['POST'])
def export_pdf():
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib import colors
    except ImportError:
        return jsonify({'error': 'ReportLab not installed'}), 500
    
    data = request.json
    conversation = data.get('conversation', [])
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=24, alignment=TA_CENTER, textColor=colors.HexColor('#667eea'))
    user_style = ParagraphStyle('UserMsg', parent=styles['Normal'], fontSize=11, leftIndent=20, textColor=colors.HexColor('#333'), backColor=colors.HexColor('#f0f0f0'), borderPadding=10, borderRadius=10)
    bot_style = ParagraphStyle('BotMsg', parent=styles['Normal'], fontSize=11, leftIndent=20, textColor=colors.HexColor('#333'), backColor=colors.HexColor('#e8f4f8'), borderPadding=10, borderRadius=10)
    
    story = []
    
    story.append(Paragraph("STRIDE AI - Conversation Export", title_style))
    story.append(Spacer(1, 20))
    story.append(Paragraph(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 20))
    
    for msg in conversation:
        role = msg.get('role', 'user')
        content = msg.get('content', '')
        content = content.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        if role == 'user':
            story.append(Paragraph(f"<b>👤 You:</b><br/>{content}", user_style))
        else:
            story.append(Paragraph(f"<b>🤖 Stride AI:</b><br/>{content}", bot_style))
        story.append(Spacer(1, 10))
    
    doc.build(story)
    buffer.seek(0)
    
    return send_file(
        buffer, 
        as_attachment=True, 
        download_name=f"stride_chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", 
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 STRIDE AI - Complete Feature Pack")
    print("="*60)
    print(f"📍 Open: http://127.0.0.1:5000")
    print("="*60)
    print("✨ NEW FEATURES:")
    print("   • Real-time Token Counter")
    print("   • Response Time Tracker")
    print("   • Message Editing")
    print("   • Share Conversation")
    print("   • Bookmark Messages")
    print("   • Message Tags")
    print("   • Chat History Calendar")
    print("   • Advanced Search")
    print("   • Career Quiz")
    print("   • Skill Score Dashboard")
    print("="*60)
    app.run(debug=True, port=5000, threaded=True)