---
name: maestri-autopilot
description: Orchestrate long-horizon Maestri agent teams with hook-backed mission state, shared notes, worktree isolation, validation loops, and autonomous continuation.
---

# Maestri Autopilot

Use this skill when the user wants a main Codex orchestrator to coordinate Maestri agents over a long-horizon task with minimal additional prompting.

## First Principles

- Treat the current Codex thread as the mission control room.
- Use Maestri for visible teammate topology: agents, notes, and portals.
- Use hooks only for explicit Autopilot sessions. The plugin is inactive by default; ordinary Codex work should not receive hook context or per-tool ledger updates.
- Use Stop-hook lifecycle pressure for active missions, not per-tool shell monitoring.
- Parallelize only across disjoint work scopes or read-only investigations.
- Keep one global mission ledger in `PLUGIN_DATA`, plus a human-readable Maestri note on the canvas.
- Prefer worktrees for implementation workers. If worktrees are unavailable, assign non-overlapping owned paths.
- Do not recruit duplicate roles when an existing connected teammate can cover the task.
- Delegate only meaningful long-horizon assignments. Before dispatching any subordinate task, ask: "Could I do this exact assignment myself in under 10 minutes, including validation and handoff?" If yes, do it yourself or combine it into a larger coherent workstream before delegating.
- When the user submits a new prompt during active mission work, add the request to the active todo list at the appropriate priority and sequence instead of abandoning the current task. Only break from the current task immediately when the user explicitly asks to stop, pause, switch, or work on the new prompt now.
- Do not mark the mission complete until validation has run and subordinate work has been reviewed.

## Mission Intake

At the beginning of the orchestrator session, ask the user for any missing fields:

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

If the user already provided enough information, proceed without asking again.

## Required Startup Commands

Run these before recruiting or delegating:

```bash
maestri list
maestri preset list
maestri role list
python3 "$PLUGIN_ROOT/scripts/maestroctl.py" inventory
```

If `PLUGIN_ROOT` is not available outside hook execution, resolve it to the installed plugin root or this repository root.

## Planning Workflow

1. Convert the goal into explicit milestones and success criteria.
2. Split the work into independent tracks:
   - research tracks: read-only, can overlap paths
   - implementation tracks: disjoint files/modules/worktrees
   - validation tracks: review-only or test-only
   - integration track: orchestrator-owned
3. Create or update a shared Maestri note named `mission-control` with:
   - goal
   - success criteria
   - roster
   - assignments
   - owned paths or worktrees
   - validation commands
   - integration queue
4. Recruit only missing roles, up to the cap.
5. Connect shared notes to each recruit.
6. Apply the 10-minute delegation gate to every proposed assignment. A task is delegable only if it is a real long-horizon slice with enough scope, ownership, and validation depth that the orchestrator could not reasonably finish it alone in under 10 minutes.
7. Dispatch independent work with `maestri ask --batch`.
8. Keep coding or validating locally while workers run.
9. When new user instructions arrive mid-stream, update the shared plan and `mission-control` note with the new or modified milestone before continuing, unless the user expressly redirects the current task.

## Delegation Rules

Subordinate agents are for substantial workstreams, not small chores. Before every `maestri ask` or `maestri ask --batch`, perform this gate:

1. Estimate whether the orchestrator could complete the assignment end-to-end in under 10 minutes.
2. If yes, do not delegate it as written. Either handle it directly or expand/bundle it into a meaningful owned workstream with real implementation, investigation, or validation depth.
3. If no, proceed only when the task has clear ownership, concrete deliverables, and a validation path.

Every worker prompt must include:

- exact assignment
- owned files, directories, or worktree
- expected output format
- commit policy
- validation command expectations
- instruction to run `maestri list`
- instruction to ask the orchestrator when blocked
- instruction not to revert unrelated changes

Use the helper when useful:

```bash
python3 "$PLUGIN_ROOT/scripts/maestroctl.py" worker-prompt \
  --session-id "$SESSION_ID" \
  --assignment "Implement the parser slice" \
  --owned-paths "src/parser/** tests/parser/**"
```

## Monitoring Loop

Repeat until done:

1. `maestri check` every active worker.
2. Read/update shared notes.
3. Answer worker questions.
4. Reassign idle workers.
5. Review completed diffs before integration.
6. Run focused validation.
7. Commit or merge only coherent, reviewed changes.
8. Update the mission ledger and `mission-control` note.

Use `maestri ask --batch` for independent status or follow-up prompts.

## Worktree Policy

For implementation work in Git repositories:

```bash
python3 "$PLUGIN_ROOT/scripts/worktree_manager.py" create \
  --repo /path/to/repo \
  --mission "<mission-id>" \
  --agent "<agent-name>" \
  --task "<slice-name>"
```

Assign each worker one worktree and one branch. Do not assign the same mutable branch to multiple worktrees.

## Completion Gate

The orchestrator may stop only when all are true:

- success criteria are satisfied or explicitly waived
- all worker outputs have been reviewed
- no active blockers/questions remain
- all implementation work is integrated, rejected, or documented as deferred
- validation commands have run or failures are documented
- final status is written to the mission note

If any gate is false, continue the loop instead of finalizing.
