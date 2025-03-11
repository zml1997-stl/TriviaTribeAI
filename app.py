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
from models import db, migrate, Game, Player, Question, Answer
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# List of random trivia topics
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
        game = Game.query.filter_by(id=game_id).first()
        if not game:
            return game_id

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")
genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# Handle DATABASE_URL from Heroku
import urllib.parse
if 'DATABASE_URL' in os.environ:
    url = os.environ['DATABASE_URL']
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/trivia_tribe_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize SQLAlchemy with the app
db.init_app(app)
migrate.init_app(app, db)

# Verify database connection with detailed logging
with app.app_context():
    try:
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        with engine.connect() as connection:
            logger.info("Database connection established successfully")
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {str(e)}")

socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Background task to clean up inactive games
def cleanup_inactive_games():
    while True:
        with app.app_context():
            try:
                now = datetime.utcnow()
                inactive_threshold = now - timedelta(minutes=2)
                inactive_games = Game.query.filter(Game.last_activity < inactive_threshold).all()
                for game in inactive_games:
                    players = Player.query.filter_by(game_id=game.id).all()
                    for player in players:
                        player.disconnected = True
                    db.session.delete(game)
                    logger.info(f"Deleted inactive game {game.id} due to 2 minutes of inactivity")
                db.session.commit()
            except Exception as e:
                logger.error(f"Error in cleanup_inactive_games: {str(e)}")
                db.session.rollback()
        socketio.sleep(60)  # Check every minute

# Start the cleanup task
socketio.start_background_task(cleanup_inactive_games)

@app.route('/')
def welcome():
    with app.app_context():
        game_id = session.get('game_id')
        if game_id:
            game = Game.query.filter_by(id=game_id).first()
            if game:
                game.last_activity = datetime.utcnow()
                db.session.commit()
    return render_template('welcome.html')

@app.route('/play')
def play():
    with app.app_context():
        game_id = session.get('game_id')
        if game_id:
            game = Game.query.filter_by(id=game_id).first()
            if game:
                game.last_activity = datetime.utcnow()
                db.session.commit()
    return render_template('index.html')

@app.route('/create_game', methods=['POST'])
def create_game():
    username = request.form.get('username')
    if not username:
        return render_template('index.html', error="Username is required")

    game_id = generate_game_id()
    existing_player = Player.query.filter_by(game_id=game_id, username=username).first()
    if existing_player:
        return render_template('index.html', error="Username already taken in this game session. Please choose a different name.")

    try:
        new_game = Game(id=game_id, host=username, status='waiting')
        db.session.add(new_game)
        db.session.flush()

        new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(PLAYER_EMOJIS), disconnected=False)
        db.session.add(new_player)
        db.session.commit()

        session['game_id'] = game_id
        session['username'] = username
        return redirect(url_for('game', game_id=game_id))
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error creating game: {str(e)}")
        return render_template('index.html', error="An error occurred while creating the game. Please try again.")

@app.route('/join_game', methods=['POST'])
def join_game():
    username = request.form.get('username')
    game_id = request.form.get('game_id')
    
    if not username or not game_id:
        return render_template('index.html', error="Username and Game ID are required")

    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return render_template('index.html', error="Game not found")

    existing_player = Player.query.filter_by(game_id=game_id, username=username).first()
    if existing_player:
        existing_player.disconnected = False
        db.session.commit()
        session['game_id'] = game_id
        session['username'] = username
        return redirect(url_for('game', game_id=game_id))
    
    if game.status != 'waiting' or Player.query.filter_by(game_id=game_id).count() >= 10:
        return render_template('index.html', error="Game already in progress or full")

    if Player.query.filter_by(game_id=game_id, username=username).first():
        return render_template('index.html', error="Username already taken in this game session. Please choose a different name.")

    try:
        available_emojis = [e for e in PLAYER_EMOJIS if e not in [p.emoji for p in Player.query.filter_by(game_id=game_id).all()]]
        new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(available_emojis) if available_emojis else random.choice(PLAYER_EMOJIS), disconnected=False)
        db.session.add(new_player)
        game.last_activity = datetime.utcnow()
        db.session.commit()

        session['game_id'] = game_id
        session['username'] = username
        return redirect(url_for('game', game_id=game_id))
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error joining game: {str(e)}")
        return render_template('index.html', error="An error occurred while joining the game. Please try again.")

@app.route('/game/<game_id>')
def game(game_id):
    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return redirect(url_for('welcome'))
    
    username = session.get('username')
    if not username or not Player.query.filter_by(game_id=game_id, username=username).first():
        return redirect(url_for('welcome'))
    
    game.last_activity = datetime.utcnow()
    db.session.commit()

    return render_template('game.html', game_id=game_id, username=username, is_host=(username == game.host))

