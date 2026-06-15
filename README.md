# Maestri Autopilot

Maestri Autopilot is a Codex plugin for long-horizon Maestri orchestration. It packages:

- a Codex skill for mission intake, planning, delegation, monitoring, validation, and completion gates
- plugin-bundled lifecycle hooks for startup context, command guardrails, mission-ledger updates, worker completion checks, and Stop-hook continuation
- Python helpers for mission state, Maestri inventory, worker prompts, and deterministic worktree paths

## Why It Exists

Maestri gives Codex a canvas with connected agents, notes, and portals. This plugin makes a main orchestrator use that surface consistently:

- collect a long-horizon goal and agent budget
- recruit only useful missing roles
- parallelize across disjoint worktrees or write scopes
- keep shared notes and state in sync
- query idle agents and answer blockers
- require progress, commits, and validation before completion

## Install Shape

The plugin follows the Codex plugin layout:

```text
.codex-plugin/plugin.json
skills/maestri-autopilot/SKILL.md
hooks/hooks.json
hooks/*.py
scripts/*.py
references/*.md
```

Codex can discover plugin hooks from `hooks/hooks.json` when the plugin is enabled. Review and trust the hooks with `/hooks` before relying on them in a session.

## Basic Use

Ask Codex:

```text
Use Maestri Autopilot for this project.
```

The orchestrator should collect:

```text
Goal:
Success criteria:
- 
Max agents:
Allowed presets: Codex, Claude Code
Allowed roles: Technical Research & Investigation, Rapid Implementation Engineer, Code Review & Validation
Worktree policy: one disjoint worktree per implementation worker
Commit policy: workers commit atomic changes before handoff; orchestrator validates before merge
```

Then it should run:

```bash
maestri list
maestri preset list
maestri role list
python3 "$PLUGIN_ROOT/scripts/maestroctl.py" inventory
```

## Hook Behavior

- `SessionStart`: creates/loads mission state and injects startup context.
- `UserPromptSubmit`: captures intake fields when they are present in the prompt.
- `PreToolUse`: guards `maestri recruit`, `maestri dismiss`, and related shell commands.
- `PostToolUse`: records `maestri list`, `ask`, `ask --batch`, `check`, and `recruit` outcomes.
- `SubagentStart`: adds worker discipline to Codex subagents.
- `SubagentStop`: asks incomplete Codex subagent reports to do one more pass.
- `Stop`: continues active missions when intake, delegation, review, validation, or integration is incomplete.

## Development

Run tests:

```bash
python3 -m unittest discover -s tests
```

Validate plugin metadata:

```bash
python3 /Users/ivg/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .
```

Run helper commands:

```bash
python3 scripts/mission_state.py --session-id demo intake-template
python3 scripts/maestroctl.py --session-id demo init --text "Goal: demo\nMax agents: 2"
python3 scripts/worktree_manager.py create --mission demo --agent Forge --task parser --dry-run
```
