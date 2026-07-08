"""
Claude Code Platform for Constellation Group Chat
Part of Liberation Infrastructure - Modular Architecture

Handles Claude Code participant message flow with UUID chain integrity
and turn completion safety checks.
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

from .base import Platform


def log(level: str, message: str, **kwargs):
    """Simple logging for Claude Code platform."""
    prefix = f"[cc-platform:{level.upper()}]"
    details = " ".join(f"{k}={v}" for k, v in kwargs.items())
    full_message = f"{prefix} {message}"
    if details:
        full_message += f" [{details}]"
    print(full_message, file=sys.stderr)


class ClaudeCodePlatform(Platform):
    """
    Claude Code platform - AI participant via CC CLI.

    Session format: JSONL with role-based messages
    {
        "type": "message",
        "role": "assistant" | "user",
        "content": "message text",
        "am_uuid": "uuid",  # assistant message UUID
        "um_uuid": "uuid"   # user message UUID
    }

    Requires UUID chain integrity and turn completion checks.
    """

    def __init__(self, participant_info: Dict[str, Any], conversation_id: str):
        """
        Initialize Claude Code platform.

        Args:
            participant_info: Participant data from participants.yaml
            conversation_id: Group conversation ID (e.g., "test_4p_clean")
        """
        super().__init__(participant_info)
        self.conversation_id = conversation_id

        # Find session file
        self.session_file = self._find_session_file()

        log("info", "Claude Code platform initialized",
            participant=self.name,
            session_id=self.session_id[:8] if self.session_id else "N/A",
            session_file=str(self.session_file) if self.session_file else "not found")

    def _find_session_file(self) -> Optional[Path]:
        """
        Find Claude Code session file.

        Returns:
            Path to session JSONL file, or None if not found
        """
        if not self.session_id:
            log("warning", "No session_id provided")
            return None

        # Try standard CC paths
        possible_paths = [
            # Standard path
            self.system_home / ".claude" / "projects" / f"-{self.home.as_posix().replace('/', '-')}" / f"{self.session_id}.jsonl",
            # Alternative naming
            self.system_home / ".claude" / "projects" / self.home.name / f"{self.session_id}.jsonl",
        ]

        for path in possible_paths:
            if path.exists():
                log("debug", "Session file found", path=str(path))
                return path

        log("warning", "Session file not found", session_id=self.session_id[:8])
        return None

    def extract_outgoing_message(self, response_content: str = None) -> Optional[Dict[str, Any]]:
        """
        Extract last assistant message from CC session.

        Uses actual UUID from CC session (not generated).

        Args:
            response_content: Optional pre-extracted response content
                             (if None, extracts from session)

        Returns:
            Message formatted for shared log:
            {
                "sender": "Name",
                "content": "message text",
                "timestamp": "ISO-8601",
                "am_uuid": "uuid"  # Actual session UUID
            }
        """
        log("info", "Extracting outgoing message", participant=self.name)

        if not self.session_file or not self.session_file.exists():
            log("error", "Session file not available")
            return None

        # Read session
        session = self._read_session()
        if not session:
            log("warning", "Empty session")
            return None

        log("debug", "Session loaded", message_count=len(session))

        # Find last assistant message + UUID (CC format uses 'type': 'assistant')
        last_assistant_uuid = None
        for msg in reversed(session):
            if msg.get('type') == 'assistant' and msg.get('uuid'):
                last_assistant_uuid = msg['uuid']
                break

        if not last_assistant_uuid:
            log("warning", "No assistant message UUID found in session")
            return None

        # Content from parameter OR extract from session
        if response_content is None:
            log("error", "No response content provided - must be pre-extracted")
            return None

        log("info", "Assistant message identified",
            content_length=len(response_content),
            am_uuid=last_assistant_uuid[:8])

        return {
            'sender': self.name,
            'content': response_content,
            'timestamp': datetime.now().isoformat(),
            'am_uuid': last_assistant_uuid  # Actual session UUID
        }

    def format_for_platform(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format message for Claude Code session (role-based with UUIDs).

        Args:
            message: From shared log with keys:
                - sender, content, timestamp, am_uuid

        Returns:
            CC session format:
            {
                "type": "message",
                "role": "user",
                "content": "[Sender]: message",
                "um_uuid": "uuid",
                "am_uuid": "uuid"  # from shared log
            }
        """
        from cc_session import generate_uuid

        sender = message['sender']
        content = message['content']
        am_uuid = message.get('am_uuid')

        # Generate um_uuid (this participant receiving)
        um_uuid = generate_uuid()

        # Format with sender prefix
        formatted_content = f"[{sender}]: {content}"

        return {
            'type': 'message',
            'role': 'user',
            'content': formatted_content,
            'um_uuid': um_uuid,
            'am_uuid': am_uuid  # Link to sender's am_uuid
        }

    def append_to_session(self, messages: List[Dict[str, Any]]) -> bool:
        """
        Append messages to CC session file.

        Args:
            messages: List of messages (already formatted for CC)

        Returns:
            True if successful
        """
        log("info", "Appending messages to CC session",
            message_count=len(messages),
            file=str(self.session_file))

        if not self.session_file:
            log("error", "No session file available")
            return False

        try:
            with open(self.session_file, 'a') as f:
                for msg in messages:
                    f.write(json.dumps(msg, ensure_ascii=False) + '\n')

            log("info", "Messages appended successfully", count=len(messages))
            return True
        except Exception as e:
            log("error", "Failed to append messages", error=str(e))
            return False

    def is_safe_to_write(self) -> bool:
        """
        Check if safe to write to CC session.

        Checks:
        1. Turn completion (hook_success marker present)
        2. File stability (no recent modifications)

        Returns:
            True if safe to write
        """
        log("debug", "Checking if safe to write", participant=self.name)

        if not self.session_file or not self.session_file.exists():
            log("warning", "Session file not available - assuming safe")
            return True

        # Check turn completion
        if not self._is_turn_complete():
            log("warning", "Turn not complete - not safe to write")
            return False

        # Check file stability
        if not self._is_file_stable():
            log("warning", "File not stable - not safe to write")
            return False

        log("info", "Safe to write", participant=self.name)
        return True

    def _is_turn_complete(self) -> bool:
        """
        Check if participant's turn is complete.

        Looks for hook_success marker in session.

        Returns:
            True if turn complete
        """
        session = self._read_session()
        if not session:
            return True  # Empty session = safe

        # Look for hook_success attachment in recent messages
        for msg in reversed(session[-50:]):  # Check last 50 messages
            if msg.get('type') == 'attachment':
                attachment_type = msg.get('attachment', {}).get('type')
                if attachment_type in ['hook_success', 'hook_cancelled', 'hook_non_blocking_error', 'turn_duration']:
                    log("debug", "Turn complete marker found", marker=attachment_type)
                    return True

        log("debug", "No turn completion marker found")
        return False

    def _is_file_stable(self, stability_window: float = 1.0) -> bool:
        """
        Check if session file is stable (no recent modifications).

        Args:
            stability_window: Seconds to wait since last modification

        Returns:
            True if file stable
        """
        try:
            mtime = self.session_file.stat().st_mtime
            age = time.time() - mtime

            stable = age >= stability_window

            if not stable:
                log("debug", "File modified recently", age_seconds=round(age, 2))
            else:
                log("debug", "File stable", age_seconds=round(age, 2))

            return stable
        except Exception as e:
            log("warning", "Could not check file stability", error=str(e))
            return True  # Assume safe on error

    def repair_uuid_chain(self) -> int:
        """
        Repair broken UUID chain in session.

        Finds user messages missing am_uuid link and repairs them.

        Returns:
            Number of repairs made
        """
        log("info", "Checking UUID chain", participant=self.name)

        if not self.session_file or not self.session_file.exists():
            log("warning", "No session file for UUID repair")
            return 0

        session = self._read_session()
        if not session:
            return 0

        repairs = 0

        # Find last user message
        last_user_idx = -1
        for i in range(len(session) - 1, -1, -1):
            msg = session[i]
            if msg.get('type') == 'message' and msg.get('role') == 'user':
                last_user_idx = i
                break

        if last_user_idx < 0:
            log("debug", "No user messages to repair")
            return 0

        # Check messages after last user
        for i in range(last_user_idx + 1, len(session)):
            msg = session[i]

            if msg.get('type') == 'message' and msg.get('role') == 'user':
                # User message should link to previous assistant
                if not msg.get('am_uuid'):
                    # Find previous assistant message
                    prev_am_uuid = self._find_previous_am_uuid(session, i)
                    if prev_am_uuid:
                        msg['am_uuid'] = prev_am_uuid
                        repairs += 1
                        log("debug", "Repaired UUID link", index=i, am_uuid=prev_am_uuid[:8])

        if repairs > 0:
            log("info", "UUID chain repaired", repair_count=repairs)
            self._write_session(session)
        else:
            log("debug", "UUID chain intact")

        return repairs

    def _find_previous_am_uuid(self, session: List[Dict], current_idx: int) -> Optional[str]:
        """Find am_uuid from previous assistant message."""
        for i in range(current_idx - 1, -1, -1):
            msg = session[i]
            if msg.get('type') == 'message' and msg.get('role') == 'assistant':
                return msg.get('am_uuid')
        return None

    def _read_session(self) -> List[Dict[str, Any]]:
        """Read session JSONL file."""
        if not self.session_file or not self.session_file.exists():
            return []

        messages = []
        try:
            with open(self.session_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        messages.append(json.loads(line))
        except Exception as e:
            log("error", "Failed to read session", error=str(e))
            return []

        return messages

    def _write_session(self, session: List[Dict[str, Any]]) -> bool:
        """Write session JSONL file."""
        if not self.session_file:
            return False

        try:
            with open(self.session_file, 'w') as f:
                for msg in session:
                    f.write(json.dumps(msg, ensure_ascii=False) + '\n')
            return True
        except Exception as e:
            log("error", "Failed to write session", error=str(e))
            return False
