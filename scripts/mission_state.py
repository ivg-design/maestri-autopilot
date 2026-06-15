#!/usr/bin/env python3
"""State and policy helpers for the Maestri Autopilot plugin."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
DEFAULT_PRESETS = ["Codex", "Claude Code", "Gemini CLI", "OpenCode", "Shell"]
DEFAULT_ROLES = [
    "Chief Orchestrator & Quality Controller",
    "Technical Research & Investigation",
    "Senior Engineer",
    "Code Review & Validation",
    "Rapid Implementation Engineer",
]
INTAKE_FIELDS = [
    "goal",
    "success_criteria",
    "max_agents",
    "allowed_presets",
    "allowed_roles",
    "worktree_policy",
    "commit_policy",
]


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def hook_input_from_stdin() -> dict[str, Any]:
    raw = sys.stdin.read().strip()
    if not raw:
        return {}
    return json.loads(raw)


def plugin_data_dir(env: dict[str, str] | None = None) -> Path:
    source = env if env is not None else os.environ
    value = source.get("PLUGIN_DATA") or source.get("CLAUDE_PLUGIN_DATA")
    if value:
        return Path(value).expanduser()
    return Path.home() / ".local" / "state" / "maestri-autopilot"


def safe_session_id(session_id: str | None) -> str:
    raw = session_id or "unknown-session"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)[:120] or "unknown-session"


def state_path(data_dir: Path, session_id: str | None) -> Path:
    return data_dir / "missions" / f"{safe_session_id(session_id)}.json"


def default_state(session_id: str | None, cwd: str | None = None) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "cwd": cwd,
        "status": "awaiting_intake",
        "goal": "",
        "success_criteria": [],
        "max_agents": None,
        "allowed_presets": DEFAULT_PRESETS[:],
        "allowed_roles": DEFAULT_ROLES[:],
        "worktree_policy": "prefer_disjoint_worktrees",
        "commit_policy": "workers_commit_atomic_changes_before_handoff",
        "agents": {},
        "tasks": {},
        "questions": [],
        "integration_queue": [],
        "validation": {"required": True, "last_result": None, "commands": []},
        "policy": {
            "allow_dismiss_before_complete": False,
            "require_assignment_for_recruit": True,
            "max_stop_continuations_per_turn": 1,
        },
        "counters": {
            "stop_continuations": 0,
            "maestri_checks": 0,
            "maestri_asks": 0,
            "maestri_batches": 0,
        },
        "events": [],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }


def load_state(path: Path, session_id: str | None = None, cwd: str | None = None) -> dict[str, Any]:
    if path.exists():
        with path.open("r", encoding="utf-8") as fh:
            state = json.load(fh)
        state.setdefault("events", [])
        state.setdefault("agents", {})
        state.setdefault("tasks", {})
        state.setdefault("questions", [])
        state.setdefault("integration_queue", [])
        state.setdefault("counters", {})
        state.setdefault("policy", {})
        return state
    return default_state(session_id, cwd)


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now()
    tmp_path = path.with_suffix(".tmp")
    with tmp_path.open("w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, sort_keys=True)
        fh.write("\n")
    tmp_path.replace(path)


def load_state_for_hook(hook: dict[str, Any]) -> dict[str, Any]:
    return load_state(
        state_path(plugin_data_dir(), hook.get("session_id")),
        session_id=hook.get("session_id"),
        cwd=hook.get("cwd"),
    )


def save_state_for_hook(hook: dict[str, Any], state: dict[str, Any]) -> None:
    save_state(state_path(plugin_data_dir(), hook.get("session_id")), state)


def append_event(state: dict[str, Any], event_type: str, data: dict[str, Any] | None = None) -> None:
    events = state.setdefault("events", [])
    events.append({"time": utc_now(), "type": event_type, "data": data or {}})
    if len(events) > 200:
        del events[:-200]


def split_csv(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]


def parse_intake_text(text: str) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    current_multiline: str | None = None
    multiline_values: list[str] = []

    def flush_multiline() -> None:
        nonlocal current_multiline, multiline_values
        if current_multiline:
            fields[current_multiline] = [item.strip(" -") for item in multiline_values if item.strip(" -")]
        current_multiline = None
        multiline_values = []

    aliases = {
        "long horizon goal": "goal",
        "goal": "goal",
        "success criteria": "success_criteria",
        "done criteria": "success_criteria",
        "max agents": "max_agents",
        "maximum agents": "max_agents",
        "allowed presets": "allowed_presets",
        "agent presets": "allowed_presets",
        "agent types": "allowed_presets",
        "allowed roles": "allowed_roles",
        "roles": "allowed_roles",
        "worktree policy": "worktree_policy",
        "commit policy": "commit_policy",
    }

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        match = re.match(r"^([A-Za-z][A-Za-z _-]{1,40})\s*:\s*(.*)$", line)
        if match:
            flush_multiline()
            key = aliases.get(match.group(1).strip().lower())
            if not key:
                continue
            value = match.group(2).strip()
            if key == "max_agents":
                int_match = re.search(r"\d+", value)
                if int_match:
                    fields[key] = int(int_match.group(0))
            elif key in {"allowed_presets", "allowed_roles", "success_criteria"}:
                if value:
                    fields[key] = split_csv(value)
                else:
                    current_multiline = key
                    multiline_values = []
            else:
                fields[key] = value
            continue
        if current_multiline and (line.startswith("-") or line.startswith("*")):
            multiline_values.append(line)

    flush_multiline()
    return fields


def merge_intake_prompt(state: dict[str, Any], prompt: str) -> list[str]:
    parsed = parse_intake_text(prompt)
    changed: list[str] = []
    for key, value in parsed.items():
        if value in ("", [], None):
            continue
        if state.get(key) != value:
            state[key] = value
            changed.append(key)
    if state.get("goal") and state.get("max_agents"):
        state["status"] = "planning"
    return changed


def missing_intake_fields(state: dict[str, Any]) -> list[str]:
    missing = []
    for key in INTAKE_FIELDS:
        value = state.get(key)
        if value in ("", [], None):
            missing.append(key)
    return missing


def session_start_context(state: dict[str, Any]) -> str:
    if state.get("status") == "complete":
        return "Maestri Autopilot has a completed mission ledger for this session. Do not restart it unless the user asks."

    missing = missing_intake_fields(state)
    checklist = "\n".join(f"- {field.replace('_', ' ')}" for field in missing)
    return (
        "Maestri Autopilot is active. If the user has not provided the full mission intake, "
        "ask once for the missing fields below before delegating. After intake, run `maestri list`, "
        "`maestri preset list`, and `maestri role list`; create shared notes; recruit only within the "
        "user's cap; use `maestri ask --batch` for independent work; use disjoint worktrees or "
        "non-overlapping write scopes; check agents frequently; answer blockers; review diffs; run "
        "validation; and only stop when the success criteria are met.\n\nMissing intake fields:\n"
        f"{checklist or '- none'}"
    )


def intake_context(state: dict[str, Any], missing: list[str]) -> str:
    if missing:
        return (
            "Maestri Autopilot intake is incomplete. Ask for these fields before recruiting agents: "
            + ", ".join(field.replace("_", " ") for field in missing)
            + "."
        )
    return (
        "Maestri Autopilot intake is available. Convert the goal into disjoint assignments, record "
        "the plan in a shared Maestri note, recruit within the cap, dispatch with `maestri ask --batch`, "
        "and keep validating subordinate progress until the mission is complete."
    )


def extract_bash_command(hook: dict[str, Any]) -> str:
    tool_input = hook.get("tool_input")
    if isinstance(tool_input, dict):
        return str(tool_input.get("command") or "")
    return ""


def shell_words(command: str) -> list[str]:
    try:
        return shlex.split(command)
    except ValueError:
        return []


def count_recruited_agents(state: dict[str, Any]) -> int:
    return sum(1 for meta in state.get("agents", {}).values() if meta.get("source") == "maestri")


def evaluate_pre_tool_policy(state: dict[str, Any], hook: dict[str, Any]) -> dict[str, str]:
    command = extract_bash_command(hook)
    words = shell_words(command)
    if not words or words[0] != "maestri":
        return {"behavior": "allow", "reason": "Maestri Autopilot observed a non-Maestri Bash command."}

    subcommand = words[1] if len(words) > 1 else ""
    if subcommand == "recruit":
        max_agents = state.get("max_agents")
        current_count = count_recruited_agents(state)
        if isinstance(max_agents, int) and current_count >= max_agents:
            return {
                "behavior": "deny",
                "reason": f"Recruit blocked: mission cap is {max_agents} active Maestri agents.",
            }
        if len(words) >= 3 and words[2] in state.get("agents", {}):
            return {"behavior": "deny", "reason": f"Recruit blocked: agent `{words[2]}` already exists in mission state."}
        return {"behavior": "allow", "reason": "Recruit is within the Maestri Autopilot cap."}

    if subcommand == "dismiss":
        if state.get("status") != "complete" and not state.get("policy", {}).get("allow_dismiss_before_complete"):
            return {
                "behavior": "deny",
                "reason": "Dismiss blocked during an active mission. Mark the mission complete or set policy.allow_dismiss_before_complete first.",
            }
        return {"behavior": "allow", "reason": "Dismiss allowed by mission policy."}

    if subcommand == "connect":
        return {"behavior": "allow", "reason": "Connect is allowed; keep the shared note and peer topology documented."}

    return {"behavior": "allow", "reason": f"Maestri `{subcommand}` command observed."}


def tool_response_text(hook: dict[str, Any]) -> str:
    response = hook.get("tool_response")
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("output", "stdout", "text"):
            if isinstance(response.get(key), str):
                return response[key]
        return json.dumps(response)
    return str(response)


def parse_maestri_list(output: str) -> dict[str, dict[str, str]]:
    agents: dict[str, dict[str, str]] = {}
    in_connected = False
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("Connected agents:"):
            in_connected = True
            continue
        if in_connected and stripped.startswith("- name:"):
            match = re.search(r'name:\s*"([^"]+)".*role:\s*"([^"]*)"', stripped)
            if match:
                agents[match.group(1)] = {"role": match.group(2), "source": "maestri", "status": "known"}
            continue
        if in_connected and stripped and not stripped.startswith("-"):
            in_connected = False
    return agents


def observe_post_tool(state: dict[str, Any], hook: dict[str, Any]) -> str:
    command = extract_bash_command(hook)
    words = shell_words(command)
    response_text = tool_response_text(hook)
    if not words:
        append_event(state, "post_tool_use", {"command": ""})
        return "Maestri Autopilot did not see a shell command to record."

    if words[:2] == ["maestri", "list"]:
        parsed_agents = parse_maestri_list(response_text)
        for name, meta in parsed_agents.items():
            existing = state.setdefault("agents", {}).setdefault(name, {})
            existing.update(meta)
            existing["last_seen"] = utc_now()
        append_event(state, "maestri_list", {"agents": sorted(parsed_agents)})
        return f"Maestri Autopilot recorded {len(parsed_agents)} connected Maestri agent(s)."

    if words[:2] == ["maestri", "check"] and len(words) >= 3:
        agent_name = words[2]
        state.setdefault("agents", {}).setdefault(agent_name, {"source": "maestri"})["last_check"] = utc_now()
        state.setdefault("counters", {})["maestri_checks"] = state.setdefault("counters", {}).get("maestri_checks", 0) + 1
        append_event(state, "maestri_check", {"agent": agent_name, "chars": len(response_text)})
        return f"Maestri Autopilot recorded a status check for `{agent_name}`."

    if words[:2] == ["maestri", "ask"]:
        counters = state.setdefault("counters", {})
        if "--batch" in words:
            counters["maestri_batches"] = counters.get("maestri_batches", 0) + 1
            append_event(state, "maestri_ask_batch", {"chars": len(command)})
            return "Maestri Autopilot recorded a parallel batch dispatch. Review every returned agent result before integrating."
        counters["maestri_asks"] = counters.get("maestri_asks", 0) + 1
        target = words[2] if len(words) >= 3 else "unknown"
        append_event(state, "maestri_ask", {"target": target, "chars": len(command)})
        return f"Maestri Autopilot recorded a delegated prompt to `{target}`."

    if words[:2] == ["maestri", "recruit"] and len(words) >= 3:
        name = words[2]
        state.setdefault("agents", {}).setdefault(name, {"source": "maestri"})["last_recruit_command"] = utc_now()
        append_event(state, "maestri_recruit", {"agent": name})
        return f"Maestri Autopilot recorded recruit `{name}`. Assign a non-overlapping task before recruiting more."

    append_event(state, "post_tool_use", {"command": command[:200]})
    return "Maestri Autopilot recorded the shell result."


def active_task_names(state: dict[str, Any]) -> list[str]:
    return [
        name
        for name, task in state.get("tasks", {}).items()
        if task.get("status") not in {"complete", "cancelled", "merged"}
    ]


def evaluate_stop(state: dict[str, Any], hook: dict[str, Any]) -> dict[str, Any]:
    if state.get("status") == "complete":
        return {"continue": True}
    if hook.get("stop_hook_active"):
        return {
            "continue": True,
            "systemMessage": "Maestri Autopilot allowed this stop because a Stop-hook continuation already ran for the current turn.",
        }

    if missing_intake_fields(state):
        reason = (
            "Maestri Autopilot intake is incomplete. Ask the user for the long-horizon goal, success criteria, "
            "max agents, allowed presets/types, allowed roles, worktree policy, and commit policy. Do not recruit yet."
        )
    else:
        tasks = active_task_names(state)
        if tasks:
            reason = (
                "Continue Maestri Autopilot orchestration. Check connected agents, answer blockers, validate completed work, "
                f"review active tasks ({', '.join(tasks)}), update the mission ledger, and reassign idle agents."
            )
        elif not state.get("agents"):
            reason = (
                "Continue Maestri Autopilot orchestration. Run `maestri list`, create shared mission/progress notes, "
                "recruit within the cap, and dispatch disjoint long-horizon assignments."
            )
        else:
            reason = (
                "Continue Maestri Autopilot validation. Review subordinate outputs, run the required checks, integrate "
                "or reject worktree changes, update progress notes, and mark mission status complete only when all success criteria are met."
            )
    state.setdefault("counters", {})["stop_continuations"] = state.setdefault("counters", {}).get("stop_continuations", 0) + 1
    return {"decision": "block", "reason": reason}


def subagent_start_context(hook: dict[str, Any]) -> str:
    agent_type = hook.get("agent_type", "subagent")
    return (
        f"Maestri Autopilot worker context for `{agent_type}`: run `maestri list` before asking peers, stay inside your assigned "
        "scope, do not overlap edits made by other agents, commit atomic changes when instructed, record changed files and validation "
        "results, and ask the orchestrator via Maestri when blocked."
    )


def evaluate_subagent_stop(hook: dict[str, Any]) -> dict[str, Any]:
    if hook.get("stop_hook_active"):
        return {"continue": True}
    message = str(hook.get("last_assistant_message") or "").lower()
    required = ["changed", "validation"]
    missing = [word for word in required if word not in message]
    if missing:
        return {
            "decision": "block",
            "reason": (
                "Run one more focused completion pass: report changed files, validation commands/results, remaining risks, "
                "and whether the task is ready for orchestrator integration."
            ),
        }
    return {"continue": True}


def render_status(state: dict[str, Any]) -> str:
    lines = [
        f"status: {state.get('status')}",
        f"goal: {state.get('goal') or '(unset)'}",
        f"max_agents: {state.get('max_agents') or '(unset)'}",
        f"agents: {', '.join(sorted(state.get('agents', {}))) or '(none)'}",
        f"active_tasks: {', '.join(active_task_names(state)) or '(none)'}",
        f"missing_intake: {', '.join(missing_intake_fields(state)) or '(none)'}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maestri Autopilot mission-state helper.")
    parser.add_argument("--session-id", default="manual")
    parser.add_argument("--data-dir", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize or update mission state from intake text.")
    init_parser.add_argument("--text", required=True)

    subparsers.add_parser("status", help="Print mission status.")
    subparsers.add_parser("intake-template", help="Print the required intake template.")

    args = parser.parse_args(argv)
    data_dir = args.data_dir or plugin_data_dir()
    path = state_path(data_dir, args.session_id)
    state = load_state(path, args.session_id)

    if args.command == "init":
        changed = merge_intake_prompt(state, args.text)
        append_event(state, "manual_init", {"changed": changed})
        save_state(path, state)
        print(render_status(state))
        return 0

    if args.command == "status":
        print(render_status(state))
        return 0

    if args.command == "intake-template":
        print(INTAKE_TEMPLATE)
        return 0

    return 2


INTAKE_TEMPLATE = """Goal:
Success criteria:
- 
Max agents:
Allowed presets: Codex, Claude Code
Allowed roles: Technical Research & Investigation, Rapid Implementation Engineer, Code Review & Validation
Worktree policy: one disjoint worktree per implementation worker
Commit policy: workers commit atomic changes before handoff; orchestrator validates before merge
"""


if __name__ == "__main__":
    raise SystemExit(main())
