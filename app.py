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
import timeout_decorator
import threading

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

# Store active timers and recent random topics per game
active_timers = {}
random_click_counters = {}  # Structure: {game_id: {username: count}}
recent_random_topics = {}   # Structure: {game_id: [topics]}

# Initialize Flask app
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
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_size': 5, 'max_overflow': 10}
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///trivia.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate.init_app(app, db)

# Verify database connection and create tables
with app.app_context():
    try:
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        with engine.connect() as connection:
            logger.info("Database connection established successfully")
        db.create_all()
    except SQLAlchemyError as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True, ping_timeout=20)

# Load environment variables
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables.")
    raise ValueError("GEMINI_API_KEY is required")
genai.configure(api_key=GEMINI_API_KEY)

# Helper Functions
def generate_game_id():
    while True:
        game_id = ''.join(random.choices(string.ascii_uppercase, k=4))
        if not Game.query.filter_by(id=game_id).first():
            return game_id

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

def get_or_create_topic(topic_name):
    normalized_name = topic_name.lower().strip()
    topic = Topic.query.filter_by(normalized_name=normalized_name).first()
    if not topic:
        topic = Topic(normalized_name=normalized_name)
        db.session.add(topic)
        db.session.commit()
    return topic

def get_player_top_topics(game_id, username, limit=3):
    player = Player.query.filter_by(game_id=game_id, username=username).first()
    if not player:
        logger.debug(f"No player found for {username} in game {game_id}")
        return "Enter a topic or click Random Topic"
    top_topics = db.session.query(
        Topic.normalized_name,
        func.count(Rating.id).label('like_count')
    ).join(Rating, Rating.topic_id == Topic.id
    ).filter(Rating.game_id == game_id, Rating.player_id == player.id, Rating.rating == 1
    ).group_by(Topic.normalized_name
    ).order_by(func.count(Rating.id).desc()
    ).limit(limit).all()
    result = ", ".join([row.normalized_name for row in top_topics]) if top_topics else "Enter a topic or click Random Topic"
    logger.debug(f"Top liked topics for {username} in game {game_id}: {result}")
    return result

