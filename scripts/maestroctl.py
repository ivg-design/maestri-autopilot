#!/usr/bin/env python3
"""Convenience commands for running Maestri Autopilot from a shell."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

from mission_state import (
    INTAKE_TEMPLATE,
    append_event,
    load_state,
    merge_intake_prompt,
    plugin_data_dir,
    render_status,
    save_state,
    state_path,
)


def run_maestri(args: list[str]) -> subprocess.CompletedProcess[str]:
    binary = shutil.which("maestri")
    if not binary:
        raise RuntimeError("maestri CLI was not found on PATH.")
    return subprocess.run([binary, *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def require_success(result: subprocess.CompletedProcess[str]) -> str:
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or f"command failed with {result.returncode}")
    return result.stdout


def command_inventory() -> int:
    for label, args in (
        ("list", ["list"]),
        ("presets", ["preset", "list"]),
        ("roles", ["role", "list"]),
    ):
        print(f"## {label}")
        print(require_success(run_maestri(args)).rstrip())
        print()
    return 0


def command_init(args: argparse.Namespace) -> int:
    path = state_path(args.data_dir or plugin_data_dir(), args.session_id)
    state = load_state(path, args.session_id)
    changed = merge_intake_prompt(state, args.text)
    append_event(state, "maestroctl_init", {"changed": changed})
    save_state(path, state)
    print(render_status(state))
    return 0


def command_status(args: argparse.Namespace) -> int:
    path = state_path(args.data_dir or plugin_data_dir(), args.session_id)
    state = load_state(path, args.session_id)
    print(render_status(state))
    if args.json:
        print(json.dumps(state, indent=2, sort_keys=True))
    return 0


def command_worker_prompt(args: argparse.Namespace) -> int:
    prompt = f"""You are working under Maestri Autopilot for mission `{args.session_id}`.

Assignment:
{args.assignment}

Owned paths:
{args.owned_paths or "Use only the paths explicitly granted by the orchestrator."}

Rules:
- Run `maestri list` before asking peers or the orchestrator for help.
- Work only inside your assigned worktree or write scope.
- Do not revert edits made by other agents.
- Commit atomic changes if this task modifies files and the orchestrator's policy allows it.
- Report changed files, validation commands/results, remaining risks, and blockers.
- If blocked, ask the orchestrator with `maestri ask`.
"""
    print(prompt)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maestri Autopilot shell helper.")
    parser.add_argument("--session-id", default="manual")
    parser.add_argument("--data-dir", type=Path, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("inventory", help="Print Maestri agents, presets, and roles.")

    init_parser = subparsers.add_parser("init", help="Initialize mission state from intake text.")
    init_parser.add_argument("--text", required=True)

    status_parser = subparsers.add_parser("status", help="Print mission status.")
    status_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("intake-template", help="Print the mission intake template.")

    worker_parser = subparsers.add_parser("worker-prompt", help="Render a subordinate assignment prompt.")
    worker_parser.add_argument("--assignment", required=True)
    worker_parser.add_argument("--owned-paths", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "inventory":
        return command_inventory()
    if args.command == "init":
        return command_init(args)
    if args.command == "status":
        return command_status(args)
    if args.command == "intake-template":
        print(INTAKE_TEMPLATE)
        return 0
    if args.command == "worker-prompt":
        return command_worker_prompt(args)
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        print(f"maestroctl: {exc}", file=sys.stderr)
        raise SystemExit(1)
