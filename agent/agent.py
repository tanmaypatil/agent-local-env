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

    # Read CLAUDE.md for project context
    claude_md_path = os.path.join(PROJECT_ROOT, "CLAUDE.md")
    with open(claude_md_path, "r") as f:
        claude_md_content = f.read()

    options = ClaudeAgentOptions(
        mcp_servers={
            "login-verifier": {
                "command": python_cmd,
                "args": [MCP_SERVER],
            }
        },
        allowed_tools=[
            "mcp__login-verifier__verify_login",
            "mcp__login-verifier__start_webapp",
        ],
    )

    prompt = (
        "You are a local dev environment validator. "
        "Below is the project's CLAUDE.md with details about the environment, "
        "services, credentials, and available tools.\n\n"
        "---\n"
        f"{claude_md_content}\n"
        "---\n\n"
        "Follow the Operational Workflow in CLAUDE.md. "
        "If a service is not running, start it and then verify it works. "
        "Report the final status of each check."
    )

    async for message in query(
        prompt=prompt,
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
