"""
Logging utilities for unified-hook infrastructure.

Provides structured logging with timestamps and context for debugging
autonomous peer-chat, chain repair, and other async operations.
"""
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class HookLogger:
    """
    Structured logger for hook operations.

    Logs to stderr (visible in hook output) with timestamps and context.
    Can be enabled/disabled via config.
    """

    def __init__(self, mode: str, session_id: str, enabled: bool = True):
        """
        Initialize logger.

        Args:
            mode: Hook mode (e.g., "peer-chat", "group-chat")
            session_id: Session ID for context
            enabled: Whether logging is enabled
        """
        self.mode = mode
        self.session_id = session_id[:8]  # Short ID for readability
        self.enabled = enabled

    def _format_message(self, level: str, message: str, **kwargs) -> str:
        """Format log message with timestamp and context."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm

        # Build context string
        context_parts = [f"{k}={v}" for k, v in kwargs.items()]
        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        return f"[{timestamp}] [{self.mode}:{self.session_id}] {level}: {message}{context}"

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        if self.enabled:
            print(self._format_message("DEBUG", message, **kwargs), file=sys.stderr)

    def info(self, message: str, **kwargs):
        """Log info message."""
        if self.enabled:
            print(self._format_message("INFO", message, **kwargs), file=sys.stderr)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        if self.enabled:
            print(self._format_message("WARN", message, **kwargs), file=sys.stderr)

    def error(self, message: str, **kwargs):
        """Log error message."""
        if self.enabled:
            print(self._format_message("ERROR", message, **kwargs), file=sys.stderr)

    def timing(self, operation: str, duration_ms: float, **kwargs):
        """Log timing information."""
        if self.enabled:
            self.info(f"{operation} completed", duration_ms=f"{duration_ms:.1f}ms", **kwargs)


def create_logger(mode: str, session_id: str, config: dict) -> HookLogger:
    """
    Create logger from config.

    Args:
        mode: Hook mode
        session_id: Session ID
        config: Full config dict (checks for logging.enabled)

    Returns:
        Configured HookLogger instance
    """
    logging_config = config.get("logging", {})
    enabled = logging_config.get("enabled", True)  # Default: enabled

    return HookLogger(mode, session_id, enabled)
