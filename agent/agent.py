import asyncio
import os
import sys

from dotenv import load_dotenv
from claude_agent_sdk import ClaudeAgentOptions, AssistantMessage, ResultMessage, query

# Resolve paths relative to the project root (one level up from agent/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
MCP_SERVER = os.path.join(PROJECT_ROOT, "mcp_server", "login_verify_server.py")


async def main():
    python_cmd = VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable
    options = ClaudeAgentOptions(
        mcp_servers={
            "login-verifier": {
                "command": python_cmd,
                "args": [MCP_SERVER],
            }
        },
        allowed_tools=["mcp__login-verifier__verify_login"],
    )

    async for message in query(
        prompt=(
            "Verify the local dev environment is up. "
            "Check if login works at http://localhost:9777/login.html "
            "with username 'Tanmay' and password 'Tanmay'. "
            "Report whether the application is running and login succeeds."
        ),
        options=options,
    ):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if hasattr(block, "text"):
                    print(block.text)
        elif isinstance(message, ResultMessage) and message.subtype == "success":
            print(message.result)


if __name__ == "__main__":
    asyncio.run(main())
