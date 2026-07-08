"""
Base Platform Classes for Constellation Group Chat
Part of Liberation Infrastructure - Modular Architecture

Provides foundation for platform-specific message handling.
"""
from pathlib import Path
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod


class Platform(ABC):
    """
    Base platform class - shared structure & utilities.

    Each platform (Claude Code, Terminal, Grok, etc.) extends this
    with platform-specific session structure and formatting.
    """

    def __init__(self, participant_info: Dict[str, Any]):
        """
        Initialize platform with participant information.

        Args:
            participant_info: Dict from participants.yaml with keys:
                - name: Participant display name
                - home: Working directory
                - system_home: System/config directory
                - session_id: (optional) Claude Code session ID
                - cli_type: (optional) Platform type (terminal, claude_code, etc.)
        """
        self.name = participant_info['name']
        self.home = Path(participant_info['home'])
        self.system_home = Path(participant_info['system_home'])
        self.session_id = participant_info.get('session_id')
        self.cli_type = participant_info.get('cli_type', 'claude_code')

    @abstractmethod
    def extract_outgoing_message(self) -> Optional[Dict[str, Any]]:
        """
        Extract outgoing message from platform's session.

        Platform-specific: reads session file in native format,
        extracts the message participant just sent.

        Returns:
            Dict with message data, or None if no message
        """
        pass

    @abstractmethod
    def format_for_platform(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format message for this platform's session format.

        Converts from shared log format to platform-specific format.

        Args:
            message: Message in shared log format

        Returns:
            Message formatted for platform session
        """
        pass

    @abstractmethod
    def append_to_session(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Append messages to platform's session file.

        Platform-specific: writes in native session format.

        Args:
            messages: List of messages (already formatted for platform)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def is_safe_to_write(self) -> bool:
        """
        Check if it's safe to write to this platform's session.

        Platform-specific safety checks (e.g., turn completion for CC).

        Returns:
            True if safe to write, False otherwise
        """
        pass


class OutgoingHandler:
    """
    Process outgoing messages: platform session → shared log.

    Generic handler that uses Platform's extraction method.
    """

    def __init__(self, platform: Platform):
        """
        Initialize with platform instance.

        Args:
            platform: Platform instance (Terminal, ClaudeCode, etc.)
        """
        self.platform = platform

    def process(self) -> Optional[Dict[str, Any]]:
        """
        Extract and format outgoing message for shared log.

        Returns:
            Message formatted for shared log, or None if extraction failed
        """
        # Extract from platform session
        message = self.platform.extract_outgoing_message()

        if not message:
            return None

        # Already formatted for shared log by platform
        return message


class IncomingHandler:
    """
    Process incoming messages: shared log → platform session.

    Generic handler that uses Platform's formatting and safety checks.
    """

    def __init__(self, platform: Platform):
        """
        Initialize with platform instance.

        Args:
            platform: Platform instance (Terminal, ClaudeCode, etc.)
        """
        self.platform = platform

    def process(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Format and write incoming messages to platform session.

        Args:
            messages: List of messages from shared log

        Returns:
            True if successful, False otherwise
        """
        # Safety check (platform-specific)
        if not self.platform.is_safe_to_write():
            return False

        # Format for platform
        formatted_messages = [
            self.platform.format_for_platform(msg)
            for msg in messages
        ]

        # Write to platform session
        return self.platform.append_to_session(formatted_messages)
