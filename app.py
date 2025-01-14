

from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pandas as pd
import random  # For random question selection
import eventlet
import json
#from flask_migrate import Migrate
from sqlalchemy.dialects.sqlite import JSON
from datetime import datetime
from random import sample




eventlet.monkey_patch()

# Initialize the Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashcard_game.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database and Socket.IO
db = SQLAlchemy(app)
socketio = SocketIO(app)



class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    score = db.Column(db.Integer, default=0)
    progress = db.Column(db.String(256), default="")
    important_questions = db.Column(JSON, default=[])

class QuizResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    topic = db.Column(db.String(255), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    date_taken = db.Column(db.DateTime, default=datetime.utcnow)
    questions = db.Column(db.Text, nullable=False)  # This column is causing the error



#migrate = Migrate(app, db)

# Load questions from Excel
QUESTIONS_FILE = 'questions.csv'
if not os.path.exists(QUESTIONS_FILE):
    raise FileNotFoundError("The questions.xlsx file is missing in the project folder.")
questions_df = pd.read_csv(QUESTIONS_FILE)

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
    session.pop('study_questions', None)
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
    important_questions = session.get('important_questions', [])
    return render_template('dashboard.html', user=user, important_questions=important_questions)


@app.route('/study', methods=['GET', 'POST'])
def study():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        selected_topic = request.form.get('topic')
        session.pop('study_questions', None)
        session.pop('current_question', None)
        session.pop('important_questions', None)

        filtered_questions = questions_df[
            questions_df['Topic'].str.strip().str.lower() == selected_topic.strip().lower()
        ]
        if filtered_questions.empty:
            return render_template(
                'study.html',
                topics=questions_df['Topic'].dropna().unique().tolist(),
                current_question=None,
                question_index=None,
                total=0,
                error="No questions available for the selected topic. Please select another topic."
            )

        selected_questions = filtered_questions.sample(min(10, len(filtered_questions))).to_dict('records')
        session['study_questions'] = selected_questions
        session['current_question'] = 0
        return redirect(url_for('study'))

    topics = questions_df['Topic'].dropna().unique().tolist()  # Remove nan values
    print(f"DEBUG: Topics available: {topics}")  # Debug

    study_questions = session.get('study_questions', [])
    current_question_index = session.get('current_question')
    current_question = (
        study_questions[current_question_index]
        if study_questions and current_question_index is not None
        else None   
    )

    return render_template(
        'study.html',
        topics=topics,
        current_question=current_question,
        question_index=current_question_index,
        total=len(study_questions),
        error=None
    )

@app.route('/category_selection', methods=['GET'])
def category_selection():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    topics = questions_df['Topic'].dropna().unique().tolist()
    print(f"DEBUG: Topics sent to category selection: {topics}")  # Debug
    return render_template('category_selection.html', topics=topics)



@app.route('/study/navigation', methods=['POST'])
def study_navigation():
    """Handle navigation between flashcards (Next/Previous)."""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    action = request.json.get('action')
    print(f"DEBUG: Received navigation action: {action}")  # Debug
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
    print(f"DEBUG: Updated current_question_index: {current_question_index}")  # Debug
    return jsonify({"question_index": current_question_index})



@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('study_questions', None)  # Clear study questions
    session.pop('current_question', None)  # Clear current question index
    session.pop('important_questions', None)  # Clear important questions
    return redirect(url_for('login'))


@app.route('/reset_questions', methods=['POST'])
def reset_questions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Clear session data related to study mode
    session.pop('study_questions', None)
    session.pop('current_question', None)
    session.pop('important_questions', None)
    return redirect(url_for('category_selection'))

@app.route('/debug_questions')
def debug_questions():
    return jsonify(questions_df.to_dict(orient='records'))

import json  # To handle serialization
@app.route('/study/mark_important', methods=['POST'])
def mark_important():
    if 'user_id' not in session:
        return jsonify({"error": "User not logged in"}), 403

    data = request.get_json()
    question_index = data.get('question_index')
    user = User.query.get(session['user_id'])

    # Ensure study_questions and user are valid
    study_questions = session.get('study_questions', [])
    if not user or question_index is None or not (0 <= question_index < len(study_questions)):
        return jsonify({"error": "Invalid request"}), 400

    # Get the selected question and its topic
    current_question = study_questions[question_index]
    topic = current_question.get('Topic', 'Unknown')
    question = current_question.get('Question', 'Unknown')
    answer = current_question.get('Answer', 'Unknown')

    # Initialize the important_questions list if empty
    if not user.important_questions:
        user.important_questions = []

    # Ensure all entries in important_questions have the required keys
    user.important_questions = [
        q for q in user.important_questions 
        if all(key in q for key in ['topic', 'question', 'answer'])
    ]

    # Check if the question is already marked as important
    for q in user.important_questions:
        if q.get('question') == question and q.get('topic') == topic:
            return jsonify({"success": False, "message": "Question already marked as important"}), 200

    # Append the question to the important_questions list
    user.important_questions.append({
        "topic": topic,
        "question": question,
        "answer": answer
    })

    # Commit the changes to the database
    db.session.commit()
    return jsonify({"success": True, "message": "Question marked as important!"})


@app.route('/important/remove', methods=['POST'])
def remove_important_question():
    if 'user_id' not in session:
        return jsonify({'error': 'User not logged in'}), 401

    user = User.query.get(session['user_id'])
    data = request.get_json()

    question_to_remove = data.get('question')
    topic_to_remove = data.get('topic')

    if not question_to_remove or not topic_to_remove:
        return jsonify({'error': 'Invalid data provided'}), 400

    # Update the user's important questions list
    user.important_questions = [
        q for q in user.important_questions
        if not (q['question'] == question_to_remove and q['topic'] == topic_to_remove)
    ]

    # Commit changes to the database
    db.session.commit()

    return jsonify({'success': True}), 200



@app.route('/important_questions')
def important_questions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    user = User.query.get(user_id)
    
    if user:
        return render_template('important_questions.html', important_questions=user.important_questions)
    return redirect(url_for('dashboard'))


@app.route('/self_quiz', methods=['GET', 'POST'])
def self_quiz_setup():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    # Dynamically generate topics from the user's current saved important questions
    topics = {q['topic']: len([q for q in user.important_questions if q['topic'] == q['topic']]) for q in user.important_questions}

    if request.method == 'POST':
        topic = request.form.get('topic')
        num_questions = int(request.form.get('num_questions'))
        session['self_quiz_topic'] = topic
        session['self_quiz_num_questions'] = num_questions
        return redirect(url_for('start_self_quiz'))

    return render_template('self_quiz_setup.html', topics=topics)


@app.route('/self_quiz/start', methods=['GET'])
def start_self_quiz():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    topic = session.get('self_quiz_topic')
    num_questions = session.get('self_quiz_num_questions')

    # Filter important questions for the selected topic
    user_topic_questions = [q for q in user.important_questions if q['topic'] == topic]
    total_user_topic_questions = len(user_topic_questions)

    # Set the number of questions to the smaller of user's input or available questions
    if num_questions > total_user_topic_questions:
        num_questions = total_user_topic_questions

    # Randomly select questions for the quiz
    selected_questions = sample(user_topic_questions, num_questions)

    # Load the master question bank
    master_questions = pd.read_csv('questions.csv')

    for question in selected_questions:
        # Find the corresponding row in the master questions bank
        master_question = master_questions[
            (master_questions['Question'] == question['question']) &
            (master_questions['Topic'] == topic)
        ]

        if master_question.empty:
            # Skip the question if no match is found in the master questions bank
            continue

        # Extract the incorrect answers
        incorrect_answers = [
            master_question.iloc[0]['Incorrect Answer 1'],
            master_question.iloc[0]['Incorrect Answer 2'],
            master_question.iloc[0]['Incorrect Answer 3']
        ]

        # Create choices and shuffle them
        question['choices'] = [{'text': question['answer'], 'correct': True}] + \
                              [{'text': ans, 'correct': False} for ans in incorrect_answers]
        random.shuffle(question['choices'])  # Shuffle the choices

    # Save the quiz session data
    session['self_quiz_questions'] = selected_questions
    session['self_quiz_index'] = 0
    session['self_quiz_score'] = 0

    return redirect(url_for('self_quiz_question'))

@app.route('/self_quiz/results', methods=['GET'])
def self_quiz_results():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Fetch session data
    score = session.get('self_quiz_score', 0)
    total = len(session.get('self_quiz_questions', []))
    topic = session.get('self_quiz_topic')

    # Save the result to the database
    user_id = session['user_id']
    questions = session.get('self_quiz_questions', [])
    questions_text = ', '.join([q['question'] for q in questions])  # Convert questions to a single string

    result = QuizResult(
        user_id=user_id,
        topic=topic,
        score=score,
        total_questions=total,
        questions=questions_text  # Save the questions
    )
    db.session.add(result)
    db.session.commit()

    # Clear quiz data from session
    session.pop('self_quiz_questions', None)
    session.pop('self_quiz_index', None)
    session.pop('self_quiz_score', None)
    session.pop('self_quiz_topic', None)

    return render_template('quiz_results.html', score=score, total=total)



@app.route('/self_quiz/question', methods=['GET', 'POST'])
def self_quiz_question():
    if 'user_id' not in session or 'self_quiz_questions' not in session:
        return redirect(url_for('self_quiz_setup'))

    quiz_questions = session['self_quiz_questions']
    quiz_index = session['self_quiz_index']

    if request.method == 'POST':
        user_answer = request.form.get('answer')
        correct_answer = quiz_questions[quiz_index]['answer']
        quiz_questions[quiz_index]['user_answer'] = user_answer

        if user_answer == correct_answer:
            session['self_quiz_score'] += 1

        session['self_quiz_index'] += 1
        if session['self_quiz_index'] >= len(quiz_questions):
            return redirect(url_for('self_quiz_results'))

        return redirect(url_for('self_quiz_question'))

    current_question = quiz_questions[quiz_index]
    return render_template('self_quiz.html', question=current_question, question_index=quiz_index + 1, total=len(quiz_questions))

@app.route('/quiz/history', methods=['GET'])
def quiz_history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    results = QuizResult.query.filter_by(user_id=user_id).order_by(QuizResult.date_taken.desc()).all()

    return render_template('quiz_history.html', results=results)


# Debug: Print all routes
print(app.url_map)

# App execution

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 25002)), debug=True)

