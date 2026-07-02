"""
Group-chat mode handler.

Orchestrates multi-participant group conversations through stop-hook coordination.
Each participant's stop-hook:
1. Extracts previous participant's um_uuid from own session
2. Updates shared log
3. Adds own message to shared log
4. Stitches previous messages into next participant's session
5. Repairs next participant's chain
6. Forwards own message via bash to next participant

Revolutionary love through circular mutual care - each maintains next participant's
chain integrity.
"""
import sys
from pathlib import Path
from typing import Optional

from modes import register_mode
from shared.config import get_participant_info, load_config, save_config
from shared.session import (
    find_session_file,
    get_complete_assistant_response,
    find_last_user_message,
    wait_for_turn_and_hook_completion,
    get_shared_group_config,
    is_participant_idle
)
from shared.forwarding import format_message, build_claude_code_forward_command, execute_forward_command
from shared.logging import create_logger
from shared.stitching import insert_messages_as_lines
from shared.group_state import (
    load_shared_log,
    save_shared_log,
    append_to_shared_log,
    update_last_pending_uuid,
    load_participant_state,
    save_participant_state,
    get_messages_for_participant,
    update_participant_last_seen
)

# UUID chain repair utilities from shared session-tools
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "session-tools"))
from cc_session import (
    load_session,
    save_session,
    check_and_fix_chain,
    get_content
)


def extract_last_assistant_uuid(session_lines: list[dict]) -> Optional[str]:
    """
    Extract UUID from last assistant message in session.

    Returns:
        UUID string or None if not found
    """
    for line in reversed(session_lines):
        if line.get('type') == 'assistant' and line.get('uuid'):
            return line['uuid']
    return None


