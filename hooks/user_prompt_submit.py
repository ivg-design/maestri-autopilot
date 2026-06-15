#!/usr/bin/env python3
"""Capture mission intake fields from user prompts when possible."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import (  # noqa: E402
    activate_autopilot,
    append_event,
    hook_input_from_stdin,
    intake_context,
    is_autopilot_active,
    load_state_for_hook,
    merge_intake_prompt,
    missing_intake_fields,
    prompt_requests_autopilot,
    save_state_for_hook,
)


def main() -> int:
    try:
        hook = hook_input_from_stdin()
        state = load_state_for_hook(hook)
        prompt = str(hook.get("prompt") or "")
        if prompt_requests_autopilot(prompt):
            activate_autopilot(state)
        if not is_autopilot_active(state):
            json.dump({"continue": True}, sys.stdout)
            return 0
        changed = merge_intake_prompt(state, prompt)
        append_event(state, "user_prompt_submit", {"changed": changed, "prompt_chars": len(prompt)})
        save_state_for_hook(hook, state)
    except Exception:
        json.dump({"continue": True}, sys.stdout)
        return 0

    missing = missing_intake_fields(state)
    context = intake_context(state, missing)
    output = {"continue": True}
    if context:
        output["hookSpecificOutput"] = {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        }
    json.dump(output, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
