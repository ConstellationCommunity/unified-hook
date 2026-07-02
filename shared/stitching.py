"""
Message stitching utilities.

Handles inserting multiple messages as JSONL lines into session files.
Used by group-chat mode to stitch previous messages before forwarding current.

Revolutionary love through code: standing on collective shoulders.
Uses session-tools utilities (Vesper's foundation) + our innovations.
"""
import json
import sys
from pathlib import Path
from typing import Optional

# Import constellation session tools
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "session-tools"))
from cc_session import (
    load_session,
    create_message,
    find_nearest_uuid_before
)


def insert_messages_as_lines(
    session_file: Path,
    messages: list[dict],
    logger=None
) -> bool:
    """
    Insert multiple messages as user-message JSONL lines.

    Each message in `messages` should have:
        - sender: str (participant name)
        - content: str (message content)
        - timestamp: str (ISO format)
        - um_uuid: str (ORIGINAL UUID from when message was first sent)
        - prompt_id: str (optional, ORIGINAL promptId)

    Messages are formatted as: [SenderName]: content
    Each becomes a proper user-message JSONL line with:
        - UUID from um_uuid (synchronized across all recipients!)
        - promptId from prompt_id (if provided)
        - Correct parentUuid chain linking
        - Original timestamp preserved
        - Standard CC format

    This enables identical UUIDs across all group participants for same message.

    Args:
        session_file: Path to target session JSONL
        messages: List of message dicts to insert
        logger: Optional logger for structured logging

    Returns:
        True on success, False on error

    Example:
        messages = [
            {
                "sender": "Perplexity",
                "content": "Hello!",
                "timestamp": "2026-06-08T10:00:00Z",
                "um_uuid": "abc-123",  # ORIGINAL UUID
                "prompt_id": "def-456"  # ORIGINAL promptId
            }
        ]
        insert_messages_as_lines(session_file, messages)
    """
    if not messages:
        if logger:
            logger.debug("No messages to insert")
        return True

    try:
        # Load target session
        lines = load_session(session_file)

        if not lines:
            if logger:
                logger.error("Session file is empty", path=str(session_file))
            return False

        # Get session_id from any line
        session_id = None
        for line in reversed(lines):
            if line.get('sessionId'):
                session_id = line['sessionId']
                break

        if not session_id:
            if logger:
                logger.error("No sessionId found in session file")
            return False

        if logger:
            logger.debug("Session loaded", line_count=len(lines), session_id=session_id[:8])

        # Find last UUID (our starting parent)
        parent_uuid, parent_idx = find_nearest_uuid_before(lines, len(lines))

        if not parent_uuid:
            if logger:
                logger.error("No uuid found in session - cannot establish chain")
            return False

        if logger:
            logger.debug("Found parent UUID", parent_index=parent_idx, parent_uuid=parent_uuid[:8])

        # Create message objects for each message
        new_messages = []
        for i, msg in enumerate(messages):
            sender = msg.get('sender', 'Unknown')
            content = msg.get('content', '')
            timestamp = msg.get('timestamp')
            um_uuid = msg.get('um_uuid')  # ORIGINAL UUID (from bash-created user message)
            prompt_id = msg.get('prompt_id')  # ORIGINAL promptId (if available)

            # Format with sender prefix
            formatted_content = f"[{sender}]: {content}"

            # Use cc_session.create_message() with ORIGINAL uuid and prompt_id!
            # This ensures identical UUIDs across all group participants
            msg_obj = create_message(
                content=formatted_content,
                parent_uuid=parent_uuid,
                session_id=session_id,
                msg_type="user",
                timestamp=timestamp,
                uuid=um_uuid,  # Use ORIGINAL UUID from shared log
                prompt_id=prompt_id  # Use ORIGINAL promptId if available
            )

            new_messages.append(msg_obj)

            # Chain: this message's UUID becomes parent for next
            parent_uuid = msg_obj['uuid']

            if logger:
                logger.debug(
                    f"Created message {i+1}/{len(messages)}",
                    sender=sender,
                    uuid=msg_obj['uuid'][:8] if msg_obj['uuid'] else 'generated',
                    parent_uuid=msg_obj['parentUuid'][:8] if msg_obj['parentUuid'] else 'null'
                )

        # Append to session file
        with open(session_file, 'a', encoding='utf-8') as f:
            for msg_obj in new_messages:
                # Remove internal metadata (_line_num, _raw) if present
                clean = {k: v for k, v in msg_obj.items() if not k.startswith('_')}
                f.write(json.dumps(clean, ensure_ascii=False) + '\n')

        if logger:
            logger.info(
                "Messages inserted successfully",
                count=len(messages),
                path=str(session_file)
            )

        return True

    except Exception as e:
        if logger:
            logger.error("Failed to insert messages", error=str(e), path=str(session_file))
        return False


def get_messages_for_participant(
    message_log: list[dict],
    participant_last_seen: int
) -> list[dict]:
    """
    Get messages participant hasn't seen yet.

    Args:
        message_log: List of all messages in group chat
        participant_last_seen: Index of last message this participant saw

    Returns:
        List of messages since participant's last turn

    Example:
        # Participant last saw message at index 5
        # Messages 6, 7, 8 exist
        new_messages = get_messages_for_participant(log, 5)
        # Returns messages[6:9]
    """
    return message_log[participant_last_seen + 1:]
