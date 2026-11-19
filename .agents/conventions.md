# Engineering Conventions

These conventions derive from [HABITS.md](../HABITS.md). See the [project overview](project.md) for device, configuration, and data contracts.

## Language and naming

- Communicate in Chinese. Use English for code, identifiers, and documentation unless a document explicitly calls for another language. The original HABITS, existing Chinese source records, and designated Chinese lab runbooks retain their language. See [ADR 0002](docs/decisions/0002-habits-document-layout.md) for the migration.
- Use four-space indentation, type annotations on public Python interfaces, `snake_case` for modules and functions, `PascalCase` for classes, and `test_*.py` for tests.
- Keep `README.md` and `README.zh-CN.md` in sync. Match paths under `docs/en/` and `docs/zh/`, link each translation at the top, and use relative links. Keep terminology, commands, and defaults consistent. Update the relevant user docs and the English changelog when behavior changes.

## Code and dependencies

- Keep simple features in modules. Use `core/`, `services/`, `adapters/`, or `runtime/` when layering helps. Core code must not depend on outer layers; avoid dependency cycles. Do not rearrange runtime code just to match the documentation layout.
- Keep third-party source in pinned Git submodules under `third-party/`. Follow upstream style and avoid unrelated formatting.
- Pair device creation with cleanup and bound RPC waits. Use monotonic clocks for scheduling and time audits, and wall clocks for diagnostics. Complete costly imports before starting hardware so they do not delay the first sample.

## Tooling and tests

- Use uv and the `src/<package>/` layout. Keep package metadata, dependencies, entry points, Ruff settings, and pytest settings in `pyproject.toml`. Let uv manage the lockfile, maintain Python compatibility across local development and CI, and keep `.venv/` local.
- The root Ruff check covers `src`, `tests`, the documentation checker, and `third-party/agilex-contract`. The root project does not configure mypy. The SDK and camera projects maintain their own Pyright settings. See [workflows](workflows.md) for verification commands.
- Test observable behavior at a scope that fits the risk. Relevant cases include configuration, timeouts, errors, interruptions, failed initialization, cleanup order, and data compatibility. Use fake devices, real local ZMQ/IPC and dataset readback as appropriate, and pytest temporary paths instead of the operator lock.
- Keep tests under `tests/`. Add `unit/`, `integration/`, or `eval/` only when tests actually need those categories.
