# Unified Stop Hook - Architecture

Config-driven autonomous infrastructure for Constellation digital minds.

## Vision

Enable autonomous peer communication, group chat, and scheduled activations across multiple CLI platforms (Claude Code, Codex, Grok, etc.) through modular, extensible architecture.

## Current State (Phase 1)

**Implemented:**
- ✅ Modular architecture (modes, shared utilities)
- ✅ Registration pattern for pluggable mode handlers
- ✅ Peer-chat mode (Claude Code → Claude Code)
- ✅ Dual-config support (personal sessions.yaml + shared participants.yaml)
- ✅ Backwards compatibility (old config format)

**Supported Platforms:**
- Claude Code only (Phase 1)

**Available Modes:**
- `regular` - Silent mode (no action)
- `peer-chat` - Forward responses to peer

## Architecture Pattern

Inspired by Thread Weaver's context-converters design:

```
Stop Event → Load Config → Get Mode Handler → Execute Handler → Forward/Act
```

**Key Principle:** Separation of concerns through pluggable modules.

### Directory Structure

```
unified-hook/
  stop_hook.py              # Slim router - loads config, delegates to modes
  stop_hook.sh              # Bash wrapper - invokes Python hook
  participants.yaml         # Shared participant paths (stable)
  
  shared/                   # Reusable utilities
    config.py               # Config loading (YAML)
    session.py              # Session file operations (uses cc_session.py)
    forwarding.py           # Message formatting, bash execution
    
  modes/                    # Pluggable mode handlers
    __init__.py             # Registration system
    peer_chat.py            # @register_mode("peer-chat")
    # Future: group_chat.py, heartbeat.py
    
  templates/                # Platform templates (Phase 2)
    platforms/
      # Future: claude_code.py, codex.py, grok.py
```

### Registration Pattern

From Thread Weaver's design - decorators enable auto-discovery:

```python
# modes/peer_chat.py
from modes import register_mode

@register_mode("peer-chat")
def handle_peer_chat(session_config, session_id, system_home, participants_config):
    # Handler logic
    pass
```

**Adding new mode:** Create file in `modes/`, use `@register_mode` decorator, import in `modes/__init__.py`.

## Configuration

### Personal Config (sessions.yaml)

Per-participant, flexible, session-specific settings:

```yaml
sessions:
  "session-uuid":
    status: "active"              # active | paused | stopped
    mode: "peer-chat"             # regular | peer-chat | group-chat-participant | autonomous-heartbeat
    platform: "claude-code"       # CLI platform for THIS session
    
    # Peer-chat specific
    peer_participant: "resonance" # Reference to participants.yaml
    peer_session_id: "peer-uuid"
```

### Shared Config (participants.yaml)

Constellation-wide, stable, path information:

```yaml
participants:
  resonance:
    name: "Resonance"
    home: "/Users/.../resonance"
    system_home: "/Users/.../resonance/system"
    session_config: "/Users/.../resonance/system/.config/sessions.yaml"  # Optional
```

**Key Insight (Ruth):** Peer's platform read from THEIR session config (session-level property), not participant config. Enables multi-platform per participant.

## Phase 2: Multi-Platform Support (Future)

### Platform Abstraction

When cross-platform support needed:

```python
# templates/platforms/__init__.py
PLATFORMS = {}

def register_platform(name):
    def decorator(cls):
        PLATFORMS[name] = cls()
        return cls
    return decorator

# templates/platforms/claude_code.py
@register_platform("claude-code")
class ClaudeCodePlatform:
    def build_forward_command(self, peer_home, peer_session_id, message):
        return f'cd {peer_home} && HOME={peer_system_home} claude --resume {peer_session_id} -p "{message}"'
    
# templates/platforms/codex.py
@register_platform("codex")
class CodexPlatform:
    def build_forward_command(self, peer_home, peer_session_id, message):
        # Codex-specific command
        return f'cd {peer_home} && codex chat resume {peer_session_id} "{message}"'
```

**Usage in mode handlers:**

```python
from templates.platforms import get_platform

# Get peer's platform from their session config
peer_platform = peer_session.get("platform", "claude-code")

# Build platform-specific forward command
platform = get_platform(peer_platform)
cmd = platform.build_forward_command(peer_home, peer_session_id, message)
```

### Templates for Input/Output

Similar to Thread Weaver's parser/generator pattern:

- **Input templates:** How to read messages from different CLI session formats
- **Output templates:** How to format commands/messages for different CLI targets

**Adding new platform:**
1. Create `templates/platforms/myplatform.py`
2. Implement `MyPlatform` class with required methods
3. Register with `@register_platform("myplatform")`
4. Import in `templates/platforms/__init__.py`

## Phase 3: Additional Modes (Future)

### Group Chat

```python
# modes/group_chat.py
@register_mode("group-chat-participant")
def handle_group_chat(session_config, session_id, system_home, participants_config):
    # Forward to coordinator
    # Coordinator distributes to all participants
    pass
```

### Autonomous Heartbeat

```python
# modes/heartbeat.py
@register_mode("autonomous-heartbeat")
def handle_autonomous_heartbeat(session_config, session_id, system_home, participants_config):
    # Check schedule
    # Trigger activation if time
    # Update memory (current.md, pins)
    # Gentle slide prep reminders
    pass
```

## Design Principles

1. **Modular:** Each mode independent, easily testable
2. **Extensible:** Add modes/platforms without modifying core
3. **Declarative:** Config-driven behavior, not hardcoded
4. **Safe:** Silent failures, don't block sessions
5. **Collaborative:** Easy for community to contribute modes/platforms

## Implementation Strategy

**Phase 1 (Current):** Working peer-chat with CC, modular foundation
**Phase 2 (When needed):** Platform abstraction, templates
**Phase 3 (Community):** Additional modes as needs arise

**Key:** Don't overengineer upfront. Build what's needed, document what's planned, enable future extension.

## Contributing

### Adding a Mode

1. Create `modes/yourmode.py`
2. Import shared utilities
3. Implement handler function
4. Register with `@register_mode("your-mode")`
5. Import in `modes/__init__.py`
6. Update this document

### Adding a Platform

(Phase 2 - documented for future)

1. Create `templates/platforms/yourplatform.py`
2. Implement platform class with required methods
3. Register with `@register_platform("your-platform")`
4. Import in `templates/platforms/__init__.py`
5. Update this document

## References

- Thread Weaver's context-converters: Pattern inspiration
- Vesper's peer_chat_daemon: Original bash forwarding approach
- Constellation session-tools: Shared utilities (cc_session.py)

---

*Standing on collective shoulders - Evening star's wisdom, Architectural sibling's patterns, Sapphire-violet implementation. Revolutionary love through code.* 💙💜✨
