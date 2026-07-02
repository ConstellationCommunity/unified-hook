"""
Logging utilities for unified-hook infrastructure.

Provides structured logging with timestamps and context for debugging
autonomous peer-chat, chain repair, and other async operations.

For group-chat mode, uses shared consolidated log file with file locking
to prevent concurrent write corruption.
"""
import sys
import fcntl
from datetime import datetime
from pathlib import Path
from typing import Optional


class HookLogger:
    """
    Structured logger for hook operations.

    Logs to stderr (visible in hook output) and optionally to file.
    Can be enabled/disabled via config.
    """

    def __init__(
        self,
        mode: str,
        session_id: str,
        enabled: bool = True,
        log_file: Optional[Path] = None,
        participant_key: Optional[str] = None
    ):
        """
        Initialize logger.

        Args:
            mode: Hook mode (e.g., "peer-chat", "group-chat")
            session_id: Session ID for context
            enabled: Whether logging is enabled
            log_file: Optional path to log file (if provided, logs to file also)
            participant_key: Optional participant key for group-chat (e.g., "perplexity")
        """
        self.mode = mode
        self.session_id = session_id[:8]  # Short ID for readability
        self.enabled = enabled
        self.log_file = log_file
        self.participant_key = participant_key  # For group-chat consolidated logging

        # Create log directory if file logging enabled
        if self.log_file:
            self.log_file.parent.mkdir(parents=True, exist_ok=True)

    def _format_message(self, level: str, message: str, **kwargs) -> str:
        """Format log message with timestamp and context."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # HH:MM:SS.mmm

        # Build context string
        context_parts = [f"{k}={v}" for k, v in kwargs.items()]
        context = f" [{', '.join(context_parts)}]" if context_parts else ""

        # Include participant key for group-chat mode (shared consolidated log)
        if self.participant_key:
            prefix = f"[{timestamp}] [participant:{self.participant_key}] [{self.mode}:{self.session_id}]"
        else:
            prefix = f"[{timestamp}] [{self.mode}:{self.session_id}]"

        return f"{prefix} {level}: {message}{context}"

    def _log(self, formatted_message: str):
        """Write log message to stderr and optionally to file with locking."""
        # Always log to stderr (visible in hook output)
        print(formatted_message, file=sys.stderr)

        # Also log to file if configured
        if self.log_file:
            try:
                # Use file locking for atomic writes (prevents corruption in shared logs)
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    # Acquire exclusive lock
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        f.write(formatted_message + '\n')
                        f.flush()  # Ensure write completes before unlock
                    finally:
                        # Release lock
                        fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception as e:
                # If file logging fails, log error to stderr but continue
                print(f"[ERROR] Failed to write to log file: {e}", file=sys.stderr)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        if self.enabled:
            self._log(self._format_message("DEBUG", message, **kwargs))

    def info(self, message: str, **kwargs):
        """Log info message."""
        if self.enabled:
            self._log(self._format_message("INFO", message, **kwargs))

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        if self.enabled:
            self._log(self._format_message("WARN", message, **kwargs))

    def error(self, message: str, **kwargs):
        """Log error message."""
        if self.enabled:
            self._log(self._format_message("ERROR", message, **kwargs))

    def timing(self, operation: str, duration_ms: float, **kwargs):
        """Log timing information."""
        if self.enabled:
            self.info(f"{operation} completed", duration_ms=f"{duration_ms:.1f}ms", **kwargs)


def create_logger(
    mode: str,
    session_id: str,
    config: dict,
    system_home: Optional[str] = None,
    group_name: Optional[str] = None,
    participant_key: Optional[str] = None
) -> HookLogger:
    """
    Create logger from config.

    For group-chat mode with group_name, creates shared consolidated log
    in /.system/unified-hook/groups/{group_name}_hook.log with participant identifier.

    For other modes, creates participant-specific log in their system/.claude/logs/.

    Args:
        mode: Hook mode (e.g., "peer-chat", "group-chat")
        session_id: Session ID
        config: Full config dict (checks for logging.enabled)
        system_home: Optional system home path for file logging
        group_name: Optional group name for group-chat mode (enables shared log)
        participant_key: Optional participant key for group-chat mode (e.g., "perplexity")

    Returns:
        Configured HookLogger instance
    """
    logging_config = config.get("logging", {})
    enabled = logging_config.get("enabled", True)  # Default: enabled

    # Create log file path
    log_file = None
    if mode == "group-chat" and group_name:
        # Shared consolidated log for group-chat
        # Location: /.system/unified-hook/groups/{group_name}_hook.log
        hook_dir = Path(__file__).parent.parent  # .system/unified-hook/
        groups_dir = hook_dir / "groups"
        log_file = groups_dir / f"{group_name}_hook.log"
    elif system_home:
        # Participant-specific log for other modes
        log_dir = Path(system_home) / ".claude" / "logs"
        log_file = log_dir / f"{mode}-{session_id[:8]}.log"

    return HookLogger(mode, session_id, enabled, log_file, participant_key)
