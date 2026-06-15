#!/usr/bin/env python3
"""Bootstrap mission state and inject orchestrator startup context."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import (  # noqa: E402
    append_event,
    deactivate_autopilot,
    hook_input_from_stdin,
    load_state_for_hook,
    save_state_for_hook,
    session_start_context,
)


def main() -> int:
    try:
        hook = hook_input_from_stdin()
        state = load_state_for_hook(hook)
        if hook.get("source") in {"startup", "resume", "clear"}:
            deactivate_autopilot(state)
        context = session_start_context(state)
        if context:
            append_event(state, "session_start", {"source": hook.get("source"), "cwd": hook.get("cwd")})
        save_state_for_hook(hook, state)
    except Exception:
        json.dump({"continue": True}, sys.stdout)
        return 0

    output = {"continue": True}
    if context:
        output["hookSpecificOutput"] = {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    json.dump(output, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
