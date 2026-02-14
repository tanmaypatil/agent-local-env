from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-prod"

VALID_USERNAME = "Tanmay"
VALID_PASSWORD = "Tanmay"


@app.route("/")
def index():
    return redirect(url_for("login_page"))


@app.route("/login.html")
def login_page():
    return render_template("login.html")


@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username", "")
    password = request.form.get("password", "")

    if username == VALID_USERNAME and password == VALID_PASSWORD:
        session["username"] = username
        return redirect(url_for("dashboard"))

    return render_template("login.html", error="Invalid credentials")


@app.route("/dashboard")
def dashboard():
    username = session.get("username")
    if not username:
        return redirect(url_for("login_page"))
    return render_template("dashboard.html", username=username)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9777, debug=True)
