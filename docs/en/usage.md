# Usage

English | [简体中文](../zh/usage.md)

All environments use uv, `.python-version`, independent `.venv` directories and frozen locks. The CLI and browser are equally supported entry points sharing config, clients and the hardware lock.

## Components

| Component | Responsibility |
| --- | --- |
| Controller | Configuration, SDK lifecycle, following, raw recording |
| Browser application | UI, hardware worker, previews and LeLab integration |
| Adapters | Official LeRobot device protocols and private IPC |
| GELLO | Leader reading/calibration and standalone experiments |
| SDK | CAN, arm commands/feedback and ZMQ |
| Camera | RGB-D, device clocks, units and calibration |
| Converter | Raw validation, matching and LeRobot quality reports |

Root application code lives in `src/`, hardware libraries in five pinned `third-party/` submodules, and defaults in `config/default.toml`. Raw/datasets under `data/` are ignored. GELLO/camera are editable root dependencies; SDK/converter/browser keep separate environments. GELLO imports `agilex_gello_software`, with PyPI DynamixelSDK 4.0.5. See its [README](../../third-party/agilex-gello-software/README.md).

## Installation

Initialize pinned children with submodule sync and update --init; explicit --remote is an upgrade, not ordinary synchronization. Main is the Python 3.12/uv baseline. See [installation](installation.md).

```bash
./scripts/setup.sh
```

To preserve existing child changes during development:

```bash
./scripts/setup.sh --skip-system --skip-submodules
./scripts/setup.sh --check-only
```

Prepare the browser's independent application environment:

```bash
uv run agilex-data-collection setup
```

This installs LeRobot 0.6.0 and pinned LeLab/builds its web app. It needs network and a complete Python 3.12 (uv-managed by default, explicit --python accepted). Log in again after joining dialout.

## Configuration and devices

Both entries read [config/default.toml](../../config/default.toml). Hardware/safety/path tables are shared; the CLI ignores collection while the browser reads it. Empty hardware_config reuses the shared file. Verify actual IDs, radian offsets, signs and gripper endpoints; follower_signs is an additional mapping.

```bash
uv run agilex-controller config
uv run agilex-controller read
uv run agilex-controller status
uv run --project third-party/camera-submodule-d455f camera-realsense info --profiles
```

GELLO read disables torque during initialization and is not strictly read-only. A state-preserving audit uses only Dynamixel PING/READ. SDK status requires CAN readiness; configure the default interface manually when authorized:

```bash
./third-party/agilex-sdk-python/scripts/config_can.sh
```

Paths resolve against project root. See [configuration](reference/config.md).

## CLI following and recording

These commands move real hardware. Prepare the workspace, base and emergency stop, verify devices and keep the operator present. Managed startup displays targets and requires yes.

```bash
./scripts/start_gello_follow.sh
./scripts/start_data_record.sh
```

With native RGB preview:

```bash
./scripts/start_camera_follow.sh
./scripts/start_camera_record.sh
```

The scripts are thin CLI wrappers. Camera variants prepend camera/preview flags, and later user arguments override them. On plain SSH use --no-camera-preview; RGB-D capture remains enabled.

The flow acquires the lock, checks serial/CAN/feedback, displays the target, warms the camera if enabled, starts the owned SDK, zeros/aligns through JS and follows. Ctrl+C/SIGTERM stops commands, releases leader/client, attempts JS zeroing and stops the owned server; then camera/raw flush and optional offline conversion finish.

| Key | Action |
| --- | --- |
| R | Begin an episode, including camera streams when enabled |
| S | Save the episode |
| D | Discard the episode |
| P / H | Status / help |
| Ctrl+C | Exit, retaining active unsaved data as partial |

Only saved episodes convert. Start-recording begins but does not save; skip-conversion keeps raw, and yes bypasses confirmation. Single-key controls require terminal stdin. Cleanup keeps the existing JS mode and does not reset, switch ordinary J mode or automatically disable torque. See [CLI reference](reference/cli.md).

## Browser collection

```bash
uv run agilex-data-collection serve
```

Physical serve prepares configured CAN (default can0 at 1 Mbit/s), allowing sudo to prompt in the terminal. Failure or conflicting ownership prevents startup. HTTP binds to loopback, port 8000 by default; use --port to change it. Keep the terminal alive and open http://127.0.0.1:8000.

Start with synthetic devices:

```bash
uv run agilex-data-collection serve --simulate
```

Simulation avoids devices but writes data. Physical start/stop zeros and aligns, so it needs the documented operator checks. Do not run CLI and browser physical control concurrently.

1. Enter the task description, which is saved with the session.
2. Confirm physical motion (simulation does not require this), then start following. Wait for following; do not submit duplicate starts.
3. Start sampling, wait for recording and perform the task.
4. Save and verify saved_episodes increments, or discard.
5. Repeat within the same session.
6. Save wanted data, stop following and await completed without errors, then Ctrl+C the server.

Closing the page does not stop a session. Stop discards unsaved active sampling, while saved episodes and persisted raw audit remain. Backend guards reject invalid starts with 409 and show the reason.

### Preview

