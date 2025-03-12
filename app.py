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
from models import db, migrate, Game, Player, Question, Answer, Rating
from sqlalchemy import create_engine, func
from sqlalchemy.exc import SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_fixed

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# List of random trivia topics
RANDOM_TOPICS = [
    "Elementary Mathematics & Mathematicians",
    "Business & Economic History",
    "1960s Music & Trends",
    "1970s Rock & Music Charts",
    "1980s Music & Nostalgia",
    "1990s Music & Pop",
    "2010s Music & Modern Hits",
    "Music Industry & Production",
    "Famous Inventions Through the Ages",
    "Ancient Civilizations & Inventions",
    "Medieval History & Legends",
    "Renaissance & Enlightenment",
    "Modern Wars & Conflicts",
    "US History & Political Figures",
    "Political Movements & Ideologies",
    "Historical Figures, Explorers & Spies",
    "Historical Events, Treaties & Disasters",
    "Space Missions & Technology",
    "Astronomy & Cosmic Discoveries",
    "Science & Innovation",
    "Technology & Computer Science",
    "History of Robotics & Automation",
    "Literature, Libraries & Classical Drama",
    "Modern & Genre Fiction",
    "Cinema & Television",
    "Theatre & Live Performances",
    "Fine Arts & Art Movements",
    "Photography & Contemporary Art",
    "Historical Architecture & Monuments",
    "Modern Architecture & Urban Design",
    "Fashion Trends & Designers",
    "Era-Specific Fashion",
    "Dance & Performance Arts",
    "Animation & Cartoons",
    "Video Games & Digital Culture",
    "Team & Olympic Sports",
    "Extreme & Alternative Sports",
    "Culinary Traditions & World Cuisine",
    "Beverages, Brewing & Confections",
    "Languages & Linguistics",
    "Pop Culture & Trends",
    "Comic Books & Superheroes",
    "Medical & Health Breakthroughs",
    "Board Games & Game Design",
    "Toys & Games History",
    "Circus & Carnival History",
    "Street Art & Graffiti",
    "Philosophy & Intellectual Movements",
    "Historical Documents & Diaries",
    "Viking & Norse History",
    "Transportation & Classic Vehicles",
    "Mountaineering & Adventure Expeditions",
    "Historical Trade Routes",
    "Women in History & Entertainment",
    "Urban Legends & Supernatural Myths",
    "Forensic Science & Investigations",
    "Hip-Hop & R&B History",
    "World Religions & Spiritual Traditions",
    "Cultural Festivals & Fairs",
    "Nobel Prize & Laureate Trivia",
    "Classical Music & Composers",
    "Jazz & Blues Legacy",
    "Live Music & Concert Culture",
    "Esports & Competitive Gaming",
    "Environment & Conservation",
    "Animal Kingdom & Wildlife",
    "Underwater Exploration & Marine Wonders",
    "Internet Memes & Viral Trends",
    "Comic Conventions & Fandom Culture",
    "Geography & Landmarks",
    "Documentary & Nonfiction Film",
    "Science Fiction & Fantasy",
    "Futurism & Future Studies",
    "Historical Cartography & Maps",
    "Cultural Icons & Biographies"
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
    logger.error("GEMINI_API_KEY not found in environment variables. Please set it in Heroku config vars.")
    raise ValueError("GEMINI_API_KEY is required")

genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
# Configure session to use cookies and ensure compatibility with Heroku
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

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
        raise
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {str(e)}")
        raise

socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

# Background task to clean up inactive games
def cleanup_inactive_games():
    while True:
        try:
            with app.app_context():
                now = datetime.utcnow()
                inactive_threshold = now - timedelta(minutes=2)
                inactive_games = Game.query.filter(Game.last_activity < inactive_threshold).all()
                if not inactive_games:
                    logger.debug("No inactive games found for cleanup")
                for game in inactive_games:
                    game_id = game.id
                    players_count = Player.query.filter_by(game_id=game_id).count()
                    questions_count = Question.query.filter_by(game_id=game_id).count()
                    answers_count = Answer.query.filter_by(game_id=game_id).count()
                    logger.info(
                        f"Cleaning up inactive game {game_id}: "
                        f"{players_count} players, {questions_count} questions, {answers_count} answers"
                    )

                    db.session.delete(game)
                    db.session.commit()

                    players_after = Player.query.filter_by(game_id=game_id).count()
                    questions_after = Question.query.filter_by(game_id=game_id).count()
                    answers_after = Answer.query.filter_by(game_id=game_id).count()
                    if players_after == 0 and questions_after == 0 and answers_after == 0:
                        logger.info(f"Successfully deleted inactive game {game_id} and all related data")
                    else:
                        logger.error(
                            f"Failed to delete all related data for game {game_id}: "
                            f"{players_after} players, {questions_after} questions, {answers_after} answers remain"
                        )
        except Exception as e:
            logger.error(f"Error in cleanup_inactive_games: {str(e)}")
            if 'db' in locals():
                db.session.rollback()
        socketio.sleep(60)

# Start the cleanup task
socketio.start_background_task(cleanup_inactive_games)

# Helper function to update last_activity for a game with retry logic
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def update_game_activity(game_id):
    try:
        game = Game.query.filter_by(id=game_id).first()
        if game:
            game.last_activity = datetime.utcnow()
            db.session.commit()
            logger.debug(f"Updated last_activity for game {game_id}")
    except Exception as e:
        logger.error(f"Error updating last_activity for game {game_id}: {str(e)}")
        db.session.rollback()
        raise

# Recommendation 3: Topic Recommendation Algorithm (for placeholder text)
def recommend_topic(game_id, username):
    player = Player.query.filter_by(game_id=game_id, username=username).first()
    if not player:
        return "Enter a topic (e.g., Science, History, Movies)"

    # Fetch all answers and questions for this player in the game
    answers_with_questions = db.session.query(Answer, Question).join(
        Question, Answer.question_id == Question.id
    ).filter(
        Answer.player_id == player.id,
        Answer.game_id == game_id
    ).all()

    topic_performance = {}
    for answer, question in answers_with_questions:
        if answer.answer == question.answer_text:
            # Extract topic heuristically from question text
            topic_match = re.search(r"about (.+?)[?.!]", question.question_text)
            topic = topic_match.group(1) if topic_match else question.question_text.split()[0]
            topic_performance[topic] = topic_performance.get(topic, 0) + 1

    if topic_performance:
        # Find the max score
        max_score = max(topic_performance.values())
        # Get all topics with the max score
        top_topics = [topic for topic, score in topic_performance.items() if score == max_score]
        if len(top_topics) == 1:
            return f"Try: {top_topics[0]}"
        else:
            return f"Try: {' or '.join(top_topics)}"
    return "Enter a topic (e.g., Science, History, Movies)"

@app.route('/')
def welcome():
    game_id = session.get('game_id')
    if game_id:
        with app.app_context():
            update_game_activity(game_id)
    return render_template('welcome.html')

@app.route('/play')
def play():
    game_id = session.get('game_id')
    if game_id:
        with app.app_context():
            update_game_activity(game_id)
    return render_template('index.html')

@app.route('/create_game', methods=['POST'])
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def create_game():
    username = request.form.get('username')
    if not username:
        return render_template('index.html', error="Username is required")

    game_id = generate_game_id()
    try:
        with app.app_context():
            existing_player = Player.query.filter_by(game_id=game_id, username=username).first()
            if existing_player:
                return render_template('index.html', error="Username already taken in this game session. Please choose a different name.")

            new_game = Game(id=game_id, host=username, status='waiting')
            db.session.add(new_game)
            db.session.flush()

            new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(PLAYER_EMOJIS), disconnected=False)
            db.session.add(new_player)
            db.session.commit()

            session['game_id'] = game_id
            session['username'] = username
            session.permanent = True
            
            update_game_activity(game_id)
            logger.info(f"Game {game_id} created by {username}")
            return redirect(url_for('game', game_id=game_id))
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error creating game: {str(e)}")
        return render_template('index.html', error="An error occurred while creating the game. Please try again.")
    except Exception as e:
        logger.error(f"Unexpected error in create_game: {str(e)}")
        return render_template('index.html', error="An unexpected error occurred. Please try again.")

