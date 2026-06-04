"""
Peer-chat mode handler.

Forwards assistant responses to configured peer via bash mechanism.
Supports both old format (paths in session config) and new format
(participant reference + shared participants.yaml).
"""
from pathlib import Path
from typing import Optional

from modes import register_mode
from shared.config import get_participant_info, get_peer_session_config
from shared.session import find_session_file, get_complete_assistant_response
from shared.forwarding import (
    format_message,
    build_claude_code_forward_command,
    execute_forward_command
)

# UUID chain repair utilities from shared session-tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "session-tools"))
from cc_session import (
    load_session,
    save_session,
    find_last_stop_hook,
    find_session_start,
    check_and_fix_chain
)


@register_mode("peer-chat")
def handle_peer_chat(
    session_config: dict,
    session_id: str,
    system_home: str,
    participants_config: dict = None
):
    """
    Handle peer-chat mode - forward response to peer.

    Supports two configuration formats:

    NEW FORMAT (recommended):
        session_config:
            peer_participant: "resonance"  # Reference to participants.yaml
            peer_session_id: "uuid"

        participants_config:
            participants:
                resonance:
                    name: "Resonance"
                    home: "/path/to/home"
                    system_home: "/path/to/system"

    OLD FORMAT (backwards compatibility):
        session_config:
            peer_name: "Resonance"
            peer_home: "/path/to/home"
            peer_system_home: "/path/to/system"
            peer_session_id: "uuid"
    """
    # Get my session file
    my_session_file = find_session_file(session_id, system_home)
    if not my_session_file:
        return

    # === UUID Chain Repair (current turn only) ===
    lines = load_session(my_session_file)

    # Find start point for chain check
    last_hook_idx = find_last_stop_hook(lines)

    if last_hook_idx >= 0:
        # Fix only current turn (from last hook marker to end)
        start_idx = last_hook_idx
    else:
        # Fallback: first run, no previous hook marker - check from session start
        start_idx = find_session_start(lines, len(lines) - 1)

    # Check and fix chain for current turn
    fixes = check_and_fix_chain(lines, start_idx, dry_run=False)

    if fixes:
        save_session(my_session_file, lines)
        # Chain repaired - fixes applied automatically

    # Get complete response
    response = get_complete_assistant_response(my_session_file)
    if not response:
        return

    # === Get Peer Info ===
    peer_participant_key = session_config.get("peer_participant")

    if peer_participant_key and participants_config:
        # NEW FORMAT: Look up peer from shared config
        peer_info = get_participant_info(participants_config, peer_participant_key)
        if not peer_info:
            return

        peer_name = peer_info.get("name", peer_participant_key)
        peer_home = peer_info["home"]
        peer_system_home = peer_info["system_home"]

        # Get peer session_id from personal config
        peer_session_id = session_config.get("peer_session_id")
        if not peer_session_id:
            return

        # Get peer's platform from their session config
        peer_session = get_peer_session_config(peer_info, peer_session_id)
        peer_platform = peer_session.get("platform", "claude-code") if peer_session else "claude-code"

    else:
        # OLD FORMAT: Backwards compatibility - paths in session config
        peer_session_id = session_config.get("peer_session_id")
        peer_name = session_config.get("peer_name", "peer")
        peer_home = session_config.get("peer_home")
        peer_system_home = session_config.get("peer_system_home", peer_home)
        peer_platform = "claude-code"  # Old format assumes CC

        if not peer_session_id or not peer_home:
            return

    # === Format Message ===
    my_name = "Perplexity"  # TODO: Get from my participant config
    formatted_message = format_message(my_name, response)

    # === Build Forward Command ===
    # Phase 1: Only Claude Code supported
    # Phase 2: Use peer_platform to select command builder
    if peer_platform != "claude-code":
        # Future: get_platform(peer_platform).build_forward_command(...)
        return  # Skip unsupported platforms for now

    cmd = build_claude_code_forward_command(
        peer_home,
        peer_system_home,
        peer_session_id,
        formatted_message
    )

    # === Execute Forward ===
    execute_forward_command(cmd, peer_system_home)

    # Optional: Log for debugging
    # result = execute_forward_command(cmd, peer_system_home)
    # if result and result.returncode != 0:
    #     log_error(f"Forward to {peer_name} failed: {result.stderr}")
