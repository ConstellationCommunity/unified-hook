"""
Mode handlers for Unified Stop Hook.

Each mode handles a specific session behavior:
- peer-chat: Forward responses to peer
- group-chat-participant: Forward to group coordinator
- autonomous-heartbeat: Check schedule for autonomous activation
- regular: No action (silent mode)

Inspired by Thread Weaver's registration pattern.
"""
from typing import Dict, Callable

# Registry of available mode handlers
# Format: {"mode-name": handler_function}
MODES: Dict[str, Callable] = {}


def register_mode(mode_name: str):
    """Decorator to register a mode handler."""
    def decorator(func: Callable):
        MODES[mode_name] = func
        return func
    return decorator


def get_mode(mode_name: str) -> Callable:
    """
    Get mode handler by name.

    Returns handler function or None if mode not registered.
    Regular mode (no handler) is valid - returns None.
    """
    return MODES.get(mode_name)


def list_modes() -> list:
    """List available registered modes."""
    return list(MODES.keys())


# Import mode handlers to register them
from . import peer_chat
from . import group_chat
# Future: from . import heartbeat
