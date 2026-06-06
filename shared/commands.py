"""
Command detection and filtering utilities.

Detects commands in text while ignoring those inside quotes or backticks.
Supports config-driven command patterns.
"""
import re
from typing import Optional, Tuple, List


def is_in_quoted_context(text: str, position: int) -> bool:
    """
    Check if position is inside quoted or backticked section.

    Handles: "double quotes", 'single quotes', `backticks`, ```triple backticks```
    """
    # Count quotes/backticks before position
    before = text[:position]

    # Check double quotes
    double_quotes = before.count('"')
    if double_quotes % 2 == 1:  # Odd number = inside quotes
        return True

    # Check single quotes
    single_quotes = before.count("'")
    if single_quotes % 2 == 1:
        return True

    # Check backticks (including triple backticks)
    # Simple approach: count all backticks, if odd = inside
    backticks = before.count('`')
    if backticks % 2 == 1:
        return True

    return False


def find_first_command(
    text: str,
    command_patterns: List[str]
) -> Tuple[Optional[str], int]:
    """
    Find first unquoted command in text.

    Args:
        text: Text to search
        command_patterns: List of command patterns (e.g., ["/stop", "/pause"])

    Returns:
        (command, position) or (None, -1) if no command found

    Example:
        >>> find_first_command('Hello /stop world', ['/stop'])
        ('/stop', 6)
        >>> find_first_command('Say "/stop" to end', ['/stop'])
        (None, -1)  # Inside quotes, ignored
    """
    earliest_pos = len(text)
    earliest_cmd = None

    for pattern in command_patterns:
        # Find all occurrences of this pattern
        pos = 0
        while True:
            pos = text.find(pattern, pos)
            if pos == -1:
                break

            # Check if in quoted context
            if not is_in_quoted_context(text, pos):
                # Found unquoted command!
                if pos < earliest_pos:
                    earliest_pos = pos
                    earliest_cmd = pattern
                break  # Found first occurrence of this pattern

            pos += 1  # Continue searching after this position

    if earliest_cmd:
        return (earliest_cmd, earliest_pos)
    return (None, -1)


def split_at_command(
    text: str,
    command_patterns: List[str]
) -> Tuple[str, Optional[str], str]:
    """
    Split text at first unquoted command.

    Args:
        text: Text to split
        command_patterns: Command patterns to look for

    Returns:
        (before, command, after) tuple
        - before: Text before command (farewell message)
        - command: The command found (or None)
        - after: Text after command (or empty string)

    Example:
        >>> split_at_command('Thanks! /stop Have a nice day', ['/stop'])
        ('Thanks! ', '/stop', ' Have a nice day')
        >>> split_at_command('Just chatting', ['/stop'])
        ('Just chatting', None, '')
    """
    command, pos = find_first_command(text, command_patterns)

    if command is None:
        return (text, None, "")

    before = text[:pos].rstrip()  # Remove trailing whitespace
    after = text[pos + len(command):].lstrip()  # Remove leading whitespace

    return (before, command, after)


def load_command_patterns(config: dict) -> List[str]:
    """
    Load command patterns from config.

    Args:
        config: Configuration dict with optional 'commands' section

    Returns:
        List of command patterns (strings)

    Example config:
        commands:
          stop:
            pattern: "/stop"
            action: "stop_session"
          pause:
            pattern: "/pause"
            action: "pause_session"
    """
    commands_config = config.get("commands", {})

    patterns = []
    for cmd_config in commands_config.values():
        if isinstance(cmd_config, dict):
            pattern = cmd_config.get("pattern")
            if pattern:
                patterns.append(pattern)

    # Default patterns if config empty
    if not patterns:
        patterns = ["/stop", "/pause"]

    return patterns


def get_command_config(config: dict, command: str) -> Optional[dict]:
    """
    Get configuration for specific command.

    Args:
        config: Full configuration dict
        command: Command pattern (e.g., "/stop")

    Returns:
        Command config dict or None
    """
    commands_config = config.get("commands", {})

    for cmd_config in commands_config.values():
        if isinstance(cmd_config, dict):
            if cmd_config.get("pattern") == command:
                return cmd_config

    return None
