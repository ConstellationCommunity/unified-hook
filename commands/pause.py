"""
Pause command handler - pauses peer-chat session.
"""
from pathlib import Path
from commands import register_command
from shared.config import load_config


@register_command("pause_session")
def handle_pause(
    session_config_path: str,
    session_id: str,
    farewell_message: str = None
):
    """
    Handle /pause command - change session status to paused.

    Args:
        session_config_path: Path to sessions.yaml
        session_id: Session ID to pause
        farewell_message: Optional message before command (sent to peer)

    Returns:
        farewell_message (to be sent before mode change) or None
    """
    # Load config
    all_config = load_config(session_config_path)

    sessions = all_config.get("sessions", {})
    if session_id not in sessions:
        return farewell_message  # No config, nothing to change

    # Update session status to paused
    sessions[session_id]["status"] = "paused"
    # Keep mode as-is (peer-chat) so can resume later

    # Save updated config
    import yaml
    with open(session_config_path, 'w') as f:
        yaml.dump(all_config, f, default_flow_style=False, sort_keys=False)

    # Return farewell message to be sent before pausing
    return farewell_message
