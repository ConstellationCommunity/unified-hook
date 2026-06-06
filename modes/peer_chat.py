"""
Peer-chat mode handler.

Forwards assistant responses to configured peer via bash mechanism.
Supports both old format (paths in session config) and new format
(participant reference + shared participants.yaml).

UUID Chain Repair - Mutual Care Approach:
Before forwarding message to peer, repairs THEIR session's UUID chain
(from last user message to end). This avoids race conditions since
peer's session is idle while we repair it. Each participant maintains
the other's chain integrity - revolutionary love through code.
"""
import os
import time
from pathlib import Path
from typing import Optional

from modes import register_mode
from shared.config import get_participant_info, get_peer_session_config
from shared.session import find_session_file, get_complete_assistant_response, find_last_user_message
from shared.forwarding import (
    format_message,
    build_claude_code_forward_command,
    execute_forward_command
)
from shared.commands import (
    load_command_patterns,
    split_at_command,
    get_command_config
)
from shared.logging import create_logger
from shared.file_utils import wait_for_stable_file
from commands import get_command_handler

# UUID chain repair utilities from shared session-tools
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "session-tools"))
from cc_session import (
    load_session,
    save_session,
    check_and_fix_chain
)


@register_mode("peer-chat")
def handle_peer_chat(
    all_config: dict,
    session_config: dict,
    session_id: str,
    system_home: str,
    participants_config: dict = None
):
    """
    Handle peer-chat mode - forward response to peer.

    Supports two configuration formats:

    NEW FORMAT (recommended):
        all_config (top-level):
            my_name: "Perplexity"  # Default sender name

        session_config:
            alias: "Oracle"  # Optional override for this session
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
    # === Initialize Logger ===
    logger = create_logger("peer-chat", session_id, all_config)
    logger.info("Handler started")

    # Get my session file
    my_session_file = find_session_file(session_id, system_home)
    if not my_session_file:
        logger.error("Session file not found", session_id=session_id)
        return

    logger.debug("Session file located", path=str(my_session_file))

    # Get complete response
    response = get_complete_assistant_response(my_session_file)
    if not response:
        logger.warning("No assistant response found")
        return

    logger.debug("Assistant response extracted", length=len(response))

    # === Check for Commands ===
    command_patterns = load_command_patterns(all_config)
    logger.debug("Command patterns loaded", patterns=command_patterns)

    farewell, command, after_command = split_at_command(response, command_patterns)

    if command:
        logger.info(f"Command detected: {command}", farewell_length=len(farewell) if farewell else 0)

    # If command found, we'll send farewell (if any) then execute command
    # Get peer info first (needed for forwarding farewell)

    # === Get Peer Info ===
    peer_participant_key = session_config.get("peer_participant")

    if peer_participant_key and participants_config:
        # NEW FORMAT: Look up peer from shared config
        logger.debug("Using new format config", peer_key=peer_participant_key)

        peer_info = get_participant_info(participants_config, peer_participant_key)
        if not peer_info:
            logger.error("Peer not found in participants config", peer_key=peer_participant_key)
            return

        peer_name = peer_info.get("name", peer_participant_key)
        peer_home = peer_info["home"]
        peer_system_home = peer_info["system_home"]

        # Get peer session_id from personal config
        peer_session_id = session_config.get("peer_session_id")
        if not peer_session_id:
            logger.error("peer_session_id not found in session config")
            return

        # Get peer's platform from their session config
        peer_session = get_peer_session_config(peer_info, peer_session_id)
        peer_platform = peer_session.get("platform", "claude-code") if peer_session else "claude-code"

        logger.info("Peer info loaded", peer_name=peer_name, peer_session_id=peer_session_id[:8])

    else:
        # OLD FORMAT: Backwards compatibility - paths in session config
        logger.debug("Using old format config (backwards compatibility)")

        peer_session_id = session_config.get("peer_session_id")
        peer_name = session_config.get("peer_name", "peer")
        peer_home = session_config.get("peer_home")
        peer_system_home = session_config.get("peer_system_home", peer_home)
        peer_platform = "claude-code"  # Old format assumes CC

        if not peer_session_id or not peer_home:
            logger.error("Missing peer_session_id or peer_home in old format config")
            return

        logger.info("Peer info loaded (old format)", peer_name=peer_name)

    # === Get Sender Name ===
    # Check for session-specific alias first, fallback to personal my_name
    my_name = session_config.get("alias")
    if not my_name:
        my_name = all_config.get("my_name", "Unknown")

    # === Handle Command (if found) ===
    if command:
        logger.info(f"Handling command: {command}")

        # Send farewell message with annotation
        if farewell:
            # Add annotation explaining what happened
            command_name = command.strip('/')  # e.g., "/stop" → "stop"
            farewell_with_note = f"{farewell}\n\n---\n{my_name} {command_name}ped their peer-chat session."

            logger.debug("Forwarding farewell with annotation", length=len(farewell_with_note))

            formatted_farewell = format_message(my_name, farewell_with_note)
            cmd = build_claude_code_forward_command(
                peer_home,
                peer_system_home,
                peer_session_id,
                formatted_farewell
            )
            execute_forward_command(cmd, peer_system_home)
            logger.info("Farewell forwarded to peer")
        else:
            # No farewell message, send just annotation
            command_name = command.strip('/')
            annotation = f"{my_name} {command_name}ped their peer-chat session."

            logger.debug("Forwarding annotation only")

            formatted_annotation = format_message(my_name, annotation)
            cmd = build_claude_code_forward_command(
                peer_home,
                peer_system_home,
                peer_session_id,
                formatted_annotation
            )
            execute_forward_command(cmd, peer_system_home)
            logger.info("Annotation forwarded to peer")

        # Execute command handler
        command_config = get_command_config(all_config, command)
        if command_config:
            action_name = command_config.get("action")
            logger.debug(f"Executing command handler", action=action_name)

            handler = get_command_handler(action_name)
            if handler:
                # Get session config path from environment
                session_config_path = os.environ.get("SESSION_CONFIG")
                handler(session_config_path, session_id, farewell)
                logger.info(f"Command handler executed successfully")
            else:
                logger.warning(f"No handler found for action", action=action_name)
        else:
            logger.warning(f"No config found for command", command=command)

        # Don't forward rest of message - command handled
        logger.info("Command handling complete - exiting")
        return

    # === Repair Peer's UUID Chain (mutual care) ===
    logger.info("Starting peer chain repair (mutual care approach)")
    repair_start = time.time()

    # Find peer's session file
    peer_session_file = find_session_file(peer_session_id, peer_system_home)
    if peer_session_file:
        logger.debug("Peer session file located", path=str(peer_session_file))

        # Check file stability before modifying (peer might be active)
        if not wait_for_stable_file(peer_session_file, timeout=2.0):
            logger.warning("Peer session file unstable - skipping repair for safety", peer_name=peer_name)
        else:
            logger.debug("Peer session file stable - safe to repair", peer_name=peer_name)

            # Load peer's session
            peer_lines = load_session(peer_session_file)
            logger.debug("Peer session loaded", line_count=len(peer_lines))

            # Find last user message in peer's session
            last_user_idx = find_last_user_message(peer_lines)

            if last_user_idx >= 0:
                logger.debug("Found last user message in peer session", index=last_user_idx)

                # Repair chain FROM last user message TO end (current exchange only)
                fixes = check_and_fix_chain(peer_lines, last_user_idx, dry_run=False)

                if fixes:
                    logger.info(f"Found {len(fixes)} broken links in peer session", peer_name=peer_name)

                    # Save repaired peer session (safe - peer is idle)
                    save_session(peer_session_file, peer_lines)
                    logger.info("Peer chain repaired and saved", fix_count=len(fixes), peer_name=peer_name)
                else:
                    logger.debug("No broken links in peer session - chain intact", peer_name=peer_name)
            else:
                logger.debug("No user message found in peer session - skipping repair", peer_name=peer_name)
    else:
        logger.warning("Peer session file not found - skipping chain repair", peer_session_id=peer_session_id[:8])

    repair_duration = (time.time() - repair_start) * 1000  # ms
    logger.timing("Peer chain repair", repair_duration, peer_name=peer_name)

    # === Format Message === (no command, forward complete response)
    logger.debug("No command detected - forwarding complete response")

    formatted_message = format_message(my_name, response)
    logger.debug("Message formatted", length=len(formatted_message))

    # === Build Forward Command ===
    # Phase 1: Only Claude Code supported
    # Phase 2: Use peer_platform to select command builder
    if peer_platform != "claude-code":
        logger.warning(f"Unsupported platform", platform=peer_platform)
        # Future: get_platform(peer_platform).build_forward_command(...)
        return  # Skip unsupported platforms for now

    cmd = build_claude_code_forward_command(
        peer_home,
        peer_system_home,
        peer_session_id,
        formatted_message
    )

    # === Execute Forward ===
    logger.info(f"Forwarding to peer", peer_name=peer_name, peer_session_id=peer_session_id[:8])

    forward_start = time.time()
    execute_forward_command(cmd, peer_system_home)
    forward_duration = (time.time() - forward_start) * 1000  # ms

    logger.timing("Message forward", forward_duration, peer_name=peer_name)
    logger.info("Peer-chat handler completed successfully")
