# Development Workflow

## Starting work

1. Read [HABITS.md](../HABITS.md), [AGENTS.md](../AGENTS.md), and `.ai-stage`. Load the current stage record and only the relevant project material. Read the [Git workflow](git.md) before branch, version, commit, or merge work.
2. Check the branch, `git status --short`, and `git submodule status`. Distinguish existing work from this task. Follow the [authorization rules](constraints.md) for remote operations; a status check does not imply pulling, switching, resetting, or updating submodules.
3. Reread the saved target before editing it. If new edits appear during the task, inspect the diff and preserve them.
4. Understand the scope and implementation, share the approach, make authorized changes, and verify at a level that fits the risk. Label unresolved facts as pending confirmation. Sync affected user documentation and project records.
5. Report what changed, the commands and results, any failures or skips, and what remains unverified.

## Project commands

Run from the repository root. Make invokes Python tooling via `uv run --frozen`.

| Command | What it checks or does |
| --- | --- |
| `make sync` | Synchronizes the root development environment from the lockfile without updating submodule pins or configuring the host or hardware |
| `make lint` | Checks Ruff lint and formatting in the root project and contract, plus shell syntax for each script |
| `make test` | Runs root and contract pytest, including simulated HAL/IPC and converter readback when the converter environment is available; pytest reports skips |
| `make docs` | Checks required files, agent routing, paired language pages, relative links and anchors, and bilingual executable examples without network access |
| `make verify` | Runs lint, docs, and tests; any failure returns a nonzero status |

Full setup uses `./scripts/setup.sh` and `uv run agilex-data-collection setup`. Use the setup script's `--skip-submodules` flag to preserve local submodule changes. Explain any network or system access needed for setup. Make verification and CI do not run hardware commands.

For cross-repository changes, validate the affected submodules as described in their READMEs and run real converter RGB-D readback when the change affects that integration. For browser changes, also run:

```bash
uv run --project third-party/agilex-adapters --frozen --extra app pytest third-party/agilex-adapters/tests -q
```

Root CI uses the same Make targets as local development. The root has no mypy, coverage threshold, or pre-commit check. CI without a separate converter environment skips that integration; do not report full multi-repository acceptance from that run.

## Stages and evidence

- Keep exactly one of `PLANNING`, `CODING`, `TESTING`, or `DEPLOY` in `.ai-stage`. When the stage changes, update its document and the root routing index. Retain previous records; create no files for stages that have not started.
- Use the stage file routed by [AGENTS.md](../AGENTS.md) for current conclusions, evidence, open items, and any authorization boundaries. Separate software simulation, read-only hardware checks, operator logs, and actual motion acceptance. A stage label does not establish acceptance or release authorization.
- When the user reports 15% remaining on the five-hour AI allowance, stop new implementation and record completed work, checks, failures, and next steps in the current stage document. Do not claim to monitor the allowance automatically.

## Skills and records

- Load skills through the [skill index](../SKILLS.md). Give the selected skill the objective, scope, acceptance criteria, project commands, and output locations. Adapt examples to actual project commands. If a skill is unavailable, say so and continue the checks you can perform under the project rules.
- Before working, verify that the installed gstack has a `bin/` directory. Check `$GSTACK_ROOT` first if set, then the actual installation path. If missing, stop and explain how to install it. For web interaction with gstack use its installed `/browse` entry. Preserve `.claude/settings.json` and `check-gstack.cjs`; report missing Node or hook errors instead of bypassing them. Older gstack setup must not overwrite project routing or bridge files.
- Put lasting decisions in `docs/decisions/`, specs and separate linked plans in `docs/specs/`, and reviews in `docs/reviews/`, all under `.agents/`. Link from the stage record rather than duplicating decision text or checklists. Keep tool-owned task files in the tool's supported format and location. Preserve evidence still cited by project documents.
- Preserve `HABITS.md` as supplied and record the reason, scope, and basis of any authorized change when applying it to the project. Temporary requests and skill suggestions do not automatically become permanent or transfer to another project.
- For delivery follow the [Git workflow](git.md) and [authorization rules](constraints.md). The PR template records the candidate version, automated verification, field results, and risks.
