# Agent to validate a local development environment

## Objective
Agent to check whether local development environment services are up.

## Project Structure
```
agent-local-env/
├── .env                              # ANTHROPIC_API_KEY (not checked in)
├── .venv/                            # Python 3.11 virtual environment
├── requirements.txt                  # All dependencies
├── docker-compose.yml                # Keycloak (port 8080) + PostgreSQL (port 5432)
├── db/
│   └── init.sql                      # Schema + seed data (accounts, payments)
├── keycloak/
│   └── realm-export.json             # Pre-configured realm, client, test user
├── webapp/
│   ├── app.py                        # Flask app (port 9777)
│   ├── db.py                         # DB helpers (psycopg2, accounts & payments CRUD)
│   └── templates/
│       ├── login.html
│       ├── dashboard.html
│       ├── upload.html               # CSV upload page (accounts & payments)
│       ├── accounts.html             # Accounts search + inline edit
│       └── payments.html             # Payments search + inline edit
├── mcp_server/
│   └── login_verify_server.py        # MCP server (stdio transport)
└── agent/
    └── agent.py                      # Claude AI agent (Agent SDK)
```

## Components

### 1. Keycloak Identity Provider (`docker-compose.yml`, `keycloak/`)
- Runs via Docker: `quay.io/keycloak/keycloak:24.0.3` in dev mode
- Admin console at `http://localhost:8080` (admin/admin)
- Realm: `local-dev` (sslRequired: none)
- Client: `flask-app` (public client, direct access grants enabled)
- Test user: `Tanmay` / `Tanmay` (with firstName, lastName, email — required by Keycloak 24 User Profile)
- Command-line flags: `--hostname-strict=false --hostname-strict-https=false --http-enabled=true --spi-realm-default-ssl-required=none`

### 2. PostgreSQL Database (`docker-compose.yml`, `db/`)
- Runs via Docker: `postgres:16`
- Connection: `localhost:5432`, database `localdev`, user `localdev`, password `localdev`
- Schema auto-initialized from `db/init.sql` on first start
- Tables:
  - `accounts` — id, name, account_type, created_at, status (active/inactive)
  - `payments` — id, amount, currency, debit_account, credit_account, created_at
- Data volume `pgdata` persists across restarts; use `docker-compose down -v` to reset

### 3. Flask Web Application (`webapp/`)
- **UI theme: light** — Use a clean light theme (white cards, light gray backgrounds, dark text) for all pages
- Login page at `http://localhost:9777/login.html`
- Dashboard page at `/dashboard` (session-protected)
- Root `/` redirects to login
- Credentials validated against Keycloak via `python-keycloak` (`KeycloakOpenID.token()` password grant)
- Keycloak connection configured via env vars: `KEYCLOAK_SERVER_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`
- Session-based auth using Flask's built-in `session`
- `require_login` decorator protects all data routes
- **Database module** (`webapp/db.py`): Uses `psycopg2` with `RealDictCursor`, connection-per-request
- **CSV Upload** (`/upload`): Upload accounts or payments via CSV, row-level error handling
- **Accounts page** (`/accounts`): Search by name/type/status, inline edit with Post/Redirect/Get
- **Payments page** (`/payments`): Search by currency/amount range, inline edit with PRG, create payment form
- **Create payment** (`POST /payments/create`): Inserts a new payment, redirects to `/payments?created=1`
- **REST API**: `/api/accounts` and `/api/payments` return JSON with search params
- All new routes are session-protected via `@require_login`
- Expected CSV formats:
  - `accounts.csv`: columns `name`, `account_type`, `status`
  - `payments.csv`: columns `amount`, `currency`, `debit_account`, `credit_account`

### 4. Login Verification MCP Server (`mcp_server/`)
- Exposes tools via stdio transport, built with `mcp` Python SDK (`FastMCP`)
- `start_docker()` — platform-agnostic Docker daemon startup
- `start_keycloak(port)` — docker-compose up, disables master SSL, provisions test user
- `start_database(port)` — starts PostgreSQL via docker-compose, waits until ready
- `verify_database(port)` — connects to PostgreSQL, verifies tables and row counts
- `start_webapp(port)` — spawns Flask app as detached subprocess
- `verify_login(url, username, password)` — Playwright headless browser login test

### 5. Claude AI Agent (`agent/`)
- Uses `claude-agent-sdk` `ClaudeSDKClient` for interactive, bidirectional sessions
- `can_use_tool` callback prompts user for Y/n approval on non-allowed tools
- Prompt sent as `AsyncIterable` (required by `can_use_tool` streaming mode)
- MCP tools in `allowed_tools` are auto-approved; other tools (e.g. Bash) trigger interactive approval
- Loads API key from `.env` via `python-dotenv`

