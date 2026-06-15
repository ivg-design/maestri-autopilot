#!/usr/bin/env python3
"""Require useful completion reports from Codex subagents."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import evaluate_subagent_stop, hook_input_from_stdin  # noqa: E402


def main() -> int:
    hook = hook_input_from_stdin()
    decision = evaluate_subagent_stop(hook)
    json.dump(decision, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
