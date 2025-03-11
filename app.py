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

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# List of random trivia topics
RANDOM_TOPICS = [
    "Famous movie quotes from the 80s", "Inventions everyone uses", "Major battles in world history", "Action movie stunts of the 90s", "Inventions that changed daily life",
    "Ancient Egyptian pyramids", "Greek mythology stories", "Unusual animal facts", "NASA moon missions", "Science fiction movie classics",
    "Popular beer brands", "Iconic landmarks everyone knows", "Olympic gold medal moments", "Netflix hit shows", "Catchphrases from classic films",
    "Lost cities in movies", "Marvel superhero movies", "Famous graffiti tags", "AI in everyday tech", "Wild parties in history",
    "Pets of US presidents", "Fashion trends of the 2000s", "Dark origins of nursery rhymes", "Broadway musical hits", "Medical breakthroughs we all know",
    "Viking warrior tales", "Legendary video game heroes", "Cool tech gadgets", "Sports team mascot stories", "Secrets in famous paintings",
    "Sitcoms with great theme songs", "Music festival moments", "Superstitions we all know", "Weird habits of world leaders", "Horror movie monsters",
    "Guitar riffs from the 70s", "Pirate adventure stories", "Renaissance artist legends", "Time travel in blockbuster movies", "Famous bank heists",
    "Car chases in action films", "Zombie movie rules", "Pop art everyone recognizes", "Disco hits of the 70s", "Political scandals everyone heard about",
    "Nicknames of big cities", "Winter holiday traditions", "Breakdance moves we’ve seen", "Board games everyone plays", "Street art in famous cities",
    "Haunted houses in movies", "Plot twists in popular films", "Women who shaped tech", "World War II spy stories", "Game show funny moments",
    "Famous duos on TV", "Con artists in the news", "Failed gadgets from the 90s", "Myths about lost islands", "Life on space stations",
    "Languages we’ve heard of", "Tattoo trends today", "Underdog sports wins", "Creatures in the ocean", "Beaches with famous stories",
    "Fashion fads by decade", "Explorers everyone knows", "Wild West cowboy tales", "Alien invasion movies", "Music genres we love",
    "Kings and queens of Africa", "Crazy war stories", "Habits of tech billionaires", "Climate change facts we know", "Ancient sports games",
    "Songs from the 60s protests", "Snacks from the 90s", "Sea monster myths", "Conspiracy theories we’ve heard", "Science facts from school",
    "Treaties that ended wars", "Cool stuff at world fairs", "Hollywood scandals of the 50s", "Math tricks we learned", "Stand-up comedy stars",
    "Weird paintings we know", "UFO stories in the news", "Silk Road treasures", "Chinese dynasty tales", "Egyptian mummy facts",
    "Music beats we recognize", "Animals we thought were gone", "Speeches we’ve heard", "Viral dances online", "Cult TV show moments",
    "Bad girls in old movies", "Rock band breakup drama", "Hip-hop fights of the 90s", "Fashion show oops moments", "Sunken ship stories",
    "Volcano eruptions we know", "Ballet dances we’ve seen", "Slasher movie deaths", "Cyber worlds in movies", "City gardening trends",
    "Dictators’ funny outfits", "Nobel Prize winners we know", "Classical music we’ve heard", "Weird ideas we’ve debated", "Cold War spy tricks",
    "Moon landing fun facts", "Famous bridges we’ve crossed", "Boy band songs of the 90s", "Meditation tips we’ve tried", "Roller coaster records",
    "Shipwrecks in movies", "Secret hideouts in history", "Video game high scores", "Chocolate candy history", "Courtroom scenes in TV",
    "Dishes by famous chefs", "Epic sports comebacks", "Toys from the 80s", "Treasure hunt legends", "Urban legends we tell",
    "Wine types we’ve tasted", "Space junk we’ve heard about", "Medieval castle tales", "Protest signs we’ve seen", "Internet memes we love",
    "Rollerblading in the 90s", "Movie soundtrack hits", "Monster sightings in lore", "Celebrity breakup gossip", "Ancient Olympic games",
    "Fast food menu hacks", "Victorian ghost stories", "Whistleblowers in the news", "Arcade game classics", "Weird laws we laugh at",
    "Books banned in school", "Extreme weather we’ve seen", "Emoji meanings we use", "Magicians we’ve watched", "Cursed movie rumors",
    "Scientists we’ve heard of", "Beauty trends we’ve tried", "Plane crash stories", "Comedy teams we love", "Lost movies found again",
    "Soda brands we drink", "Daredevil stunts on TV", "Secret clubs we’ve heard of", "Album covers we know", "Roller derby fun facts",
    "Book rivalries we’ve read", "Retro fashion we’ve worn", "Bank robbery stories", "Popcorn flavors we’ve tried", "TV shows that got canceled",
    "Recipes from grandma", "Cartoon voices we know", "Skateboarding tricks we’ve seen", "Missing person mysteries", "Train robbery legends",
    "VR games we’ve played", "Theme park ride flops", "Bubble gum brands", "Spy tricks in movies", "Sibling fights in history",
    "Pinball game themes", "Courtroom TV moments", "Firework show stories", "Celebrity pet names", "Yo-yo tricks we’ve tried",
    "Movie car chase scenes", "Hot sauce brands", "Prison escape stories", "Kite flying fun", "Stunt doubles in films",
    "Ice cream flavors we love", "Survival shows we watch", "Graffiti tags we’ve seen", "Monster truck crashes", "Jigsaw puzzle fun",
    "Celebrity nicknames we know", "Karaoke songs we sing", "TV cliffhanger endings", "Glow stick party tricks", "Circus acts we’ve seen",
    "Slapstick comedy gags", "Reality TV meltdowns", "Breakdance battles on TV", "Celebrity tattoo stories", "Snow globe scenes",
    "Movie bloopers we’ve laughed at", "Fortune cookie sayings", "TV theme song hits", "Hacky sack games", "Stunt fails on video",
    "Rubber duck designs", "Celebrity pranks we’ve seen", "Yo-yo moves we know", "TV spin-offs we’ve watched", "Frisbee games we’ve played",
    "Movie props we recognize", "Trick-or-treat stories", "Celebrity feuds in the news", "Glow-in-the-dark toys", "TV reboots we’ve seen",
    "Jump rope rhymes", "Movie poster art", "Silly string pranks", "Celebrity impersonators on TV", "Dodgeball games we’ve played",
    "TV crossover episodes", "Water balloon fight stories", "Movie trailer lines we know", "Pogo stick fun", "Celebrity book deals",
    "Hacky sack tricks we’ve tried", "Movie set mishaps", "Slinky toy fun", "TV award show moments", "Hula hoop games",
    "Celebrity cameos we’ve spotted", "Paper airplane games", "Movie opening scenes we love", "Yo-yo contest stories", "TV finale surprises",
    "Bubble wrap popping fun", "Celebrity roast jokes", "Kite surfing crashes", "Movie sequel flops", "Bouncy ball games",
    "TV pilot episodes we’ve seen", "Glow stick rave stories", "Movie villain deaths", "Hopscotch games we played", "Celebrity scandals we know",
    "Taffy candy flavors", "Movie monster looks", "Limbo dance parties", "TV guest stars we love", "Pinata party stories",
    "Movie dance scene hits", "Twister game nights", "Celebrity arrest headlines", "Balloon animal fun", "TV show locations we know",
    "Tug-of-war games", "Movie fight scenes we love", "Jacks game tricks", "Celebrity apology clips", "Yo-yo fad stories",
    "Movie costumes we recognize", "Hoppy taw fun", "TV show drama moments", "Fidget spinner crazes", "Movie taglines we quote",
    "Kite fighting stories", "Celebrity wedding gossip", "Silly putty play", "TV catchphrases we say", "Water gun fight tales",
    "Movie chase music hits", "Hacky sack champs", "Celebrity ads we’ve seen", "Bubble blowing fun", "TV show props we know",
    "Jump rope games we played", "Movie cliffhanger scenes", "Dodgeball rule twists", "Celebrity lawsuit news", "Slinky race fun"
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

# Verify database connection
with app.app_context():
    try:
        engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])
        with engine.connect() as connection:
            logger.info("Database connection established successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")

socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

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
    new_game = Game(id=game_id, host=username, status='waiting')
    db.session.add(new_game)
    db.session.flush()  # Get the game ID assigned by the database

    new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(PLAYER_EMOJIS), disconnected=False)
    db.session.add(new_player)
    db.session.commit()

    session['game_id'] = game_id
    session['username'] = username
    
    return redirect(url_for('game', game_id=game_id))

@app.route('/join_game', methods=['POST'])
def join_game():
    username = request.form.get('username')
    game_id = request.form.get('game_id')
    
    if not username or not game_id:
        return redirect(url_for('play'))
    
    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return "Game not found", 404
    
    # Allow rejoining only if the player was already in the game
    existing_player = Player.query.filter_by(game_id=game_id, username=username).first()
    if existing_player:
        existing_player.disconnected = False
        db.session.commit()
        session['game_id'] = game_id
        session['username'] = username
        return redirect(url_for('game', game_id=game_id))
    
    # Block new players if game is in progress or full
    if game.status != 'waiting' or Player.query.filter_by(game_id=game_id).count() >= 10:
        return "Game already in progress or full", 403
    
    # Add new player during waiting phase
    available_emojis = [e for e in PLAYER_EMOJIS if e not in [p.emoji for p in Player.query.filter_by(game_id=game_id).all()]]
    new_player = Player(game_id=game_id, username=username, score=0, emoji=random.choice(available_emojis) if available_emojis else random.choice(PLAYER_EMOJIS), disconnected=False)
    db.session.add(new_player)
    db.session.commit()

    session['game_id'] = game_id
    session['username'] = username
    
    return redirect(url_for('game', game_id=game_id))

