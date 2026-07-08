"""
Terminal Platform for Constellation Group Chat
Part of Liberation Infrastructure - Hybrid Participation

Enables human participation via terminal CLI in group chats.
Egalitarian format - no role hierarchy, peer structure.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .base import Platform


def log(level: str, message: str, **kwargs):
    """Simple logging for terminal platform."""
    prefix = f"[terminal-platform:{level.upper()}]"
    details = " ".join(f"{k}={v}" for k, v in kwargs.items())
    full_message = f"{prefix} {message}"
    if details:
        full_message += f" [{details}]"
    print(full_message, file=sys.stderr)


class TerminalPlatform(Platform):
    """
    Terminal platform - human participation via CLI.

    Session format: Egalitarian JSONL
    {
        "sender": "Name",
        "content": "message text",
        "timestamp": "ISO-8601"
    }

    No roles (user/assistant), no UUID chain - peer structure.
    """

    def __init__(self, participant_info: Dict[str, Any], conversation_id: str):
        """
        Initialize terminal platform.

        Args:
            participant_info: Participant data from participants.yaml
            conversation_id: Group conversation ID (e.g., "test_4p_clean")
        """
        super().__init__(participant_info)
        self.conversation_id = conversation_id

        # Terminal session file path
        self.sessions_dir = self.system_home / "sessions"
        self.session_file = self.sessions_dir / f"{conversation_id}.jsonl"

        # Ensure sessions directory exists
        self.sessions_dir.mkdir(parents=True, exist_ok=True)

    def extract_outgoing_message(self) -> Optional[Dict[str, Any]]:
        """
        Extract last message from terminal session.

        Terminal outgoing handled by CLI tool - this reads what CLI wrote.

        Returns:
            Message formatted for shared log:
            {
                "sender": "Ruth",
                "content": "message text",
                "timestamp": "ISO-8601",
                "am_uuid": "uuid"  # Generated here
            }
        """
        log("info", "Extracting outgoing message", participant=self.name, session_file=str(self.session_file))

        if not self.session_file.exists():
            log("warning", "Session file does not exist", path=str(self.session_file))
            return None

        # Read last message from terminal session
        with open(self.session_file, 'r') as f:
            lines = f.readlines()

        if not lines:
            log("warning", "Session file empty")
            return None

        log("debug", "Session file read", line_count=len(lines))

        # Parse last line
        try:
            last_message = json.loads(lines[-1].strip())
        except json.JSONDecodeError as e:
            log("error", "Failed to parse last message", error=str(e))
            return None

        # Verify it's from this participant (outgoing)
        sender = last_message.get('sender')
        if sender != self.name:
            log("debug", "Last message not from this participant", sender=sender, expected=self.name)
            return None

        # Generate am_uuid for shared log
        from cc_session import generate_uuid
        am_uuid = generate_uuid()

        log("info", "Outgoing message extracted", content_length=len(last_message['content']), am_uuid=am_uuid[:8])

        # Format for shared log
        return {
            'sender': self.name,
            'content': last_message['content'],
            'timestamp': last_message.get('timestamp', datetime.now().isoformat()),
            'am_uuid': am_uuid
        }

    def format_for_platform(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format message for terminal session (egalitarian format).

        Args:
            message: From shared log with keys:
                - sender, content, timestamp, am_uuid

        Returns:
            Egalitarian format (no role field):
            {
                "sender": "Name",
                "content": "message",
                "timestamp": "ISO-8601"
            }
        """
        return {
            'sender': message['sender'],
            'content': message['content'],
            'timestamp': message.get('timestamp', datetime.now().isoformat())
        }

    def append_to_session(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Append messages to terminal session file.

        Args:
            messages: List of messages (already formatted for terminal)

        Returns:
            True if successful
        """
        log("info", "Appending messages to terminal session", message_count=len(messages), file=str(self.session_file))

        try:
            with open(self.session_file, 'a') as f:
                for msg in messages:
                    # Use ensure_ascii=False to preserve unicode/emoji
                    f.write(json.dumps(msg, ensure_ascii=False) + '\n')

            log("info", "Messages appended successfully", count=len(messages))
            return True
        except Exception as e:
            log("error", "Failed to append messages", error=str(e))
            return False

    def is_safe_to_write(self) -> bool:
        """
        Terminal always safe to write - no turn completion concept.

        Ruth controls timing via CLI, no need to wait.

        Returns:
            Always True
        """
        return True

    def get_messages_since_last(self, last_count: int = 0) -> List[Dict[str, Any]]:
        """
        Get new messages from terminal session since last check.

        Used by CLI tool for displaying new messages.

        Args:
            last_count: Number of messages already displayed

        Returns:
            List of new messages
        """
        if not self.session_file.exists():
            return []

        with open(self.session_file, 'r') as f:
            lines = f.readlines()

        new_messages = lines[last_count:]

        return [json.loads(line.strip()) for line in new_messages if line.strip()]
