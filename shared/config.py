"""
Configuration loading utilities.

Handles loading and accessing session and participant configurations.
"""
import os
from typing import Optional
import yaml


def load_config(config_path: str) -> dict:
    """Load YAML configuration file."""
    if not config_path or not os.path.exists(config_path):
        return {}

    with open(config_path, 'r') as f:
        return yaml.safe_load(f) or {}


def get_session_config(all_config: dict, session_id: str) -> Optional[dict]:
    """Get configuration for specific session."""
    sessions = all_config.get("sessions", {})
    return sessions.get(session_id)


def get_participant_info(participants_config: dict, participant_key: str) -> Optional[dict]:
    """Get participant info from shared configuration."""
    return participants_config.get("participants", {}).get(participant_key)


def get_peer_session_config(peer_participant: dict, peer_session_id: str) -> Optional[dict]:
    """
    Get peer's session configuration.

    Reads peer's sessions.yaml to get their session-specific settings
    (like platform).
    """
    # Get peer's session config path
    peer_system_home = peer_participant["system_home"]

    # Try explicit path first, fall back to convention
    peer_config_path = peer_participant.get(
        "session_config",
        f"{peer_system_home}/.config/sessions.yaml"
    )

    # Load peer's sessions config
    peer_sessions = load_config(peer_config_path)

    # Get specific session
    return get_session_config(peer_sessions, peer_session_id)
