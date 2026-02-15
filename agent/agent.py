import asyncio
import os
import sys

from dotenv import load_dotenv
from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    AssistantMessage,
    ResultMessage,
    PermissionResultAllow,
    PermissionResultDeny,
    ToolPermissionContext,
)

# Resolve paths relative to the project root (one level up from agent/)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
VENV_PYTHON = os.path.join(PROJECT_ROOT, ".venv", "bin", "python3")
MCP_SERVER = os.path.join(PROJECT_ROOT, "mcp_server", "login_verify_server.py")


async def handle_tool_permission(
    tool_name: str,
    tool_input: dict,
    context: ToolPermissionContext,
):
    """Prompt the user to approve or deny tool usage."""
    print(f"\n--- Tool approval requested ---")
    print(f"  Tool:  {tool_name}")
    if tool_name == "Bash":
        print(f"  Command: {tool_input.get('command', '')}")
    else:
        print(f"  Input: {tool_input}")

    answer = input("  Allow? [Y/n]: ").strip().lower()
    if answer in ("", "y", "yes"):
        return PermissionResultAllow(behavior="allow")
    return PermissionResultDeny(
        behavior="deny",
        message="User denied the tool call",
    )


async def make_prompt(text: str):
    """Wrap a string prompt as an AsyncIterable (required for can_use_tool streaming mode)."""
    yield {
        "type": "user",
        "session_id": "",
        "message": {"role": "user", "content": text},
        "parent_tool_use_id": None,
    }


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
            "mcp__login-verifier__start_keycloak",
            "mcp__login-verifier__start_docker",
        ],
        can_use_tool=handle_tool_permission,
    )

    prompt_text = (
        "You are a local dev environment validator. "
        "Below is the project's CLAUDE.md with details about the environment, "
        "services, credentials, and available tools.\n\n"
        "---\n"
        f"{claude_md_content}\n"
        "---\n\n"
        "Follow the Operational Workflow in CLAUDE.md. "
        "Prefer using the MCP tools (start_docker, start_keycloak, start_webapp, "
        "verify_login) as they already handle health checks and startup internally. "
        "You may also use shell commands like curl or wget if needed for additional checks. "
        "Report the final status of each step."
    )

    async with ClaudeSDKClient(options=options) as client:
        await client.connect(prompt=make_prompt(prompt_text))

        async for message in client.receive_messages():
            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if hasattr(block, "text"):
                        print(block.text)
            elif isinstance(message, ResultMessage):
                if message.subtype == "success":
                    print(message.result)
                break


if __name__ == "__main__":
    asyncio.run(main())