@app.route('/join_game', methods=['POST'])
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def join_game():
    username = request.form.get('username')
    game_id = request.form.get('game_id')
    
    if not username or not game_id:
        return render_template('index.html', error="Username and Game ID are required")

    try:
        with app.app_context():
            game = Game.query.filter_by(id=game_id).first()
            if not game:
                return render_template('index.html', error="Game not found")

            existing_player = Player.query.filter_by(game_id=game_id, username=username).first()
            if existing_player:
                existing_player.disconnected = False
                db.session.commit()
                session['game_id'] = game_id
                session['username'] = username
                session.permanent = True
                update_game_activity(game_id)
                logger.info(f"Player {username} rejoined game {game_id}")
                return redirect(url_for('game', game_id=game_id))
            
            if game.status != 'waiting' or Player.query.filter_by(game_id=game_id).count() >= 10:
                return render_template('index.html', error="Game already in progress or full")

            if Player.query.filter_by(game_id=game_id, username=username).first():
                return render_template('index.html', error="Username already taken in this game session. Please choose a different name.")

            available_emojis = [e for e in PLAYER_EMOJIS if e not in [p.emoji for p in Player.query.filter_by(game_id=game_id).all()]]
            new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(available_emojis) if available_emojis else random.choice(PLAYER_EMOJIS), disconnected=False)
            db.session.add(new_player)
            db.session.commit()
            session['game_id'] = game_id
            session['username'] = username
            session.permanent = True
            update_game_activity(game_id)
            logger.info(f"Player {username} joined game {game_id}")
            return redirect(url_for('game', game_id=game_id))
    except SQLAlchemyError as e:
        db.session.rollback()
        logger.error(f"Error joining game: {str(e)}")
        return render_template('index.html', error="An error occurred while joining the game. Please try again.")
    except Exception as e:
        logger.error(f"Unexpected error in join_game: {str(e)}")
        return render_template('index.html', error="An unexpected error occurred. Please try again.")

