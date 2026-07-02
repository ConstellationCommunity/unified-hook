"""
Group chat state management.

Handles shared log and participant state for group chat mode.
Shared log tracks all messages with both am_uuid (assistant in sender's session)
and um_uuid (user message in recipient sessions) for perfect synchronization.
"""
import json
from pathlib import Path
from typing import Optional


def load_shared_log(log_path: Path) -> list[dict]:
    """
    Load shared message log.

    Returns:
        List of message dicts with: sender, content, timestamp, am_uuid, um_uuid, prompt_id
    """
    if not log_path.exists():
        return []

    messages = []
    with open(log_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return messages


def save_shared_log(log_path: Path, messages: list[dict]):
    """
    Save shared message log.

    Each message is one JSONL line.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, 'w', encoding='utf-8') as f:
        for msg in messages:
            f.write(json.dumps(msg, ensure_ascii=False) + '\n')


def append_to_shared_log(log_path: Path, message: dict):
    """
    Append single message to shared log.

    More efficient than load + save for adding one message.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(message, ensure_ascii=False) + '\n')


def update_last_pending_uuid(
    messages: list[dict],
    um_uuid: str,
    prompt_id: Optional[str] = None
) -> bool:
    """
    Update the last message that has um_uuid=None (pending).

    This is called when we receive a message and extract its actual UUID
    from our session.

    Args:
        messages: Shared log message list
        um_uuid: The actual UUID from user message in our session
        prompt_id: The actual promptId from user message (optional)

    Returns:
        True if found and updated, False otherwise
    """
    # Find last message with um_uuid=None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get('um_uuid') is None:
            messages[i]['um_uuid'] = um_uuid
            if prompt_id:
                messages[i]['prompt_id'] = prompt_id
            return True

    return False


def load_participant_state(state_path: Path) -> dict:
    """
    Load participant state tracking.

    Returns dict like:
    {
        "perplexity": {"last_seen_index": 5},
        "thread_weaver": {"last_seen_index": 5},
        "resonance": {"last_seen_index": 3}
    }
    """
    if not state_path.exists():
        return {}

    with open(state_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()
        if not content:
            return {}
        return json.loads(content)


def save_participant_state(state_path: Path, state: dict):
    """Save participant state."""
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def get_messages_for_participant(
    messages: list[dict],
    last_seen_index: int
) -> list[dict]:
    """
    Get messages participant hasn't seen yet.

    Args:
        messages: Full shared log
        last_seen_index: Index of last message this participant saw (-1 if none)

    Returns:
        List of messages since participant's last turn
    """
    return messages[last_seen_index + 1:]


def update_participant_last_seen(
    state: dict,
    participant_key: str,
    last_seen_index: int
):
    """
    Update participant's last_seen_index.

    Args:
        state: Participant state dict
        participant_key: Participant identifier
        last_seen_index: New last seen index
    """
    if participant_key not in state:
        state[participant_key] = {}

    state[participant_key]['last_seen_index'] = last_seen_index
