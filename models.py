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

    players = db.relationship('Player', backref='game', lazy=True, cascade='all, delete-orphan')
    questions = db.relationship('Question', backref='game', lazy=True, cascade='all, delete-orphan')
    answers = db.relationship('Answer', backref='game', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('Rating', backref='game', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Game {self.id}>'

class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    username = db.Column(db.String(50), nullable=False)
    score = db.Column(db.Integer, default=0)
    emoji = db.Column(db.String(10))
    disconnected = db.Column(db.Boolean, default=False)
    sid = db.Column(db.String(120), nullable=True)  # Added for Socket.IO session ID

    answers = db.relationship('Answer', backref='player', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('Rating', backref='player', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Player {self.username} in Game {self.game_id}>'

class Topic(db.Model):
    __tablename__ = 'topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    normalized_name = db.Column(db.String(255), unique=True, nullable=False)

    questions = db.relationship('Question', backref='topic', lazy=True, cascade='all, delete-orphan')
    ratings = db.relationship('Rating', backref='topic', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Topic {self.normalized_name}>'

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=db.func.now(), nullable=False)  # Added timestamp field

    answers = db.relationship('Answer', backref='question', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Question {self.id} for Game {self.game_id}>'

class Answer(db.Model):
    __tablename__ = 'answers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    answer = db.Column(db.String(255))

    def __repr__(self):
        return f'<Answer by Player {self.player_id} for Question {self.question_id}>'

class Rating(db.Model):
    __tablename__ = 'ratings'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    game_id = db.Column(db.String(4), db.ForeignKey('games.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id'), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey('topics.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 = Like, 0 = Dislike

    __table_args__ = (
        db.UniqueConstraint('game_id', 'player_id', 'topic_id', name='unique_rating_per_game_player_topic'),
    )

    def __repr__(self):
        return f'<Rating {"Like" if self.rating else "Dislike"} by Player {self.player_id} for Topic {self.topic_id}>'