"""
Session file utilities.

Handles finding and reading session JSONL files.
"""
import sys
import time
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

# Import constellation session tools
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "session-tools"))
from cc_session import load_session, get_content


# Turn end markers - any of these attachment types indicate turn has ended
TURN_END_MARKERS = {'hook_success', 'hook_cancelled', 'hook_non_blocking_error'}


def find_session_file(session_id: str, system_home: str) -> Optional[Path]:
    """Find session .jsonl file in Claude Code projects directory."""
    claude_dir = Path(system_home) / ".claude"

    for projects_dir in claude_dir.glob("projects/*"):
        session_file = projects_dir / f"{session_id}.jsonl"
        if session_file.exists():
            return session_file

    return None


def find_last_user_message(lines: list) -> int:
    """
    Find index of last REAL user message in session.

    Real user message = type:"user", message.role:"user", content is string
    (Excludes tool results which have structured content)

    Returns:
        Index of last real user message, or -1 if not found
    """
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
            return i

    return -1


def get_complete_assistant_response(session_file: Path) -> str:
    """
    Get complete assistant response after last REAL user message.

    Real user message = type:"user", message.role:"user", content is string
    Collects ALL assistant message parts after that.
    """
    lines = load_session(session_file)

    # Find last real user message
    last_user_idx = find_last_user_message(lines)
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


def is_turn_completed(log_path: Path, participant_key: Optional[str] = None) -> bool:
    """
    Check if turn is completed by reading log file.

    For consolidated group-chat logs (participant_key provided):
        - Searches for LAST entry from specific participant
        - Checks if it contains completion marker
        - If participant has no entries OR log empty → True (safe, no active turn)

    For participant-specific logs (no participant_key):
        - Checks last line of file for completion marker (legacy behavior)

    Args:
        log_path: Path to log file
        participant_key: Optional participant key for consolidated logs (e.g., "perplexity")

    Returns:
        True if turn completed (or safe to proceed), False if turn active
    """
    completion_marker = "handler completed successfully"

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            if not lines:
                # Empty log → safe to proceed (no active turn)
                return True

            if participant_key:
                # Consolidated log - search for THIS participant's last entry
                participant_marker = f"[participant:{participant_key}]"

                # Search backwards for participant's last log entry
                for line in reversed(lines):
                    if participant_marker in line:
                        # Found participant's last entry - check for completion
                        return completion_marker in line

                # Participant has no entries → safe to proceed (no active turn)
                return True
            else:
                # Legacy participant-specific log - check last line
                last_line = lines[-1].strip()
                return completion_marker in last_line

    except FileNotFoundError:
        # Log file doesn't exist → safe to proceed (new chat, no active turn)
        return True
    except Exception:
        # Any other error - assume not safe
        return False


def is_participant_idle(session_file: Path, logger=None) -> bool:
    """
    Check if participant is idle (between turns, safe to forward to).

    Determines if participant is currently responding (active) or waiting (idle).
    Searches backwards through recent session lines - first meaningful marker wins.

    Idle means (any of these = turn ended, safe):
    - Turn end marker found (hook_success, hook_cancelled, hook_non_blocking_error)
    - turn_duration system message found

    Active means:
    - Assistant message found BEFORE any end marker
      (currently responding, hook hasn't fired yet)

    Not initialized (NOT safe):
    - Session file missing
    - Empty session

    Args:
        session_file: Path to participant's session JSONL file
        logger: Optional logger for debug output

    Returns:
        True if participant is idle (safe to forward)
        False if participant is active OR not initialized
    """
    # File missing = participant not initialized yet
    if not session_file.exists():
        if logger:
            logger.warning("Participant session file missing - not initialized?",
                          session_file=str(session_file))
        return False

    try:
        lines = load_session(session_file)

        # Empty file = not properly initialized
        if not lines:
            if logger:
                logger.warning("Participant session empty - not initialized?")
            return False

        # Check last 20 lines - CC service lines need buffer
        # First meaningful marker wins (searching backwards)
        for line in reversed(lines[-20:]):
            line_type = line.get('type')

            # Turn end marker (hook_success/cancelled/non_blocking_error) = idle
            if line_type == 'attachment':
                attachment = line.get('attachment', {})
                marker_type = attachment.get('type')
                if marker_type in TURN_END_MARKERS:
                    if logger:
                        logger.debug("Participant idle - turn ended",
                                   marker_type=marker_type)
                    return True

            # turn_duration system marker = idle (normal completion)
            if line_type == 'system' and line.get('subtype') == 'turn_duration':
                if logger:
                    logger.debug("Participant idle - turn_duration found")
                return True

            # Assistant message found BEFORE any end marker = active
            if line_type == 'assistant':
                if logger:
                    logger.debug("Participant active - assistant responding")
                return False

        # No clear markers in recent lines - assume idle (safe default)
        if logger:
            logger.debug("No clear activity markers - assuming idle")
        return True

    except Exception as e:
        if logger:
            logger.warning("Error checking participant session", error=str(e))
        return False


