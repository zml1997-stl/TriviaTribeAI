from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

class Game(db.Model):
    __tablename__ = 'games'

    id = db.Column(db.String(4), primary_key=True)
    host = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), nullable=False, default='waiting')
    current_player_index = db.Column(db.Integer, nullable=False, default=0)
    question_start_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    players = db.relationship('Player', backref='game', lazy=True)
    questions_asked = db.relationship('Question', backref='game', lazy=True)

class Player(db.Model):
    __tablename__ = 'players'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False, unique=True)
    score = db.Column(db.Integer, nullable=False, default=0)
    emoji = db.Column(db.String(10), nullable=False)
    disconnected = db.Column(db.Boolean, default=False)

class Question(db.Model):
    __tablename__ = 'questions_asked'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.String(255), nullable=False)
    asked_at = db.Column(db.DateTime, default=db.func.now())

class Answer(db.Model):
    __tablename__ = 'answers'

    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    answer = db.Column(db.String(255), nullable=True)
    submitted_at = db.Column(db.DateTime, default=db.func.now())

    player = db.relationship('Player', backref='answers')