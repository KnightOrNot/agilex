# Git Workflow

## Branches and acceptance

- `main` holds released, stable code. Do not commit directly to it, bypass branch protection, or force push. Merge only through an authorized release or hotfix workflow.
- `dev` integrates verified work. For a new iteration, synchronize with remote `dev` while preserving existing changes, then start an independent `dev-<task>` branch. Keep edits, verification, and commits on that branch.
- Prepare the candidate version, changelog, and description. Run `make lint`, `make test`, and any required checks. Resolve failures and disclose checks that did not run before committing.
- Provide the candidate version, changes, automated results, and field test steps in the current conversation. Wait for explicit confirmation that field testing passed before any commit, including docs, plans, or checkpoints, or any merge. Silence is not acceptance.
- After confirmation, commit the implementation, tests, version, and related docs on the task branch, then merge into `dev`. If `dev` advances or conflict resolution changes the verified result, rerun relevant checks and obtain field confirmation again when the change affects it.
- Merging into `dev` does not release to `main`, tag a release, or deploy. Release and hotfix merge details and branch cleanup rules still need confirmation. Prefer a fast-forward when possible; review diverged branches before deciding. Branch deletion requires explicit authorization.

## Versions and change records

- Increment the final component of `project.version` once per patch iteration before committing. Fixes, test retries, waiting for acceptance, and merging do not increment it again. Check for version collisions if `dev` moves.
- Record actual changes in the English changelog and preserve history. Mark an unreleased candidate as such. Describe current capabilities accurately in the English `project.description`, and update lockfiles only through uv.
- Use a short English imperative and a conventional prefix for a commit. Keep one independently verifiable change together with its tests and documentation. A PR describes the change, version, verification, field results, risks, and related issues.
- Skill defaults do not override the version, acceptance, commit, or release rules.

## Submodules and publishing

- For normal initialization use `git submodule sync --recursive` and `git submodule update --init` to check out the parent pins. Use `--remote --merge` only for an explicitly requested upgrade. The five original submodules use `main` for such upgrades; `agilex-contract` tracks `dev`. Normal initialization still checks out the recorded commit.
- When relocating a submodule, back up and recreate its `.venv` rather than rewriting shebangs. Parent, child, and neighboring checkouts do not synchronize automatically.
- Test the submodules, obtain authorization to commit and push them, update the parent gitlinks, verify the parent, then publish the parent if authorized. A published gitlink must refer to a commit reachable by users.
- Keep local environments, caches, build output, environment or credential files, and capture data out of Git. Track the shared `.agents/` docs, routing index, hooks, and workflows.

## Historical exceptions

- **2026-11-08:** The user authorized the final direct commit and push to `main` for the previous HABITS migration, its checks, and version 0.2.1. The same commit initialized `dev`. This did not assert a hardware result or change the five original submodule pins. See [ADR 0003](docs/decisions/0003-habits-branch-gates.md).
- **2026-11-11:** The user authorized distributing the 0.2.2 candidate before field testing so the lab machine could pull it from GitHub. The requested contract repository was `git@github.com:KnightOrNot/agilex-contract.git`. The contract went to its `dev` first; the parent pinned that revision, was verified, and fast-forwarded `dev`. The original five pins and existing `main` branches stayed unchanged; no release tag or field acceptance was implied. See the [testing record](docs/stages/testing.md).

Neither exception applies to later iterations. See the [validation baseline](docs/decisions/0001-baseline-and-validation.md) for earlier Git and environment decisions.