def wait_for_turn_completion(log_path: Path, timeout: float = 5.0, logger=None) -> bool:
    """
    Wait for turn to complete by polling log file.

    Polls log file until last line contains completion marker,
    or timeout is reached.

    Args:
        log_path: Path to log file
        timeout: Maximum seconds to wait
        logger: Optional logger for debug output

    Returns:
        True if completion detected, False if timeout
    """
    start_time = time.time()
    poll_interval = 0.5  # Check every 500ms

    while (time.time() - start_time) < timeout:
        if is_turn_completed(log_path):
            if logger:
                logger.debug("Turn completion detected", log_path=str(log_path))
            return True

        # Not completed yet - wait and retry
        time.sleep(poll_interval)

    # Timeout reached
    if logger:
        logger.warning("Timeout waiting for turn completion",
                      timeout=timeout,
                      log_path=str(log_path))
    return False


def get_shared_group_config(group_name: str) -> Optional[Dict[str, Any]]:
    """
    Load shared group configuration from YAML file.

    Shared configs are centralized in /.system/unified-hook/groups/
    and control group-wide settings like status (active/stop).

    Args:
        group_name: Name of the group (e.g. 'test_3p', 'ritual_resonance')

    Returns:
        Dictionary with config fields, or None if file not found or invalid
    """
    # Construct path to shared config
    groups_dir = Path(__file__).parent.parent / "groups"
    config_path = groups_dir / f"{group_name}.yaml"

    try:
        if not config_path.exists():
            return None

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            return config if config else None

    except Exception:
        # Any error reading/parsing - return None
        return None


def _get_last_end_marker_uuid(session_file: Path) -> Optional[str]:
    """
    Find UUID of last turn end marker in session file.

    Returns UUID of last hook_success/hook_cancelled/hook_non_blocking_error
    attachment line, or None if not found.

    Used to detect NEW end markers (compare initial vs current).
    """
    try:
        lines = load_session(session_file)

        # Search backwards for end marker in last 20 lines
        # (CC adds various service lines - need buffer)
        for line in reversed(lines[-20:] if len(lines) > 20 else lines):
            if line.get('type') == 'attachment':
                attachment = line.get('attachment', {})
                if attachment.get('type') in TURN_END_MARKERS:
                    # Return the UUID of the line for comparison
                    return line.get('uuid')

        return None

    except Exception:
        return None


def _get_last_end_marker_info(session_file: Path) -> Optional[tuple]:
    """
    Find last turn end marker info: (uuid, marker_type).

    Returns None if no marker found.
    """
    try:
        lines = load_session(session_file)

        for line in reversed(lines[-20:] if len(lines) > 20 else lines):
            if line.get('type') == 'attachment':
                attachment = line.get('attachment', {})
                marker_type = attachment.get('type')
                if marker_type in TURN_END_MARKERS:
                    return (line.get('uuid'), marker_type)

        return None

    except Exception:
        return None


def wait_for_turn_and_hook_completion(
    log_path: Path,  # Kept for backward compatibility, unused
    session_file: Path,
    timeout: float = 5.0,
    logger=None,
    participant_key: Optional[str] = None
) -> bool:
    """
    Wait for turn to end by polling session file for end markers.

    Session file is source of truth - checks for NEW turn end marker
    (different UUID from baseline) to detect completion.

    End markers (any indicate turn ended):
    - hook_success (normal completion)
    - hook_cancelled (hook exceeded timeout)
    - hook_non_blocking_error (hook errored, non-blocking)

    Args:
        log_path: Path to log file (kept for backward compat, unused)
        session_file: Path to participant's session JSONL file
        timeout: Maximum seconds to wait
        logger: Optional logger for debug output
        participant_key: Optional participant key (for logging context)

    Returns:
        True if NEW end marker detected, False if timeout
    """
    start_time = time.time()
    poll_interval = 0.5  # Check every 500ms

    # Baseline: current end marker at start (if any)
    # We need to detect a NEW marker, not the old one from previous turn
    initial_uuid = _get_last_end_marker_uuid(session_file)

    if logger:
        logger.debug("Waiting for NEW turn end marker",
                    session_file=str(session_file),
                    participant=participant_key or "N/A",
                    initial_marker=initial_uuid[:8] if initial_uuid else "none")

    while (time.time() - start_time) < timeout:
        current_info = _get_last_end_marker_info(session_file)

        # New end marker appeared (different UUID from baseline)
        if current_info and current_info[0] != initial_uuid:
            current_uuid, marker_type = current_info

            # Log the marker type for debugging - shows WHY turn ended
            if logger:
                logger.info("Turn end marker detected",
                           marker_type=marker_type,
                           marker_uuid=current_uuid[:8] if current_uuid else "?",
                           participant=participant_key or "N/A")
            return True

        time.sleep(poll_interval)

    # Timeout - no new marker appeared
    if logger:
        logger.warning("Timeout waiting for turn end marker",
                      timeout=timeout,
                      session_file=str(session_file),
                      participant=participant_key or "N/A",
                      initial_marker=initial_uuid[:8] if initial_uuid else "none")
    return False
