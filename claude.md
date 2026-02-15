# Agent to validate a local development environment

## Objective
Agent to check whether local development environment services are up.

## Project Structure
```
agent-local-env/
├── .env                              # ANTHROPIC_API_KEY (not checked in)
├── .venv/                            # Python 3.11 virtual environment
├── requirements.txt                  # All dependencies
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

### 1. Flask Web Application (`webapp/`)
- Login page at `http://localhost:9777/login.html`
- Dashboard page at `/dashboard` (session-protected)
- Root `/` redirects to login
- Credentials: username `Tanmay`, password `Tanmay`
- Session-based auth using Flask's built-in `session`

### 2. Login Verification MCP Server (`mcp_server/`)
- Exposes `verify_login(url, username, password)` tool via stdio transport
- Uses Playwright (headless Chromium) to fill login form, click submit, and verify dashboard
- Built with `mcp` Python SDK (`FastMCP`)

### 3. Claude AI Agent (`agent/`)
- Uses `claude-agent-sdk` to orchestrate verification
- Spawns the MCP server automatically as a subprocess
- Loads API key from `.env` via `python-dotenv`
- Streams Claude's reasoning and tool results to stdout

## How to Run

### Prerequisites
- Python 3.11+ (system `python3` is 3.9, use `.venv`)
- `ANTHROPIC_API_KEY` set in `.env`

### Steps
```bash
# Install dependencies (one-time)
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium

# Terminal 1: Start the web app
.venv/bin/python3 webapp/app.py

# Terminal 2: Run the agent (must NOT be inside a Claude Code session)
cd /Users/tanmaypatil/agent-local-env
.venv/bin/python3 agent/agent.py
```

### Known Constraints
- The agent cannot run from inside a Claude Code terminal (nested session detection). Use a separate terminal or `unset CLAUDECODE` first.

## Available MCP Tools
- `start_webapp(port)` — Starts the Flask web app if it's not running. Waits until healthy.
- `verify_login(url, username, password)` — Uses Playwright to test login flow in a headless browser.

## Operational Workflow
1. Check if the web app at http://localhost:9777 is running
2. If not running, use `start_webapp` to start it
3. Verify login works using `verify_login` with credentials from the Components section above

## Documentation
Update claude.md at the end of every code changes.

