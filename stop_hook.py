#!/usr/bin/env python3
"""
Unified Stop Hook - handles all session modes via config

Part of Constellation Autonomy Infrastructure

ARCHITECTURE:
    Config-driven routing to pluggable mode handlers.
    New modes can be added by creating a handler in modes/
    and registering it with @register_mode decorator.

MODES:
    - regular: No action (silent mode)
    - peer-chat: Forward responses to peer
    - group-chat-participant: Forward to group coordinator
    - autonomous-heartbeat: Check schedule for activation

See ARCHITECTURE.md for design details and future vision.
"""
import os
import sys

from shared.config import load_config, get_session_config
from modes import get_mode


def main():
    """Main hook entry point - slim router."""

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
        # No config for this session - regular mode (silent)
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

    # Get mode and handler
    mode = session_config.get("mode", "regular")
    handler = get_mode(mode)

    if handler:
        # Execute mode handler
        handler(session_config, session_id, system_home, participants_config)
    # else: regular mode - no action (silent)

    sys.exit(0)


if __name__ == "__main__":
    main()
