# Maestri Autopilot Task Templates

## Batch Dispatch

```bash
maestri ask --batch '{
  "Scout": "Investigate the API boundary. Read-only. Report risks and implementation notes.",
  "Forge": "Implement slice A in worktree /path/to/worktree. Own src/a/** and tests/a/** only.",
  "Lens": "Review slice B diff. Do not edit files. Return findings with severity."
}'
```

## Worker Assignment

```text
Mission:

Assignment:

Owned scope:

Worktree:

Do:
- Run `maestri list`.
- Inspect the relevant code before editing.
- Keep changes inside the owned scope.
- Commit atomic changes if instructed.
- Report changed files and validation.

Do not:
- Revert unrelated changes.
- Edit outside the owned scope.
- Mark complete without validation output.
```

## Status Check

```text
Status check. Report:
- current state
- files touched
- validation run
- blockers/questions
- whether you are ready for review
```
