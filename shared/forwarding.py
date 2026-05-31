"""
Message forwarding utilities.

Handles formatting messages and executing bash forwarding commands.
"""
import os
import subprocess
from typing import Optional


def escape_for_bash(text: str) -> str:
    """
    Escape text for safe bash command usage.

    Escapes: backslash, double-quote, dollar sign, backtick
    """
    return (text
            .replace('\\', '\\\\')
            .replace('"', '\\"')
            .replace('$', '\\$')
            .replace('`', '\\`'))


def format_message(sender_name: str, content: str) -> str:
    """
    Format message with sender prefix.

    Format: [SenderName]: content
    """
    escaped = escape_for_bash(content)
    return f"[{sender_name}]: {escaped}"


def build_claude_code_forward_command(
    peer_home: str,
    peer_system_home: str,
    peer_session_id: str,
    message: str
) -> str:
    """
    Build bash command for forwarding to Claude Code peer.

    Uses Vesper's proven approach:
    - cd to peer_home (working directory)
    - Set HOME env var to peer_system_home (so claude finds .claude/)
    - Execute claude --resume with message
    """
    return f'cd {peer_home} && HOME={peer_system_home} claude --resume {peer_session_id} -p "{message}"'


def execute_forward_command(
    cmd: str,
    peer_system_home: str,
    timeout: int = 180
) -> Optional[subprocess.CompletedProcess]:
    """
    Execute bash forwarding command.

    Returns CompletedProcess on success, None on failure.
    Silent failure - hook shouldn't block session.
    """
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=timeout,
            text=True,
            env={**os.environ, "HOME": peer_system_home}  # Also set in subprocess env
        )
        return result
    except Exception:
        # Silent failure - hook shouldn't block
        return None


# === Platform Abstraction (Phase 2 - Future) ===
# When implementing multi-platform support, create Platform classes:
#
# class Platform:
#     """Base platform interface."""
#     def build_forward_command(self, peer_home, peer_session_id, message) -> str:
#         raise NotImplementedError
#
# class ClaudeCodePlatform(Platform):
#     def build_forward_command(self, peer_home, peer_session_id, message) -> str:
#         return build_claude_code_forward_command(...)
#
# PLATFORMS = {"claude-code": ClaudeCodePlatform(), ...}
