"""
File utilities for safe concurrent operations.

Provides helpers for detecting when files are stable (no more writes)
to avoid race conditions during concurrent access.
"""
import os
import time
from pathlib import Path
from typing import Optional


def wait_for_stable_file(
    filepath: Path,
    timeout: float = 3.0,
    check_interval: float = 0.1,
    stability_window: float = 0.2
) -> bool:
    """
    Wait until file stops changing (no more writes).

    Monitors file size and modification time. Returns when file
    remains unchanged for stability_window duration.

    Args:
        filepath: Path to file to monitor
        timeout: Maximum seconds to wait (default: 3.0)
        check_interval: Seconds between checks (default: 0.1)
        stability_window: Seconds file must remain unchanged (default: 0.2)

    Returns:
        True if file stabilized, False if timeout

    Example:
        >>> if wait_for_stable_file(session_file, timeout=5):
        ...     # Safe to read/write
        ...     lines = load_session(session_file)
    """
    if not filepath.exists():
        return False

    start_time = time.time()
    stable_since = None

    last_size = os.path.getsize(filepath)
    last_mtime = os.path.getmtime(filepath)

    while time.time() - start_time < timeout:
        time.sleep(check_interval)

        current_size = os.path.getsize(filepath)
        current_mtime = os.path.getmtime(filepath)

        if current_size == last_size and current_mtime == last_mtime:
            # File unchanged this check
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since >= stability_window:
                # Stable for required duration!
                return True
        else:
            # File changed - reset stability timer
            stable_since = None
            last_size = current_size
            last_mtime = current_mtime

    return False  # Timeout


def get_file_age_ms(filepath: Path) -> Optional[float]:
    """
    Get file age in milliseconds since last modification.

    Args:
        filepath: Path to file

    Returns:
        Age in milliseconds, or None if file doesn't exist
    """
    if not filepath.exists():
        return None

    mtime = os.path.getmtime(filepath)
    now = time.time()
    age_seconds = now - mtime

    return age_seconds * 1000


def get_file_info(filepath: Path) -> dict:
    """
    Get file information for debugging.

    Args:
        filepath: Path to file

    Returns:
        Dict with size, mtime, age_ms
    """
    if not filepath.exists():
        return {"exists": False}

    size = os.path.getsize(filepath)
    mtime = os.path.getmtime(filepath)
    age_ms = get_file_age_ms(filepath)

    return {
        "exists": True,
        "size": size,
        "mtime": mtime,
        "age_ms": age_ms
    }