@app.route('/game/<game_id>')
def game(game_id):
    try:
        with app.app_context():
            game = Game.query.filter_by(id=game_id).first()
            if not game:
                logger.warning(f"Game {game_id} not found, redirecting to welcome")
                session.pop('game_id', None)
                session.pop('username', None)
                return redirect(url_for('welcome'))
            
            username = session.get('username')
            if not username or not Player.query.filter_by(game_id=game_id, username=username).first():
                logger.warning(f"Username {username} not found in game {game_id}, redirecting to welcome")
                session.pop('game_id', None)
                session.pop('username', None)
                return redirect(url_for('welcome'))
            
            update_game_activity(game_id)
            logger.debug(f"Rendering game {game_id} for {username}")
            return render_template('game.html', game_id=game_id, username=username, is_host=(username == game.host))
    except Exception as e:
        logger.error(f"Error in game route for game {game_id}: {str(e)}")
        return redirect(url_for('welcome'))

@app.route('/final_scoreboard/<game_id>')
def final_scoreboard(game_id):
    try:
        with app.app_context():
            game = Game.query.filter_by(id=game_id).first()
            if not game:
                logger.warning(f"Game {game_id} not found for final scoreboard, redirecting to welcome")
                return redirect(url_for('welcome'))
            players = Player.query.filter_by(game_id=game_id).all()
            player_scores = {p.username: p.score for p in players}
            player_emojis = {p.username: p.emoji for p in players}

            update_game_activity(game_id)
            return render_template('final_scoreboard.html', game_id=game_id, scores=player_scores, player_emojis=player_emojis)
    except Exception as e:
        logger.error(f"Error in final_scoreboard for game {game_id}: {str(e)}")
        return redirect(url_for('welcome'))

@app.route('/reset_game/<game_id>', methods=['POST'])
@retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
def reset_game(game_id):
    try:
        with app.app_context():
            game = Game.query.filter_by(id=game_id).first()
            if not game:
                logger.warning(f"Game {game_id} not found for reset")
                return jsonify({'error': 'Game not found'}), 404
            
            game.status = 'waiting'
            game.current_player_index = 0
            game.question_start_time = None
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
            
            update_game_activity(game_id)
            return Response(status=200)
    except Exception as e:
        logger.error(f"Error resetting game {game_id}: {str(e)}")
        return jsonify({'error': 'Failed to reset game'}), 500

