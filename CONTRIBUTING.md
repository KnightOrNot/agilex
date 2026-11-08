# Contributing

English | [简体中文](CONTRIBUTING.zh-CN.md)

## Development environment

The root uses stable main, integration dev and dedicated dev-<task> working branches. Do not edit main or dev directly. Child gitlinks remain pinned; prepare child development branches separately when needed. New browser application code belongs in src/agilex_data_collection and the independent adapters child, preserving legacy controller behavior. See [usage](docs/en/usage.md) and [architecture](docs/en/index.md).

uv manages Python 3.12, independent environments and frozen dependencies. GELLO/camera are root editable sources; do not install the SDK hardware stack, LeRobot or PyTorch into the root control environment.

```bash
./scripts/setup.sh --skip-system --skip-submodules
uv sync --frozen
uv run agilex-controller --help
```

Child development/CLI environments remain independent and do not implicitly extend another interpreter's path.

## Module ownership

| Module | Responsibility |
| --- | --- |
| cli.py | Parsing, dispatch and exit codes |
| configuration.py | TOML/CLI precedence, validation and paths |
| robot_client.py | Existing SDK wire protocol, timeouts/errors/cleanup |
| gello.py | Explicit leader calibration, direction and alignment |
| control.py | JS positioning, startup guards, rates, following and keys |
| recording.py | Raw v1/v2 sessions, bounded writers, save/discard/partial |
| camera.py | RGB-D lifecycle, preview subprocess and lossless image writers |
| workflow.py | Preflight, processes/signals, client composition, cleanup/conversion |

GELLO keeps its upstream reading interfaces. CAN/protection stays in SDK, acquisition/host clocks in camera, matching/conversion in converter. Do not import the GELLO application command module into controller.

## Changes

Use four spaces, public type annotations, snake_case functions/modules and PascalCase classes. Keep resources owned by the workflow and release previously acquired resources when later initialization fails.

Use monotonic scheduling/timing and wall clock for diagnosis. Raw observations follow the sent action; changing pairing semantics requires evaluating conversion/training. RPC waits are bounded; close interrupted/timed-out REQ sockets and use a fresh client for exit zeroing.

Bounded persistence failures stay visible/partial. Interrupted saving must not leave writers waiting forever. Clean hardware before expensive flushing/conversion; preserve JS cleanup without resetting or changing motion mode.

There are five shell entry points: setup and four thin wrappers. Do not duplicate runtime logic in them. Camera variants enable capture/preview, legacy variants stay camera-free. Pass calibration through DynamixelRobotConfig, not a library global port map.

## Validation

Run from the root:

```bash
make lint
make docs
make test
make verify
uv build
```

Tests cover configuration, SDK protocol, startup/JS limits, recording, signals and cleanup without physical devices. Converter integration uses its separate interpreter for real numerical/RGB/RGB-D conversion, video decoding and meter-depth readback. Missing converter environment is explicitly skipped:

```bash
uv run --frozen pytest -m integration
uv run --frozen pytest -m "not integration"
```

There is no global coverage threshold. Add meaningful regressions for behavioral changes, particularly errors, cancellation and data compatibility.

After GELLO changes, run its pytest from that checkout and its existing CI lint:

```bash
uv run --frozen ruff check src tests experiments scripts --select E9,F63,F7,F82
```

Preserve upstream style. Current GELLO uses agilex_gello_software and PyPI dynamixel-sdk 4.0.5; there is no required nested SDK, old gello namespace or offline upstream-audit command. Shared dependency changes update locks through uv; SDK changes use its own README checks.

## Submodules

A neighboring independent GELLO checkout and the child inside this project do not synchronize automatically. Publish tested child changes before updating parent gitlinks, and do not reference unavailable commits.

```bash
git -C third-party/agilex-gello-software status --short
git submodule status
git diff --submodule
```

Use setup --skip-submodules to preserve local work. Default setup rejects dirty children. Validate clean-checkout installation when publishing a baseline.

## Commits and PRs

Use concise imperative conventional-prefix subjects. Keep behavior, necessary tests and corresponding docs in one reviewable change. PRs explain the concrete problem/result, affected repositories/revisions, actual checks, hardware status and relevant issues. Do not present simulations as physical acceptance.

## Data and documentation

Raw is immutable; LeRobot outputs are derived. Do not commit data, environments, artifacts or caches. Resolve runtime paths against project roots instead of personal home directories.

Update both READMEs, affected configuration/docs and CHANGELOG when behavior changes. Add assets under the matching docs/en/assets and docs/zh/assets only when content exists. Preserve third-party sources/licenses in THIRD_PARTY_NOTICES.

## Camera changes

Run camera Pyright and unittest discovery in its directory. Run converter dataset-extra pytest and isolated Ruff there. Cross-repository changes require a real root RGB-D round trip checking native values, matching, unchanged raw and camera-failure JS cleanup. Physical USB bandwidth, exposure latency and sustained rate need separate acceptance.

## Bilingual docs and CI

English README.md and Chinese README.zh-CN.md are paired. User pages under docs/en and docs/zh use identical relative paths and top language links. Keep AI rules/stage records out of user manuals.

Make sync prepares only root development dependencies, not submodule upgrades/system/device configuration; full setup remains separate. Make docs validates real local links, routing and paired executable examples. Prose translation still needs review. Root mypy, coverage threshold and pre-commit are not configured and are not reported as passed.

GitHub CI reuses make sync / make verify. Private children require a repository read-only SUBMODULES_READ_TOKEN because default GITHUB_TOKEN may not span repositories. CI does not install the independent converter dataset environment, so integration skips are explicit; this is not full six-repository acceptance. Local checks do not imply the unpublished workflow ran remotely.

Project-wide licensing is undecided: preserve LICENSE's status rather than inventing license terms. Root/child repositories remain independent; documentation normalization does not automatically propagate to other projects.

## Iteration and acceptance gates

Before each edit, reread the saved target and preserve concurrent user work. Synchronize dev and create dev-<task>. Prepare one patch increment of project.version, a current English description and an unreleased CHANGELOG entry before validation; update locks only through uv. Retries and merges do not increment again.

Run make lint, make test and all change-specific checks, then provide the candidate version, summary, results and physical test instructions in the current conversation. Wait for the user's explicit physical-test pass before any commit, including documentation or checkpoint commits. Silence and software-only passes do not count. After confirmation, commit on the working branch and merge dev. Recheck after conflicts or dev advances; obtain renewed confirmation when physical acceptance is affected.

A dev merge does not publish main, tag or deploy. Future release/hotfix merge and cleanup details remain to be confirmed. The PR template records candidate version, automated evidence, user physical acceptance and risks. The 2026-11-08 policy migration has a one-time user authorization to push main directly; it does not waive later gates.
