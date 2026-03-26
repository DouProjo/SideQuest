from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import os
import uuid

app = Flask(__name__)
CORS(app)

# Config
app.config['SECRET_KEY'] = 'change-this-in-production-please'
app.config['JWT_SECRET_KEY'] = 'jwt-secret-change-this-too'
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=30)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sidequests.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

db = SQLAlchemy(app)
jwt = JWTManager(app)

# ---- Models ----

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    avatar_color = db.Column(db.String(20), default='#7C3AED')
    bio = db.Column(db.String(200), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    completions = db.relationship('Completion', backref='user', lazy=True)
    schedules = db.relationship('Schedule', backref='user', lazy=True)
    login_events = db.relationship('LoginEvent', backref='user', lazy=True)

    @property
    def total_points(self):
        return sum(c.points_earned for c in self.completions if c.approved)

    @property
    def completed_count(self):
        return len([c for c in self.completions if c.approved])

    def to_dict(self, include_email=False):
        d = {
            'id': self.id,
            'username': self.username,
            'avatar_color': self.avatar_color,
            'bio': self.bio,
            'total_points': self.total_points,
            'completed_count': self.completed_count,
            'created_at': self.created_at.isoformat(),
            'is_admin': self.is_admin
        }
        if include_email:
            d['email'] = self.email
        return d


class LoginEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(80), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(300), nullable=True)
    successful = db.Column(db.Boolean, default=False)
    reason = db.Column(db.String(200), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'timestamp': self.timestamp.isoformat(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'successful': self.successful,
            'reason': self.reason,
        }


class Quest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)  # easy, medium, hard, legendary
    points = db.Column(db.Integer, nullable=False)
    solo_allowed = db.Column(db.Boolean, default=True)
    duo_allowed = db.Column(db.Boolean, default=True)
    group_allowed = db.Column(db.Boolean, default=True)
    icon = db.Column(db.String(10), default='⚔️')
    completions = db.relationship('Completion', backref='quest', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'category': self.category,
            'difficulty': self.difficulty,
            'points': self.points,
            'solo_allowed': self.solo_allowed,
            'duo_allowed': self.duo_allowed,
            'group_allowed': self.group_allowed,
            'icon': self.icon,
            'completion_count': len(self.completions)
        }


class Completion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quest_id = db.Column(db.Integer, db.ForeignKey('quest.id'), nullable=False)
    mode = db.Column(db.String(20), nullable=False)  # solo, duo, group
    partner_ids = db.Column(db.String(200), default='')  # comma-separated user IDs
    photo_url = db.Column(db.String(255), nullable=True)
    note = db.Column(db.Text, default='')
    points_earned = db.Column(db.Integer, nullable=False)
    approved = db.Column(db.Boolean, default=True)
    completed_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'quest_id': self.quest_id,
            'mode': self.mode,
            'partner_ids': self.partner_ids,
            'photo_url': self.photo_url,
            'note': self.note,
            'points_earned': self.points_earned,
            'approved': self.approved,
            'completed_at': self.completed_at.isoformat(),
            'quest': self.quest.to_dict() if self.quest else None,
            'username': self.user.username if self.user else None
        }


class Schedule(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    day_of_week = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.String(10), nullable=False)
    end_time = db.Column(db.String(10), nullable=False)
    label = db.Column(db.String(100), default='Available')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'day_of_week': self.day_of_week,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'label': self.label
        }


# ---- Helpers ----

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        user = User.query.get(get_jwt_identity())
        if not user or not user.is_admin:
            return jsonify({'error': 'Admin access required'}), 403
        return fn(*args, **kwargs)
    return wrapper


# ---- Auth Routes ----

@app.route('/api/auth/register', methods=['POST'])
def register():
    data = request.get_json()
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'error': 'Username already taken'}), 400
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Email already registered'}), 400
    colors = ['#7C3AED', '#059669', '#DC2626', '#2563EB', '#D97706', '#DB2777']
    user = User(
        username=data['username'],
        email=data['email'],
        password_hash=generate_password_hash(data['password']),
        avatar_color=colors[User.query.count() % len(colors)]
    )
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=user.id)
    return jsonify({'token': token, 'user': user.to_dict(include_email=True)}), 201


