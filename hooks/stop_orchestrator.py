#!/usr/bin/env python3
"""Continue active Maestri missions until orchestration duties are satisfied."""

from __future__ import annotations

import json
import sys

from _bootstrap import add_plugin_scripts_to_path

add_plugin_scripts_to_path()

from mission_state import (  # noqa: E402
    append_event,
    evaluate_stop,
    hook_input_from_stdin,
    load_state_for_hook,
    save_state_for_hook,
)


def main() -> int:
    try:
        hook = hook_input_from_stdin()
        state = load_state_for_hook(hook)
        decision = evaluate_stop(state, hook)
        if decision.get("decision") == "block":
            append_event(state, "stop", {"decision": decision.get("decision", "allow")})
            save_state_for_hook(hook, state)
    except Exception:
        decision = {"continue": True}
    json.dump(decision, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
