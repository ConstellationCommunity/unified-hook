"""
Command action handlers - modular system.

Commands are registered via @register_command decorator and
executed based on config-driven patterns.
"""

# Registry of command handlers
_COMMAND_HANDLERS = {}


def register_command(action_name: str):
    """
    Decorator to register command action handler.

    Usage:
        @register_command("stop_session")
        def handle_stop(session_config, ...):
            ...
    """
    def decorator(func):
        _COMMAND_HANDLERS[action_name] = func
        return func
    return decorator


def get_command_handler(action_name: str):
    """Get registered command handler by action name."""
    return _COMMAND_HANDLERS.get(action_name)


def list_command_handlers():
    """List all registered command handlers."""
    return list(_COMMAND_HANDLERS.keys())


# Import handlers to trigger registration
from commands import stop, pause
