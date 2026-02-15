# Agent to validate a local development environment

## Objective
Agent to check whether local development environment services are up.

## Project Structure
```
agent-local-env/
├── .env                              # ANTHROPIC_API_KEY (not checked in)
├── .venv/                            # Python 3.11 virtual environment
├── requirements.txt                  # All dependencies
├── docker-compose.yml                # Keycloak (port 8080)
├── keycloak/
│   └── realm-export.json             # Pre-configured realm, client, test user
├── webapp/
│   ├── app.py                        # Flask app (port 9777)
│   └── templates/
│       ├── login.html
│       └── dashboard.html
├── mcp_server/
│   └── login_verify_server.py        # MCP server (stdio transport)
└── agent/
    └── agent.py                      # Claude AI agent (Agent SDK)
```

## Components

### 1. Keycloak Identity Provider (`docker-compose.yml`, `keycloak/`)
- Runs via Docker: `quay.io/keycloak/keycloak:24.0.3` in dev mode
- Admin console at `http://localhost:8080` (admin/admin)
- Realm: `local-dev`
- Client: `flask-app` (public client, direct access grants enabled)
- Test user: `Tanmay` / `Tanmay`

### 2. Flask Web Application (`webapp/`)
- Login page at `http://localhost:9777/login.html`
- Dashboard page at `/dashboard` (session-protected)
- Root `/` redirects to login
- Credentials validated against Keycloak via `python-keycloak` (password grant)
- Session-based auth using Flask's built-in `session`

### 3. Login Verification MCP Server (`mcp_server/`)
- Exposes `verify_login(url, username, password)` tool via stdio transport
- Uses Playwright (headless Chromium) to fill login form, click submit, and verify dashboard
- Built with `mcp` Python SDK (`FastMCP`)

### 4. Claude AI Agent (`agent/`)
- Uses `claude-agent-sdk` to orchestrate verification
- Spawns the MCP server automatically as a subprocess
- Loads API key from `.env` via `python-dotenv`
- Streams Claude's reasoning and tool results to stdout

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

# Terminal 1: Start Keycloak
docker-compose up -d
# Wait ~30s for Keycloak to be ready

# Terminal 2: Start the web app
.venv/bin/python3 webapp/app.py

# Terminal 3: Run the agent (must NOT be inside a Claude Code session)
cd /Users/tanmaypatil/agent-local-env
.venv/bin/python3 agent/agent.py
```

### Known Constraints
- The agent cannot run from inside a Claude Code terminal (nested session detection). Use a separate terminal or `unset CLAUDECODE` first.

## Available MCP Tools
- `start_docker()` — Starts the Docker daemon if not running. Platform-agnostic: uses `open -a Docker` on macOS, `systemctl start docker` on Linux.
- `start_keycloak(port)` — Starts Keycloak via docker-compose if it's not running. Automatically starts Docker first if needed. Waits until healthy (up to 60s).
- `start_webapp(port)` — Starts the Flask web app if it's not running. Waits until healthy.
- `verify_login(url, username, password)` — Uses Playwright to test login flow in a headless browser.

## Operational Workflow
1. Check if Docker is running; if not, use `start_docker` to start it (also called automatically by `start_keycloak`)
2. Check if Keycloak at http://localhost:8080 is running; if not, use `start_keycloak` to start it
3. Check if the web app at http://localhost:9777 is running; if not, use `start_webapp` to start it
4. Verify login works using `verify_login` with credentials: username `Tanmay`, password `Tanmay`

## Documentation
Update claude.md at the end of every code changes.
