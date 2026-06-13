# =========================
# CYRUS PROJECT V3 - CLEAN BACKEND
# =========================

import time
from flask import Flask, request
from flask_cors import CORS
from flask_restful import Resource, Api
from flask_sqlalchemy import SQLAlchemy
from sklearn.linear_model import LinearRegression
from werkzeug.security import generate_password_hash, check_password_hash

# =========================
# FLASK SETUP
# =========================

cyrus = Flask(__name__)
CORS(cyrus, resources={r"/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}})
api = Api(cyrus)

cyrus.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cyrus.db'
cyrus.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(cyrus)

# =========================
# DATABASE MODEL
# =========================

class CYR(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    importance = db.Column(db.Integer, nullable=False)
    effort = db.Column(db.Integer, nullable=False)
    urgency = db.Column(db.Integer, nullable=False)
    time = db.Column(db.Integer, nullable=False)

    start_time = db.Column(db.Float, nullable=False)
    finished_time = db.Column(db.Float, nullable=True)
    actual_time = db.Column(db.Float, nullable=True)

    completed = db.Column(db.Boolean, default=False)
    outcome = db.Column(db.Integer, nullable=True)

def task_to_dict(t):
    return {
        "id": t.id,
        "name": t.name,
        "importance": t.importance,
        "effort": t.effort,
        "urgency": t.urgency,
        "time": t.time,
        "completed": t.completed,
    }


#username + password for future user authentication system
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)

#Signup
class SignUp(Resource):
    def post(self):
        data = request.get_json()

        email = data["email"]
        password = data["password"]

        if User.query.filter_by(email=email).first():
            return {"message": "User already exists"}, 409

        hashed_password = generate_password_hash(password)
        user = User(email=email, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()

        return {"message": "User created successfully"}, 201
    
#Login
class Login(Resource):
    def post(self):
        data = request.get_json()

        email = data["email"]
        password = data["password"]

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            return {"message": "Invalid email or password"}, 401

        return {
            "message": "Login successful",
            "user_id": user.id,
            "email": user.email,
        }

# =========================
# API ROUTES
# =========================

class GetTasks(Resource):
    def get(self):
        tasks = CYR.query.all()
        return [task_to_dict(t) for t in tasks]


class AddTask(Resource):
    def post(self):
        data = request.get_json()

        task = CYR(
            name=data["name"],
            importance=data["importance"],
            effort=data["effort"],
            urgency=data["urgency"],
            time=data["time"],
            start_time=time.time(),
            completed=False,
            outcome=None
        )

        db.session.add(task)
        db.session.commit()

        return task_to_dict(task), 201


class UpdateTask(Resource):
    def put(self, task_id):
        task = CYR.query.get(task_id)

        if not task:
            return {"message": "Task not found"}, 404

        data = request.get_json()

        task.name = data.get("name", task.name)
        task.importance = data.get("importance", task.importance)
        task.effort = data.get("effort", task.effort)
        task.urgency = data.get("urgency", task.urgency)
        task.time = data.get("time", task.time)

        db.session.commit()

        return task_to_dict(task)


class DeleteTask(Resource):
    def delete(self, task_id):
        task = CYR.query.get(task_id)

        if not task:
            return {"message": "Task not found"}, 404

        db.session.delete(task)
        db.session.commit()

        return {"message": "Task deleted"}


class FinishTask(Resource):
    def post(self, task_id):
        task = CYR.query.get(task_id)

        if not task:
            return {"error": "not found"}, 404

        task.finished_time = time.time()
        task.actual_time = task.finished_time - task.start_time
        task.completed = True

        data = request.get_json()
        task.outcome = data["outcome"]

        db.session.commit()

        return {"message": "task finished"}


# =========================
# ML SYSTEM
# =========================

model = None

def train_model():
    global model

    X = []
    y = []

    tasks = CYR.query.all()

    for t in tasks:
        if t.outcome is None:
            continue

        X.append([t.importance, t.urgency, t.effort, t.time])
        y.append(t.outcome)

    if len(X) < 5:
        return None

    model = LinearRegression()
    model.fit(X, y)

    return model


class MLTasks(Resource):
    def get(self):
        global model

        tasks = CYR.query.filter_by(completed=False).all()

        if len(tasks) < 2:
            return []

        if model is None:
            train_model()

        if model is None:
            return {"message": "Not enough data to train"}, 400

        scored = []

        for t in tasks:
            score = model.predict([[t.importance, t.urgency, t.effort, t.time]])[0]

            scored.append({
                "id": t.id,
                "name": t.name,
                "score": score
            })

        scored.sort(key=lambda x: x["score"], reverse=True)

        return scored
# =========================
# REGISTER ROUTES
# =========================
api.add_resource(SignUp, '/signup')
api.add_resource(Login, '/login')
api.add_resource(GetTasks, '/tasks')
api.add_resource(AddTask, '/add')
api.add_resource(UpdateTask, '/update/<int:task_id>')
api.add_resource(DeleteTask, '/delete/<int:task_id>')
api.add_resource(FinishTask, '/finish/<int:task_id>')
api.add_resource(MLTasks, '/ml')

# =========================
# START SERVER
# =========================

with cyrus.app_context():
    db.create_all()

if __name__ == "__main__":
    cyrus.run(host="0.0.0.0", port=5000, debug=True)