import asyncio
import os
import subprocess
import sys
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
