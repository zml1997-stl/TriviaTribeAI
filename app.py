[file name]: app.py
[file content begin]
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import uuid
import google.generativeai as genai
from dotenv import load_dotenv
import secrets
import json
import difflib
import re
from flask_socketio import SocketIO, emit, join_room, leave_room
import string
import random
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Configure PostgreSQL database
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL').replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)
socketio = SocketIO(app, cors_allowed_origins="*")

# Database models
class Game(db.Model):
    id = db.Column(db.String(4), primary_key=True)
    host = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='waiting')
    current_player_index = db.Column(db.Integer, nullable=False, default=0)
    current_question = db.Column(db.JSON)
    question_start_time = db.Column(db.DateTime)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), nullable=False)
    game_id = db.Column(db.String(4), db.ForeignKey('game.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False, default=0)

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(4), db.ForeignKey('game.id'), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.String(200), nullable=False)
    options = db.Column(db.JSON, nullable=False)
    explanation = db.Column(db.String(500))

# Game state storage (temporary, will be replaced by database)
games = {}

# Helper functions for fuzzy matching
def normalize_text(text):
    # Lowercase, trim whitespace, and remove punctuation.
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', '', text)
    return text

def is_close_enough(user_answer, correct_answer, threshold=0.8):
    # Normalize both strings.
    user_norm = normalize_text(user_answer)
    correct_norm = normalize_text(correct_answer)
    
    # If both answers are numeric, compare as floats.
    try:
        if float(user_norm) == float(correct_norm):
            return True
    except ValueError:
        pass

    # Use difflib for fuzzy matching.
    ratio = difflib.SequenceMatcher(None, user_norm, correct_norm).ratio()
    return ratio >= threshold

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/create_game', methods=['POST'])
def create_game():
    username = request.form.get('username')
    if not username:
        return redirect(url_for('index'))
    
    game_id = generate_game_id()
    games[game_id] = {
        'host': username,
        'players': [username],
        'disconnected': set(),
        'status': 'waiting',
        'current_player_index': 0,
        'current_question': None,
        'answers': {},
        'scores': {username: 0},
        'question_start_time': None
    }
    
    session['game_id'] = game_id
    session['username'] = username
    
    return redirect(url_for('game', game_id=game_id))

@app.route('/join_game', methods=['POST'])
def join_game():
    username = request.form.get('username')
    game_id = request.form.get('game_id')
    
    if not username or not game_id:
        return redirect(url_for('index'))
    
    if game_id not in games:
        return "Game not found", 404
    
    if games[game_id]['status'] != 'waiting':
        return "Game already in progress", 403
    
    if len(games[game_id]['players']) >= 10:
        return "Game is full", 403
    
    if username not in games[game_id]['players']:
        games[game_id]['players'].append(username)
        games[game_id]['scores'][username] = 0
    
    session['game_id'] = game_id
    session['username'] = username
    
    return redirect(url_for('game', game_id=game_id))

@app.route('/game/<game_id>')
def game(game_id):
    if game_id not in games:
        return redirect(url_for('index'))
    
    username = session.get('username')
    if not username or username not in games[game_id]['players']:
        return redirect(url_for('index'))
    
    return render_template('game.html', game_id=game_id, username=username, is_host=(username == games[game_id]['host']))

def get_trivia_question(topic):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')  # Use 'gemini-pro'

        prompt = f"""
        Create a trivia question about {topic}. 
        The question must be engaging, specific, and have a single, clear, unambiguous answer. 
        Return your response strictly in the following JSON format, with no additional text outside the JSON:
        {{
            "question": "The trivia question",
            "answer": "The correct answer",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "explanation": "A concise explanation of why the answer is correct"
        }}
        Ensure the options include one correct answer and three plausible but incorrect distractors.
        Do not include any part of the answer in the question.
        Tailor the difficulty to a general audience unless otherwise specified. Try to keep questions mondern,
        and something that most people would know unless the topic is specifically realted to pre modern topics.
        """

        response = model.generate_content(prompt)

        # Parse the response text as JSON immediately.
        try:
            # Clean up response.text
            cleaned_text = response.text.replace('`json', '').replace('`', '').strip()
            result = json.loads(cleaned_text)
            return result
        except json.JSONDecodeError as e:
            print(f"JSONDecodeError: {e}")
            print(f"Raw response text: {response.text}")
            return {
                "question": f"What is a notable fact about {topic}?",  # Fallback question
                "answer": "Unable to generate answer",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "explanation": "There was an error parsing the AI response (JSONDecodeError)."
            }

    except Exception as e:
        print(f"Error generating question: {str(e)}")
        return {
            "question": f"What is a notable fact about {topic}?",  # Fallback question
            "answer": "Unable to generate answer",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "explanation": "There was an error with the AI service (General Exception)."
        }

@socketio.on('connect')
def handle_connect():
    print("Client connected")

@socketio.on('join_game_room')
def handle_join_game_room(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    if game_id in games and username in games[game_id]['players']:
        # Remove from disconnected set if the user is rejoining.
        games[game_id].setdefault('disconnected', set()).discard(username)
        join_room(game_id)
        emit('player_joined', {'username': username, 'players': games[game_id]['players']}, to=game_id)

@socketio.on('start_game')
def handle_start_game(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    if game_id in games and username == games[game_id]['host'] and games[game_id]['status'] == 'waiting':
        games[game_id]['status'] = 'in_progress'
        current_player = games[game_id]['players'][games[game_id]['current_player_index']]
        
        emit('game_started', {
            'current_player': current_player,
            'players': games[game_id]['players'],
            'scores': games[game_id]['scores']
        }, to=game_id)

# Helper function to normalize the answer
def normalize_answer(answer):
    return re.sub(r'\s+', ' ', answer.strip().lower())

# Check for previously asked questions and answers in a more detailed way
@socketio.on('select_topic')
def handle_select_topic(data):
    game_id = data.get('game_id')
    username = data.get('username')
    topic = data.get('topic')

    if (game_id in games and 
        username in games[game_id]['players'] and 
        games[game_id]['status'] == 'in_progress' and
        games[game_id]['players'][games[game_id]['current_player_index']] == username):

        # Ensure the game has a set to track asked questions and answers
        if 'questions_asked' not in games[game_id]:
            games[game_id]['questions_asked'] = []

        max_attempts = 5  # Limit retries to avoid infinite loops

        for _ in range(max_attempts):
            # If topic is empty, select a random one
            if not topic:
                topic = random.choice(RANDOM_TOPICS)
                emit('random_topic_selected', {'topic': topic}, to=game_id)

            question_data = get_trivia_question(topic)
            question_text = question_data['question']
            answer_text = question_data['answer']

            normalized_answer = normalize_answer(answer_text)

            # Check for duplicates using normalized answer and question content
            duplicate_found = False
            for prev_question, prev_answer in games[game_id]['questions_asked']:
                normalized_prev_answer = normalize_answer(prev_answer)

                # If both the question and answer are similar, skip this question
                if normalized_answer == normalized_prev_answer or question_text == prev_question:
                    duplicate_found = True
                    break

            if not duplicate_found:
                games[game_id]['questions_asked'].append((question_text, answer_text))
                games[game_id]['current_question'] = question_data
                games[game_id]['answers'] = {}
                games[game_id]['question_start_time'] = datetime.now()

                emit('question_ready', {
                    'question': question_data['question'],
                    'options': question_data['options'],
                    'topic': topic
                }, to=game_id)
                return  # Stop retrying if a unique question-answer pair is found

        # If all attempts result in duplicates, notify the players
        emit('error', {'message': "Couldn't generate a unique question. Try another topic."}, to=game_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    username = data.get('username')
    answer = data.get('answer')
    
    if (game_id in games and 
        username in games[game_id]['players'] and 
        games[game_id]['status'] == 'in_progress' and
        games[game_id]['current_question']):
        
        # Check if time is up
        time_elapsed = datetime.now() - games[game_id]['question_start_time']
        if time_elapsed.total_seconds() > 30:
            answer = None  # Mark as no answer submitted
        
        # Map the selected letter (A, B, C, D) to the corresponding option text
        if answer in ['A', 'B', 'C', 'D']:
            option_index = ord(answer) - ord('A')  # Convert A=0, B=1, C=2, D=3
            answer = games[game_id]['current_question']['options'][option_index]
        
        games[game_id]['answers'][username] = answer
        emit('player_answered', {'username': username}, to=game_id)
        
        # Check if all players (even disconnected ones) have answered.
        if len(games[game_id]['answers']) == len(games[game_id]['players']):
            correct_answer = games[game_id]['current_question']['answer']
            correct_players = []
            
            for player, player_answer in games[game_id]['answers'].items():
                # Use fuzzy matching to determine if the answer is close enough.
                if player_answer and is_close_enough(player_answer, correct_answer):
                    correct_players.append(player)
                    games[game_id]['scores'][player] += 1
            
            # Update to the next player's turn.
            games[game_id]['current_player_index'] = (games[game_id]['current_player_index'] + 1) % len(games[game_id]['players'])
            next_player = games[game_id]['players'][games[game_id]['current_player_index']]
            
            emit('round_results', {
                'correct_answer': correct_answer,
                'explanation': games[game_id]['current_question']['explanation'],
                'player_answers': games[game_id]['answers'],
                'correct_players': correct_players,
                'next_player': next_player,
                'scores': games[game_id]['scores']
            }, to=game_id)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    # Instead of removing the user, mark them as disconnected.
    for game_id, game in games.items():
        if username in game['players']:
            game.setdefault('disconnected', set()).add(username)
            emit('player_disconnected', {'username': username}, to=game_id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
[file content end]