Choose RGB, depth, side-by-side or 3D cloud. Labels distinguish actual browser presentation FPS, observed/target sampling rate and measured capture rate/profile per stream. WebSocket `/api/preview/ws?mode=rgb|depth|rgbd|cloud` sends latest frames at dataset target rate, drops stale display frames and permits two same-origin connections. Encoding/cloud work remains outside control/recording threads.

Cloud is calibrated XYZ in depth-camera meters, colored by depth rather than RGB. Only rectified zero-distortion depth intrinsics are accepted. Display-only max-depth/stride defaults are 3.0 m and 4, capped at 20000 points. Drag orbits, wheel zooms and double-click resets; WebGL is required. Raw/dataset values are unaffected.

### Positioning

The browser uses collection position_tolerance_deg=1.1 for startup zero, GELLO alignment and exit zero, with the existing final-target wait. The CLI defaults to 1.0 independently. Logs identify startup_zero/gello_alignment/exit_zero and six-axis targets, start/final feedback, signed residuals, observed range and successful commands. Primary and cleanup errors remain separate.

Prior operator diagnostics found J3 zero is its upper limit (-170°..0°), with output-side residual near 1° and output/motor differences under load. Do not subtract offsets, automatically recalibrate or change modes to hide residuals. A new physical run requires operator confirmation.

### Data

| Location | Content |
| --- | --- |
| `data/lerobot/app/<session>/` | Direct LeRobot v3, no converter needed |
| `data/raw/app/<session>/manifest.json` | Configuration, calibration, actual profile and throughput metadata |
| `data/raw/app/<session>/take_*/` | Samples timing audit, RGB/Z16 .npy and save/discard outcome |
| `data/logs/<session>.log` | Initialization, failure and cleanup logs |

RGB is video; dataset depth is float32 meters, with raw Z16 and scale retained separately. Defaults are 50 Hz control/30 FPS sampling. Bounded persistence is separated from control; latest frames are checked against robot feedback at the host-monotonic max_skew_ms (default 50). Original timing, counters, clock offsets/uncertainty and command/feedback intervals remain auditable. This is software mapping, not hardware synchronization. Browser raw is not legacy converter input.

### LeLab

The collection home links to `/dataset-browser`, embedding official `/edit-dataset` with a return route. It supports:

- Merge two or more local datasets into a new local/name without modifying sources; names allow letters/digits/dot/underscore/hyphen.
- User-triggered HF upload after authentication, with tags/private settings.
- Confirmed local deletion, guarded against active sessions; no Hub deletion.

Upload shows dataset summary and tags/private; merge hides internal paths. Unavailable recording/teleoperation/training/inference/calibration/new-dataset/tour controls remain disabled. Direct unavailable SPA routes return to the dataset browser. Jobs 404 is expected, not a dataset failure.

The web process uses owner-private Unix IPC to the independent worker, reuses hardware helpers, shares the lock and retains a watchdog. It does not call the legacy workflow. Hardware cleanup precedes dataset flushing.

## Camera profiles and timing

Legacy camera defaults are disabled; camera wrappers request RGB/depth 640×480@30 and enable preview. Inspect supported profiles and specify serial for multiple cameras. No-camera-depth selects RGB only.

Browser auto prioritizes 640×360@90 and falls back through measured 90/60/30. Slow avoids fast candidates; manual uses configured profiles. These rates do not change the independent dataset/control rates. Actual metadata determines the final profile.

Each stream has its own SDK timestamp and calibrated host mapping. Save flushes all image/joint writers; failures stay partial. Converter independently matches joint/RGB/depth against its target timeline and rejects excess skew, reporting actual errors. See [RGB-D and synchronization](cameras.md).

## Legacy raw and conversion

A raw session contains manifest, joint episodes and per-camera frames/indexes. With camera it is piper_x_gello_raw v2, lossless RGB/Z16 PNG; without camera, compatible v1. Rows pair final actions with subsequent observations and monotonic/wall timestamps. Raw remains authoritative.

```bash
uv run agilex-controller convert data/raw/SESSION data/lerobot/DATASET
```

Replace SESSION/DATASET with actual paths. Partial episodes are ignored and existing outputs cannot be overwritten. Output includes meta/data/RGB videos and quality_report; meter depth is losslessly embedded in Parquet. See the [converter](../../third-party/lerobot-converter/README.md).

## Troubleshooting and validation

Use the [error reference](reference/errors.md) for setup, serial/CAN, positioning, previews, timestamps, persistence and LeLab issues. Unavailable job routes are intentional. Never label simulated success as physical acceptance.

```bash
uv run --frozen pytest
uv run --frozen ruff check src tests
uv run --frozen ruff format --check src tests
uv run --project third-party/agilex-adapters --extra app pytest third-party/agilex-adapters/tests -q
uv build
```

These checks do not replace physical throughput/timing or motion validation. The unified Make entry points and contribution process are in [Contributing](../../CONTRIBUTING.md). See the [documentation index](index.md), [CLI](reference/cli.md), [config](reference/config.md), [child config](reference/submodule-config.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md). Project-wide licensing is still undecided; see [LICENSE](../../LICENSE).