@app.route('/game/<game_id>')
def game(game_id):
    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return redirect(url_for('welcome'))
    
    username = session.get('username')
    if not username or not Player.query.filter_by(game_id=game_id, username=username).first():
        return redirect(url_for('welcome'))
    
    return render_template('game.html', game_id=game_id, username=username, is_host=(username == game.host))

@app.route('/final_scoreboard/<game_id>')
def final_scoreboard(game_id):
    game = Game.query.filter_by(id=game_id).first()
    if not game:
        return redirect(url_for('welcome'))
    players = Player.query.filter_by(game_id=game_id).all()
    player_scores = {p.username: p.score for p in players}
    player_emojis = {p.username: p.emoji for p in players}
    return render_template('final_scoreboard.html', game_id=game_id, scores=player_scores, player_emojis=player_emojis)

@app.route('/reset_game/<game_id>', methods=['POST'])
def reset_game(game_id):
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

    logger.debug(f"Game {game_id} reset by request")
    socketio.emit('game_reset', {
        'players': [p.username for p in players],
        'scores': {p.username: p.score for p in players],
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
            # Player is reconnecting
            player.disconnected = False
            db.session.commit()
            join_room(game_id)
            logger.debug(f"Player {username} rejoined room {game_id}")
            emit('player_rejoined', {
                'username': username,
                'players': [p.username for p in Player.query.filter_by(game_id=game_id).all()],
                'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()],
                'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()],
                'status': game.status,
                'current_player': Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first().username if game.status == 'in_progress' else None,
                'current_question': None  # To be handled separately if needed
            }, to=game_id)
        elif game.status == 'waiting' and Player.query.filter_by(game_id=game_id).count() < 10:
            # New player joining in waiting phase
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

@socketio.on('start_game')
def handle_start_game(data):
    game_id = data.get('game_id')
    username = data.get('username')
    
    try:
        game = Game.query.filter_by(id=game_id).first()
        if game and username == game.host and game.status == 'waiting':
            game.status = 'in_progress'
            current_player = Player.query.filter_by(game_id=game_id).offset(game.current_player_index).first()
            if current_player.disconnected:
                current_player = get_next_active_player(game_id)
            db.session.commit()
            logger.debug(f"Game {game_id} started by host {username}, current player: {current_player.username}")
            
            emit('game_started', {
                'current_player': current_player.username,
                'players': [p.username for p in Player.query.filter_by(game_id=game_id).all()],
                'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()],
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

            # Check for duplicates in the current game
            duplicate_found = Question.query.filter_by(game_id=game_id, question_text=question_text, answer_text=answer_text).first()

            if not duplicate_found:
                new_question = Question(game_id=game_id, question_text=question_text, answer_text=answer_text)
                db.session.add(new_question)
                game.current_question = question_data  # Store as JSON or restructure as needed
                game.question_start_time = datetime.now()
                db.session.commit()

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
    game = Game.query.filter_by(id=game_id).first()
    if game and game.status == 'in_progress':
        active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
        # If there's only one player, skip waiting since they should have already submitted
        if len(active_players) == 1 and Answer.query.filter_by(game_id=game_id).count() == 1:
            return  # Already handled in submit_answer

        for player in active_players:
            if not Answer.query.filter_by(game_id=game_id, player_id=player.id).first():
                new_answer = Answer(game_id=game_id, player_id=player.id, answer=None)
                db.session.add(new_answer)
        db.session.commit()

        correct_answer = game.current_question['answer']
        correct_players = [p for p in active_players if Answer.query.filter_by(game_id=game_id, player_id=p.id).first().answer == correct_answer]
        for p in correct_players:
            p.score += 1
        db.session.commit()

        max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
        if max_score >= 10:
            emit('game_ended', {
                'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
            }, to=game_id)
            return
        
        next_player = get_next_active_player(game_id)
        if next_player:
            emit('round_results', {
                'correct_answer': correct_answer,
                'explanation': game.current_question['explanation'],
                'player_answers': {p.username: a.answer for p, a in [(p, Answer.query.filter_by(game_id=game_id, player_id=p.id).first()) for p in Player.query.filter_by(game_id=game_id).all()]},
                'correct_players': [p.username for p in correct_players],
                'next_player': next_player.username,
                'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
            }, to=game_id)
            # Clear answers for the next round
            db.session.query(Answer).filter_by(game_id=game_id).delete()
            db.session.commit()
        else:
            emit('game_paused', {'message': 'No active players remaining'}, to=game_id)

@socketio.on('submit_answer')
def handle_submit_answer(data):
    game_id = data.get('game_id')
    username = data.get('username')
    answer = data.get('answer')
    
    game = Game.query.filter_by(id=game_id).first()
    player = Player.query.filter_by(game_id=game_id, username=username).first()
    if (game and player and game.status == 'in_progress' and game.current_question):
        
        time_elapsed = datetime.now() - game.question_start_time
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
        db.session.commit()

        emit('player_answered', {'username': username}, to=game_id)
        
        active_players = Player.query.filter_by(game_id=game_id, disconnected=False).all()
        # If there's only one active player, proceed to results immediately
        if len(active_players) == 1:
            correct_answer = game.current_question['answer']
            correct_players = [p for p in active_players if Answer.query.filter_by(game_id=game_id, player_id=p.id).first().answer == correct_answer]
            
            for p in correct_players:
                p.score += 1
            db.session.commit()

            max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
            if max_score >= 10:
                emit('game_ended', {
                    'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                }, to=game_id)
                return

            next_player = get_next_active_player(game_id)
            if next_player:
                emit('round_results', {
                    'correct_answer': correct_answer,
                    'explanation': game.current_question['explanation'],
                    'player_answers': {p.username: a.answer for p, a in [(p, Answer.query.filter_by(game_id=game_id, player_id=p.id).first()) for p in Player.query.filter_by(game_id=game_id).all()]},
                    'correct_players': [p.username for p in correct_players],
                    'next_player': next_player.username,
                    'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                }, to=game_id)
                # Clear answers for the next round
                db.session.query(Answer).filter_by(game_id=game_id).delete()
                db.session.commit()
            else:
                emit('game_paused', {'message': 'No active players remaining'}, to=game_id)
        elif Answer.query.filter_by(game_id=game_id).count() == len(active_players):
            # Original logic for multiple players
            correct_answer = game.current_question['answer']
            correct_players = [p for p in active_players if Answer.query.filter_by(game_id=game_id, player_id=p.id).first().answer == correct_answer]
            
            for p in correct_players:
                p.score += 1
            db.session.commit()

            max_score = max([p.score for p in Player.query.filter_by(game_id=game_id).all()] + [0])
            if max_score >= 10:
                emit('game_ended', {
                    'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                }, to=game_id)
                return

            next_player = get_next_active_player(game_id)
            if next_player:
                emit('round_results', {
                    'correct_answer': correct_answer,
                    'explanation': game.current_question['explanation'],
                    'player_answers': {p.username: a.answer for p, a in [(p, Answer.query.filter_by(game_id=game_id, player_id=p.id).first()) for p in Player.query.filter_by(game_id=game_id).all()]},
                    'correct_players': [p.username for p in correct_players],
                    'next_player': next_player.username,
                    'scores': {p.username: p.score for p in Player.query.filter_by(game_id=game_id).all()},
                    'player_emojis': {p.username: p.emoji for p in Player.query.filter_by(game_id=game_id).all()}
                }, to=game_id)
                # Clear answers for the next round
                db.session.query(Answer).filter_by(game_id=game_id).delete()
                db.session.commit()
            else:
                emit('game_paused', {'message': 'No active players remaining'}, to=game_id)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    for game in Game.query.all():
        player = Player.query.filter_by(game_id=game.id, username=username).first()
        if player:
            player.disconnected = True
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