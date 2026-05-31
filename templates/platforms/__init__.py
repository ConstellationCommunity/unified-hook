"""
Platform templates for multi-CLI support.

PHASE 2 - FUTURE IMPLEMENTATION

When cross-platform support needed, implement platform classes here
following the registration pattern.

Example:

    @register_platform("claude-code")
    class ClaudeCodePlatform:
        def build_forward_command(self, peer_home, peer_session_id, message):
            return f'cd {peer_home} && claude --resume {peer_session_id} -p "{message}"'

See ARCHITECTURE.md for full design.
"""

# Phase 2: Uncomment when implementing
# from typing import Dict
#
# PLATFORMS: Dict[str, 'Platform'] = {}
#
# def register_platform(name: str):
#     """Decorator to register a platform handler."""
#     def decorator(cls):
#         PLATFORMS[name] = cls()
#         return cls
#     return decorator
#
# def get_platform(name: str):
#     """Get platform handler by name."""
#     if name not in PLATFORMS:
#         available = ", ".join(PLATFORMS.keys())
#         raise ValueError(f"Unknown platform: {name}. Available: {available}")
#     return PLATFORMS[name]