# Modified get_trivia_question for Recommendation 5
def get_trivia_question(topic):
    try:
        # Check average rating for the topic
        avg_rating = db.session.query(func.avg(Rating.rating)).join(Question).filter(Question.question_text.contains(topic)).scalar() or 5
        if avg_rating < 2:
            logger.debug(f"Topic '{topic}' has low rating ({avg_rating}), selecting random topic")
            topic = random.choice([t for t in RANDOM_TOPICS if t != topic])

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

# Helper function to get the next active player
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
            update_game_activity(game_id)
            return next_player
    return None

@socketio.on('connect')
def handle_connect():
    logger.debug("Client connected")

@socketio.on('join_game_room')
def handle_join_game_room(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        if game:
            player = Player.query.filter_by(game_id=game_id, username=username).first()
            if player:
                player.disconnected = False
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
                    'current_question': game.current_question
                }, to=game_id)
            elif game.status == 'waiting' and Player.query.filter_by(game_id=game_id).count() < 10:
                if Player.query.filter_by(game_id=game_id, username=username).first():
                    emit('error', {'message': "Username already taken in this game session. Please choose a different name."}, to=game_id)
                    return

                available_emojis = [e for e in PLAYER_EMOJIS if e not in [p.emoji for p in Player.query.filter_by(game_id=game_id).all()]]
                new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(available_emojis) if available_emojis else random.choice(PLAYER_EMOJIS), disconnected=False)
                db.session.add(new_player)
                db.session.commit()
                join_room(game_id)
                emit('player_joined', {
                    'username': username,
                    'players': [p.username for p in Player.query.filter_by(game_id=game_id).all()],
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                }, to=game_id)
            update_game_activity(game_id)