## How to Run

### Prerequisites
- Python 3.11+ (system `python3` is 3.9, use `.venv`)
- Docker (for Keycloak)
- `ANTHROPIC_API_KEY` set in `.env`

### Steps
```bash
# Install dependencies (one-time)
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

# Terminal 1: Start Keycloak (or let the agent do it)
docker-compose down -v && docker-compose up -d
# Wait ~30s for Keycloak to be ready

# Terminal 2: Start the web app (or let the agent do it)
.venv/bin/python3 webapp/app.py

# Terminal 3: Run the agent (must NOT be inside a Claude Code session)
cd /Users/tanmaypatil/agent-local-env
.venv/bin/python3 agent/agent.py
```

### Known Constraints
- The agent cannot run from inside a Claude Code terminal (nested session detection). Use a separate terminal or `unset CLAUDECODE` first.
- When recreating Keycloak, always use `docker-compose down -v` to remove volumes — Keycloak skips realm import if the realm already exists.

## Available MCP Tools
- `start_docker()` — Starts the Docker daemon if not running. Platform-agnostic: uses `open -a Docker` on macOS, `systemctl start docker` on Linux.
- `start_keycloak(port)` — Starts Keycloak via docker-compose if it's not running. Automatically starts Docker first if needed. Disables SSL on master realm and ensures test user exists. Waits until healthy (up to 60s).
- `start_database(port)` — Starts PostgreSQL via docker-compose if it's not running. Automatically starts Docker first if needed. Waits until ready (up to 30s).
- `verify_database(port)` — Connects to PostgreSQL and verifies accounts/payments tables exist with data.
- `start_webapp(port)` — Starts the Flask web app if it's not running. Waits until healthy.
- `verify_login(url, username, password)` — Uses Playwright to test login flow in a headless browser.
- `create_and_verify_payment(url, username, password)` — Logs in via Playwright, creates a payment (amount=50, USD, debit=1, credit=2) through the webapp form, and verifies the row exists in PostgreSQL.

## Operational Workflow
1. Check if Docker is running; if not, use `start_docker` to start it (also called automatically by `start_keycloak`)
2. Check if Keycloak at http://localhost:8080 is running; if not, use `start_keycloak` to start it
3. Check if PostgreSQL at localhost:5432 is running; if not, use `start_database` to start it
4. Verify database is healthy using `verify_database`
5. Check if the web app at http://localhost:9777 is running; if not, use `start_webapp` to start it
6. Verify login works using `verify_login` with credentials: username `Tanmay`, password `Tanmay`
7. Create and verify a payment using `create_and_verify_payment` — logs in, submits the create payment form, and checks the database

## Keycloak Gotchas (Learned)
- **HTTPS required**: Keycloak 24 enforces SSL even in dev mode. Must set `sslRequired: "none"` in realm JSON AND disable it on the master realm via `kcadm.sh` after startup.
- **User Profile**: Keycloak 24 requires `firstName`, `lastName`, `email` on all users. Without these, password grant fails with "Account is not fully set up".
- **Realm import credentials**: `--import-realm` does NOT accept plain-text passwords. Credentials must use pre-hashed PBKDF2-SHA256 format (`secretData`/`credentialData`). Alternatively, create users via the Admin REST API after startup.
- **Realm import is idempotent**: If the realm already exists, import is silently skipped (`IGNORE_EXISTING` strategy). Use `docker-compose down -v` to force re-import.
- **Health check**: `/health/ready` returns 404 in dev mode. Use `/realms/master` instead.
- **Username case**: Keycloak normalizes usernames to lowercase internally.

## Claude Agent SDK Gotchas (Learned)
- **`query()` vs `ClaudeSDKClient`**: `query()` is fire-and-forget — no interactive tool approval. Use `ClaudeSDKClient` for bidirectional sessions where tool approvals work.
- **`can_use_tool` + `permission_prompt_tool_name`**: These are mutually exclusive. Use one or the other.
- **`can_use_tool` requires streaming mode**: The prompt must be an `AsyncIterable`, not a string. Wrap with an async generator yielding `{"type": "user", "session_id": "", "message": {"role": "user", "content": text}, "parent_tool_use_id": None}`.
- **Permission flow**: Permission requests are NOT yielded from `receive_messages()`. They are intercepted by the `can_use_tool` callback via a separate control protocol.

## Documentation
Update CLAUDE.md at the end of every code change.
