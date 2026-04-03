from datetime import datetime
from fractions import Fraction
import json
import re

from bs4 import BeautifulSoup
from flask import Flask, redirect, render_template, request, url_for
from flask_login import LoginManager, UserMixin, current_user, login_required, login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
import requests


app = Flask(__name__)
app.config["SECRET_KEY"] = "devkey"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///recipe.db"


db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)


class Recipe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    ingredients_json = db.Column(db.Text, nullable=False, default="[]")
    instructions = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


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

    if any(keyword in html.lower() for keyword in PAYWALL_KEYWORDS):
        raise ValueError("This page appears to be paywalled. Use a freely accessible recipe URL.")

    soup = BeautifulSoup(html, "html.parser")
    for script in soup.select("script[type='application/ld+json']"):
        if not script.string:
            continue
        try:
            payload = json.loads(script.string)
        except json.JSONDecodeError:
            continue

        blocks = payload if isinstance(payload, list) else [payload]
        for block in blocks:
            block_type = block.get("@type", [])
            types = block_type if isinstance(block_type, list) else [block_type]
            if "Recipe" not in types:
                continue

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
                "title": block.get("name", "Untitled Recipe"),
                "ingredients": block.get("recipeIngredient", []),
                "instructions": instructions,
            }

    raise ValueError("Could not find recipe data on that page.")


@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("recipes"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            error = "Email and password are required."
        elif User.query.filter_by(email=email).first():
            error = "Email already registered."
        else:
            user = User(email=email, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for("recipes"))

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip()).first()
        if user and check_password_hash(user.password, request.form.get("password", "")):
            login_user(user)
            return redirect(url_for("recipes"))
        error = "Invalid email or password"

    return render_template("login.html", error=error)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


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
                    user_id=current_user.id,
                )
                db.session.add(recipe)
                db.session.commit()
                return redirect(url_for("recipes"))
            except requests.RequestException:
                error = "Could not fetch that URL right now."
            except ValueError as exc:
                error = str(exc)

    saved = Recipe.query.filter_by(user_id=current_user.id).order_by(Recipe.created_at.desc()).all()
    return render_template("recipes.html", recipes=saved, error=error, json=json)


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
