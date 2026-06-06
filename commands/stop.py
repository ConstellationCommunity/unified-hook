"""
Stop command handler - ends peer-chat session.
"""
from pathlib import Path
from commands import register_command
from shared.config import load_config


@register_command("stop_session")
def handle_stop(
    session_config_path: str,
    session_id: str,
    farewell_message: str = None
):
    """
    Handle /stop command - change session mode to regular.

    Args:
        session_config_path: Path to sessions.yaml
        session_id: Session ID to stop
        farewell_message: Optional message before command (sent to peer)

    Returns:
        farewell_message (to be sent before mode change) or None
    """
    # Load config
    all_config = load_config(session_config_path)

    sessions = all_config.get("sessions", {})
    if session_id not in sessions:
        return farewell_message  # No config, nothing to change

    # Update session mode to regular
    sessions[session_id]["mode"] = "regular"
    sessions[session_id]["status"] = "active"  # Keep active, just change mode

    # Save updated config
    import yaml
    with open(session_config_path, 'w') as f:
        yaml.dump(all_config, f, default_flow_style=False, sort_keys=False)

    # Return farewell message to be sent before stopping
    return farewell_message
