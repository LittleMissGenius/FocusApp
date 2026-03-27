from flask import Flask, render_template, redirect, request, url_for, session, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from sqlalchemy import func
from datetime import date
from bs4 import BeautifulSoup
from fractions import Fraction
import json
import re
import requests
import random



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
    streak = db.Column(db.Integer, default=0)
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


class Plant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    stage = db.Column(db.Integer, default=0)  # 0–3
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    priority = db.Column(db.String(10))  # high / medium / low
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

class HarvestedPlant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    flower_type = db.Column(db.String(10), default="🌸") # Stores which emoji was grown
    date_harvested = db.Column(db.DateTime, default=datetime.utcnow)

class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    ingredients_json = db.Column(db.Text, nullable=False, default="[]")
    instructions = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Remember to run with app.app_context(): db.create_all() after adding this!

PAYWALL_KEYWORDS = ("subscribe", "membership", "sign in to continue", "start your free trial")

UNIT_ALIASES = {
    "tsp": "teaspoon",
    "teaspoons": "teaspoon",
    "tbsp": "tablespoon",
    "tablespoons": "tablespoon",
    "oz": "ounce",
    "ounces": "ounce",
    "lb": "pound",
    "lbs": "pound",
    "pounds": "pound",
    "cups": "cup",
}

METRIC_CONVERSIONS = {
    "teaspoon": ("ml", 5),
    "tablespoon": ("ml", 15),
    "cup": ("ml", 240),
    "ounce": ("g", 28.35),
    "pound": ("g", 453.59),
}

LIQUID_HINTS = {"water", "milk", "broth", "stock", "juice", "oil", "vinegar", "syrup"}

INGREDIENT_RE = re.compile(
    r"^\s*(?P<amount>\d+(?:\.\d+)?(?:\s+\d+/\d+)?|\d+/\d+)\s+"
    r"(?P<unit>[A-Za-z]+)\b"
    r"(?:\s+of)?\s*(?P<name>.*)$"
)


def parse_amount(amount_text):
    parts = amount_text.split()
    if len(parts) == 2 and "/" in parts[1]:
        return float(parts[0]) + float(Fraction(parts[1]))
    if "/" in amount_text:
        return float(Fraction(amount_text))
    return float(amount_text)


def format_amount(amount):
    if amount.is_integer():
        return str(int(amount))
    return f"{amount:.1f}".rstrip("0").rstrip(".")


def normalize_ingredient(ingredient):
    match = INGREDIENT_RE.match(ingredient)
    if not match:
        return ingredient

    amount = parse_amount(match.group("amount"))
    unit = UNIT_ALIASES.get(match.group("unit").lower(), match.group("unit").lower())
    name = match.group("name").strip()

    if unit not in METRIC_CONVERSIONS:
        return ingredient

    metric_unit, multiplier = METRIC_CONVERSIONS[unit]
    if unit == "ounce" and any(hint in name.lower() for hint in LIQUID_HINTS):
        metric_unit, multiplier = "ml", 29.57

    metric_amount = amount * multiplier
    return f"{format_amount(metric_amount)} {metric_unit} {name}".strip()


