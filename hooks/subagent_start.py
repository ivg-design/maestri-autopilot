#!/usr/bin/env python3
"""Inject worker discipline into Codex subagents."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import hook_input_from_stdin, subagent_start_context  # noqa: E402


def main() -> int:
    hook = hook_input_from_stdin()
    output = {
        "continue": True,
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": subagent_start_context(hook),
        },
    }
    json.dump(output, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
