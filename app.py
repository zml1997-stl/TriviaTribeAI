from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import os
import uuid
import google.generativeai as genai
from dotenv import load_dotenv
import secrets
import json
import random
import re
import string
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# List of random trivia topics
RANDOM_TOPICS = [
    "3rd grade math", "Business", "2010s music", "80s nostalgia", "Famous inventions", 
    "World history", "Mythology", "Animal kingdom", "Space exploration", "Famous authors", 
    "Food and cuisine", "Famous landmarks", "Olympic history", "Pop culture", "Famous movie quotes", 
    "Geography", "Superheroes", "Modern art", "Scientific discoveries", "Historical events", 
    "US presidents", "Fashion trends", "Classic literature", "Broadway musicals", "Medical breakthroughs", 
    "Ancient civilizations", "Video game history", "Technology innovations", "Sports trivia", "Famous paintings", 
    "Iconic TV shows", "Music festivals", "World religions", "Presidents of other countries", "Film directors", 
    "Musical instruments", "Historical figures", "90s cartoons", "Natural wonders", "Famous scientists", 
    "Classic cars", "Environmental issues", "Art movements", "70s rock music", "Political scandals", 
    "World capitals", "Winter holidays", "Dance styles", "Popular board games", "Famous photographers", 
    "Architecture", "Classic literature adaptations", "Inventions by women", "World War II", "Famous TV hosts", 
    "Famous duos in history", "Famous criminals", "Inventions in the 20th century", "Lost civilizations", "Space missions", 
    "Languages", "Famous artists", "World sports tournaments", "Underwater exploration", "Famous beaches", 
    "Political revolutions", "Famous explorers", "Wild West history", "The Renaissance", "Famous writers of the 20th century", 
    "African history", "Historical wars", "Technology companies", "Global warming", "Ancient architecture", 
    "Civil rights movements", "Favorite childhood snacks", "Legendary monsters and cryptids", "Historical novels", "Scientific theories", 
    "Major historical treaties", "World fairs", "Golden Age of Hollywood", "Famous mathematicians", "Famous comedians", 
    "Surrealist artists", "Unsolved mysteries", "World Trade history", "Chinese dynasties", "Ancient Egypt", 
    "Music theory", "Wildlife conservation", "Famous political speeches", "Social movements", "Vintage TV shows", 
    "Film noir", "Rock ‘n’ roll pioneers", "Hip-hop history", "Fashion designers", "Great explorers of the seas", 
    "Major natural disasters", "Ballet history", "Horror movie icons", "Futurism", "Street art", 
    "Political ideologies", "Nobel Prize winners", "Classical composers", "Modern philosophy", "Cold War", 
    "World War I", "Civilizations of Mesoamerica", "Classic movie musicals", "Famous historical speeches", "The Enlightenment", 
    "Dinosaurs", "Famous historical paintings", "Forensic science", "The American Revolution", "Inventions that changed the world", 
    "Industrial Revolution", "Broadway legends", "Historic music genres", "Wonders of the Ancient World", "Native American history", 
    "Prohibition", "Space telescopes", "Women in history", "Music videos", "Great scientific minds", 
    "Early cinema", "Punk rock", "World food history", "Mythological creatures", "Comedy legends", 
    "Early explorers", "Natural history museums", "Astronomy", "Ancient Rome", "Ancient Greece", 
    "Invention of the airplane", "Nobel laureates in science", "Pirates", "Shakespearean plays", "Famous philosophers", 
    "Art history", "Supernatural legends", "Circus history", "Comic book artists", "Classic literature quotes", 
    "80s cartoons", "Famous murders", "Urban legends", "Extreme sports", "Music charts", 
    "Historical diseases", "Fairytales and folklore", "Nobel Prize in Literature", "Victorian England", "Global protests", 
    "The Great Depression", "Historical weapons", "Environmental movements", "Christmas traditions", "Modern dance", 
    "Musical genres from the 60s", "Famous athletes of the 20th century", "Space technology", "African American history", "Famous female politicians", 
    "Renaissance painters", "Gender equality movements", "Rock festivals", "History of photography", "Monarchy history", 
    "Comic book movies", "Ancient rituals", "Steam engines", "Victorian fashion", "Nature documentaries", 
    "World folk music", "Famous historical documents", "Classic board games", "Inventions of the 21st century", "Hidden treasures", 
    "Ancient texts and manuscripts", "Famous food chefs", "Mid-century architecture", "Medieval kings and queens", "Famous sports teams", 
    "US history", "Famous TV villains", "Bizarre laws around the world", "World mythologies", "Art exhibitions", 
    "Scientific explorations", "Renaissance festivals", "Classic sci-fi literature", "Medieval knights", "International film festivals", 
    "Music charts in the 70s", "The Silk Road", "Renaissance art", "Old Hollywood stars", "Political dynasties", 
    "Ancient inventions", "Famous spies", "2000s fashion", "Famous libraries", "Color theory in art", 
    "History of robotics", "Music producers", "Nobel Peace Prize winners", "Ancient philosophy", "Viking history", 
    "Mysterious disappearances", "Famous art heists", "Ancient medicine", "Pirates of the Caribbean", "Early civilizations", 
    "Famous historical novels", "Global economic history", "Archaeological discoveries", "Rock legends", "World capitals trivia", 
    "Famous movie directors", "Animal migration", "History of the internet", "Famous television writers", "Famous cartoonists", 
    "Famous philosophers of the 20th century", "Olympic athletes of all time", "Medieval architecture", "Music theory terms", "The Beatles", 
    "Classical architecture", "Romanticism in art", "Internet culture", "2000s TV shows", "Military strategies in history", 
    "The Great Wall of China", "Chinese philosophy", "Space exploration milestones", "History of banking", "Baroque art", 
    "Beatles songs", "Famous space missions", "The Industrial Age", "Victorian novels", "Pop culture references", 
    "Modern superheroes", "American authors", "90s music", "Global cities", "Early computer science", 
    "Classic cinema icons", "First ladies of the United States", "Women in entertainment", "Famous classical operas", "The Salem witch trials", 
    "Ancient Chinese inventions", "Nobel Prize in Peace", "Famous fashion icons", "Renaissance artists", "Jazz history", 
    "Golden Age of Television", "Famous historical diaries", "Famous World War II generals", "90s video games", "Shakespeare's works", 
    "Classic board game design", "History of circus performances", "Mountaineering expeditions", "Ancient Rome vs. Ancient Greece", "Famous mathematicians of history", 
    "The evolution of the internet", "Renowned chefs and their dishes", "Black History Month trivia", "Ancient Egyptian gods", "Legendary actors and actresses", 
    "Feminism in history", "Environmental disasters", "Music legends of the 60s", "History of the telephone", "Classic detective novels", 
    "Ancient libraries", "Mythological heroes", "Endangered species", "World War I leaders", "The Great Fire of London", 
    "Classic punk bands", "Gold Rush history", "The Spanish Inquisition", "History of skateboarding", "History of chocolate", 
    "History of theater", "The art of brewing", "The history of toys and games"
]

