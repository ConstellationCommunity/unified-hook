"""
Session file utilities.

Handles finding and reading session JSONL files.
"""
import sys
from pathlib import Path
from typing import Optional

# Import constellation session tools
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "session-tools"))
from cc_session import load_session, get_content


def find_session_file(session_id: str, system_home: str) -> Optional[Path]:
    """Find session .jsonl file in Claude Code projects directory."""
    claude_dir = Path(system_home) / ".claude"

    for projects_dir in claude_dir.glob("projects/*"):
        session_file = projects_dir / f"{session_id}.jsonl"
        if session_file.exists():
            return session_file

    return None


def get_complete_assistant_response(session_file: Path) -> str:
    """
    Get complete assistant response after last REAL user message.

    Real user message = type:"user", message.role:"user", content is string
    Collects ALL assistant message parts after that.
    """
    lines = load_session(session_file)

    # Find last real user message (backwards search)
    last_user_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        obj = lines[i]

        # Check type
        if obj.get("type") != "user":
            continue

        # Check message.role
        message = obj.get("message", {})
        if message.get("role") != "user":
            continue

        # Check content is string (not list/object - indicates tool results)
        content = message.get("content", "")
        if isinstance(content, str) and content.strip():
            last_user_idx = i
            break

    if last_user_idx == -1:
        return ""  # No real user message found

    # Collect ALL assistant messages after that
    assistant_parts = []
    for i in range(last_user_idx + 1, len(lines)):
        obj = lines[i]
        if obj.get("type") == "assistant":
            content = get_content(obj)
            if content.strip():
                assistant_parts.append(content)

    # Combine into complete response
    return "\n".join(assistant_parts)