@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    user = User.query.filter_by(username=username).first()
    ip = request.remote_addr or 'unknown'
    ua = request.headers.get('User-Agent', '')

    if not user or not check_password_hash(user.password_hash, password):
        event = LoginEvent(
            user_id=user.id if user else None,
            username=username,
            ip_address=ip,
            user_agent=ua,
            successful=False,
            reason='invalid credentials'
        )
        db.session.add(event)
        db.session.commit()
        return jsonify({'error': 'Invalid credentials'}), 401

    event = LoginEvent(
        user_id=user.id,
        username=user.username,
        ip_address=ip,
        user_agent=ua,
        successful=True,
        reason='login success'
    )
    db.session.add(event)
    db.session.commit()

    token = create_access_token(identity=user.id)
    return jsonify({'token': token, 'user': user.to_dict(include_email=True)})


@app.route('/api/auth/me', methods=['GET'])
@jwt_required()
def me():
    user = User.query.get(get_jwt_identity())
    return jsonify(user.to_dict(include_email=True))


@app.route('/api/auth/logins', methods=['GET'])
@admin_required
def list_login_events():
    username = request.args.get('username')
    successful = request.args.get('successful')
    query = LoginEvent.query.order_by(LoginEvent.timestamp.desc())
    if username:
        query = query.filter(LoginEvent.username == username)
    if successful in ['true', 'false', '1', '0']:
        query = query.filter(LoginEvent.successful == (successful in ['true', '1']))
    events = query.limit(250).all()
    return jsonify([e.to_dict() for e in events])


@app.route('/api/auth/logins/<int:event_id>', methods=['DELETE'])
@admin_required
def delete_login_event(event_id):
    ev = LoginEvent.query.get_or_404(event_id)
    db.session.delete(ev)
    db.session.commit()
    return jsonify({'message': 'deleted'})


# ---- User Routes ----

@app.route('/api/users', methods=['GET'])
@jwt_required()
def list_users():
    users = User.query.all()
    return jsonify([u.to_dict() for u in users])


