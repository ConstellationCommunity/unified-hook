"""
Message forwarding utilities.

Handles formatting messages and executing bash forwarding commands.
"""
import os
import subprocess
from typing import Optional  # Keeping for potential future use


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
    timeout: int = 180  # No longer used, kept for API compatibility
) -> bool:
    """
    Execute bash forwarding command (fire-and-forget).

    Uses subprocess.Popen() with detachment to avoid circular deadlock.

    CRITICAL: subprocess.run() blocks until command completes, which means
    the hook waits for the peer to fully respond. In circular group chat,
    this creates deadlock - each participant waits for the entire cycle
    before writing hook_success marker.

    Solution: Popen() with start_new_session=True fires command and returns
    immediately. Hook completes right away, hook_success marker written,
    no circular waiting.

    Returns True on successful start, False on failure.
    Silent failure - hook shouldn't block session.
    """
    try:
        subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Detach from parent process
            env={**os.environ, "HOME": peer_system_home}
        )
        return True
    except Exception:
        # Silent failure - hook shouldn't block
        return False


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
