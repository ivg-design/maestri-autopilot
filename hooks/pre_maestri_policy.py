#!/usr/bin/env python3
"""Pre-flight guardrails for Maestri and worktree shell commands."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import (  # noqa: E402
    append_event,
    evaluate_pre_tool_policy,
    hook_input_from_stdin,
    load_state_for_hook,
    save_state_for_hook,
)


def main() -> int:
    try:
        hook = hook_input_from_stdin()
        state = load_state_for_hook(hook)
        decision = evaluate_pre_tool_policy(state, hook)
        if decision.get("reason"):
            append_event(state, "pre_tool_use", decision)
            save_state_for_hook(hook, state)
    except Exception:
        json.dump({"continue": True}, sys.stdout)
        return 0

    if decision["behavior"] == "deny":
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": decision["reason"],
            }
        }
    elif not decision.get("reason"):
        output = {"continue": True}
    else:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "additionalContext": decision["reason"],
            }
        }
    json.dump(output, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