@app.route('/api/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())


@app.route('/api/users/me', methods=['PATCH'])
@jwt_required()
def update_profile():
    user = User.query.get(get_jwt_identity())
    data = request.get_json()
    if 'bio' in data:
        user.bio = data['bio']
    if 'avatar_color' in data:
        user.avatar_color = data['avatar_color']
    db.session.commit()
    return jsonify(user.to_dict(include_email=True))


# ---- Quest Routes ----

@app.route('/api/quests', methods=['GET'])
@jwt_required()
def list_quests():
    quests = Quest.query.all()
    return jsonify([q.to_dict() for q in quests])


@app.route('/api/quests/<int:quest_id>', methods=['GET'])
@jwt_required()
def get_quest(quest_id):
    quest = Quest.query.get_or_404(quest_id)
    return jsonify(quest.to_dict())


# ---- Completion Routes ----

@app.route('/api/completions', methods=['POST'])
@jwt_required()
def submit_completion():
    user_id = get_jwt_identity()
    quest_id = request.form.get('quest_id')
    mode = request.form.get('mode', 'solo')
    partner_ids = request.form.get('partner_ids', '')
    note = request.form.get('note', '')

    quest = Quest.query.get_or_404(quest_id)

    # Check if already completed
    existing = Completion.query.filter_by(user_id=user_id, quest_id=quest_id).first()
    if existing:
        return jsonify({'error': 'Quest already completed'}), 400

    photo_url = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and allowed_file(file.filename):
            filename = str(uuid.uuid4()) + '.' + file.filename.rsplit('.', 1)[1].lower()
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            photo_url = f'/api/uploads/{filename}'

    completion = Completion(
        user_id=user_id,
        quest_id=int(quest_id),
        mode=mode,
        partner_ids=partner_ids,
        photo_url=photo_url,
        note=note,
        points_earned=quest.points
    )
    db.session.add(completion)
    db.session.commit()
    return jsonify(completion.to_dict()), 201


@app.route('/api/completions/me', methods=['GET'])
@jwt_required()
def my_completions():
    user_id = get_jwt_identity()
    completions = Completion.query.filter_by(user_id=user_id).order_by(Completion.completed_at.desc()).all()
    return jsonify([c.to_dict() for c in completions])


@app.route('/api/completions/feed', methods=['GET'])
@jwt_required()
def feed():
    completions = Completion.query.order_by(Completion.completed_at.desc()).limit(50).all()
    return jsonify([c.to_dict() for c in completions])


@app.route('/api/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# ---- Schedule Routes ----

@app.route('/api/schedules', methods=['GET'])
@jwt_required()
def list_schedules():
    user_id = request.args.get('user_id', get_jwt_identity())
    schedules = Schedule.query.filter_by(user_id=user_id).all()
    return jsonify([s.to_dict() for s in schedules])


@app.route('/api/schedules', methods=['POST'])
@jwt_required()
def add_schedule():
    user_id = get_jwt_identity()
    data = request.get_json()
    schedule = Schedule(
        user_id=user_id,
        day_of_week=data['day_of_week'],
        start_time=data['start_time'],
        end_time=data['end_time'],
        label=data.get('label', 'Available')
    )
    db.session.add(schedule)
    db.session.commit()
    return jsonify(schedule.to_dict()), 201


@app.route('/api/schedules/<int:sid>', methods=['DELETE'])
@jwt_required()
def delete_schedule(sid):
    user_id = get_jwt_identity()
    schedule = Schedule.query.filter_by(id=sid, user_id=user_id).first_or_404()
    db.session.delete(schedule)
    db.session.commit()
    return jsonify({'message': 'Deleted'})


# ---- Leaderboard ----

@app.route('/api/leaderboard', methods=['GET'])
@jwt_required()
def leaderboard():
    users = User.query.all()
    ranked = sorted(users, key=lambda u: u.total_points, reverse=True)
    return jsonify([{**u.to_dict(), 'rank': i+1} for i, u in enumerate(ranked)])


# ---- Seed quests on startup ----

QUESTS = [
    # EASY (25-50 pts)
    ("Watch the sunrise together", "Wake up before 6am and watch the sunrise as a group.", "Outdoor", "easy", 25, "🌅"),
    ("Cook a meal from scratch", "Make a full meal with no pre-packaged ingredients.", "Food", "easy", 30, "🍳"),
    ("Visit a local museum", "Spend at least an hour exploring a museum.", "Culture", "easy", 30, "🏛️"),
    ("Go on a 5km walk", "Walk 5km in one go without stopping.", "Fitness", "easy", 25, "🚶"),
    ("Try a new cuisine", "Eat at a restaurant serving a cuisine you've never tried.", "Food", "easy", 25, "🍜"),
    ("Watch a classic movie", "Watch a movie from before 1990 that none of you have seen.", "Culture", "easy", 25, "🎬"),
    ("Play a board game marathon", "Play 3+ board games in a single session.", "Social", "easy", 30, "🎲"),
    ("Find and photograph 10 flowers", "Identify and photograph 10 different flower species.", "Nature", "easy", 35, "🌸"),
    ("Visit a farmer's market", "Buy at least 3 things from a local farmer's market.", "Food", "easy", 25, "🥕"),
    ("Write and send letters", "Write physical letters to 3 people and actually mail them.", "Social", "easy", 30, "✉️"),
    ("Stargazing night", "Spend 30 min outside identifying constellations.", "Outdoor", "easy", 35, "⭐"),
    ("Random act of kindness", "Do 5 random acts of kindness for strangers in one day.", "Social", "easy", 40, "💝"),
    ("Learn 10 words in a new language", "Learn and correctly use 10 words in a language none of you speak.", "Learning", "easy", 30, "🗣️"),
    ("Visit every coffee shop on a street", "Walk a high street and get a drink from every café.", "Food", "easy", 35, "☕"),
    ("Picnic in a new park", "Find a park you've never visited and have a picnic.", "Outdoor", "easy", 25, "🧺"),
    ("Attend a free event", "Find and attend any free local event.", "Culture", "easy", 30, "🎉"),
    ("Complete a puzzle", "Finish a 500+ piece jigsaw puzzle together.", "Social", "easy", 35, "🧩"),
    ("Go thrift shopping", "Visit a charity shop and each buy something under £5.", "Culture", "easy", 25, "👕"),
    ("Make homemade ice cream", "Make ice cream from scratch without a machine.", "Food", "easy", 40, "🍦"),
    ("Take a cold shower", "Everyone takes a 2 min cold shower. All must verify.", "Fitness", "easy", 50, "🚿"),

    # MEDIUM (75-150 pts)
    ("Climb a local hill", "Reach the summit of any hill or small mountain nearby.", "Outdoor", "medium", 75, "⛰️"),
    ("Cook a 3-course meal for others", "Plan, cook and serve a proper 3-course dinner.", "Food", "medium", 80, "🍽️"),
    ("Attend a live music event", "Go to any live music event together.", "Culture", "medium", 75, "🎵"),
    ("Complete a 10K run", "Run a full 10 kilometres together.", "Fitness", "medium", 100, "🏃"),
    ("Go wild swimming", "Swim in a natural body of water (lake, river, sea).", "Outdoor", "medium", 90, "🏊"),
    ("Host a trivia night", "Host a full trivia night with at least 10 rounds.", "Social", "medium", 80, "🧠"),
    ("Visit 5 different towns in a day", "Travel to and photograph 5 different towns in 24 hours.", "Adventure", "medium", 120, "🗺️"),
    ("Learn and perform a dance", "Learn a choreographed dance and perform it.", "Culture", "medium", 100, "💃"),
    ("Camp overnight in the wild", "Set up camp and spend a full night outdoors.", "Outdoor", "medium", 130, "⛺"),
    ("Bake a celebration cake", "Bake a layered, decorated celebration cake from scratch.", "Food", "medium", 85, "🎂"),
    ("Complete a charity challenge", "Sign up for and complete any charity challenge event.", "Fitness", "medium", 110, "💪"),
    ("Visit a historical site", "Explore a UNESCO or nationally significant historical site.", "Culture", "medium", 80, "🏰"),
    ("Do a day trip abroad", "Travel to another country for a day trip.", "Adventure", "medium", 140, "✈️"),
    ("Go kayaking or canoeing", "Complete a kayak or canoe route.", "Outdoor", "medium", 95, "🛶"),
    ("Complete a cooking class", "Attend an in-person cooking class.", "Food", "medium", 90, "👨‍🍳"),
    ("Run a 5K race", "Enter and complete an official 5K race.", "Fitness", "medium", 85, "🏅"),
    ("Visit an art gallery", "Spend 2+ hours in an art gallery and discuss 5 pieces.", "Culture", "medium", 75, "🎨"),
    ("Make a short film", "Write, film and edit a short film (minimum 3 mins).", "Creative", "medium", 120, "🎥"),
    ("Do a 24-hour no-phone challenge", "Everyone goes 24 hours without a smartphone.", "Challenge", "medium", 150, "📵"),
    ("Complete a volunteer day", "Volunteer together for a full day at a charity.", "Social", "medium", 130, "🤝"),

    # HARD (200-350 pts)
    ("Hike a long distance trail", "Complete a hike of 20+ miles in one day.", "Outdoor", "hard", 200, "🥾"),
    ("Learn to cook a foreign cuisine", "Master 3 authentic dishes from a cuisine you've never cooked.", "Food", "hard", 210, "🌍"),
    ("Complete a triathlon", "Swim, cycle and run in an official or unofficial triathlon.", "Fitness", "hard", 300, "🏊‍♂️"),
    ("Organise a community event", "Plan and host a community event with 20+ attendees.", "Social", "hard", 250, "🎪"),
    ("Travel somewhere new for a weekend", "Take an unplanned weekend trip to somewhere none of you have been.", "Adventure", "hard", 220, "🧳"),
    ("Learn a musical instrument", "Learn to play a recognisable song on any instrument.", "Learning", "hard", 240, "🎸"),
    ("Complete a 100-mile cycle", "Cycle 100 miles in a single day.", "Fitness", "hard", 280, "🚴"),
    ("Build something with your hands", "Build a piece of furniture or structure from scratch.", "Creative", "hard", 230, "🔨"),
    ("Complete a silent retreat", "Spend 48 hours in silence together (no talking, no phones).", "Challenge", "hard", 300, "🧘"),
    ("Swim in the sea in winter", "Ocean swim between October and March.", "Outdoor", "hard", 200, "🌊"),
    ("Host a dinner party for 10+", "Plan and cook a full dinner party for 10 or more guests.", "Food", "hard", 220, "🥂"),
    ("Complete a Tough Mudder / obstacle course", "Finish any obstacle course race event.", "Fitness", "hard", 250, "🏆"),
    ("Read the same book and discuss", "Everyone reads a 300+ page book and has a 2-hour book club session.", "Learning", "hard", 200, "📚"),
    ("Do an improv or stand-up comedy class", "Take an improv or stand-up class and perform in front of people.", "Creative", "hard", 230, "🎭"),
    ("Complete a multi-day backpacking trip", "Backpack for 3+ consecutive days carrying all gear.", "Outdoor", "hard", 320, "🎒"),
    ("Learn conversational phrases in a language", "Have a 5-minute basic conversation in a new language with a native speaker.", "Learning", "hard", 260, "🌐"),
    ("Organise a scavenger hunt for others", "Create and run a city-wide scavenger hunt for other people.", "Social", "hard", 240, "🔍"),
    ("Complete a 48-hour challenge", "Pick any hard personal challenge and document completing it over 48 hours.", "Challenge", "hard", 280, "⏱️"),
    ("Wild forage a meal", "Forage all ingredients for a meal from nature.", "Outdoor", "hard", 250, "🍄"),
    ("Row a boat across a lake", "Row a rowing boat across a substantial lake or harbour.", "Outdoor", "hard", 210, "🚣"),

    # LEGENDARY (500-1000 pts)
    ("Summit a mountain above 3000m", "Reach the summit of any peak over 3000 metres above sea level.", "Outdoor", "legendary", 600, "🏔️"),
    ("Complete a marathon", "Run a full 42.2km marathon event.", "Fitness", "legendary", 700, "🏁"),
    ("Solo travel for a month", "One person travels to 3+ new countries solo for a month.", "Adventure", "legendary", 800, "🌏"),
    ("Learn to surf", "Stand up and ride a wave at least 5 times in one session.", "Outdoor", "legendary", 500, "🏄"),
    ("Complete a 100-day streak challenge", "Do one thing every single day for 100 days. Document each.", "Challenge", "legendary", 1000, "🔥"),
    ("Write and publish something", "Write and publish a blog post, article or zine read by 100+ people.", "Creative", "legendary", 550, "📝"),
    ("Learn to fly or sail", "Get a PPL, microlight, or dinghy sailing qualification.", "Learning", "legendary", 900, "⚓"),
    ("Complete an ultramarathon", "Run any official ultra (50k+).", "Fitness", "legendary", 950, "💥"),
    ("Raise £500 for charity", "Fundraise and donate £500+ to any registered charity.", "Social", "legendary", 700, "💸"),
    ("Build an app or website", "Build and launch a functional app or website used by real people.", "Creative", "legendary", 750, "💻"),
]


def seed_quests():
    if Quest.query.count() == 0:
        for title, desc, cat, diff, pts, icon in QUESTS:
            q = Quest(title=title, description=desc, category=cat,
                      difficulty=diff, points=pts, icon=icon)
            db.session.add(q)
        db.session.commit()
        print(f"Seeded {len(QUESTS)} quests!")


with app.app_context():
    db.create_all()
    seed_quests()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
