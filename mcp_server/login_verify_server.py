import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("login-verifier")


@mcp.tool()
def verify_login(url: str, username: str, password: str) -> str:
    """Verify that a web application login page is reachable and credentials work.

    Args:
        url: The login page URL (e.g. http://localhost:9777/login.html)
        username: The username to log in with
        password: The password to log in with

    Returns:
        A message indicating whether the login succeeded or failed.
    """
    session = requests.Session()

    # Step 1: Check if login page is reachable
    try:
        resp = session.get(url, timeout=5)
        resp.raise_for_status()
    except requests.ConnectionError:
        return f"FAIL: Could not connect to {url}. Is the server running?"
    except requests.RequestException as e:
        return f"FAIL: Error reaching login page: {e}"

    # Step 2: POST credentials
    login_post_url = url.rsplit("/", 1)[0] + "/login"
    try:
        resp = session.post(
            login_post_url,
            data={"username": username, "password": password},
            allow_redirects=True,
            timeout=5,
        )
    except requests.RequestException as e:
        return f"FAIL: Error posting login credentials: {e}"

    # Step 3: Check if we reached the dashboard
    if "Welcome" in resp.text:
        return f"SUCCESS: Login worked. Reached dashboard for user '{username}'."

    return f"FAIL: Login did not reach dashboard. Response status: {resp.status_code}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
