import os
import time
import json
from flask import Flask, request, jsonify, session
from flask_session import Session
import google.generativeai as genai

app = Flask(__name__)

# Configure Google Generative AI
genai.configure(api_key='AIzaSyBU1BhybBEaYGRKM45KWvomihSXgYvV22U')

# Flask session configuration
app.config['SECRET_KEY'] = 'supersecretkey'
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# Ensure data directory exists
if not os.path.exists('data/'):
    os.makedirs('data/')

# Load past chats if available
try:
    with open('data/past_chats_list.json', 'r') as f:
        past_chats = json.load(f)
except FileNotFoundError:
    past_chats = {}

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
}

def save_chat_history(chat_id, chat_data):
    with open(f'data/{chat_id}.json', 'w') as f:
        json.dump(chat_data, f)

def load_chat_history(chat_id):
    try:
        with open(f'data/{chat_id}.json', 'r') as f:
            chat_data = json.load(f)
    except FileNotFoundError:
        chat_data = {'messages': [], 'gemini_history': []}
    return chat_data

@app.route('/chat', methods=['POST'])
def chat():
    if 'chat_id' not in session:
        session['chat_id'] = f'{time.time()}'
        session['chat_title'] = f'ChatSession-{session["chat_id"]}'

    user_message = request.json.get('message')
    chat_id = session['chat_id']
    chat_title = session['chat_title']

    if chat_id not in past_chats:
        past_chats[chat_id] = chat_title
        with open('data/past_chats_list.json', 'w') as f:
            json.dump(past_chats, f)

    # Load chat history
    chat_data = load_chat_history(chat_id)
    messages = chat_data['messages']
    gemini_history = chat_data['gemini_history']

    # Convert gemini_history back to the required format
    gemini_history_converted = [
        {
            'role': msg['role'],
            'parts': [{'text': msg['content']}]
        }
        for msg in gemini_history
    ]

    # Initialize the chat model
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        generation_config=generation_config
    )
    chat = model.start_chat(history=gemini_history_converted)

    # Add system instruction as a message if it's a new chat
    if not gemini_history:
        system_instruction = "You are a Medical LLM that will have conversations with patients in question and answer format. And after 3-4 questions, finally give some remedy."
        chat.send_message(system_instruction)
        gemini_history = chat.history

    # Add user message to history
    messages.append({'role': 'user', 'content': user_message})
    
    # Get AI response
    response = chat.send_message(user_message)
    assistant_response = ''.join(chunk.text for chunk in response)

    # Add AI response to history
    messages.append({'role': 'ai', 'content': assistant_response})
    gemini_history = chat.history

    # Convert gemini_history to JSON-serializable format
    gemini_history_serializable = [
        {
            'role': msg.role,
            'content': msg.parts[0].text if msg.parts else ''
        }
        for msg in gemini_history
    ]

    # Save chat history
    chat_data['messages'] = messages
    chat_data['gemini_history'] = gemini_history_serializable
    save_chat_history(chat_id, chat_data)

    return jsonify({
        'chat_id': chat_id,
        'chat_title': chat_title,
        'user_message': user_message,
        'ai_response': assistant_response,
    })

@app.route('/past_chats', methods=['GET'])
def get_past_chats():
    return jsonify(past_chats)

if __name__ == '__main__':
    app.run(debug=True)
