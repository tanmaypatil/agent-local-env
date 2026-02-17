import psycopg2
from psycopg2.extras import RealDictCursor

DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "dbname": "localdev",
    "user": "localdev",
    "password": "localdev",
}


def get_conn():
    return psycopg2.connect(**DB_CONFIG)


# ── Accounts ─────────────────────────────────────────────────────────

def insert_accounts(rows):
    """Insert list of dicts with keys: name, account_type, status. Returns (inserted, errors)."""
    inserted, errors = 0, []
    conn = get_conn()
    try:
        cur = conn.cursor()
        for i, row in enumerate(rows, 1):
            try:
                cur.execute(
                    "INSERT INTO accounts (name, account_type, status) VALUES (%s, %s, %s)",
                    (row["name"], row["account_type"], row.get("status", "active")),
                )
                inserted += 1
            except Exception as e:
                conn.rollback()
                errors.append(f"Row {i}: {e}")
                continue
        conn.commit()
    finally:
        conn.close()
    return inserted, errors


def search_accounts(name=None, account_type=None, status=None):
    clauses, params = [], []
    if name:
        clauses.append("name ILIKE %s")
        params.append(f"%{name}%")
    if account_type:
        clauses.append("account_type = %s")
        params.append(account_type)
    if status:
        clauses.append("status = %s")
        params.append(status)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM accounts{where} ORDER BY id", params)
        return cur.fetchall()
    finally:
        conn.close()


def update_account(account_id, name, account_type, status):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE accounts SET name=%s, account_type=%s, status=%s WHERE id=%s",
            (name, account_type, status, account_id),
        )
        conn.commit()
    finally:
        conn.close()


# ── Payments ─────────────────────────────────────────────────────────

def insert_payments(rows):
    """Insert list of dicts with keys: amount, currency, debit_account, credit_account. Returns (inserted, errors)."""
    inserted, errors = 0, []
    conn = get_conn()
    try:
        cur = conn.cursor()
        for i, row in enumerate(rows, 1):
            try:
                cur.execute(
                    "INSERT INTO payments (amount, currency, debit_account, credit_account) VALUES (%s, %s, %s, %s)",
                    (row["amount"], row.get("currency", "USD"), row["debit_account"], row["credit_account"]),
                )
                inserted += 1
            except Exception as e:
                conn.rollback()
                errors.append(f"Row {i}: {e}")
                continue
        conn.commit()
    finally:
        conn.close()
    return inserted, errors


def search_payments(currency=None, min_amount=None, max_amount=None):
    clauses, params = [], []
    if currency:
        clauses.append("currency = %s")
        params.append(currency)
    if min_amount:
        clauses.append("amount >= %s")
        params.append(min_amount)
    if max_amount:
        clauses.append("amount <= %s")
        params.append(max_amount)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SELECT * FROM payments{where} ORDER BY id", params)
        return cur.fetchall()
    finally:
        conn.close()


def update_payment(payment_id, amount, currency, debit_account, credit_account):
    conn = get_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE payments SET amount=%s, currency=%s, debit_account=%s, credit_account=%s WHERE id=%s",
            (amount, currency, debit_account, credit_account, payment_id),
        )
        conn.commit()
    finally:
        conn.close()
