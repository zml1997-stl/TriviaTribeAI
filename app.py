from flask import Flask, render_template, request, redirect, url_for, session, jsonify, Response
import os
import google.generativeai as genai
from dotenv import load_dotenv
import secrets
import json
import random
import string
from flask_socketio import SocketIO, emit, join_room, leave_room
from datetime import datetime, timedelta
import logging
from models import db, migrate, Game, Player, Topic, Question, Answer, Rating
from sqlalchemy import create_engine, func
from sqlalchemy.exc import SQLAlchemyError
from tenacity import retry, stop_after_attempt, wait_fixed

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# List of random trivia topics (for fallback)
RANDOM_TOPICS = [
    "Elementary Mathematics & Mathematicians", "Business & Economic History", "1960s Music & Trends",
    "1970s Rock & Music Charts", "1980s Music & Nostalgia", "1990s Music & Pop", "2010s Music & Modern Hits",
    "Music Industry & Production", "Famous Inventions Through the Ages", "Ancient Civilizations & Inventions",
    "Medieval History & Legends", "Renaissance & Enlightenment", "Modern Wars & Conflicts",
    "US History & Political Figures", "Political Movements & Ideologies", "Historical Figures, Explorers & Spies",
    "Historical Events, Treaties & Disasters", "Space Missions & Technology", "Astronomy & Cosmic Discoveries",
    "Science & Innovation", "Technology & Computer Science", "History of Robotics & Automation",
    "Literature, Libraries & Classical Drama", "Modern & Genre Fiction", "Cinema & Television",
    "Theatre & Live Performances", "Fine Arts & Art Movements", "Photography & Contemporary Art",
    "Historical Architecture & Monuments", "Modern Architecture & Urban Design", "Fashion Trends & Designers",
    "Era-Specific Fashion", "Dance & Performance Arts", "Animation & Cartoons", "Video Games & Digital Culture",
    "Team & Olympic Sports", "Extreme & Alternative Sports", "Culinary Traditions & World Cuisine",
    "Beverages, Brewing & Confections", "Languages & Linguistics", "Pop Culture & Trends",
    "Comic Books & Superheroes", "Medical & Health Breakthroughs", "Board Games & Game Design",
    "Toys & Games History", "Circus & Carnival History", "Street Art & Graffiti",
    "Philosophy & Intellectual Movements", "Historical Documents & Diaries", "Viking & Norse History",
    "Transportation & Classic Vehicles", "Mountaineering & Adventure Expeditions", "Historical Trade Routes",
    "Women in History & Entertainment", "Urban Legends & Supernatural Myths", "Forensic Science & Investigations",
    "Hip-Hop & R&B History", "World Religions & Spiritual Traditions", "Cultural Festivals & Fairs",
    "Nobel Prize & Laureate Trivia", "Classical Music & Composers", "Jazz & Blues Legacy",
    "Live Music & Concert Culture", "Esports & Competitive Gaming", "Environment & Conservation",
    "Animal Kingdom & Wildlife", "Underwater Exploration & Marine Wonders", "Internet Memes & Viral Trends",
    "Comic Conventions & Fandom Culture", "Geography & Landmarks", "Documentary & Nonfiction Film",
    "Science Fiction & Fantasy", "Futurism & Future Studies", "Historical Cartography & Maps",
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
        if not Game.query.filter_by(id=game_id).first():
            return game_id

# Load environment variables
load_dotenv()

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables.")
    raise ValueError("GEMINI_API_KEY is required")

genai.configure(api_key=GEMINI_API_KEY)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

# Database configuration
if 'DATABASE_URL' in os.environ:
    url = os.environ['DATABASE_URL'].replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = url
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://localhost/trivia_tribe_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate.init_app(app, db)

# Verify database connection
with app.app_context():
    try:
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        with engine.connect() as connection:
            logger.info("Database connection established successfully")
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {str(e)}")
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
                for game in inactive_games:
                    db.session.delete(game)
                    db.session.commit()
                    logger.info(f"Cleaned up inactive game {game.id}")
        except Exception as e:
            logger.error(f"Error in cleanup_inactive_games: {str(e)}")
            if 'db' in locals():
                db.session.rollback()
        socketio.sleep(60)

socketio.start_background_task(cleanup_inactive_games)

# Helper function to update last_activity
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

# Get or create a topic
def get_or_create_topic(topic_name):
    normalized_name = topic_name.lower().strip()
    topic = Topic.query.filter_by(normalized_name=normalized_name).first()
    if not topic:
        topic = Topic(normalized_name=normalized_name)
        db.session.add(topic)
        db.session.commit()
    return topic

# NEW: Get player-specific top-rated topics for placeholder
def get_player_top_topics(game_id, username, limit=3):
    player = Player.query.filter_by(game_id=game_id, username=username).first()
    if not player:
        return "Enter a topic or click Random Topic"
    top_topics = db.session.query(
        Topic.normalized_name,
        func.avg(Rating.rating).label('avg_rating'),
        func.count(Rating.id).label('rating_count')
    ).join(Rating, Rating.topic_id == Topic.id
    ).filter(Rating.game_id == game_id, Rating.player_id == player.id
    ).group_by(Topic.normalized_name
    ).order_by(func.avg(Rating.rating).desc()
    ).limit(limit).all()
    return ", ".join([row.normalized_name for row in top_topics]) if top_topics else "Enter a topic or click Random Topic"

# NEW: Suggest a random topic with adaptive logic
def suggest_random_topic(game_id, username=None):
    # Fetch game to determine current player if username not provided
    game = Game.query.get(game_id)
    if not username and game:
        if game.players and 0 <= game.current_player_index < len(game.players):
            username = game.players[game.current_player_index].username

    # Check for 3 incorrect answers in a row if username is available
    use_top_rated = False
    if username:
        player = Player.query.filter_by(username=username, game_id=game_id).first()
        if player:
            recent_answers = db.session.query(Answer, Question
                ).join(Question, Question.id == Answer.question_id
                ).filter(Answer.player_id == player.id,
                         Answer.game_id == game_id
                ).order_by(Question.id.desc()
                ).limit(3).all()
            if len(recent_answers) == 3:
                incorrect_streak = all(
                    a.answer.strip().lower() != q.answer_text.strip().lower()
                    for a, q in recent_answers
                )
                if incorrect_streak:
                    use_top_rated = True

    try:
        # Get the last 5 distinct topics used in this game
        recent_questions = db.session.query(Question.topic_id, Question.id
            ).filter(Question.game_id == game_id
            ).distinct(Question.topic_id
            ).order_by(Question.id.desc()
            ).limit(5).all()
        recent_topic_ids = [tid for (tid, _) in recent_questions if tid is not None]
        recent_topics = [t.normalized_name for t in Topic.query.filter(Topic.id.in_(recent_topic_ids)).all()]
    except Exception as e:
        logger.error(f"Error fetching recent topics for game {game_id}: {str(e)}")
        db.session.rollback()
        recent_topics = []

    try:
        # Get game-wide topic ratings (average across all players)
        topic_ratings = db.session.query(
            Topic.normalized_name,
            func.avg(Rating.rating).label('avg_rating')
        ).join(Rating, Rating.topic_id == Topic.id
        ).filter(Rating.game_id == game_id
        ).group_by(Topic.normalized_name
        ).all()
        rated_topics = {row.normalized_name: float(row.avg_rating) for row in topic_ratings}
    except Exception as e:
        logger.error(f"Error fetching ratings for game {game_id}: {str(e)}")
        db.session.rollback()
        rated_topics = {}

    # If 3 incorrect answers, prioritize player's top 5 rated topics
    top_rated_candidates = []
    if use_top_rated and username and player:
        try:
            top_rated = db.session.query(
                Topic.normalized_name,
                Rating.rating
            ).join(Rating, Rating.topic_id == Topic.id
            ).filter(Rating.game_id == game_id,
                     Rating.player_id == player.id
            ).order_by(Rating.rating.desc()
            ).limit(5).all()
            top_rated_candidates = [t.normalized_name for t, _ in top_rated if t in RANDOM_TOPICS]
            logger.debug(f"Game {game_id}: Player {username} has 3 incorrect answers, top rated: {top_rated_candidates}")
        except Exception as e:
            logger.error(f"Error fetching top rated topics for {username} in game {game_id}: {str(e)}")
            db.session.rollback()

    # Define candidates
    if top_rated_candidates:
        # Use top-rated topics, ignoring recent_topics restriction
        candidate_topics = top_rated_candidates
    else:
        # Normal logic: start with all RANDOM_TOPICS, exclude recent ones
        candidate_topics = [t.lower().strip() for t in RANDOM_TOPICS if t.lower().strip() not in recent_topics]
        # Filter out poorly rated topics (avg < 2) if rated
        if rated_topics:
            candidate_topics = [t for t in candidate_topics if t not in rated_topics or rated_topics[t] >= 2]

        # If no candidates, relax to just exclude the last topic
        if not candidate_topics and recent_topics:
            last_topic = recent_topics[0]
            candidate_topics = [t.lower().strip() for t in RANDOM_TOPICS if t.lower().strip() != last_topic]

        # Final fallback: use all RANDOM_TOPICS
        if not candidate_topics:
            candidate_topics = [t.lower().strip() for t in RANDOM_TOPICS]

    # Log for debugging
    logger.debug(f"Game {game_id}: Recent topics: {recent_topics}, Rated topics: {rated_topics}, Candidates: {candidate_topics[:10]}... ({len(candidate_topics)} total)")

    # Return a random choice
    return random.choice(candidate_topics)
    
@app.route('/')
def welcome():
    game_id = session.get('game_id')
    if game_id:
        update_game_activity(game_id)
    return render_template('welcome.html')

@app.route('/play')
def play():
    game_id = session.get('game_id')
    if game_id:
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
            new_game = Game(id=game_id, host=username, status='waiting')
            db.session.add(new_game)
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
        return render_template('index.html', error="An error occurred while creating the game.")

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
            if game.status != 'waiting' or Player.query.filter_by(game_id=game_id).count() >= 10:
                return render_template('index.html', error="Game already in progress or full")
            existing_player = Player.query.filter_by(game_id=game_id, username=username).first()
            if existing_player:
                existing_player.disconnected = False
                db.session.commit()
            else:
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
        return render_template('index.html', error="An error occurred while joining the game.")

@app.route('/game/<game_id>')
def game(game_id):
    try:
        with app.app_context():
            game = Game.query.filter_by(id=game_id).first()
            if not game:
                session.pop('game_id', None)
                session.pop('username', None)
                return redirect(url_for('welcome'))
            username = session.get('username')
            if not username or not Player.query.filter_by(game_id=game_id, username=username).first():
                session.pop('game_id', None)
                session.pop('username', None)
                return redirect(url_for('welcome'))
            update_game_activity(game_id)
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

def get_trivia_question(topic):
    try:
        model = genai.GenerativeModel('gemini-2.0-flash')  # Use a verified model name
        prompt = f"""
        Generate a trivia question about "{topic}" with a single, clear answer.
        Requirements:
        - Engaging, specific, average difficulty (not too easy or obscure; suitable for a general audience).
        - Avoid current events or topics requiring information after December 31, 2024.
        - Ensure factual accuracy and clarity in wording.
        - Avoid ambiguity or multiple possible answers.
        - Provide four multiple-choice options: one correct answer and three plausible distractors.
        - Include a brief explanation (1-2 sentences) of the correct answer.
        - Format the response in JSON with the following structure:
          ```json
          {{
            "question": "string",
            "answer": "string",
            "options": ["string", "string", "string", "string"],
            "explanation": "string"
          }}
        """
        response = model.generate_content(prompt)
        logger.debug(f"Raw response from Gemini: {response.text}")
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '')
        logger.debug(f"Cleaned response: {cleaned_text}")
        return json.loads(cleaned_text)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {str(e)}")
        return {
            "question": f"What is a fact about {topic}?",
            "answer": "Unable to generate",
            "options": ["A", "B", "C", "D"],
            "explanation": "Invalid response format from AI service."
        }
    except Exception as e:
        logger.error(f"Error generating question: {str(e)}")
        return {
            "question": f"What is a fact about {topic}?",
            "answer": "Unable to generate",
            "options": ["A", "B", "C", "D"],
            "explanation": "Error with AI service."
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
        game = Game.query.filter_by(id=game_id, host=username, status='waiting').first()
        if not game:
            emit('error', {'message': 'Game not found or not host'}, to=game_id)
            return
        game.status = 'in_progress'
        db.session.commit()
        players = Player.query.filter_by(game_id=game_id).all()
        current_player = players[game.current_player_index] if players else None
        if current_player and current_player.disconnected:
            current_player = get_next_active_player(game_id)
        emit('game_started', {
            'current_player': current_player.username if current_player else None,
            'players': [p.username for p in players],
            'scores': {p.username: p.score for p in players},
            'player_emojis': {p.username: p.emoji for p in players}
        }, to=game_id)
        update_game_activity(game_id)

@socketio.on('request_player_top_topics')
def handle_request_player_top_topics(data):
    game_id = data.get('game_id')
    username = data.get('username')
    placeholder_text = get_player_top_topics(game_id, username)
    emit('player_top_topics', {'placeholder': placeholder_text}, to=request.sid)

@socketio.on('select_topic')
def handle_select_topic(data):
    game_id = data['game_id']
    username = data['username']
    topic = data['topic']
    if topic.lower() == 'random':
        topic = suggest_random_topic(game_id, username)
    topic_obj = get_or_create_topic(topic)
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        current_player = Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first()
        if game and username == current_player.username and game.status == 'in_progress':
            if topic == "random":  # Triggered by "Random Topic" button
                topic = suggest_random_topic(game_id)
            elif not topic:  # Fallback for empty input
                topic = random.choice(RANDOM_TOPICS)
            topic_obj = get_or_create_topic(topic)
            question_data = get_trivia_question(topic)
            new_question = Question(game_id=game_id, topic_id=topic_obj.id, question_text=question_data['question'], answer_text=question_data['answer'])
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
                else:
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
                            'question_id': current_question.id,
                            'topic_id': current_question.topic_id
                        }, to=game_id)
                        emit('request_feedback', {'topic_id': current_question.topic_id}, to=game_id)
                        db.session.query(Answer).filter_by(game_id=game_id, question_id=current_question.id).delete()
                        db.session.commit()
                        update_game_activity(game_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    username = data.get('username')
    answer = data.get('answer')
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        player = Player.query.filter_by(game_id=game_id, username=username).first()
        if game and player and game.status == 'in_progress' and game.current_question:
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
            if Answer.query.filter_by(game_id=game_id, question_id=game.current_question['question_id']).count() == len(active_players):
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
                else:
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
                            'question_id': current_question.id,
                            'topic_id': current_question.topic_id
                        }, to=game_id)
                        emit('request_feedback', {'topic_id': current_question.topic_id}, to=game_id)
                        db.session.query(Answer).filter_by(game_id=game_id, question_id=current_question.id).delete()
                        db.session.commit()
                        update_game_activity(game_id)

@socketio.on('submit_feedback')
def handle_feedback(data):
    game_id = data.get('game_id')
    topic_id = data.get('topic_id')
    username = data.get('username')
    rating = data.get('rating')
    with app.app_context():
        player = Player.query.filter_by(username=username, game_id=game_id).first()
        topic = Topic.query.get(topic_id)
        if player and topic and 0 <= rating <= 5:
            existing_rating = Rating.query.filter_by(game_id=game_id, player_id=player.id, topic_id=topic_id).first()
            if existing_rating:
                existing_rating.rating = rating
            else:
                new_rating = Rating(game_id=game_id, player_id=player.id, topic_id=topic_id, rating=rating)
                db.session.add(new_rating)
            db.session.commit()
            logger.debug(f"Player {username} rated topic {topic.normalized_name} with {rating}")

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
                emit('player_left', {
                    'username': username,
                    'players': [p.username for p in Player.query.filter_by(game_id=game.id).all()],
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game.id).all()}
                }, to=game.id)
                if game.status == 'in_progress' and Player.query.filter_by(game.id).offset(game.current_player_index).first().username == username:
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