def suggest_random_topic(game_id, username=None):
    try:
        if game_id not in recent_random_topics:
            recent_random_topics[game_id] = []
        if game_id not in random_click_counters:
            random_click_counters[game_id] = {}
        if username and username not in random_click_counters[game_id]:
            random_click_counters[game_id][username] = 0

        last_question = db.session.query(Question.topic_id
            ).filter(Question.game_id == game_id
            ).order_by(Question.id.desc()
            ).first()
        last_topic = Topic.query.get(last_question.topic_id).normalized_name if last_question else None

        player = Player.query.filter_by(game_id=game_id, username=username).first()
        if not player:
            logger.debug(f"No player found for {username} in game {game_id}, using fallback topics")
            candidate_topics = [t.lower().strip() for t in RANDOM_TOPICS if t.lower().strip() not in recent_random_topics[game_id]]
            topic = random.choice(candidate_topics or RANDOM_TOPICS)
            if username:
                random_click_counters[game_id][username] += 1
            recent_random_topics[game_id].append(topic)
            if len(recent_random_topics[game_id]) > 3:
                recent_random_topics[game_id].pop(0)
            logger.debug(f"Game {game_id}: Suggested random topic '{topic}' for {username or 'unknown'}")
            return topic

        liked_topics = db.session.query(Topic.normalized_name
            ).join(Rating, Rating.topic_id == Topic.id
            ).filter(Rating.game_id == game_id, Rating.player_id == player.id, Rating.rating == 1
            ).group_by(Topic.normalized_name
            ).all()
        disliked_topics = db.session.query(Topic.normalized_name
            ).join(Rating, Rating.topic_id == Topic.id
            ).filter(Rating.game_id == game_id, Rating.player_id == player.id, Rating.rating == 0
            ).group_by(Topic.normalized_name
            ).all()

        liked_topic_names = [t.normalized_name for t in liked_topics]
        disliked_topic_names = [t.normalized_name for t in disliked_topics]

        logger.debug(f"Game {game_id}: Liked topics for {username}: {liked_topic_names}")
        logger.debug(f"Game {game_id}: Disliked topics for {username}: {disliked_topic_names}")
        logger.debug(f"Game {game_id}: Random click count for {username}: {random_click_counters[game_id][username]}")

        # Base candidate topics exclude disliked and recent topics
        candidate_topics = [t.lower().strip() for t in RANDOM_TOPICS if t.lower().strip() not in disliked_topic_names]
        candidate_topics = [t for t in candidate_topics if t not in recent_random_topics[game_id] and t != (last_topic or "")]

        # Introduce liked topics less frequently (every 5th click) and with randomness
        click_count = random_click_counters[game_id][username]
        use_liked = click_count > 0 and click_count % 5 == 0 and liked_topic_names and random.random() < 0.6  # 60% chance

        if use_liked:
            liked_candidates = [t for t in liked_topic_names if t not in recent_random_topics[game_id] and t != (last_topic or "")]
            if liked_candidates:
                topic = random.choice(liked_candidates)
                logger.debug(f"Game {game_id}: Selected liked topic '{topic}' for {username} on click {click_count}")
            else:
                topic = random.choice(candidate_topics or RANDOM_TOPICS)
                logger.debug(f"Game {game_id}: No available liked topics, using random '{topic}' for {username}")
        else:
            topic = random.choice(candidate_topics or RANDOM_TOPICS)
            logger.debug(f"Game {game_id}: Selected random topic '{topic}' for {username}")

        random_click_counters[game_id][username] += 1
        recent_random_topics[game_id].append(topic)
        if len(recent_random_topics[game_id]) > 3:
            recent_random_topics[game_id].pop(0)
        return topic
    except Exception as e:
        logger.error(f"Error fetching random topic for game {game_id}, user {username}: {str(e)}")
        db.session.rollback()
        topic = random.choice([t.lower().strip() for t in RANDOM_TOPICS])
        if username:
            random_click_counters[game_id][username] += 1
        recent_random_topics[game_id].append(topic)
        if len(recent_random_topics[game_id]) > 3:
            recent_random_topics[game_id].pop(0)
        return topic

