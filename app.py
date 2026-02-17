from flask import Flask, render_template, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta

app = Flask(__name__)
app.config["SECRET_KEY"] = "devkey"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///focus.db"

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(200))
def get_streak(user_id):
    sessions = FocusSession.query.filter_by(user_id=user_id).all()

    days = set(s.timestamp.date() for s in sessions)
    if not days:
        return 0

    streak = 0
    today = datetime.utcnow().date()

    while today in days:
        streak += 1
        today -= timedelta(days=1)

    return streak


from datetime import datetime

class FocusSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    minutes = db.Column(db.Integer)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    done = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stage = db.Column(db.Integer, default=0)  # 0=seed, 1=sprout, 2=plant, 3=flower
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def home():
    return redirect("/login")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        hashed = generate_password_hash(request.form["password"])
        user = User(email=request.form["email"], password=hashed)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return redirect("/dashboard")
    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        if user and check_password_hash(user.password, request.form["password"]):
            login_user(user)
            return redirect("/dashboard")
        else:
            error = "Invalid email or password"
    return render_template("login.html", error=error)


@app.route("/dashboard")
@login_required
def dashboard():
    tasks = Task.query.filter_by(user_id=current_user.id).all()
    streak = get_streak(current_user.id)

    plant = Plant.query.filter_by(user_id=current_user.id).first()

    if not plant:
        plant = Plant(user_id=current_user.id, stage=0)
        db.session.add(plant)
        db.session.commit()

    return render_template(
        "dashboard.html",
        user=current_user,
        tasks=tasks,
        streak=streak,
        plant=plant
    )


@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    title = request.form.get("title")
    task = Task(title=title, user_id=current_user.id)
    db.session.add(task)
    db.session.commit()
    return redirect("/dashboard")


@app.route("/stats")
@login_required
def stats():
    sessions = FocusSession.query.filter_by(user_id=current_user.id).all()
    total = sum(s.minutes for s in sessions)
    return render_template("stats.html", sessions=sessions, total=total)

@app.route("/chart_data")
@login_required
def chart_data():
    sessions = FocusSession.query.filter_by(user_id=current_user.id).all()

    daily = {}
    for s in sessions:
        day = s.timestamp.strftime("%Y-%m-%d")
        daily[day] = daily.get(day, 0) + s.minutes

    labels = list(daily.keys())
    values = list(daily.values())

    return {"labels": labels, "values": values}


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")

@app.route("/log_session", methods=["POST"])
@login_required
def log_session():
    minutes = request.form.get("minutes")
    session = FocusSession(minutes=int(minutes), user_id=current_user.id)
    db.session.add(session)
    # 🌱 Grow plant
    plant = Plant.query.filter_by(user_id=current_user.id).first()
    if plant:
        plant.stage += 1
        if plant.stage > 3:
            plant.stage = 3
        db.session.add(plant)
    db.session.commit()
    return "OK"

@app.route("/complete_task/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
    return redirect("/dashboard")


@app.route("/delete_task/<int:task_id>")
@login_required
def delete_task(task_id):
    task = Task.query.get(task_id)
    if task and task.user_id == current_user.id:
        db.session.delete(task)
        db.session.commit()
    return redirect("/dashboard")

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)

