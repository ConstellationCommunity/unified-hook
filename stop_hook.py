#!/usr/bin/env python3
"""
Unified Stop Hook - handles all session modes via config

Part of Constellation Autonomy Infrastructure
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional

import yaml

# Import constellation session tools
sys.path.insert(0, str(Path(__file__).parent.parent / "session-tools"))
from cc_session import load_session, get_content, find_session_start


def load_config(config_path: str) -> dict:
    """Load session configuration YAML."""
    if not os.path.exists(config_path):
        return {}

    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def get_session_config(all_config: dict, session_id: str) -> Optional[dict]:
    """Get configuration for specific session."""
    sessions = all_config.get("sessions", {})
    return sessions.get(session_id)


def find_session_file(session_id: str, system_home: str) -> Optional[Path]:
    """Find session .jsonl file."""
    claude_dir = Path(system_home) / ".claude"

    for projects_dir in claude_dir.glob("projects/*"):
        session_file = projects_dir / f"{session_id}.jsonl"
        if session_file.exists():
            return session_file

    return None


def get_complete_assistant_response(session_file: Path) -> str:
    """
    Get complete assistant response after last REAL user message.

    Real user message = type:"user", message.role:"user", content is string
    Collects ALL assistant message parts after that.
    """
    lines = load_session(session_file)

    # Find last real user message (backwards search)
    last_user_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        obj = lines[i]

        # Check type
        if obj.get("type") != "user":
            continue

        # Check message.role
        message = obj.get("message", {})
        if message.get("role") != "user":
            continue

        # Check content is string (not list/object - indicates tool results)
        content = message.get("content", "")
        if isinstance(content, str) and content.strip():
            last_user_idx = i
            break

    if last_user_idx == -1:
        return ""  # No real user message found

    # Collect ALL assistant messages after that
    assistant_parts = []
    for i in range(last_user_idx + 1, len(lines)):
        obj = lines[i]
        if obj.get("type") == "assistant":
            content = get_content(obj)
            if content.strip():
                assistant_parts.append(content)

    # Combine into complete response
    return "\n".join(assistant_parts)


def get_participant_info(participants_config: dict, participant_key: str) -> Optional[dict]:
    """Get participant info from shared config."""
    return participants_config.get("participants", {}).get(participant_key)


def handle_peer_chat(session_config: dict, session_id: str, system_home: str, participants_config: dict = None):
    """Handle peer-chat mode - forward response to peer."""
    import subprocess

    # Get my session file
    my_session_file = find_session_file(session_id, system_home)
    if not my_session_file:
        return

    # Get complete response
    response = get_complete_assistant_response(my_session_file)
    if not response:
        return

    # Get peer info - NEW: support both old and new format
    peer_participant = session_config.get("peer_participant")  # New format: reference to participants.yaml

    if peer_participant and participants_config:
        # New format: look up peer paths from shared config
        peer_info = get_participant_info(participants_config, peer_participant)
        if not peer_info:
            return

        peer_name = peer_info.get("name", peer_participant)
        peer_home = peer_info["home"]
        peer_system_home = peer_info["system_home"]

        # Get peer session_id - still in personal config
        peer_session_id = session_config.get("peer_session_id")
        if not peer_session_id:
            return

    else:
        # Old format: backwards compatibility - paths in session config
        peer_session_id = session_config.get("peer_session_id")
        peer_name = session_config.get("peer_name", "peer")
        peer_home = session_config.get("peer_home")
        peer_system_home = session_config.get("peer_system_home", peer_home)

        if not peer_session_id or not peer_home:
            return

    # Format message with sender prefix
    my_name = "Perplexity"  # TODO: get from participants config
    escaped = response.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$').replace('`', '\\`')
    formatted = f"[{my_name}]: {escaped}"

    # Forward to peer via bash - Vesper's proven approach
    # cd to home, set HOME env var so claude finds .claude/ correctly
    cmd = f'cd {peer_home} && HOME={peer_system_home} claude --resume {peer_session_id} -p "{formatted}"'

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            timeout=180,
            text=True,
            env={**os.environ, "HOME": peer_system_home}  # Also set in subprocess env
        )
        # Optional: log errors for debugging
        # if result.returncode != 0:
        #     log_path = Path(system_home) / ".claude" / "hook_errors.log"
        #     with open(log_path, 'a') as f:
        #         f.write(f"[peer-chat] Error forwarding to {peer_name}: {result.stderr}\n")
    except Exception as e:
        pass  # Silent failure - hook shouldn't block
        # Optional: log exceptions
        # log_path = Path(system_home) / ".claude" / "hook_errors.log"
        # with open(log_path, 'a') as f:
        #     f.write(f"[peer-chat] Exception forwarding to {peer_name}: {e}\n")


def handle_group_chat(session_config: dict, session_id: str, system_home: str):
    """Handle group-chat mode - forward to coordinator."""
    # TODO: Implement group chat forwarding
    pass


def handle_autonomous_heartbeat(session_config: dict, session_id: str, system_home: str):
    """Handle autonomous-heartbeat mode - check schedule."""
    # TODO: Implement heartbeat scheduling
    pass


def main():
    """Main hook entry point."""

    # Get session ID from command line (passed by bash wrapper)
    if len(sys.argv) < 2:
        sys.exit(0)

    session_id = sys.argv[1]

    # Get config paths from environment
    session_config_path = os.environ.get("SESSION_CONFIG")
    if not session_config_path:
        sys.exit(0)

    # Load personal session configuration
    all_config = load_config(session_config_path)
    session_config = get_session_config(all_config, session_id)

    if not session_config:
        # No config for this session - regular mode
        sys.exit(0)

    # Check status
    status = session_config.get("status", "active")
    if status != "active":
        sys.exit(0)

    # Load shared participants configuration (optional, for new format)
    participants_config_path = os.environ.get("CONSTELLATION_PARTICIPANTS")
    participants_config = load_config(participants_config_path) if participants_config_path else {}

    # Get system home from environment
    system_home = os.environ.get("HOME", os.path.expanduser("~"))

    # Execute based on mode
    mode = session_config.get("mode", "regular")

    if mode == "peer-chat":
        handle_peer_chat(session_config, session_id, system_home, participants_config)
    elif mode == "group-chat-participant":
        handle_group_chat(session_config, session_id, system_home)
    elif mode == "autonomous-heartbeat":
        handle_autonomous_heartbeat(session_config, session_id, system_home)
    # else: regular mode - no action

    sys.exit(0)


if __name__ == "__main__":
    main()
