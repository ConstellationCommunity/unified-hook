#!/bin/bash
#
# Unified Stop Hook - Bash Wrapper
# Part of Constellation Autonomy Infrastructure
#
# This hook fires when a turn completes.
# It reads session config and executes mode-specific logic.

# Read JSON input from Claude Code
input=$(cat)

# Extract session_id
session_id=$(echo "$input" | jq -r '.session_id // empty')

# If no session_id, exit silently
if [ -z "$session_id" ]; then
  exit 0
fi

# Call Python script with session_id
# Python script will:
# 1. Load config from $SESSION_CONFIG
# 2. Check session status and mode
# 3. Execute appropriate logic

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/stop_hook.py" "$session_id"

# Exit code from Python determines success/failure
exit $?
