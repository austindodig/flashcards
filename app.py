from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO
import os
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
import random  # For random question selection

# Initialize the Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashcard_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and Socket.IO
db = SQLAlchemy(app)
socketio = SocketIO(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    score = db.Column(db.Integer, default=0)
    progress = db.Column(db.String(256), default="")

# Load questions from Excel
QUESTIONS_FILE = 'questions.xlsx'
if not os.path.exists(QUESTIONS_FILE):
    raise FileNotFoundError("The questions.xlsx file is missing in the project folder.")
questions_df = pd.read_excel(QUESTIONS_FILE)

# Routes
@app.route('/')
def home():
    return render_template('home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        return "Invalid credentials. Please try again."
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            return "Username already exists."
        new_user = User(
            username=username,
            password_hash=generate_password_hash(password)
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', user=user)

# Create tables
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)



#####STUDY MODE######
@app.route('/study', methods=['GET', 'POST'])
def study():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Handle topic selection and random question generation
        selected_topic = request.form.get('topic')
        filtered_questions = questions_df[questions_df['Topic'] == selected_topic]
        if filtered_questions.empty:
            return "No questions found for the selected topic.", 400

        # Randomly select 10 questions
        selected_questions = filtered_questions.sample(min(10, len(filtered_questions))).to_dict('records')
        session['study_questions'] = selected_questions
        session['current_question'] = 0  # Start at the first question
        return redirect(url_for('study'))

    # GET: Display the study page
    topics = questions_df['Topic'].unique()
    current_question_index = session.get('current_question', 0)
    study_questions = session.get('study_questions', [])

    current_question = study_questions[current_question_index] if study_questions else None
    return render_template(
        'study.html',
        topics=topics,
        current_question=current_question,
        question_index=current_question_index,
        total=len(study_questions)
    )

@app.route('/study/navigation', methods=['POST'])
def study_navigation():
    """Handle navigation between flashcards (Next/Previous)."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    action = request.json.get('action')
    if action not in ['next', 'previous']:
        return jsonify({"error": "Invalid action"}), 400

    total_questions = len(session.get('study_questions', []))
    if total_questions == 0:
        return jsonify({"error": "No questions available."}), 400

    current_question_index = session.get('current_question', 0)
    if action == 'next' and current_question_index < total_questions - 1:
        current_question_index += 1
    elif action == 'previous' and current_question_index > 0:
        current_question_index -= 1

    session['current_question'] = current_question_index
    return jsonify({"question_index": current_question_index})

print(app.url_map)

# Create tables
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True)