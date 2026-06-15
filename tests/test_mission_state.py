from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mission_state import (  # noqa: E402
    default_state,
    evaluate_pre_tool_policy,
    evaluate_stop,
    merge_intake_prompt,
    missing_intake_fields,
    observe_post_tool,
    parse_intake_text,
)


class MissionStateTests(unittest.TestCase):
    def test_parse_intake_text(self) -> None:
        parsed = parse_intake_text(
            """Goal: ship the feature
Success criteria:
- tests pass
- docs updated
Max agents: 4
Allowed presets: Codex, Claude Code
Allowed roles: Rapid Implementation Engineer, Code Review & Validation
Worktree policy: one per worker
Commit policy: atomic commits
"""
        )
        self.assertEqual(parsed["goal"], "ship the feature")
        self.assertEqual(parsed["success_criteria"], ["tests pass", "docs updated"])
        self.assertEqual(parsed["max_agents"], 4)
        self.assertEqual(parsed["allowed_presets"], ["Codex", "Claude Code"])
        self.assertEqual(parsed["worktree_policy"], "one per worker")

    def test_merge_intake_moves_to_planning(self) -> None:
        state = default_state("s1", "/tmp/repo")
        changed = merge_intake_prompt(state, "Goal: ship\nMax agents: 2")
        self.assertEqual(changed, ["goal", "max_agents"])
        self.assertEqual(state["status"], "planning")
        self.assertNotIn("goal", missing_intake_fields(state))
        self.assertNotIn("max_agents", missing_intake_fields(state))

    def test_recruit_policy_blocks_over_cap(self) -> None:
        state = default_state("s1")
        state["max_agents"] = 1
        state["agents"] = {"A": {"source": "maestri"}}
        hook = {"tool_input": {"command": 'maestri recruit "B" --role "Rapid Implementation Engineer"'}}
        decision = evaluate_pre_tool_policy(state, hook)
        self.assertEqual(decision["behavior"], "deny")
        self.assertIn("cap", decision["reason"])

    def test_dismiss_policy_blocks_active_mission(self) -> None:
        state = default_state("s1")
        state["status"] = "planning"
        hook = {"tool_input": {"command": 'maestri dismiss "A"'}}
        decision = evaluate_pre_tool_policy(state, hook)
        self.assertEqual(decision["behavior"], "deny")

    def test_observe_maestri_list_records_agents(self) -> None:
        state = default_state("s1")
        hook = {
            "tool_input": {"command": "maestri list"},
            "tool_response": {
                "stdout": 'Connected agents:\n  - name: "Codex", role: "Chief Orchestrator & Quality Controller"\n'
            },
        }
        message = observe_post_tool(state, hook)
        self.assertIn("1 connected", message)
        self.assertIn("Codex", state["agents"])

    def test_stop_continues_incomplete_mission(self) -> None:
        state = default_state("s1")
        decision = evaluate_stop(state, {"stop_hook_active": False})
        self.assertEqual(decision["decision"], "block")
        self.assertIn("intake", decision["reason"].lower())

    def test_stop_allows_after_already_continued(self) -> None:
        state = default_state("s1")
        decision = evaluate_stop(state, {"stop_hook_active": True})
        self.assertTrue(decision["continue"])
        self.assertNotIn("decision", decision)


class WorktreeManagerTests(unittest.TestCase):
    def test_worktree_dry_run(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "worktree_manager.py"),
                "create",
                "--repo",
                str(ROOT),
                "--mission",
                "Demo Mission",
                "--agent",
                "Forge",
                "--task",
                "Parser Slice",
                "--dry-run",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("git worktree add -b maestri/demo-mission/forge-parser-slice", result.stdout)


class HookScriptTests(unittest.TestCase):
    def run_hook(self, script: str, payload: dict[str, object], data_dir: Path) -> dict[str, object]:
        env = os.environ.copy()
        env["PLUGIN_ROOT"] = str(ROOT)
        env["PLUGIN_DATA"] = str(data_dir)
        result = subprocess.run(
            [sys.executable, str(ROOT / "hooks" / script)],
            input=json.dumps(payload),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_session_start_hook_outputs_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_hook(
                "session_start.py",
                {"session_id": "s1", "cwd": str(ROOT), "source": "startup", "hook_event_name": "SessionStart"},
                Path(tmp),
            )
        self.assertEqual(output["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("Maestri Autopilot is active", output["hookSpecificOutput"]["additionalContext"])

    def test_user_prompt_submit_hook_records_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_hook(
                "user_prompt_submit.py",
                {
                    "session_id": "s2",
                    "cwd": str(ROOT),
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "Goal: ship\nMax agents: 2",
                },
                Path(tmp),
            )
        self.assertIn("intake", output["hookSpecificOutput"]["additionalContext"].lower())

    def test_subagent_stop_blocks_incomplete_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_hook(
                "subagent_stop.py",
                {
                    "session_id": "s3",
                    "hook_event_name": "SubagentStop",
                    "agent_type": "worker",
                    "last_assistant_message": "Done.",
                    "stop_hook_active": False,
                },
                Path(tmp),
            )
        self.assertEqual(output["decision"], "block")


if __name__ == "__main__":
    unittest.main()
