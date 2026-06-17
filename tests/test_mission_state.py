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
    activate_autopilot,
    default_state,
    evaluate_pre_tool_policy,
    evaluate_stop,
    intake_context,
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

    def test_parse_numbered_intake_text(self) -> None:
        parsed = parse_intake_text(
            """1. the long horizon task is to make BakerBoy fully operational
2. see above
3. 4 - can be codex and/or claude
4. no restriction
5. no preferences
6. as needed
7. orchestrator reviews, commits, and pushes
"""
        )
        self.assertEqual(parsed["goal"], "the long horizon task is to make BakerBoy fully operational")
        self.assertEqual(parsed["success_criteria"], ["see above"])
        self.assertEqual(parsed["max_agents"], 4)
        self.assertEqual(parsed["allowed_presets"], ["any"])
        self.assertEqual(parsed["allowed_roles"], ["any"])
        self.assertEqual(parsed["worktree_policy"], "as needed")
        self.assertEqual(parsed["commit_policy"], "orchestrator reviews, commits, and pushes")

    def test_merge_intake_moves_to_planning(self) -> None:
        state = default_state("s1", "/tmp/repo")
        activate_autopilot(state)
        changed = merge_intake_prompt(state, "Goal: ship\nMax agents: 2")
        self.assertEqual(changed, ["goal", "max_agents"])
        self.assertEqual(state["status"], "planning")
        self.assertNotIn("goal", missing_intake_fields(state))
        self.assertNotIn("max_agents", missing_intake_fields(state))

    def test_intake_context_includes_ten_minute_delegation_gate(self) -> None:
        state = default_state("s1", "/tmp/repo")
        activate_autopilot(state)
        message = intake_context(state, [])
        self.assertIn("10-minute delegation gate", message)
        self.assertIn("under 10 minutes", message)
        self.assertIn("bundle it into a larger meaningful workstream", message)

    def test_recruit_policy_blocks_over_cap(self) -> None:
        state = default_state("s1")
        activate_autopilot(state)
        state["max_agents"] = 1
        state["agents"] = {"A": {"source": "maestri"}}
        hook = {"tool_input": {"command": 'maestri recruit "B" --role "Rapid Implementation Engineer"'}}
        decision = evaluate_pre_tool_policy(state, hook)
        self.assertEqual(decision["behavior"], "deny")
        self.assertIn("cap", decision["reason"])

    def test_dismiss_policy_blocks_active_mission(self) -> None:
        state = default_state("s1")
        activate_autopilot(state)
        state["status"] = "planning"
        hook = {"tool_input": {"command": 'maestri dismiss "A"'}}
        decision = evaluate_pre_tool_policy(state, hook)
        self.assertEqual(decision["behavior"], "deny")

    def test_observe_maestri_list_records_agents(self) -> None:
        state = default_state("s1")
        activate_autopilot(state)
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
        activate_autopilot(state)
        decision = evaluate_stop(state, {"stop_hook_active": False})
        self.assertEqual(decision["decision"], "block")
        self.assertIn("intake", decision["reason"].lower())

    def test_stop_allows_inactive_mission(self) -> None:
        state = default_state("s1")
        decision = evaluate_stop(state, {"stop_hook_active": False})
        self.assertTrue(decision["continue"])
        self.assertNotIn("decision", decision)

    def test_stop_allows_after_already_continued(self) -> None:
        state = default_state("s1")
        decision = evaluate_stop(state, {"stop_hook_active": True})
        self.assertTrue(decision["continue"])
        self.assertNotIn("decision", decision)

    def test_stop_hook_active_still_blocks_active_tasks(self) -> None:
        state = default_state("s1")
        activate_autopilot(state)
        state.update(
            {
                "goal": "ship",
                "success_criteria": ["tests pass"],
                "max_agents": 1,
                "agents": {"A": {"source": "maestri"}},
                "tasks": {"long-track": {"status": "assigned"}},
            }
        )
        decision = evaluate_stop(state, {"stop_hook_active": True})
        self.assertEqual(decision["decision"], "block")
        self.assertIn("Stop-hook continuation", decision["reason"])
        self.assertIn("long-track", decision["reason"])

    def test_stop_blocks_terminal_tasks_without_success_criteria(self) -> None:
        state = default_state("s1")
        activate_autopilot(state)
        state.update(
            {
                "goal": "ship",
                "success_criteria": ["tests pass"],
                "max_agents": 1,
                "agents": {"A": {"source": "maestri"}},
                "tasks": {"long-track": {"status": "complete"}},
            }
        )
        decision = evaluate_stop(state, {"stop_hook_active": False})
        self.assertEqual(decision["decision"], "block")
        self.assertIn("success criteria", decision["reason"].lower())

    def test_stop_allows_terminal_tasks_with_success_criteria(self) -> None:
        state = default_state("s1")
        activate_autopilot(state)
        state.update(
            {
                "goal": "ship",
                "success_criteria": ["tests pass"],
                "max_agents": 1,
                "agents": {"A": {"source": "maestri"}},
                "tasks": {"long-track": {"status": "complete"}},
                "completion": {"success_criteria_reached": True},
            }
        )
        decision = evaluate_stop(state, {"stop_hook_active": True})
        self.assertTrue(decision["continue"])
        self.assertNotIn("decision", decision)

    def test_stop_deactivates_orphan_project_worker_state(self) -> None:
        state = default_state("s1", "/Users/example/repo/.maestri/roles/worker")
        activate_autopilot(state)
        state["agents"] = {"Codex": {"source": "maestri"}}
        decision = evaluate_stop(state, {"stop_hook_active": False})
        self.assertEqual(decision["continue"], True)
        self.assertNotIn("decision", decision)
        self.assertFalse(state["autopilot_active"])
        self.assertEqual(state["status"], "inactive")

    def test_stop_still_blocks_orchestrator_intake(self) -> None:
        state = default_state("s1", str(Path.home() / ".maestri" / "roles" / "orchestrator"))
        activate_autopilot(state)
        decision = evaluate_stop(state, {"stop_hook_active": False})
        self.assertEqual(decision["decision"], "block")
        self.assertIn("intake", decision["reason"].lower())


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