@app.route('/final_scoreboard/<game_id>')
def final_scoreboard(game_id):
    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return redirect(url_for('welcome'))
    players = Player.query.filter_by(game_id=game_id).all()
    player_scores = {p.username: p.score for p in players}
    player_emojis = {p.username: p.emoji for p in players}

    game.last_activity = datetime.utcnow()
    db.session.commit()

    return render_template('final_scoreboard.html', game_id=game_id, scores=player_scores, player_emojis=player_emojis)

@app.route('/reset_game/<game_id>', methods=['POST'])
def reset_game(game_id):
    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return jsonify({'error': 'Game not found'}), 404
    
    game.status = 'waiting'
    game.current_player_index = 0
    game.question_start_time = None
    game.last_activity = datetime.utcnow()
    db.session.query(Question).filter_by(game_id=game_id).delete()
    db.session.query(Answer).filter_by(game_id=game_id).delete()
    players = Player.query.filter_by(game_id=game_id).all()
    for player in players:
        player.score = 0
        player.disconnected = False
    db.session.commit()

    logger.debug(f"Game {game_id} reset by request")
    socketio.emit('game_reset', {
        'players': [p.username for p in players],
        'scores': {p.username: p.score for p in players},
        'player_emojis': {p.username: p.emoji for p in players}
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
    - Provide four multiple-choice options: one correct answer and three plausible but incorrect distractors. At least one of these should be very plausible. 
    - Do not repeat, hint at, or include any part of the answer within the question. The wording should not make the correct answer obvious.
    - Ensure the question is broad enough that an average person might reasonably know or guess it if it is super specific.
    - Ensure the "{topic}" is not the answer to the question. 
    - The wording should feel natural and match the style of a well-crafted trivia question.
    - Keep the question modern and widely recognizable unless the topic requires historical context or are super specific topics. 
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

def get_next_active_player(game_id):
    game = Game.query.filter_by(id=game_id).first()
    players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
    current_index = game.current_player_index
    num_players = len(players)
    
    for _ in range(num_players):
        current_index = (current_index + 1) % num_players
        next_player = players[current_index]
        if not next_player.disconnected:
            game.current_player_index = current_index
            game.last_activity = datetime.utcnow()
            db.session.commit()
            return next_player
    return None

@socketio.on('connect')
def handle_connect():
    logger.debug("Client connected")

@socketio.on('join_game_room')
def handle_join_game_room(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    game = Game.query.filter_by(id=game_id).first()
    if game:
        player = Player.query.filter_by(game_id=game_id, username=username).first()
        if player:
            player.disconnected = False
            game.last_activity = datetime.utcnow()
            db.session.commit()
            join_room(game_id)
            logger.debug(f"Player {username} rejoined room {game_id}")
            emit('player_rejoined', {
                'username': username,
                'players': [p.username for p in Player.query.filter_by(game_id=game_id).all()],
                'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()},
                'status': game.status,
                'current_player': Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first().username if game.status == 'in_progress' else None,
                'current_question': None
            }, to=game_id)
        elif game.status == 'waiting' and Player.query.filter_by(game_id=game_id).count() < 10:
            if Player.query.filter_by(game_id=game_id, username=username).first():
                emit('error', {'message': "Username already taken in this game session. Please choose a different name."}, to=game_id)
                return

            available_emojis = [e for e in PLAYER_EMOJIS if e not in [p.emoji for p in Player.query.filter_by(game_id=game_id).all()]]
            new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(available_emojis) if available_emojis else random.choice(PLAYER_EMOJIS), disconnected=False)
            db.session.add(new_player)
            game.last_activity = datetime.utcnow()
            db.session.commit()
            join_room(game_id)
            emit('player_joined', {
                'username': username,
                'players': [p.username for p in Player.query.filter_by(game_id=game_id).all()],
                'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
            }, to=game_id)

@socketio.on('start_game')
def handle_start_game(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    try:
        game = Game.query.filter_by(id=game_id).first()
        if game and username == game.host and game.status == 'waiting':
            game.status = 'in_progress'
            game.last_activity = datetime.utcnow()
            current_player = Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first()
            if current_player.disconnected:
                current_player = get_next_active_player(game_id)
            db.session.commit()
            logger.debug(f"Game {game_id} started by host {username}, current player: {current_player.username}")
            
            emit('game_started', {
                'current_player': current_player.username,
                'players': [p.username for p in Player.query.filter_by(game_id=game_id).all()],
                'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
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

    game = Game.query.filter_by(id=game_id).first()
    current_player = Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first()
    if (game and username in [p.username for p in Player.query.filter_by(game_id=game_id).all()] and 
        game.status == 'in_progress' and current_player.username == username):

        max_attempts = 10
        for _ in range(max_attempts):
            if not topic:
                topic = random.choice(RANDOM_TOPICS)
                emit('random_topic_selected', {'topic': topic}, to=game_id)

            question_data = get_trivia_question(topic)
            question_text = question_data['question']
            answer_text = question_data['answer']

            duplicate_found = Question.query.filter_by(game_id=game_id, question_text=question_text, answer_text=answer_text).first()
            if not duplicate_found:
                new_question = Question(game_id=game_id, question_text=question_text, answer_text=answer_text)
                db.session.add(new_question)
                game.current_question = question_data  # Store as JSON or restructure as needed
                game.question_start_time = datetime.utcnow()
                game.last_activity = datetime.utcnow()
                db.session.commit()

                emit('question_ready', {
                    'question': question_data['question'],
                    'options': question_data['options'],
                    'topic': topic
                }, to=game_id)
                socketio.start_background_task(question_timer, game_id)
                return

        emit('error', {'message': "Couldn't generate a unique question. Try another topic."}, to=game_id)

def process_round_results(game_id):
    game = Game.query.filter_by(id=game_id).first()
    if not game or game.status != 'in_progress':
        return True  # Return True to indicate game should end if invalid
    
    active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
    correct_answer = game.current_question['answer']
    player_answers = {p.username: Answer.query.filter_by(game_id=game_id, player_id=p.id).first().answer if Answer.query.filter_by(game_id=game_id, player_id=p.id).first() else None for p in active_players}
    correct_players = [p for p in active_players if player_answers[p.username] == correct_answer]
    
    for p in correct_players:
        p.score += 1
    db.session.commit()

    max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
    if max_score >= 10:
        emit('game_ended', {
            'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
            'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
        }, to=game_id)
        return True

    next_player = get_next_active_player(game_id) if len(active_players) > 1 else active_players[0]
    emit('round_results', {
        'correct_answer': correct_answer,
        'explanation': game.current_question['explanation'],
        'player_answers': player_answers,
        'correct_players': [p.username for p in correct_players],
        'next_player': next_player.username if len(active_players) > 1 else active_players[0].username,
        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
    }, to=game_id)
    
    # Clear answers for the next round
    db.session.query(Answer).filter_by(game_id=game_id).delete()
    db.session.commit()
    return False

def question_timer(game_id):
    import time
    time.sleep(30)  # 30-second timeout
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        if game and game.status == 'in_progress':
            active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
            num_answers = Answer.query.filter_by(game_id=game_id).count()
            
            # Force submission for unanswered players
            for player in active_players:
                if not Answer.query.filter_by(game_id=game_id, player_id=player.id).first():
                    new_answer = Answer(game_id=game_id, player_id=player.id, answer=None)
                    db.session.add(new_answer)
            db.session.commit()
            
            # Process results immediately for single player or when all have answered
            if len(active_players) == 1 or num_answers == len(active_players):
                process_round_results(game_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    username = data.get('username')
    answer = data.get('answer')
    
    game = Game.query.filter_by(id=game_id).first()
    player = Player.query.filter_by(game_id=game_id, username=username).first()
    if not (game and player and game.status == 'in_progress' and game.current_question):
        return
    
    time_elapsed = datetime.utcnow() - game.question_start_time
    if time_elapsed.total_seconds() > 30:
        answer = None

    if answer in ['A', 'B', 'C', 'D']:
        option_index = ord(answer) - ord('A')
        answer = game.current_question['options'][option_index]
    
    existing_answer = Answer.query.filter_by(game_id=game_id, player_id=player.id).first()
    if existing_answer:
        existing_answer.answer = answer
    else:
        new_answer = Answer(game_id=game_id, player_id=player.id, answer=answer)
        db.session.add(new_answer)
    game.last_activity = datetime.utcnow()
    db.session.commit()

    emit('player_answered', {'username': username}, to=game_id)
    
    active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
    num_answers = Answer.query.filter_by(game_id=game_id).count()
    
    # Process results immediately for single player or when all have answered
    if len(active_players) == 1 or num_answers == len(active_players):
        process_round_results(game_id)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    for game in Game.query.all():
        player = Player.query.filter_by(game_id=game.id, username=username).first()
        if player:
            player.disconnected = True
            game.last_activity = datetime.utcnow()
            db.session.commit()
            emit('player_disconnected', {'username': username}, to=game.id)
            if (game.status == 'in_progress' and 
                Player.query.filter_by(game_id=game.id).offset(game.current_player_index).first().username == username):
                next_player = get_next_active_player(game.id)
                if next_player:
                    game.current_player_index = Player.query.filter_by(game.id).all().index(next_player)
                    db.session.commit()
                    emit('turn_skipped', {
                        'disconnected_player': username,
                        'next_player': next_player.username
                    }, to=game.id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)