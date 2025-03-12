from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.String(4), primary_key=True)
    host = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default='waiting')
    current_player_index = db.Column(db.Integer, default=0)
    current_question = db.Column(db.JSON)
    question_start_time = db.Column(db.DateTime)
    last_activity = db.Column(db.DateTime, default=db.func.now())

    # Define relationships with cascading deletes
    players = db.relationship('Player', backref='game', lazy=True, cascade='all, delete-orphan')
    questions = db.relationship('Question', backref='game', lazy=True, cascade='all, delete-orphan')
    answers = db.relationship('Answer', backref='game', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('Rating', backref='game', lazy=True, cascade='all, delete-orphan')

class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, default=0)
    emoji = db.Column(db.String(10))
    disconnected = db.Column(db.Boolean, default=False)

    # Relationships
    answers = db.relationship('Answer', backref='player', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('Rating', backref='player', lazy=True, cascade='all, delete-orphan')

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=False)

    # Relationship for feedback
    ratings = db.relationship('Rating', backref='question', lazy=True, cascade='all, delete-orphan')

class Answer(db.Model):
    __tablename__ = 'answers'  # Added explicit table name for consistency
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)  # Fixed to 'games.id'
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)  # Fixed to 'players.id'
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer = db.Column(db.String(255))

class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 0-5 scale