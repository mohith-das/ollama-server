from flask import Flask, render_template, redirect, url_for, request, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import requests

app = Flask(__name__)
app.secret_key = "your_secret_key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# Database Model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)


# Initialize the database
with app.app_context():
    db.create_all()


@app.route("/")
def index():
    if "user" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Check if the user already exists
        if User.query.filter_by(email=email).first():
            return "Email already registered!", 400

        # Hash the password and generate a token
        hashed_password = generate_password_hash(password, method="sha256")
        token = str(uuid.uuid4())

        # Save the user to the database
        new_user = User(email=email, password=hashed_password, token=token)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for("login"))
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        # Check the user exists
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session["user"] = user.email
            session["token"] = user.token
            return redirect(url_for("dashboard"))
        return "Invalid credentials!", 401
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("token", None)
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("dashboard.html")


@app.route("/autogen/<path:path>", methods=["GET", "POST"])
def autogen_proxy(path):
    if "user" not in session:
        return redirect(url_for("login"))

    # Proxy request to autogen studio
    autogen_url = f"http://127.0.0.1:5000/{path}"
    if request.method == "POST":
        response = requests.post(autogen_url, data=request.form)
    else:
        response = requests.get(autogen_url)
    return (response.content, response.status_code, response.headers.items())


if __name__ == "__main__":
    app.run(debug=True)
