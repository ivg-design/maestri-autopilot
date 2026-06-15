#!/usr/bin/env python3
"""Record Maestri command output into the mission ledger."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import (  # noqa: E402
    hook_input_from_stdin,
    load_state_for_hook,
    observe_post_tool,
    save_state_for_hook,
)


def main() -> int:
    try:
        hook = hook_input_from_stdin()
        state = load_state_for_hook(hook)
        message = observe_post_tool(state, hook)
        if message:
            save_state_for_hook(hook, state)
    except Exception:
        json.dump({"continue": True}, sys.stdout)
        return 0
    output = {"continue": True}
    if message:
        output["hookSpecificOutput"] = {
            "hookEventName": "PostToolUse",
            "additionalContext": message,
        }
    json.dump(output, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