def extract_recipe_from_url(source_url):
    response = requests.get(source_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    html = response.text
    lower_html = html.lower()

    if any(keyword in lower_html for keyword in PAYWALL_KEYWORDS):
        raise ValueError("This page appears to be paywalled. Please use a freely accessible recipe URL.")

    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select("script[type='application/ld+json']"):
        script_content = script.string
        if not script_content:
            continue
        try:
            payload = json.loads(script_content)
        except json.JSONDecodeError:
            continue

        blocks = payload if isinstance(payload, list) else [payload]
        for block in blocks:
            block_type = block.get("@type", [])
            block_types = block_type if isinstance(block_type, list) else [block_type]
            if "Recipe" not in block_types:
                continue

            title = block.get("name", "Untitled Recipe")
            ingredients = block.get("recipeIngredient", [])
            instructions_block = block.get("recipeInstructions", [])
            if isinstance(instructions_block, str):
                instructions = instructions_block
            else:
                steps = []
                for item in instructions_block:
                    if isinstance(item, dict) and item.get("text"):
                        steps.append(item["text"])
                    elif isinstance(item, str):
                        steps.append(item)
                instructions = "\n".join(steps)

            return {
                "title": title,
                "ingredients": ingredients,
                "instructions": instructions,
            }

    raise ValueError("Could not find recipe data on this page. Try a different URL.")


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
    completed_count = len([t for t in tasks if t.completed])
    
    # Calculate progress for the initial page load
    progress = 0
    if len(tasks) > 0:
        progress = int((completed_count / len(tasks)) * 100)

    active_plant = Plant.query.filter_by(user_id=current_user.id, completed=False).first()
    # ... rest of your code ...

# IF NO PLANT EXISTS, CREATE ONE!
    if not active_plant:
        active_plant = Plant(user_id=current_user.id, stage=0)
        db.session.add(active_plant)
        db.session.commit()

    user_streak = current_user.streak if hasattr(current_user, 'streak') else 0
    current_streak = current_user.streak
   
    garden_flowers = HarvestedPlant.query.filter_by(user_id=current_user.id).all()
    
    return render_template("dashboard.html", 
                           tasks=tasks, 
                           plant=active_plant, 
                           progress=progress,
                           streak=current_streak,
                           garden=garden_flowers)


@app.route("/recipes", methods=["GET", "POST"])
@login_required
def recipes():
    error = None

    if request.method == "POST":
        source_url = request.form.get("source_url", "").strip()
        if not source_url:
            error = "Please enter a recipe URL."
        else:
            try:
                parsed = extract_recipe_from_url(source_url)
                normalized_ingredients = [normalize_ingredient(item) for item in parsed["ingredients"]]

                recipe = Recipe(
                    title=parsed["title"],
                    source_url=source_url,
                    ingredients_json=json.dumps(normalized_ingredients),
                    instructions=parsed["instructions"],
                    user_id=current_user.id
                )
                db.session.add(recipe)
                db.session.commit()
                return redirect(url_for("recipes"))
            except requests.RequestException:
                error = "Could not fetch that URL right now."
            except ValueError as exc:
                error = str(exc)

    saved_recipes = Recipe.query.filter_by(user_id=current_user.id).order_by(Recipe.created_at.desc()).all()
    recipe_cards = [
        {
            "title": recipe.title,
            "source_url": recipe.source_url,
            "ingredients": json.loads(recipe.ingredients_json),
            "instructions": recipe.instructions,
        }
        for recipe in saved_recipes
    ]
    return render_template("recipes.html", recipes=recipe_cards, error=error)

@app.route("/add_task", methods=["POST"])
@login_required
def add_task():
    task_text = request.form.get("task")
    priority = request.form.get("priority", "medium")

    if not task_text:
        return jsonify({"error": "Task text is required"}), 400

    new_task = Task(
        title=task_text,
        priority=priority,
        user_id=current_user.id
    )

    db.session.add(new_task)
    db.session.commit()

    # We return JSON so the JavaScript can add the row instantly
    return jsonify({
        "id": new_task.id,
        "title": new_task.title,
        "priority": new_task.priority
    })

@app.route("/delete_task/<int:id>", methods=["POST"])
@login_required
def delete_task(id):
    task = Task.query.get_or_404(id)
    if task.user_id != current_user.id:
        return "Unauthorized", 403
        
    db.session.delete(task)
    db.session.commit()
    return jsonify({"success": True}) # Return JSON success



@app.route("/stats")
@login_required
def stats():
    results = (
        db.session.query(
            func.date(FocusSession.timestamp),
            func.sum(FocusSession.minutes)
        )
        .filter(FocusSession.user_id == current_user.id)
        .group_by(func.date(FocusSession.timestamp))
        .order_by(func.date(FocusSession.timestamp))
        .all()
    )

    dates = [r[0] for r in results]
    totals = [r[1] for r in results]

    return render_template("stats.html", dates=dates, totals=totals)


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
    minutes = int(request.form.get("minutes", 25))
    session_record = FocusSession(minutes=minutes, user_id=current_user.id)
    db.session.add(session_record)

    plant = Plant.query.filter_by(user_id=current_user.id, completed=False).first()
    if not plant:
        plant = Plant(user_id=current_user.id)
        db.session.add(plant)

    plant.stage += 1

    if plant.stage >= 3:
        plant.stage = 3
        plant.completed = True # Fixed typo 'TruE'
        # Only create a NEW plant after the old one is completed
        new_plant = Plant(user_id=current_user.id)
        db.session.add(new_plant)

    db.session.commit()
    return "OK"

@app.route("/complete_task/<int:task_id>", methods=["POST"])
@login_required
def complete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if task.user_id != current_user.id:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    # 1. Toggle task
    task.completed = not task.completed
    db.session.commit()

    # 2. Calculate progress safely
    all_tasks = Task.query.filter_by(user_id=current_user.id).all()
    total = len(all_tasks)
    completed = len([t for t in all_tasks if t.completed])
    progress = int((completed / total) * 100) if total > 0 else 0

    # 3. Get the plant and update stage
    plant = Plant.query.filter_by(user_id=current_user.id, completed=False).first()
    if not plant:
        plant = Plant(user_id=current_user.id)
        db.session.add(plant)
    
    # Update stage based on task progress
    if progress < 30: plant.stage = 0
    elif progress < 60: plant.stage = 1
    elif progress < 90: plant.stage = 2
    else: plant.stage = 3
    
    db.session.commit()

    # 4. Return EVERYTHING the JS needs
    return jsonify({
        "success": True,
        "completed_count": completed,
        "total_count": total,
        "progress": progress,
        "plant_stage": plant.stage
    })

@app.route("/harvest_plant", methods=["POST"])
@login_required
def harvest_plant():
    plant = Plant.query.filter_by(user_id=current_user.id, completed=False).first()
    
    if plant and plant.stage >= 3:
        # RANDOM FLOWER CODE GOES HERE
        flower_options = ["🌸", "🌻", "🌷", "🌹", "🌼", "🌺", "🌵", "🪴"]
        chosen_flower = random.choice(flower_options)

        # Create the trophy
        new_trophy = HarvestedPlant(user_id=current_user.id, flower_type=chosen_flower)
        db.session.add(new_trophy)
        
        # Reset the current plant and update streak
        plant.stage = 0
        current_user.streak += 1
        
        db.session.commit()
        return jsonify({"success": True})
    
    return jsonify({"success": False, "error": "Not ready"})


@app.route("/toggle_theme", methods=["POST"])
@login_required
def toggle_theme():
    # Get current theme from session
    current_theme = session.get("theme", "light")
    # Toggle it
    session["theme"] = "dark" if current_theme == "light" else "light"
    # Redirect back to the page the user was on
    return redirect(request.referrer or url_for("dashboard"))



if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
