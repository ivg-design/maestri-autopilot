#!/usr/bin/env python3
"""Capture mission intake fields from user prompts when possible."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import (  # noqa: E402
    append_event,
    hook_input_from_stdin,
    intake_context,
    load_state_for_hook,
    merge_intake_prompt,
    missing_intake_fields,
    save_state_for_hook,
)


def main() -> int:
    hook = hook_input_from_stdin()
    state = load_state_for_hook(hook)
    prompt = str(hook.get("prompt") or "")
    changed = merge_intake_prompt(state, prompt)
    append_event(state, "user_prompt_submit", {"changed": changed, "prompt_chars": len(prompt)})
    save_state_for_hook(hook, state)

    missing = missing_intake_fields(state)
    context = intake_context(state, missing)
    output = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        },
    }
    json.dump(output, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