class InstallerTests(unittest.TestCase):
    def test_plugin_version_is_hook_cache_safe(self) -> None:
        manifest = json.loads((ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], "0.1.0")
        self.assertNotIn("+", manifest["version"])

    def test_personal_marketplace_installer(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "install_personal_marketplace.py"),
                    "--source",
                    str(ROOT),
                    "--home",
                    tmp,
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            target = Path(tmp) / "plugins" / "maestri-autopilot"
            marketplace = Path(tmp) / ".agents" / "plugins" / "marketplace.json"
            self.assertTrue((target / ".codex-plugin" / "plugin.json").is_file())
            payload = json.loads(marketplace.read_text(encoding="utf-8"))
            entries = [entry for entry in payload["plugins"] if entry["name"] == "maestri-autopilot"]
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["source"]["path"], "./plugins/maestri-autopilot")


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

    def test_session_start_hook_is_silent_when_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_hook(
                "session_start.py",
                {"session_id": "s1", "cwd": str(ROOT), "source": "startup", "hook_event_name": "SessionStart"},
                Path(tmp),
            )
        self.assertEqual(output, {"continue": True})

    def test_user_prompt_submit_hook_is_silent_without_activation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_hook(
                "user_prompt_submit.py",
                {
                    "session_id": "s2",
                    "cwd": str(ROOT),
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "What is the status?",
                },
                Path(tmp),
            )
        self.assertEqual(output, {"continue": True})

    def test_user_prompt_submit_hook_activates_and_records_intake(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = self.run_hook(
                "user_prompt_submit.py",
                {
                    "session_id": "s2",
                    "cwd": str(ROOT),
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "Use Maestri Autopilot for this project.\nGoal: ship\nMax agents: 2",
                },
                Path(tmp),
            )
        self.assertIn("intake", output["hookSpecificOutput"]["additionalContext"].lower())

    def test_stop_hook_fails_open_on_corrupt_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "missions" / "s4.json"
            state_file.parent.mkdir(parents=True)
            state_file.write_text("{not json", encoding="utf-8")
            output = self.run_hook(
                "stop_orchestrator.py",
                {"session_id": "s4", "hook_event_name": "Stop", "stop_hook_active": False},
                Path(tmp),
            )
        self.assertEqual(output, {"continue": True})

    def test_stop_hook_deactivates_orphan_worker_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "missions" / "s5.json"
            state_file.parent.mkdir(parents=True)
            state_file.write_text(
                json.dumps(
                    {
                        "status": "awaiting_intake",
                        "autopilot_active": True,
                        "cwd": "/repo/.maestri/roles/worker",
                        "agents": {"Codex": {"source": "maestri"}},
                        "tasks": {},
                    }
                ),
                encoding="utf-8",
            )
            output = self.run_hook(
                "stop_orchestrator.py",
                {"session_id": "s5", "hook_event_name": "Stop", "stop_hook_active": False},
                Path(tmp),
            )
            state = json.loads(state_file.read_text(encoding="utf-8"))
        self.assertEqual(output, {"continue": True})
        self.assertFalse(state["autopilot_active"])
        self.assertEqual(state["status"], "inactive")

    def test_subagent_stop_blocks_incomplete_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "missions" / "s3.json"
            state_file.parent.mkdir(parents=True)
            state_file.write_text(
                json.dumps({"status": "planning", "autopilot_active": True}),
                encoding="utf-8",
            )
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

    def test_subagent_stop_hook_active_still_blocks_incomplete_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "missions" / "s6.json"
            state_file.parent.mkdir(parents=True)
            state_file.write_text(
                json.dumps({"status": "planning", "autopilot_active": True}),
                encoding="utf-8",
            )
            output = self.run_hook(
                "subagent_stop.py",
                {
                    "session_id": "s6",
                    "hook_event_name": "SubagentStop",
                    "agent_type": "worker",
                    "last_assistant_message": "Done.",
                    "stop_hook_active": True,
                },
                Path(tmp),
            )
        self.assertEqual(output["decision"], "block")
        self.assertIn("completion report", output["reason"])


if __name__ == "__main__":
    unittest.main()