# List of emojis for player icons
PLAYER_EMOJIS = [
    "😄", "😂", "😎", "🤓", "🎉", "🚀", "🌟", "🍕", "🎸", "🎮",
    "🏆", "💡", "🌍", "🎨", "📚", "🔥", "💎", "🐱", "🐶", "🌸"
]

def generate_game_id():
    while True:
        game_id = ''.join(random.choices(string.ascii_uppercase, k=4))
        if game_id not in games:
            return game_id

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Game state storage
games = {}

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/play')
def play():
    return render_template('index.html')

@app.route('/create_game', methods=['POST'])
def create_game():
    username = request.form.get('username')
    if not username:
        return redirect(url_for('play'))
    
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
        'question_start_time': None,
        'player_emojis': {username: random.choice(PLAYER_EMOJIS)},
        'questions_asked': []
    }
    
    session['game_id'] = game_id
    session['username'] = username
    
    return redirect(url_for('game', game_id=game_id))

@app.route('/join_game', methods=['POST'])
def join_game():
    username = request.form.get('username')
    game_id = request.form.get('game_id')
    
    if not username or not game_id:
        return redirect(url_for('play'))
    
    if game_id not in games:
        return "Game not found", 404
    
    # Allow rejoining only if the player was already in the game
    if username in games[game_id]['players']:
        session['game_id'] = game_id
        session['username'] = username
        return redirect(url_for('game', game_id=game_id))
    
    # Block new players if game is in progress or full
    if games[game_id]['status'] != 'waiting':
        return "Game already in progress", 403
    
    if len(games[game_id]['players']) >= 10:
        return "Game is full", 403
    
    # Add new player during waiting phase
    games[game_id]['players'].append(username)
    games[game_id]['scores'][username] = 0
    available_emojis = [e for e in PLAYER_EMOJIS if e not in games[game_id]['player_emojis'].values()]
    if available_emojis:
        games[game_id]['player_emojis'][username] = random.choice(available_emojis)
    else:
        games[game_id]['player_emojis'][username] = random.choice(PLAYER_EMOJIS)
    
    session['game_id'] = game_id
    session['username'] = username
    
    return redirect(url_for('game', game_id=game_id))