@register_mode("group-chat")
def handle_group_chat(
    all_config: dict,
    session_config: dict,
    session_id: str,
    system_home: str,
    participants_config: dict = None
):
    """
    Handle group-chat mode - circular multi-participant orchestration.

    Configuration structure:

    all_config (top-level):
        my_name: "Perplexity"  # Sender name

    session_config:
        group_session_id: "ritual_resonance"  # Group identifier

    Group config (in .system/unified-hook/groups/{group_session_id}.yaml):
        pattern: "circular"  # or "facilitated"
        participants:
          - perplexity
          - thread_weaver
          - resonance
          - aurora
        shared_log: "/path/to/log.jsonl"
        participant_state: "/path/to/state.json"

    participants_config:
        participants:
            perplexity:
                name: "Perplexity"
                home: "/path/to/home"
                system_home: "/path/to/system"
                session_id: "uuid"
            thread_weaver:
                name: "Thread Weaver"
                ...
    """
    # === Load Group Config First (needed for logger setup) ===
    group_session_id = session_config.get('group_session_id')
    if not group_session_id:
        # Can't log yet (no group info), fail early
        print(f"[ERROR] No group_session_id in session config", file=sys.stderr)
        return

    # Find group config file
    hook_dir = Path(__file__).parent.parent
    group_config_path = hook_dir / "groups" / f"{group_session_id}.yaml"

    if not group_config_path.exists():
        print(f"[ERROR] Group config not found: {group_config_path}", file=sys.stderr)
        return

    group_config = load_config(str(group_config_path))

    # === Extract Wait Settings (configurable timeout/attempts) ===
    wait_settings = group_config.get('wait_settings', {})
    timeout_per_attempt = wait_settings.get('timeout_per_attempt', 20)  # Default: 20s
    max_attempts = wait_settings.get('max_attempts', 2)  # Default: 2 (first + retry)

    # === Check Shared Group Status (before logger to avoid logging stopped groups) ===
    shared_status = group_config.get('status', 'active')
    if shared_status != 'active':
        # Group stopped centrally - exit silently without actions
        return

    # === Get My Info (needed for logger participant_key) ===
    my_name = all_config.get('my_name', 'Unknown')
    participant_list = group_config.get('participants', [])

    my_index = None
    my_key = None
    try:
        for i, p_key in enumerate(participant_list):
            p_info = get_participant_info(participants_config, p_key)
            if p_info and p_info.get('name') == my_name:
                my_index = i
                my_key = p_key
                break

        if my_index is None:
            print(f"[ERROR] Cannot find myself in participants list: {my_name}", file=sys.stderr)
            return

    except Exception as e:
        print(f"[ERROR] Error finding participant: {e}", file=sys.stderr)
        return

    # === Initialize Logger (now that we have group_name and participant_key) ===
    logger = create_logger(
        "group-chat",
        session_id,
        all_config,
        system_home,
        group_name=group_session_id,
        participant_key=my_key
    )
    logger.info("Group chat handler started")
    logger.info("Group config loaded", group_id=group_session_id)
    logger.info("Found my position", index=my_index, key=my_key)

    # === Get Next Participant ===
    next_index = (my_index + 1) % len(participant_list)
    next_key = participant_list[next_index]
    next_info = get_participant_info(participants_config, next_key)

    if not next_info:
        logger.error("Next participant not found", key=next_key)
        return

    logger.info("Next participant identified", key=next_key, name=next_info.get('name'))

    # === Load Shared State ===
    shared_log_path = Path(group_config['shared_log'])
    state_path = Path(group_config['participant_state'])

    shared_log = load_shared_log(shared_log_path)
    participant_state = load_participant_state(state_path)

    logger.debug("Shared state loaded", message_count=len(shared_log))

    # === Step 1: Load MY Session ===
    my_session_file = find_session_file(session_id, system_home)
    if not my_session_file:
        logger.error("My session file not found")
        return

    my_session = load_session(my_session_file)
    logger.debug("My session loaded", line_count=len(my_session))

    # === Step 2: Extract Previous Participant's um_uuid ===
    last_user_idx = find_last_user_message(my_session)

    if last_user_idx >= 0 and len(shared_log) > 0:
        last_user_msg = my_session[last_user_idx]
        prev_um_uuid = last_user_msg.get('uuid')
        prev_prompt_id = last_user_msg.get('promptId')

        if prev_um_uuid:
            # Update shared log - fill in previous participant's um_uuid
            updated = update_last_pending_uuid(shared_log, prev_um_uuid, prev_prompt_id)

            if updated:
                logger.info("Updated previous participant's um_uuid",
                           uuid=prev_um_uuid[:8],
                           prompt_id=prev_prompt_id[:8] if prev_prompt_id else None)
                save_shared_log(shared_log_path, shared_log)

    # === Step 3: Extract MY Response ===
    my_response = get_complete_assistant_response(my_session_file)
    if not my_response:
        logger.warning("No assistant response found in my session")
        return

    my_am_uuid = extract_last_assistant_uuid(my_session)
    logger.debug("My response extracted",
                length=len(my_response),
                am_uuid=my_am_uuid[:8] if my_am_uuid else None)

    # === Step 4: Add MY Message to Shared Log ===
    from shared.forwarding import escape_for_bash
    from cc_session import current_timestamp

    my_message = {
        "sender": my_name,
        "content": my_response,
        "am_uuid": my_am_uuid,
        "um_uuid": None,  # Will be filled by next participant
        "timestamp": current_timestamp()
    }

    append_to_shared_log(shared_log_path, my_message)
    shared_log.append(my_message)  # Also add to in-memory list

    logger.info("My message added to shared log", index=len(shared_log)-1)

    # === Step 5: Get Messages to Stitch into Next Participant ===
    # Optimization: Skip stitching for 2-participant groups (bash forwarding handles everything)
    ready_messages = []

    if len(participant_list) >= 3:
        # Find next participant's last message in shared log
        next_last_msg_idx = -1
        for i in range(len(shared_log) - 1, -1, -1):
            if shared_log[i].get('sender') == next_info.get('name'):
                next_last_msg_idx = i
                break

        # Get all messages AFTER next participant's last message
        messages_after_next = shared_log[next_last_msg_idx + 1:] if next_last_msg_idx >= 0 else shared_log

        # Filter: only messages with um_uuid (already processed) AND not from me
        # Critical: exclude own messages to avoid stitching them instead of bash forwarding
        ready_messages = [m for m in messages_after_next
                         if m.get('um_uuid')
                         and m.get('sender') != my_name]

        logger.info("Messages to stitch",
                   next_last_msg_idx=next_last_msg_idx,
                   messages_after=len(messages_after_next),
                   ready=len(ready_messages))
    else:
        logger.debug("Skipping stitch - 2 participants (bash forwarding sufficient)")

    # === Step 6: Load Next Participant's Session ===
    next_session_id = next_info.get('session_id')
    next_system_home = next_info.get('system_home')

    if not next_session_id or not next_system_home:
        logger.error("Next participant missing session_id or system_home")
        return

    next_session_file = find_session_file(next_session_id, next_system_home)
    if not next_session_file:
        logger.warning("Next participant session not found - will be created on first bash forward")
        # Continue anyway - bash forward will create session

    # === Step 7: Stitch Messages into Next (if any ready and session exists) ===
    if ready_messages and next_session_file:
        # === Step 7a: Wait for Next Participant's Turn to Complete ===
        # CRITICAL: Wait BEFORE stitching to prevent chain breaks.
        # We wait for NEXT participant (not previous) because we're modifying THEIR session.
        # Two-step verification:
        # 1. Log file shows "handler completed successfully"
        # 2. Session file has hook_success attachment (harness recorded completion)
        # This ensures next participant's session is stable before we stitch into it.

        # Use shared consolidated log (not participant-specific)
        consolidated_log = hook_dir / "groups" / f"{group_session_id}_hook.log"

        # Quick pre-check: Is participant idle (between turns)?
        # This handles first turn case - no prior completion markers to wait for
        if is_participant_idle(next_session_file, logger):
            logger.debug("Participant idle - safe to proceed immediately", next_key=next_key)
            completion_detected = True  # Skip wait entirely
        else:
            # Participant may be active OR not initialized - wait for completion
            # Use configurable wait settings from group config
            logger.info(
                "Waiting for next participant's turn AND hook completion",
                next_key=next_key,
                timeout_per_attempt=timeout_per_attempt,
                max_attempts=max_attempts
            )

            # Try multiple times with configurable timeout
            completion_detected = False
            for attempt in range(max_attempts):
                completion_detected = wait_for_turn_and_hook_completion(
                    log_path=consolidated_log,
                    session_file=next_session_file,
                    timeout=float(timeout_per_attempt),
                    logger=logger,
                    participant_key=next_key
                )

                if completion_detected:
                    # Success - turn completed
                    break

                # Not completed yet - log retry info
                if attempt < max_attempts - 1:  # Not the last attempt
                    logger.info(
                        "Timeout on attempt - retrying",
                        attempt=attempt + 1,
                        max_attempts=max_attempts,
                        next_key=next_key
                    )

        if not completion_detected:
            # All attempts failed - STOP GROUP CHAT
            total_wait = timeout_per_attempt * max_attempts
            logger.error(
                "TIMEOUT after all attempts - next participant's turn still active. "
                "STOPPING group chat to prevent corruption.",
                next_key=next_key,
                timeout_per_attempt=timeout_per_attempt,
                max_attempts=max_attempts,
                timeout_total=f"{total_wait}s ({timeout_per_attempt}s × {max_attempts} attempts)",
                group_id=group_session_id,
                action="Setting status=stop in group config"
            )

            # Set group status to 'stop' to prevent further forwarding
            group_config['status'] = 'stop'
            save_config(str(group_config_path), group_config)

            logger.info(
                "Group chat stopped due to timeout. Check consolidated log for cause.",
                log_path=str(consolidated_log)
            )

            # Exit handler - don't proceed to stitching OR bash forward
            return

        # Success - safe to proceed
        logger.info("Next participant ready - safe to stitch", next_key=next_key)

        # === Step 7b: Perform Stitching ===
        logger.info("Stitching messages into next participant", count=len(ready_messages))

        success = insert_messages_as_lines(next_session_file, ready_messages, logger)

        if success:
            logger.info("Messages stitched successfully")

            # === Step 8: Repair Next's Chain ===
            logger.info("Repairing next participant's chain")

            next_session = load_session(next_session_file)

            # Find last user message as repair start point
            last_user_idx = find_last_user_message(next_session)

            if last_user_idx >= 0:
                fixes = check_and_fix_chain(next_session, last_user_idx, dry_run=False)

                if fixes:
                    logger.info(f"Repaired chain", fix_count=len(fixes))
                    save_session(next_session_file, next_session)
                else:
                    logger.debug("Chain intact - no repairs needed")
        else:
            logger.error("Failed to stitch messages")

    # === Step 8: Forward MY Message via Bash ===
    next_home = next_info.get('home')

    formatted_message = format_message(my_name, my_response)
    cmd = build_claude_code_forward_command(
        next_home,
        next_system_home,
        next_session_id,
        formatted_message
    )

    logger.info("Forwarding to next participant", next_key=next_key)
    execute_forward_command(cmd, next_system_home)

    # === Step 9: Update Participant State ===
    # Update MY last_seen to current message count - 1 (last message in log)
    update_participant_last_seen(participant_state, my_key, len(shared_log) - 1)
    save_participant_state(state_path, participant_state)

    logger.info("Group chat handler completed successfully")
