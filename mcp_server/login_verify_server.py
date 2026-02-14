from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("login-verifier")


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