@timeout_decorator.timeout(5, timeout_exception=TimeoutError)
def get_trivia_question(topic, game_id):
    try:
        cached_question = Question.query.filter_by(game_id=game_id, topic_id=get_or_create_topic(topic).id).order_by(func.random()).first()
        if cached_question and random.random() < 0.5:  # 50% chance to reuse cached question
            return {
                "question": cached_question.question_text,
                "answer": cached_question.answer_text,
                "options": [cached_question.answer_text, "Option B", "Option C", "Option D"],  # Simplified distractors
                "explanation": "Retrieved from cache"
            }

        model = genai.GenerativeModel('gemini-2.0-flash')
        prior_questions = Question.query.filter_by(game_id=game_id).all()
        prior_questions_list = [f"- {q.question_text} (Answer: {q.answer_text})" for q in prior_questions]
        prior_questions_str = "\n".join(prior_questions_list[:10]) if prior_questions_list else "None"

        prompt = f"""
        Generate a trivia question about "{topic}" with a single, clear answer.
        Requirements:
        - Engaging, specific, average difficulty (not too easy or obscure; suitable for a general audience).
        - Avoid current events or topics requiring information after December 31, 2024.
        - Ensure factual accuracy and clarity in wording.
        - Avoid ambiguity or multiple possible answers.
        - Do NOT repeat or closely mimic any of the following previously used questions and answers in this game:
          {prior_questions_str}
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
        cleaned_text = response.text.strip().replace('```json', '').replace('```', '')
        question_data = json.loads(cleaned_text)

        if any(q.question_text.lower() == question_data['question'].lower() for q in prior_questions):
            raise ValueError("Generated question is a duplicate")

        return question_data
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error for topic {topic}: {str(e)}")
        return {
            "question": f"What is a fact about {topic}?",
            "answer": "Unable to generate",
            "options": ["A", "B", "C", "D"],
            "explanation": "Invalid response format from AI service."
        }
    except TimeoutError:
        logger.error(f"Timeout generating question for topic {topic}")
        return {
            "question": f"What is a basic fact about {topic}?",
            "answer": "Fallback answer",
            "options": ["Fallback answer", "B", "C", "D"],
            "explanation": "Question generation timed out; this is a fallback."
        }
    except Exception as e:
        logger.error(f"Error generating question for topic {topic}: {str(e)}")
        return {
            "question": f"What is a fact about {topic}?",
            "answer": "Unable to generate",
            "options": ["A", "B", "C", "D"],
            "explanation": "Error with AI service or duplicate detected."
        }

def get_next_active_player(game_id):
    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return None
    players = Player.query.filter_by(game_id=game_id, disconnected=False).order_by(Player.id).all()
    if not players:
        return None
    current_index = game.current_player_index
    num_players = len(players)
    for _ in range(num_players):
        current_index = (current_index + 1) % num_players
        next_player = players[current_index]
        if not next_player.disconnected:
            game.current_player_index = current_index
            db.session.commit()
            update_game_activity(game_id)
            return next_player
    return None

def question_timer(game_id):
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        if not game or game.status != 'in_progress' or not game.current_question:
            logger.debug(f"Game {game_id} not found, not in progress, or no current question; timer aborted")
            if game_id in active_timers:
                del active_timers[game_id]
            return

        logger.debug(f"Game {game_id}: 30s timer expired, processing answers")
        active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
        current_question_id = game.current_question['question_id']
        for player in active_players:
            if not Answer.query.filter_by(game_id=game_id, player_id=player.id, question_id=current_question_id).first():
                new_answer = Answer(game_id=game_id, player_id=player.id, question_id=current_question_id, answer=None)
                db.session.add(new_answer)
        db.session.commit()

        correct_answer = game.current_question['answer']
        correct_players = [
            p for p in active_players
            if Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first() and
               Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first().answer == correct_answer
        ]
        for p in correct_players:
            p.score += 1
        db.session.commit()

        max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
        if max_score >= 15:
            socketio.emit('game_ended', {
                'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
            }, room=game_id)
        else:
            next_player = get_next_active_player(game_id)
            if next_player:
                current_question = Question.query.filter_by(id=current_question_id).first()
                socketio.emit('round_results', {
                    'correct_answer': correct_answer,
                    'explanation': game.current_question['explanation'],
                    'player_answers': {
                        p.username: Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first().answer
                        if Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first()
                        else None
                        for p in Player.query.filter_by(game_id=game_id).all()
                    },
                    'correct_players': [p.username for p in correct_players],
                    'next_player': next_player.username,
                    'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()},
                    'question_id': current_question.id,
                    'topic_id': current_question.topic_id
                }, room=game_id)
                socketio.emit('request_feedback', {'topic_id': current_question.topic_id}, room=game_id)
                db.session.commit()
                update_game_activity(game_id)

        if game_id in active_timers:
            del active_timers[game_id]
            logger.debug(f"Timer for game {game_id} completed and removed")

# Background task to clean up inactive games
def cleanup_inactive_games():
    while True:
        try:
            with app.app_context():
                now = datetime.utcnow()
                inactive_threshold = now - timedelta(minutes=2)
                inactive_games = Game.query.filter(Game.last_activity < inactive_threshold).all()
                for game in inactive_games:
                    if game.id in active_timers:
                        active_timers[game.id].cancel()
                        del active_timers[game.id]
                    db.session.delete(game)  # Cascades to delete Questions, Answers, etc.
                    db.session.commit()
                    logger.info(f"Cleaned up inactive game {game.id}")
                    if game.id in recent_random_topics:
                        del recent_random_topics[game.id]
                    if game.id in random_click_counters:
                        del random_click_counters[game.id]
        except Exception as e:
            logger.error(f"Error in cleanup_inactive_games: {str(e)}")
            db.session.rollback()
        socketio.sleep(60)

socketio.start_background_task(cleanup_inactive_games)

# Routes
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
            session_game_id = session.get('game_id')
            session_username = session.get('username')
            if not session_game_id or not session_username or session_game_id != game_id:
                logger.warning(f"Unauthorized reset attempt for game {game_id} from session {session_game_id}")
                return jsonify({'error': 'Unauthorized: Invalid session'}), 403

            game = Game.query.filter_by(id=game_id).first()
            if not game:
                logger.error(f"Game {game_id} not found for reset")
                return jsonify({'error': 'Game not found'}), 404

            logger.info(f"Resetting game {game_id} by {session_username}")
            if game_id in active_timers:
                active_timers[game_id].cancel()
                del active_timers[game_id]
                logger.debug(f"Cancelled timer for game {game_id} on reset")

            # Reset game state without deleting Questions or Answers
            game.status = 'waiting'
            game.current_player_index = 0
            game.current_question = None
            game.question_start_time = None
            
            # Reset player scores and connection status
            players = Player.query.filter_by(game_id=game_id).all()
            for player in players:
                player.score = 0
                player.disconnected = False
            db.session.commit()

            socketio.emit('game_reset', {
                'players': [p.username for p in players],
                'scores': {p.username: p.score for p in players},
                'player_emojis': {p.username: p.emoji for p in players}
            }, room=game_id)
            update_game_activity(game_id)
            logger.info(f"Game {game_id} successfully reset")
            return jsonify({'success': 'Game reset successfully'}), 200
    except SQLAlchemyError as e:
        logger.error(f"Database error resetting game {game_id}: {str(e)}")
        db.session.rollback()
        return jsonify({'error': 'Database error occurred'}), 500
    except Exception as e:
        logger.error(f"Unexpected error resetting game {game_id}: {str(e)}")
        return jsonify({'error': 'Unexpected server error'}), 500

# Socket.IO Handlers
@socketio.on('connect')
def handle_connect():
    logger.debug(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if not username:
        return
    with app.app_context():
        for game in Game.query.all():
            player = Player.query.filter_by(game_id=game.id, username=username).first()
            if player:
                player.disconnected = True
                db.session.commit()
                socketio.emit('player_disconnected', {'username': username}, room=game.id)
                socketio.emit('player_left', {
                    'username': username,
                    'players': [p.username for p in Player.query.filter_by(game_id=game.id).all()],
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game.id).all()}
                }, room=game.id)
                if game.status == 'in_progress' and Player.query.filter_by(game_id=game.id).offset(game.current_player_index).first().username == username:
                    next_player = get_next_active_player(game.id)
                    if next_player:
                        socketio.emit('turn_skipped', {
                            'disconnected_player': username,
                            'next_player': next_player.username
                        }, room=game.id)
            update_game_activity(game.id)

@socketio.on('join_game_room')
def handle_join_game_room(data):
    game_id = data.get('game_id')
    username = data.get('username')
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        if not game:
            socketio.emit('error', {'message': 'Game not found'}, to=request.sid)
            return
        player = Player.query.filter_by(game_id=game_id, username=username).first()
        if player:
            player.disconnected = False
            db.session.commit()
            join_room(game_id)
            players = Player.query.filter_by(game_id=game_id).all()
            current_player = Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first() if game.status == 'in_progress' and Player.query.filter_by(game_id=game_id).count() > game.current_player_index else None
            socketio.emit('player_rejoined', {
                'username': username,
                'players': [p.username for p in players],
                'scores': {p.username: p.score for p in players},
                'player_emojis': {p.username: p.emoji for p in players},
                'status': game.status,
                'current_player': current_player.username if current_player else None,
                'current_question': game.current_question
            }, room=game_id)
        elif game.status == 'waiting' and Player.query.filter_by(game_id=game_id).count() < 10:
            available_emojis = [e for e in PLAYER_EMOJIS if e not in [p.emoji for p in Player.query.filter_by(game_id=game_id).all()]]
            new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(available_emojis) if available_emojis else random.choice(PLAYER_EMOJIS), disconnected=False)
            db.session.add(new_player)
            db.session.commit()
            join_room(game_id)
            players = Player.query.filter_by(game_id=game_id).all()
            socketio.emit('player_joined', {
                'username': username,
                'players': [p.username for p in players],
                'player_emojis': {p.username: p.emoji for p in players}
            }, room=game_id)
        else:
            socketio.emit('error', {'message': 'Game is full or already started'}, to=request.sid)
        update_game_activity(game_id)

@socketio.on('start_game')
def handle_start_game(data):
    game_id = data.get('game_id')
    username = data.get('username')
    with app.app_context():
        game = Game.query.filter_by(id=game_id, host=username, status='waiting').first()
        if not game:
            socketio.emit('error', {'message': 'Game not found or not host'}, room=game_id)
            return
        game.status = 'in_progress'
        db.session.commit()
        players = Player.query.filter_by(game_id=game_id).all()
        current_player = players[game.current_player_index] if players else None
        if current_player and current_player.disconnected:
            current_player = get_next_active_player(game_id)
        socketio.emit('game_started', {
            'current_player': current_player.username if current_player else None,
            'players': [p.username for p in players],
            'scores': {p.username: p.score for p in players},
            'player_emojis': {p.username: p.emoji for p in players}
        }, room=game_id)
        update_game_activity(game_id)

@socketio.on('request_player_top_topics')
def handle_request_player_top_topics(data):
    game_id = data.get('game_id')
    username = data.get('username')
    placeholder_text = get_player_top_topics(game_id, username)
    logger.debug(f"Game {game_id}: Sending top topics placeholder '{placeholder_text}' to {username}")
    socketio.emit('player_top_topics', {'placeholder': placeholder_text}, to=request.sid)

@socketio.on('select_topic')
def handle_select_topic(data):
    game_id = data.get('game_id')
    username = data.get('username')
    topic = data.get('topic', '').strip().lower()

    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        if not game or game.status != 'in_progress':
            socketio.emit('error', {'message': 'Game not in progress'}, to=request.sid)
            return
        player = Player.query.filter_by(username=username, game_id=game_id).first()
        if not player:
            logger.error(f"No player found for {username} in game {game_id}")
            socketio.emit('error', {'message': 'Player not found'}, to=request.sid)
            return
        if Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first().username != username:
            socketio.emit('error', {'message': 'Not your turn'}, to=request.sid)
            return

        if not topic:
            topic = suggest_random_topic(game_id, username)

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                topic_obj = get_or_create_topic(topic)
                question_data = get_trivia_question(topic, game_id)
                
                prior_questions = Question.query.filter_by(game_id=game_id).all()
                if any(q.question_text.lower() == question_data['question'].lower() for q in prior_questions):
                    if attempt < max_attempts - 1:
                        logger.debug(f"Game {game_id}: Duplicate question detected on attempt {attempt + 1}, retrying with topic '{topic}'")
                        continue
                    else:
                        logger.warning(f"Game {game_id}: Max attempts reached, switching to random topic")
                        topic = suggest_random_topic(game_id, username)
                        topic_obj = get_or_create_topic(topic)
                        question_data = get_trivia_question(topic, game_id)

                new_question = Question(
                    game_id=game_id,
                    topic_id=topic_obj.id,
                    question_text=question_data['question'],
                    answer_text=question_data['answer']
                )
                db.session.add(new_question)
                db.session.flush()

                game.current_question = question_data
                game.current_question['question_id'] = new_question.id
                game.question_start_time = datetime.utcnow()
                db.session.commit()

                socketio.emit('question_ready', {
                    'question': question_data['question'],
                    'options': question_data['options'],
                    'topic': topic,
                    'question_id': new_question.id
                }, room=game_id)

                if game_id in active_timers:
                    active_timers[game_id].cancel()
                    logger.debug(f"Cancelled existing timer for game {game_id}")
                timer = threading.Timer(30.0, question_timer, args=(game_id,))
                active_timers[game_id] = timer
                timer.start()
                logger.debug(f"Started new 30s timer for game {game_id}")

                update_game_activity(game_id)
                break
            except Exception as e:
                logger.error(f"Error generating question for topic {topic} in game {game_id} (attempt {attempt + 1}): {str(e)}")
                if attempt < max_attempts - 1:
                    continue
                socketio.emit('error', {'message': 'Failed to generate unique question after multiple attempts. Please try again.'}, room=game_id)
                db.session.rollback()
                return

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    username = data.get('username')
    answer = data.get('answer')
    with app.app_context():
        game = Game.query.filter_by(id=game_id).first()
        player = Player.query.filter_by(game_id=game_id, username=username).first()
        if not game or not player or game.status != 'in_progress' or not game.current_question:
            logger.debug(f"Game {game_id}: Invalid submit_answer attempt by {username}")
            socketio.emit('error', {'message': 'Invalid game state'}, to=request.sid)
            return

        current_question_id = game.current_question['question_id']
        time_elapsed = datetime.utcnow() - game.question_start_time
        if time_elapsed.total_seconds() > 30:
            logger.debug(f"Game {game_id}: Time expired for {username}, setting answer to None")
            answer = None
        else:
            if answer in ['A', 'B', 'C', 'D']:
                option_index = ord(answer) - ord('A')
                answer = game.current_question['options'][option_index]

        existing_answer = Answer.query.filter_by(game_id=game_id, player_id=player.id, question_id=current_question_id).first()
        if existing_answer:
            existing_answer.answer = answer
        else:
            new_answer = Answer(game_id=game_id, player_id=player.id, question_id=current_question_id, answer=answer)
            db.session.add(new_answer)
        db.session.commit()
        logger.debug(f"Game {game_id}: Answer recorded for {username} as {answer}")
        socketio.emit('player_answered', {'username': username}, room=game_id)

        active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
        answers_submitted = Answer.query.filter_by(game_id=game_id, question_id=current_question_id).count()
        if answers_submitted == len(active_players):
            logger.debug(f"Game {game_id}: All players answered, processing results")
            if game_id in active_timers:
                active_timers[game_id].cancel()
                del active_timers[game_id]
                logger.debug(f"Game {game_id}: Timer cancelled due to all answers submitted")

            correct_answer = game.current_question['answer']
            correct_players = [
                p for p in active_players
                if Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first() and
                   Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first().answer == correct_answer
            ]
            for p in correct_players:
                p.score += 1
            db.session.commit()

            max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
            current_question = Question.query.filter_by(id=current_question_id).first()
            if max_score >= 15:
                socketio.emit('game_ended', {
                    'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                }, room=game_id)
            else:
                next_player = get_next_active_player(game_id)
                if next_player:
                    socketio.emit('round_results', {
                        'correct_answer': correct_answer,
                        'explanation': game.current_question['explanation'],
                        'player_answers': {
                            p.username: Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first().answer
                            if Answer.query.filter_by(game_id=game_id, player_id=p.id, question_id=current_question_id).first()
                            else None
                            for p in Player.query.filter_by(game_id=game_id).all()
                        },
                        'correct_players': [p.username for p in correct_players],
                        'next_player': next_player.username,
                        'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                        'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()},
                        'question_id': current_question.id,
                        'topic_id': current_question.topic_id
                    }, room=game_id)
                    socketio.emit('request_feedback', {'topic_id': current_question.topic_id}, room=game_id)
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
        if not player or not topic:
            logger.error(f"Invalid player {username} or topic {topic_id} in game {game_id}")
            socketio.emit('error', {'message': 'Invalid player or topic'}, to=request.sid)
            return
        if not isinstance(rating, bool):
            logger.error(f"Invalid rating value: {rating} for {username} in game {game_id}")
            socketio.emit('error', {'message': 'Invalid rating'}, to=request.sid)
            return
        try:
            rating_value = 1 if rating else 0
            existing_rating = Rating.query.filter_by(game_id=game_id, player_id=player.id, topic_id=topic_id).first()
            if existing_rating:
                existing_rating.rating = rating_value
            else:
                new_rating = Rating(game_id=game_id, player_id=player.id, topic_id=topic_id, rating=rating_value)
                db.session.add(new_rating)
            db.session.commit()
            logger.debug(f"Player {username} rated topic {topic.normalized_name} as {'Like' if rating_value else 'Dislike'} in game {game_id}")
        except SQLAlchemyError as e:
            logger.error(f"Failed to save rating for {username} on topic {topic_id} in game {game_id}: {str(e)}")
            db.session.rollback()
            socketio.emit('error', {'message': 'Failed to save rating'}, to=request.sid)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)