@app.route('/game/<game_id>')
def game(game_id):
    if game_id not in games:
        return redirect(url_for('welcome'))
    
    username = session.get('username')
    if not username or username not in games[game_id]['players']:
        return redirect(url_for('welcome'))
    
    return render_template('game.html', game_id=game_id, username=username, is_host=(username == games[game_id]['host']))

@app.route('/final_scoreboard/<game_id>')
def final_scoreboard(game_id):
    if game_id not in games:
        return redirect(url_for('welcome'))
    return render_template('final_scoreboard.html', game_id=game_id, scores=games[game_id]['scores'], player_emojis=games[game_id]['player_emojis'])

@app.route('/reset_game/<game_id>', methods=['POST'])
def reset_game(game_id):
    if game_id not in games:
        return jsonify({'error': 'Game not found'}), 404
    
    game = games[game_id]
    game['status'] = 'waiting'
    game['current_player_index'] = 0
    game['current_question'] = None
    game['answers'] = {}
    game['scores'] = {player: 0 for player in game['players']}
    game['question_start_time'] = None
    game['questions_asked'] = []
    
    logger.debug(f"Game {game_id} reset by request")
    socketio.emit('game_reset', {
        'players': game['players'],
        'scores': game['scores'],
        'player_emojis': game['player_emojis']
    }, to=game_id)
    
    return Response(status=200)

