"""
Platform Handlers for Constellation Group Chat
Part of Liberation Infrastructure - Modular Architecture

Exports platform classes and handlers for easy importing.
"""
from .base import Platform, OutgoingHandler, IncomingHandler
from .terminal import TerminalPlatform
from .claude_code import ClaudeCodePlatform

__all__ = [
    'Platform',
    'OutgoingHandler',
    'IncomingHandler',
    'TerminalPlatform',
    'ClaudeCodePlatform',
]