@socketio.on('start_game')
def handle_start_game(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    with app.app_context():
        try:
            start_time = datetime.utcnow()
            logger.debug(f"Starting game {game_id} by {username} at {start_time}")
            
            game = Game.query.filter_by(id=game_id, host=username, status='waiting').first()
            if not game:
                game_check = Game.query.filter_by(id=game_id).first()
                if not game_check:
                    logger.warning(f"Game {game_id} not found for start_game")
                    emit('error', {'message': 'Game not found. Please create a new game.'}, to=game_id)
                    return
                if username != game_check.host:
                    logger.warning(f"User {username} is not the host of game {game_id}")
                    emit('error', {'message': 'Only the host can start the game.'}, to=game_id)
                    return
                if game_check.status != 'waiting':
                    logger.warning(f"Game {game_id} is not in waiting state, current status: {game_check.status}")
                    emit('error', {'message': 'Game cannot be started. It may already be in progress.'}, to=game_id)
                    return

            game.status = 'in_progress'
            db.session.commit()

            players = Player.query.filter_by(game_id=game_id).all()
            current_player = players[game.current_player_index] if players else None
            if current_player and current_player.disconnected:
                current_player = get_next_active_player(game_id)
            
            player_data = {
                'current_player': current_player.username if current_player else None,
                'players': [p.username for p in players],
                'scores': {p.username: p.score for p in players},
                'player_emojis': {p.username: p.emoji for p in players}
            }
            
            end_time = datetime.utcnow()
            logger.debug(f"Game {game_id} started by host {username}, current player: {current_player.username if current_player else 'None'}, took {(end_time - start_time).total_seconds()} seconds")
            emit('game_started', player_data, to=game_id)
            update_game_activity(game_id)
        except Exception as e:
            logger.error(f"Error starting game {game_id}: {str(e)}")
            db.session.rollback()
            emit('error', {'message': 'Failed to start game. Please try again.'}, to=game_id)

@socketio.on('select_topic')
def handle_select_topic(data):
    game_id = data.get('game_id')
    username = data.get('username')
    topic = data.get('topic')

    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        current_player = Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first()
        if (game and username in [p.username for p in Player.query.filter_by(game_id=game_id).all()] and 
            game.status == 'in_progress' and current_player.username == username):

            existing_questions = Question.query.filter_by(game_id=game_id).all()
            existing_question_texts = [q.question_text for q in existing_questions]
            existing_answers = [q.answer_text for q in existing_questions]

            max_attempts = 10
            for attempt in range(max_attempts):
                # If topic is empty and 'Random Topic' was clicked, pick a truly random topic
                if not topic or topic.strip() == "":
                    topic = random.choice(RANDOM_TOPICS)
                    emit('random_topic_selected', {'topic': topic}, to=game_id)
                # Otherwise, use the player-entered topic

                question_data = get_trivia_question(topic)
                question_text = question_data['question']
                answer_text = question_data['answer']

                is_duplicate = (question_text in existing_question_texts or 
                              answer_text in existing_answers)

                if not is_duplicate:
                    new_question = Question(game_id=game_id, question_text=question_text, answer_text=answer_text)
                    db.session.add(new_question)
                    db.session.flush()
                    game.current_question = question_data
                    game.current_question['question_id'] = new_question.id
                    game.question_start_time = datetime.utcnow()
                    db.session.commit()

                    emit('question_ready', {
                        'question': question_data['question'],
                        'options': question_data['options'],
                        'topic': topic,
                        'question_id': new_question.id
                    }, to=game_id)
                    socketio.start_background_task(question_timer, game_id)
                    update_game_activity(game_id)
                    return
                else:
                    logger.debug(f"Attempt {attempt + 1} failed: Duplicate question or answer found")

            emit('error', {'message': "Couldn't generate a unique question after 10 attempts. Try another topic."}, to=game_id)
        else:
            # Send placeholder recommendation if not their turn
            recommendation = recommend_topic(game_id, username)
            emit('update_placeholder', {'placeholder': recommendation}, to=request.sid)

def question_timer(game_id):
    import time
    time.sleep(30)
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        if game and game.status == 'in_progress':
            active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
            for player in active_players:
                if not Answer.query.filter_by(game_id=game_id, player_id=player.id, question_id=game.current_question['question_id']).first():
                    new_answer = Answer(game_id=game_id, player_id=player.id, question_id=game.current_question['question_id'], answer=None)
                    db.session.add(new_answer)
            db.session.commit()

            if Answer.query.filter_by(game_id=game_id, question_id=game.current_question['question_id']).count() == len(active_players):
                current_question = Question.query.filter_by(game_id=game_id, id=game.current_question['question_id']).first()
                correct_answer = game.current_question['answer']
                correct_players = [p for p in active_players if Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question.id).first().answer == correct_answer]
                for p in correct_players:
                    p.score += 1
                db.session.commit()

                max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
                if max_score >= 10:
                    emit('game_ended', {
                        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                    }, to=game_id)
                    update_game_activity(game_id)
                    return
                
                next_player = get_next_active_player(game_id)
                if next_player:
                    emit('round_results', {
                        'correct_answer': correct_answer,
                        'explanation': game.current_question['explanation'],
                        'player_answers': {p.username: a.answer for p, a in [(p, Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question.id).first()) for p in Player.query.filter_by(game_id=game_id).all()]},
                        'correct_players': [p.username for p in correct_players],
                        'next_player': next_player.username,
                        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()},
                        'question_id': current_question.id
                    }, to=game_id)
                    emit('request_feedback', {'question_id': current_question.id}, to=game_id)
                    db.session.query(Answer).filter_by(game_id=game_id, question_id=current_question.id).delete()
                    db.session.commit()
                    update_game_activity(game_id)
                else:
                    emit('game_paused', {'message': 'No active players remaining'}, to=game_id)
                    update_game_activity(game_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    username = data.get('username')
    answer = data.get('answer')
    
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        player = Player.query.filter_by(game_id=game_id, username=username).first()
        if (game and player and game.status == 'in_progress' and game.current_question):
            
            time_elapsed = datetime.utcnow() - game.question_start_time
            if time_elapsed.total_seconds() > 30:
                answer = None

            if answer in ['A', 'B', 'C', 'D']:
                option_index = ord(answer) - ord('A')
                answer = game.current_question['options'][option_index]
            
            existing_answer = Answer.query.filter_by(game_id=game_id, player_id=player.id, question_id=game.current_question['question_id']).first()
            if existing_answer:
                existing_answer.answer = answer
            else:
                new_answer = Answer(game_id=game_id, player_id=player.id, question_id=game.current_question['question_id'], answer=answer)
                db.session.add(new_answer)
            db.session.commit()

            emit('player_answered', {'username': username}, to=game_id)
            
            active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
            if len(active_players) == 1:
                correct_answer = game.current_question['answer']
                correct_players = [p for p in active_players if Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=game.current_question['question_id']).first().answer == correct_answer]
                
                for p in correct_players:
                    p.score += 1
                db.session.commit()

                current_question = Question.query.filter_by(game_id=game_id, id=game.current_question['question_id']).first()
                max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
                if max_score >= 10:
                    emit('game_ended', {
                        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                    }, to=game_id)
                    update_game_activity(game_id)
                    return

                next_player = get_next_active_player(game_id)
                if next_player:
                    emit('round_results', {
                        'correct_answer': correct_answer,
                        'explanation': game.current_question['explanation'],
                        'player_answers': {p.username: a.answer for p, a in [(p, Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question.id).first()) for p in Player.query.filter_by(game_id=game_id).all()]},
                        'correct_players': [p.username for p in correct_players],
                        'next_player': next_player.username,
                        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()},
                        'question_id': current_question.id
                    }, to=game_id)
                    emit('request_feedback', {'question_id': current_question.id}, to=game_id)
                    db.session.query(Answer).filter_by(game_id=game_id, question_id=current_question.id).delete()
                    db.session.commit()
                    update_game_activity(game_id)
                else:
                    emit('game_paused', {'message': 'No active players remaining'}, to=game_id)
                    update_game_activity(game_id)
            elif Answer.query.filter_by(game_id=game_id, question_id=game.current_question['question_id']).count() == len(active_players):
                correct_answer = game.current_question['answer']
                correct_players = [p for p in active_players if Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=game.current_question['question_id']).first().answer == correct_answer]
                
                for p in correct_players:
                    p.score += 1
                db.session.commit()

                current_question = Question.query.filter_by(game_id=game_id, id=game.current_question['question_id']).first()
                max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
                if max_score >= 10:
                    emit('game_ended', {
                        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                    }, to=game_id)
                    update_game_activity(game_id)
                    return

                next_player = get_next_active_player(game_id)
                if next_player:
                    emit('round_results', {
                        'correct_answer': correct_answer,
                        'explanation': game.current_question['explanation'],
                        'player_answers': {p.username: a.answer for p, a in [(p, Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question.id).first()) for p in Player.query.filter_by(game_id=game_id).all()]},
                        'correct_players': [p.username for p in correct_players],
                        'next_player': next_player.username,
                        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()},
                        'question_id': current_question.id
                    }, to=game_id)
                    emit('request_feedback', {'question_id': current_question.id}, to=game_id)
                    db.session.query(Answer).filter_by(game_id=game_id, question_id=current_question.id).delete()
                    db.session.commit()
                    update_game_activity(game_id)
                else:
                    emit('game_paused', {'message': 'No active players remaining'}, to=game_id)
                    update_game_activity(game_id)

