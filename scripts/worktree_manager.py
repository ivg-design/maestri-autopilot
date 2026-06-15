#!/usr/bin/env python3
"""Small worktree helper for Maestri Autopilot implementation slices."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-").lower() or "slice"


def run(args: list[str], cwd: Path, dry_run: bool = False) -> int:
    if dry_run:
        print(" ".join(args))
        return 0
    return subprocess.run(args, cwd=cwd, check=False).returncode


def create_worktree(args: argparse.Namespace) -> int:
    repo = args.repo.resolve()
    base = args.base
    mission = slug(args.mission)
    agent = slug(args.agent)
    task = slug(args.task)
    branch = args.branch or f"maestri/{mission}/{agent}-{task}"
    worktree_root = (args.worktree_root or (repo / ".maestri" / "worktrees")).resolve()
    worktree_path = worktree_root / mission / f"{agent}-{task}"
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "worktree", "add", "-b", branch, str(worktree_path), base]
    result = run(cmd, cwd=repo, dry_run=args.dry_run)
    if result == 0:
        print(worktree_path)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create deterministic Maestri Autopilot git worktrees.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create")
    create.add_argument("--repo", type=Path, default=Path.cwd())
    create.add_argument("--mission", required=True)
    create.add_argument("--agent", required=True)
    create.add_argument("--task", required=True)
    create.add_argument("--base", default="HEAD")
    create.add_argument("--branch", default="")
    create.add_argument("--worktree-root", type=Path, default=None)
    create.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "create":
        return create_worktree(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
