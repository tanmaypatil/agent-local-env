import os

from flask import Flask, render_template, request, redirect, session, url_for
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakAuthenticationError

app = Flask(__name__)
app.secret_key = "dev-secret-key-change-in-prod"

KEYCLOAK_SERVER_URL = os.environ.get("KEYCLOAK_SERVER_URL", "http://localhost:8080/")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "local-dev")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "flask-app")

keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_SERVER_URL,
    client_id=KEYCLOAK_CLIENT_ID,
    realm_name=KEYCLOAK_REALM,
)


def authenticate(username: str, password: str) -> bool:
    """Validate credentials against Keycloak using the direct access grant (password grant)."""
    try:
        keycloak_openid.token(username, password)
        return True
    except KeycloakAuthenticationError:
        return False
    except Exception:
        return False


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

    if authenticate(username, password):
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