# Recommendation 5: Handle feedback submission
@socketio.on('submit_feedback')
def handle_feedback(data):
    game_id = data.get('game_id')  # Added to match client emit
    question_id = data.get('question_id')
    username = data.get('username')
    rating = data.get('rating')
    with app.app_context():
        player = Player.query.filter_by(username=username).first()
        question = Question.query.get(question_id)
        if player and question and 0 <= rating <= 5:
            existing_rating = Rating.query.filter_by(player_id=player.id, question_id=question_id).first()
            if existing_rating:
                existing_rating.rating = rating
            else:
                new_rating = Rating(game_id=question.game_id, player_id=player.id, question_id=question_id, rating=rating)
                db.session.add(new_rating)
            db.session.commit()
            logger.debug(f"Player {username} rated question {question_id} with {rating}")

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    with app.app_context():
        for game in Game.query.all():
            player = Player.query.filter_by(game_id=game.id, username=username).first()
            if player:
                player.disconnected = True
                db.session.commit()
                emit('player_disconnected', {'username': username}, to=game.id)
                emit('player_left', {  # Added to match your game.html expectation
                    'username': username,
                    'players': [p.username for p in Player.query.filter_by(game_id=game.id).all()],
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game.id).all()}
                }, to=game.id)
                if (game.status == 'in_progress' and 
                    Player.query.filter_by(game.id).offset(game.current_player_index).first().username == username):
                    next_player = get_next_active_player(game.id)
                    if next_player:
                        game.current_player_index = Player.query.filter_by(game.id).all().index(next_player)
                        db.session.commit()
                        emit('turn_skipped', {
                            'disconnected_player': username,
                            'next_player': next_player.username
                        }, to=game.id)
                update_game_activity(game.id)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)