def get_trivia_question(topic):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""
    Generate a well-structured trivia question about "{topic}" with a single, clear, and unambiguous answer.
    
    Requirements:
    - The question should be engaging, specific, and of average difficulty, similar to a standard trivia game.
    - The answer must be accurate and verifiable.
    - Provide four multiple-choice options: one correct answer and three plausible but incorrect distractors.
    - Do not repeat or hint at the answer within the question.
    - Ensure the question is broad enough that an average person might reasonably know or guess it if it is super specific.
    - Keep the question modern and widely recognizable unless the topic requires historical context. 
    - Return your response strictly in the following JSON format, with no additional text outside the JSON:
        {{
            "question": "The trivia question",
            "answer": "The correct answer",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "explanation": "A concise explanation of why the answer is correct"
        }}
        """
        response = model.generate_content(prompt)
        try:
            cleaned_text = response.text.replace('`json', '').replace('`', '').strip()
            result = json.loads(cleaned_text)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError: {e} - Raw response text: {response.text}")
            return {
                "question": f"What is a notable fact about {topic}?",
                "answer": "Unable to generate answer",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "explanation": "There was an error parsing the AI response (JSONDecodeError)."
            }
    except Exception as e:
        logger.error(f"Error generating question: {str(e)}")
        return {
            "question": f"What is a notable fact about {topic}?",
            "answer": "Unable to generate answer",
            "options": ["Option A", "Option B", "Option C", "Option D"],
            "explanation": "There was an error with the AI service (General Exception)."
        }

# Helper function to get the next active player
def get_next_active_player(game_id):
    game = games[game_id]
    current_index = game['current_player_index']
    players = game['players']
    num_players = len(players)
    
    for _ in range(num_players):
        current_index = (current_index + 1) % num_players
        next_player = players[current_index]
        if next_player not in game['disconnected']:
            game['current_player_index'] = current_index
            return next_player
    return None

@socketio.on('connect')
def handle_connect():
    logger.debug("Client connected")

@socketio.on('join_game_room')
def handle_join_game_room(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    if game_id in games:
        if username in games[game_id]['players']:
            # Player is reconnecting
            games[game_id]['disconnected'].discard(username)
            join_room(game_id)
            logger.debug(f"Player {username} rejoined room {game_id}")
            emit('player_rejoined', {
                'username': username,
                'players': games[game_id]['players'],
                'scores': games[game_id]['scores'],
                'player_emojis': games[game_id]['player_emojis'],
                'status': games[game_id]['status'],
                'current_player': games[game_id]['players'][games[game_id]['current_player_index']] if games[game_id]['status'] == 'in_progress' else None,
                'current_question': games[game_id]['current_question'] if games[game_id]['status'] == 'in_progress' else None
            }, to=game_id)
        elif games[game_id]['status'] == 'waiting' and len(games[game_id]['players']) < 10:
            # New player joining in waiting phase
            games[game_id]['players'].append(username)
            games[game_id]['scores'][username] = 0
            available_emojis = [e for e in PLAYER_EMOJIS if e not in games[game_id]['player_emojis'].values()]
            games[game_id]['player_emojis'][username] = random.choice(available_emojis) if available_emojis else random.choice(PLAYER_EMOJIS)
            join_room(game_id)
            emit('player_joined', {
                'username': username,
                'players': games[game_id]['players'],
                'player_emojis': games[game_id]['player_emojis']
            }, to=game_id)

@socketio.on('start_game')
def handle_start_game(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    try:
        if game_id in games and username == games[game_id]['host'] and games[game_id]['status'] == 'waiting':
            games[game_id]['status'] = 'in_progress'
            current_player = games[game_id]['players'][games[game_id]['current_player_index']]
            if current_player in games[game_id]['disconnected']:
                current_player = get_next_active_player(game_id)
            logger.debug(f"Game {game_id} started by host {username}, current player: {current_player}")
            
            emit('game_started', {
                'current_player': current_player,
                'players': games[game_id]['players'],
                'scores': games[game_id]['scores'],
                'player_emojis': games[game_id]['player_emojis']
            }, to=game_id)
        else:
            logger.warning(f"Invalid start game request for game {game_id} by {username}")
    except Exception as e:
        logger.error(f"Error starting game {game_id}: {str(e)}")
        emit('error', {'message': 'Failed to start game. Please try again.'}, to=game_id)

@socketio.on('select_topic')
def handle_select_topic(data):
    game_id = data.get('game_id')
    username = data.get('username')
    topic = data.get('topic')

    if (game_id in games and 
        username in games[game_id]['players'] and 
        games[game_id]['status'] == 'in_progress' and
        games[game_id]['players'][games[game_id]['current_player_index']] == username):

        if 'questions_asked' not in games[game_id]:
            games[game_id]['questions_asked'] = []

        max_attempts = 10
        for _ in range(max_attempts):
            if not topic:
                topic = random.choice(RANDOM_TOPICS)
                emit('random_topic_selected', {'topic': topic}, to=game_id)

            question_data = get_trivia_question(topic)
            question_text = question_data['question']
            answer_text = question_data['answer']

            duplicate_found = False
            for prev_question, prev_answer in games[game_id]['questions_asked']:
                if answer_text == prev_answer or question_text == prev_question:
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
                socketio.start_background_task(question_timer, game_id)
                return

        emit('error', {'message': "Couldn't generate a unique question. Try another topic."}, to=game_id)

def question_timer(game_id):
    import time
    time.sleep(30)  # 30-second timeout
    if game_id in games and games[game_id]['status'] == 'in_progress':
        active_players = [p for p in games[game_id]['players'] if p not in games[game_id]['disconnected']]
        for player in active_players:
            if player not in games[game_id]['answers']:
                games[game_id]['answers'][player] = None
        for player in games[game_id]['disconnected']:
            if player in games[game_id]['players']:
                games[game_id]['answers'][player] = None
        
        correct_answer = games[game_id]['current_question']['answer']
        correct_players = [p for p, a in games[game_id]['answers'].items() if a == correct_answer]
        for p in correct_players:
            games[game_id]['scores'][p] += 1
        
        max_score = max(games[game_id]['scores'].values())
        if max_score >= 10:
            emit('game_ended', {
                'scores': games[game_id]['scores'],
                'player_emojis': games[game_id]['player_emojis']
            }, to=game_id)
            return
        
        next_player = get_next_active_player(game_id)
        if next_player:
            games[game_id]['current_player_index'] = games[game_id]['players'].index(next_player)
            emit('round_results', {
                'correct_answer': correct_answer,
                'explanation': games[game_id]['current_question']['explanation'],
                'player_answers': games[game_id]['answers'],
                'correct_players': correct_players,
                'next_player': next_player,
                'scores': games[game_id]['scores'],
                'player_emojis': games[game_id]['player_emojis']
            }, to=game_id)
        else:
            emit('game_paused', {'message': 'No active players remaining'}, to=game_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    username = data.get('username')
    answer = data.get('answer')
    
    if (game_id in games and 
        username in games[game_id]['players'] and 
        games[game_id]['status'] == 'in_progress' and
        games[game_id]['current_question']):
        
        time_elapsed = datetime.now() - games[game_id]['question_start_time']
        if time_elapsed.total_seconds() > 30:
            answer = None

        if answer in ['A', 'B', 'C', 'D']:
            option_index = ord(answer) - ord('A')
            answer = games[game_id]['current_question']['options'][option_index]
        
        games[game_id]['answers'][username] = answer
        emit('player_answered', {'username': username}, to=game_id)
        
        active_players = [p for p in games[game_id]['players'] if p not in games[game_id]['disconnected']]
        if len(games[game_id]['answers']) == len(active_players):
            correct_answer = games[game_id]['current_question']['answer']
            correct_players = []
            
            for player, player_answer in games[game_id]['answers'].items():
                if player_answer == correct_answer:
                    correct_players.append(player)
                    games[game_id]['scores'][player] += 1
            
            max_score = max(games[game_id]['scores'].values())
            if max_score >= 10:
                emit('game_ended', {
                    'scores': games[game_id]['scores'],
                    'player_emojis': games[game_id]['player_emojis']
                }, to=game_id)
                return

            next_player = get_next_active_player(game_id)
            if next_player:
                games[game_id]['current_player_index'] = games[game_id]['players'].index(next_player)
                emit('round_results', {
                    'correct_answer': correct_answer,
                    'explanation': games[game_id]['current_question']['explanation'],
                    'player_answers': games[game_id]['answers'],
                    'correct_players': correct_players,
                    'next_player': next_player,
                    'scores': games[game_id]['scores'],
                    'player_emojis': games[game_id]['player_emojis']
                }, to=game_id)
            else:
                emit('game_paused', {'message': 'No active players remaining'}, to=game_id)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    for game_id, game in games.items():
        if username in game['players']:
            game['disconnected'].add(username)
            emit('player_disconnected', {'username': username}, to=game_id)
            if (game['status'] == 'in_progress' and 
                game['players'][game['current_player_index']] == username):
                next_player = get_next_active_player(game_id)
                if next_player:
                    game['current_player_index'] = game['players'].index(next_player)
                    emit('turn_skipped', {
                        'disconnected_player': username,
                        'next_player': next_player
                    }, to=game_id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)