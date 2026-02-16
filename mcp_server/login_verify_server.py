import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("login-verifier")


def log(msg: str) -> None:
    """Log to stderr so messages appear in the terminal without interfering with MCP stdio transport."""
    print(msg, file=sys.stderr, flush=True)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@mcp.tool()
async def start_webapp(port: int = 9777) -> str:
    """Start the Flask web application if it is not already running.

    Spawns the webapp as a detached subprocess and waits until it is healthy.

    Args:
        port: The port the web app listens on (default 9777).

    Returns:
        A message indicating whether the app was started or was already running.
    """
    url = f"http://localhost:{port}/"

    # Check if already running
    try:
        urllib.request.urlopen(url, timeout=3)
        log(f"[start_webapp] App is already running on port {port}")
        return f"App is already running on port {port}"
    except Exception:
        log(f"[start_webapp] Web app is NOT running on port {port}. Starting it now...")

    # Resolve paths
    venv_python = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
    webapp_script = os.path.join(PROJECT_ROOT, "webapp", "app.py")

    if not os.path.exists(venv_python):
        return f"FAIL: Python not found at {venv_python}"
    if not os.path.exists(webapp_script):
        return f"FAIL: webapp/app.py not found at {webapp_script}"

    # Spawn as a detached subprocess
    log(f"[start_webapp] Spawning webapp process: {venv_python} {webapp_script}")
    subprocess.Popen(
        [venv_python, webapp_script],
        cwd=PROJECT_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    # Poll until healthy (up to 15 seconds)
    for _ in range(15):
        await asyncio.sleep(1)
        try:
            urllib.request.urlopen(url, timeout=2)
            log(f"[start_webapp] Web app is now healthy on port {port}")
            return f"SUCCESS: Web app started and healthy on port {port}"
        except Exception:
            continue

    return f"FAIL: Started process but app not responding on port {port} after 15 seconds"


def _ensure_keycloak_user(
    base_url: str,
    realm: str = "local-dev",
    username: str = "Tanmay",
    password: str = "Tanmay",
    admin_user: str = "admin",
    admin_password: str = "admin",
) -> str:
    """Create the test user in Keycloak if it doesn't already exist.

    Uses the Keycloak Admin REST API (no extra dependencies needed).
    Returns a status message.
    """
    # Step 1: Get admin token
    token_url = f"{base_url}realms/master/protocol/openid-connect/token"
    token_data = urllib.parse.urlencode({
        "grant_type": "password",
        "client_id": "admin-cli",
        "username": admin_user,
        "password": admin_password,
    }).encode()
    try:
        req = urllib.request.Request(token_url, data=token_data)
        resp = urllib.request.urlopen(req, timeout=10)
        token = json.loads(resp.read())["access_token"]
    except Exception as e:
        return f"FAIL: Could not get admin token: {e}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Step 2: Check if user already exists
    users_url = f"{base_url}admin/realms/{realm}/users?username={username}&exact=true"
    try:
        req = urllib.request.Request(users_url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=10)
        users = json.loads(resp.read())
        if users:
            log(f"[ensure_user] User '{username}' already exists in realm '{realm}'")
            return f"User '{username}' already exists"
    except Exception as e:
        return f"FAIL: Could not check users: {e}"

    # Step 3: Create user with password
    create_url = f"{base_url}admin/realms/{realm}/users"
    user_payload = json.dumps({
        "username": username,
        "firstName": username,
        "lastName": "User",
        "email": f"{username.lower()}@localhost",
        "emailVerified": True,
        "enabled": True,
        "credentials": [{
            "type": "password",
            "value": password,
            "temporary": False,
        }],
    }).encode()
    try:
        req = urllib.request.Request(create_url, data=user_payload, headers=headers, method="POST")
        urllib.request.urlopen(req, timeout=10)
        log(f"[ensure_user] Created user '{username}' in realm '{realm}'")
        return f"SUCCESS: Created user '{username}'"
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return f"FAIL: Could not create user (HTTP {e.code}): {body}"
    except Exception as e:
        return f"FAIL: Could not create user: {e}"


def _disable_master_ssl(container_name: str = "agent-local-env-keycloak-1") -> str:
    """Disable SSL requirement on master realm via kcadm.sh inside the container."""
    try:
        # Configure kcadm credentials
        subprocess.run(
            ["docker", "exec", container_name, "/opt/keycloak/bin/kcadm.sh",
             "config", "credentials", "--server", "http://localhost:8080",
             "--realm", "master", "--user", "admin", "--password", "admin"],
            capture_output=True, text=True, timeout=10,
        )
        # Set sslRequired=NONE on master
        result = subprocess.run(
            ["docker", "exec", container_name, "/opt/keycloak/bin/kcadm.sh",
             "update", "realms/master", "-s", "sslRequired=NONE"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            log("[disable_master_ssl] Disabled SSL on master realm")
            return "SUCCESS"
        return f"FAIL: {result.stderr}"
    except Exception as e:
        return f"FAIL: {e}"


def _is_docker_running() -> bool:
    """Check if the Docker daemon is responsive."""
    docker_cmd = shutil.which("docker")
    if not docker_cmd:
        return False
    try:
        result = subprocess.run(
            [docker_cmd, "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except Exception:
        return False


@mcp.tool()
async def start_docker() -> str:
    """Start the Docker daemon if it is not already running.

    Detects the platform (macOS or Linux) and uses the appropriate method:
    - macOS: opens Docker Desktop via 'open -a Docker'
    - Linux: uses 'systemctl start docker'

    Returns:
        A message indicating whether Docker was started or was already running.
    """
    if _is_docker_running():
        log("[start_docker] Docker is already running")
        return "Docker is already running"

    if not shutil.which("docker"):
        return "FAIL: docker command not found. Please install Docker."

    system = platform.system()
    log(f"[start_docker] Docker is NOT running. Platform: {system}. Starting it now...")

    if system == "Darwin":
        subprocess.Popen(
            ["open", "-a", "Docker"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    elif system == "Linux":
        result = subprocess.run(
            ["systemctl", "start", "docker"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            # Try with sudo as fallback
            log("[start_docker] systemctl failed without sudo, retrying with sudo...")
            result = subprocess.run(
                ["sudo", "systemctl", "start", "docker"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                return f"FAIL: Could not start Docker: {result.stderr}"
    else:
        return f"FAIL: Unsupported platform '{system}'. Please start Docker manually."

    # Poll until Docker daemon is responsive (up to 30 seconds)
    log("[start_docker] Waiting for Docker daemon to be ready...")
    for i in range(30):
        await asyncio.sleep(1)
        if _is_docker_running():
            log("[start_docker] Docker is now running")
            return "SUCCESS: Docker started and ready"
        if i % 10 == 9:
            log(f"[start_docker] Still waiting... ({i + 1}s)")

    return "FAIL: Started Docker but daemon not responding after 30 seconds"


@mcp.tool()
async def start_keycloak(port: int = 8080) -> str:
    """Start Keycloak via docker-compose if it is not already running.

    Spawns Keycloak as a Docker container and waits until the health endpoint responds.

    Args:
        port: The port Keycloak listens on (default 8080).

    Returns:
        A message indicating whether Keycloak was started or was already running.
    """
    health_url = f"http://localhost:{port}/realms/master"

    # Check if already running
    try:
        urllib.request.urlopen(health_url, timeout=3)
        log(f"[start_keycloak] Keycloak is already running on port {port}")
        _disable_master_ssl()
        user_result = _ensure_keycloak_user(f"http://localhost:{port}/")
        log(f"[start_keycloak] User provisioning: {user_result}")
        return f"Keycloak is already running on port {port}. {user_result}"
    except Exception:
        log(f"[start_keycloak] Keycloak is NOT running on port {port}. Starting it now...")

    # Ensure Docker daemon is running first
    if not _is_docker_running():
        log("[start_keycloak] Docker is not running, starting it first...")
        docker_result = await start_docker()
        if docker_result.startswith("FAIL"):
            return f"FAIL: Cannot start Keycloak — {docker_result}"

    # Start via docker-compose
    compose_file = os.path.join(PROJECT_ROOT, "docker-compose.yml")
    if not os.path.exists(compose_file):
        return f"FAIL: docker-compose.yml not found at {compose_file}"

    log("[start_keycloak] Running docker-compose up -d")
    result = subprocess.run(
        ["docker-compose", "up", "-d"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"[start_keycloak] docker-compose failed: {result.stderr}")
        return f"FAIL: docker-compose up -d failed: {result.stderr}"

    # Poll until healthy (up to 60 seconds — Keycloak is slow to cold-start)
    log("[start_keycloak] Waiting for Keycloak to become healthy...")
    for i in range(60):
        await asyncio.sleep(1)
        try:
            urllib.request.urlopen(health_url, timeout=2)
            log(f"[start_keycloak] Keycloak is now healthy on port {port}")
            # Disable SSL on master realm so admin API works over HTTP
            ssl_result = _disable_master_ssl()
            log(f"[start_keycloak] Master SSL disable: {ssl_result}")
            # Ensure the test user exists
            user_result = _ensure_keycloak_user(f"http://localhost:{port}/")
            log(f"[start_keycloak] User provisioning: {user_result}")
            return f"SUCCESS: Keycloak started and healthy on port {port}. {user_result}"
        except Exception:
            if i % 10 == 9:
                log(f"[start_keycloak] Still waiting... ({i + 1}s)")
            continue

    return f"FAIL: Started Keycloak container but not responding on port {port} after 60 seconds"


@mcp.tool()
async def start_database(port: int = 5432) -> str:
    """Start PostgreSQL via docker-compose if it is not already running.

    Args:
        port: The port PostgreSQL listens on (default 5432).

    Returns:
        A message indicating whether PostgreSQL was started or was already running.
    """
    # Check if already running by attempting a TCP connection
    import socket
    def _pg_ready():
        try:
            s = socket.create_connection(("localhost", port), timeout=2)
            s.close()
            return True
        except Exception:
            return False

    if _pg_ready():
        log(f"[start_database] PostgreSQL is already running on port {port}")
        return f"PostgreSQL is already running on port {port}"

    # Ensure Docker daemon is running first
    if not _is_docker_running():
        log("[start_database] Docker is not running, starting it first...")
        docker_result = await start_docker()
        if docker_result.startswith("FAIL"):
            return f"FAIL: Cannot start PostgreSQL — {docker_result}"

    # Start via docker-compose
    compose_file = os.path.join(PROJECT_ROOT, "docker-compose.yml")
    if not os.path.exists(compose_file):
        return f"FAIL: docker-compose.yml not found at {compose_file}"

    log("[start_database] Running docker-compose up -d postgres")
    result = subprocess.run(
        ["docker-compose", "up", "-d", "postgres"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log(f"[start_database] docker-compose failed: {result.stderr}")
        return f"FAIL: docker-compose up -d postgres failed: {result.stderr}"

    # Poll until healthy (up to 30 seconds)
    log("[start_database] Waiting for PostgreSQL to become ready...")
    for i in range(30):
        await asyncio.sleep(1)
        if _pg_ready():
            log(f"[start_database] PostgreSQL is now ready on port {port}")
            return f"SUCCESS: PostgreSQL started and ready on port {port}"
        if i % 10 == 9:
            log(f"[start_database] Still waiting... ({i + 1}s)")

    return f"FAIL: Started PostgreSQL container but not responding on port {port} after 30 seconds"


@mcp.tool()
async def verify_database(port: int = 5432) -> str:
    """Verify that PostgreSQL is running and the accounts/payments tables exist with data.

    Args:
        port: The port PostgreSQL listens on (default 5432).

    Returns:
        A message with table row counts or an error.
    """
    try:
        import psycopg2
        conn = psycopg2.connect(
            host="localhost", port=port,
            dbname="localdev", user="localdev", password="localdev",
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT count(*) FROM accounts")
        accounts_count = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM payments")
        payments_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return f"SUCCESS: Database is healthy. accounts={accounts_count} rows, payments={payments_count} rows."
    except Exception as e:
        return f"FAIL: Could not connect to PostgreSQL: {e}"


@mcp.tool()
async def verify_login(url: str, username: str, password: str) -> str:
    """Verify that a web application login page is reachable and credentials work.

    Uses a headless browser (Playwright) to fill in the login form and submit it,
    just like a real user would.

    Args:
        url: The login page URL (e.g. http://localhost:9777/login.html)
        username: The username to log in with
        password: The password to log in with

    Returns:
        A message indicating whether the login succeeded or failed.
    """
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Step 1: Navigate to the login page
            try:
                await page.goto(url, timeout=5000)
            except Exception as e:
                await browser.close()
                return f"FAIL: Could not connect to {url}. Is the server running? ({e})"

            # Step 2: Fill in credentials and submit
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')

            # Step 3: Wait for navigation and check for dashboard
            await page.wait_for_load_state("networkidle")

            if "Welcome" in (await page.content()):
                await browser.close()
                return f"SUCCESS: Login worked. Reached dashboard for user '{username}'."

            current_url = page.url
            await browser.close()
            return f"FAIL: Login did not reach dashboard. Page URL: {current_url}"
    except Exception as e:
        return f"FAIL: Browser automation error: {e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
