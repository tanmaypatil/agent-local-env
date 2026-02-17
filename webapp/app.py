import csv
import io
import os
from functools import wraps

from flask import Flask, jsonify, render_template, request, redirect, session, url_for
from keycloak import KeycloakOpenID
from keycloak.exceptions import KeycloakAuthenticationError

from db import (
    insert_accounts, search_accounts, update_account,
    insert_payments, search_payments, update_payment,
)

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


def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated


def parse_csv(file_storage):
    """Parse an uploaded CSV file into a list of dicts."""
    stream = io.StringIO(file_storage.stream.read().decode("utf-8"))
    reader = csv.DictReader(stream)
    return list(reader)


# ── Auth routes ──────────────────────────────────────────────────────

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
@require_login
def dashboard():
    return render_template("dashboard.html", username=session["username"])


# ── Upload routes ────────────────────────────────────────────────────

@app.route("/upload")
@require_login
def upload_page():
    return render_template("upload.html")


@app.route("/upload/accounts", methods=["POST"])
@require_login
def upload_accounts():
    f = request.files.get("file")
    if not f or not f.filename.endswith(".csv"):
        return render_template("upload.html", message="Please upload a .csv file.", success=False)
    rows = parse_csv(f)
    inserted, errors = insert_accounts(rows)
    return render_template(
        "upload.html",
        message=f"Inserted {inserted} account(s).",
        success=inserted > 0,
        errors=errors,
    )


@app.route("/upload/payments", methods=["POST"])
@require_login
def upload_payments():
    f = request.files.get("file")
    if not f or not f.filename.endswith(".csv"):
        return render_template("upload.html", message="Please upload a .csv file.", success=False)
    rows = parse_csv(f)
    inserted, errors = insert_payments(rows)
    return render_template(
        "upload.html",
        message=f"Inserted {inserted} payment(s).",
        success=inserted > 0,
        errors=errors,
    )


# ── Accounts routes ─────────────────────────────────────────────────

@app.route("/accounts")
@require_login
def accounts_page():
    name = request.args.get("name", "").strip()
    account_type = request.args.get("account_type", "").strip()
    status = request.args.get("status", "").strip()
    updated = request.args.get("updated") == "1"
    accounts = search_accounts(
        name=name or None,
        account_type=account_type or None,
        status=status or None,
    )
    return render_template(
        "accounts.html",
        accounts=accounts,
        search_name=name,
        search_type=account_type,
        search_status=status,
        updated=updated,
    )


@app.route("/accounts/<int:account_id>/update", methods=["POST"])
@require_login
def update_account_route(account_id):
    update_account(
        account_id,
        name=request.form["name"],
        account_type=request.form["account_type"],
        status=request.form["status"],
    )
    return redirect(url_for(
        "accounts_page",
        name=request.form.get("search_name", ""),
        account_type=request.form.get("search_type", ""),
        status=request.form.get("search_status", ""),
        updated="1",
    ))


# ── Payments routes ──────────────────────────────────────────────────

@app.route("/payments")
@require_login
def payments_page():
    currency = request.args.get("currency", "").strip()
    min_amount = request.args.get("min_amount", "").strip()
    max_amount = request.args.get("max_amount", "").strip()
    updated = request.args.get("updated") == "1"
    created = request.args.get("created") == "1"
    payments = search_payments(
        currency=currency or None,
        min_amount=min_amount or None,
        max_amount=max_amount or None,
    )
    return render_template(
        "payments.html",
        payments=payments,
        search_currency=currency,
        search_min=min_amount,
        search_max=max_amount,
        updated=updated,
        created=created,
    )


@app.route("/payments/create", methods=["POST"])
@require_login
def create_payment():
    row = {
        "amount": request.form["amount"],
        "currency": request.form["currency"],
        "debit_account": request.form["debit_account"],
        "credit_account": request.form["credit_account"],
    }
    insert_payments([row])
    return redirect(url_for("payments_page", created="1"))


@app.route("/payments/<int:payment_id>/update", methods=["POST"])
@require_login
def update_payment_route(payment_id):
    update_payment(
        payment_id,
        amount=request.form["amount"],
        currency=request.form["currency"],
        debit_account=request.form["debit_account"],
        credit_account=request.form["credit_account"],
    )
    return redirect(url_for(
        "payments_page",
        currency=request.form.get("search_currency", ""),
        min_amount=request.form.get("search_min", ""),
        max_amount=request.form.get("search_max", ""),
        updated="1",
    ))


# ── REST API routes ──────────────────────────────────────────────────

@app.route("/api/accounts")
@require_login
def api_accounts():
    name = request.args.get("name")
    account_type = request.args.get("account_type")
    status = request.args.get("status")
    rows = search_accounts(name=name, account_type=account_type, status=status)
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
    return jsonify(rows)


@app.route("/api/payments")
@require_login
def api_payments():
    currency = request.args.get("currency")
    min_amount = request.args.get("min_amount")
    max_amount = request.args.get("max_amount")
    rows = search_payments(currency=currency, min_amount=min_amount, max_amount=max_amount)
    for r in rows:
        r["created_at"] = r["created_at"].isoformat()
        r["amount"] = float(r["amount"])
    return jsonify(rows)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9777, debug=True)
