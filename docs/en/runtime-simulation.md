# Unified runtime simulation (P2)

English | [简体中文](../zh/runtime-simulation.md)

This guide covers the synthetic HAL path. P3 adds [physical HAL backends](hardware-hal.md), whose hardware acceptance is pending. The existing hardware CLI and browser still use their original paths. P0 hardware measurements are accepted. Physical HAL acceptance, legacy raw migration and LeRobot export remain separate work. Simulated success does not establish PiPER-X behavior after communication loss.

## Run and inspect

From this development checkout after `make sync`, run a sensor-only session (two cameras plus a force/torque sensor), or simulated following:

```bash
uv run --frozen agx-runtime run --config config/runtime-sensors.toml --seconds 1
uv run --frozen agx-runtime run --config config/runtime-sim.toml --seconds 1 --confirm yes
uv run --frozen agx-runtime run --config config/runtime-sim.toml --mode sampled --seconds 1 --confirm yes
uv run --frozen agx-runtime run --config config/runtime-extended.toml --seconds 1 --confirm yes
```

The last example includes a leader, follower, two cameras and force/torque. Without `--confirm yes`, following displays the target and requires typing `yes`. Sensor-only sessions require no motion confirmation. The result is a JSON session report with an episode path under `data/raw-v3`. `--data-root` and `--lock-path` override configuration; the default lock is shared with the existing controller.

```bash
uv run --frozen agx-runtime check data/raw-v3/EPISODE_ID
uv run --frozen agx-runtime replay data/raw-v3/EPISODE_ID
uv run --frozen agx-runtime replay data/raw-v3/EPISODE_ID --commands
```

Replace `EPISODE_ID` with the reported directory name. Checking verifies file hashes, native image lengths, boundaries, row counts and selection references. Command replay recomputes mapping/step limiting from the actual observations recorded with each command; it sends no motion. CLI sample replay prints metadata and byte counts; Python `replay_episode()` yields samples containing the original RGB8/Z16 bytes.

## Configuration and lifecycle

Defaults are loaded by `agx_runtime.config.load_config()`, then a TOML file, then explicit overrides. Installed packages also have matching model defaults when the checkout's configuration file is absent. Each `[[devices]]` specifies a synthetic `kind`, ID, optional `axes`, `hz`, interpreter `python`, and optional absolute existing `endpoint`. Only owned subprocesses are terminated. Descriptors must match the configured simulated device and preparation effects.

Every stream needs `role` and `monitor_when`. Control streams must be `control_required`; recording streams normally use `record_required`; `optional` failures warn; unusable samples are excluded from sampled selections, and an epoch change quarantines that optional stream for the rest of the episode. The manifest retains these warnings. Both required roles stop the session on failure. Example cameras are monitored in `READY`, `ALIGN`, `FOLLOWING` and `RECORDING`, including following without recording. New devices do not inherit a return-to-zero policy. `stop_simulated_targets` is the default; explicit `simulated_zero` on a follower uses a new authority and checks fresh valid feedback and limits before every step. Neither policy establishes physical hardware behavior.

| Setting | Default | Meaning |
| --- | --- | --- |
| `record.mode` | `full` | All streams; camera capture can be capped |
| `record.dataset_fps` | `30` | Sampled selection rate, no higher than control rate |
| `record.capture_fps_max` | `90.0` | Full-mode RGB/depth cap; skipped frames counted separately |
| `record.max_skew_ms` | `50.0` | Online camera alignment and sampled selection bound |
| `record.queue_size` | `512` | Nonblocking writer queue; overflow fails the episode/session |
| `record.boundary_timeout_s` | `1.0` | One deadline for all producer boundary confirmations |
| `record.drain_timeout_s` | `5.0` | One deadline for remaining receipt, writes, checks and publication |
| `motion.position_tolerance_deg` | `1.5` | Per-axis arrival tolerance for alignment and explicit simulated zero |
| `runtime.watchdog_s` | `1.0` | Daemon controller heartbeat deadline |

Deadlines must be finite positive numbers. Boundary time starts when save fixes the end time; drain time starts after boundary confirmation. Neither resets per device or with progress. The 1/5 second values are simulation defaults; P4 must measure the new raw path. P0 supports retaining an isolated writer thread and ZMQ frame transport for the measured profiles. This does not establish multi-camera 90 FPS throughput or cover the separate LeRobot export duration.

`full` supports sensor-only and multi-rate force capture. `sampled` supports leader/follower/camera configurations and records target times plus references to selected samples; configurations containing force sensors or lacking a leader are rejected. Legacy `[recording].dataset_fps/queue_size` emit a migration warning, with explicit `[record]` taking precedence. The operator adopted a common 1.5° arrival baseline for CLI, Web and runtime on 2026-11-17 and waived further tolerance experiments. P0 evidence retains the original 1.0°/1.1° criteria and measured residuals.

## Embedded and daemon API

`Session(config)` exposes `prepare`, `confirm(True)`, `record`, `save`, `discard`, `stop`, `status`, `preview`, and `wait`. Calls acknowledge transitions; use status to observe completion. Preparation precedes confirmation and authorization. Save/discard finishes an episode boundary while following continues; another recording is allowed after `FINISHING`. Discard keeps a partial audit directory. Stop interrupts an unsaved episode and releases devices without waiting for disk. A stopped Session cannot be reused; create a new one. Releasing or losing a HAL lease freezes its active episode counters, allowing an existing external HAL to serve the next session without a restart.

```bash
uv run --frozen agx-runtime serve --config config/runtime-sensors.toml --endpoint-dir /tmp/agx-runtime-api
```

Use `RuntimeClient(directory, client_id)` for automation: `acquire`, `prepare`, then send `heartbeat` at intervals shorter than `runtime.watchdog_s`. Poll `status`; issue `record`, `save`, `discard`, `stop` or `shutdown`. Teleoperation additionally requires `confirm(confirmed=True)`. `preview` returns latest metadata, with image byte counts. `status`/`preview` do not renew the heartbeat. The directory must be owned by the user with mode 0700, the socket 0600; existing endpoints are never replaced. There is no TCP listener.

```bash
uv run --frozen agx-runtime request --endpoint-dir /tmp/agx-runtime-api --client-id operator acquire
uv run --frozen agx-runtime request --endpoint-dir /tmp/agx-runtime-api --client-id operator status
uv run --frozen agx-runtime request --endpoint-dir /tmp/agx-runtime-api --client-id operator shutdown
```

These one-shot commands inspect/control the service; an automated active session needs continuous heartbeats.

## Raw v3 and failure handling

An episode starts in `ID.partial`. Per-stream JSONL files retain typed headers, clock/source/freshness fields and epochs; images use native binary files; force samples retain units via the descriptor, frame, reference point, zero bias and calibration ID. The manifest contains produced/received/written/intentional-skipped/transport-lost/write-failed counters and missing sequence ranges. `commands.jsonl` includes the actual control observations, which may precede the recording start; these are audit context, separate from in-boundary stream rows.

The sole committer verifies required counts and writes `complete.json`, then publishes the episode directory. Sampled completion requires at least one valid selection covering every required stream; a recording too short to produce one fails explicitly. Check/replay independently validates descriptors, policies, stream statistics, selection coverage and skew. Failed, discarded or partial episodes are rejected by check/replay. Blocking I/O can continue after timeout, but it cannot promote the episode back to success. Failure/revocation does not wait on the writer or boundary requests; command/lease watchdogs also run inside each HAL. Main errors and cleanup errors are reported separately. Saved episodes remain readable after a later session fault.

```bash
uv run --frozen pytest tests/test_runtime_boundaries.py tests/test_runtime_safety.py tests/test_runtime_recording.py tests/test_runtime_session.py tests/test_runtime_service.py tests/test_runtime_review.py
make verify
```

These checks use synthetic data and local IPC. They do not access serial ports, CAN or physical cameras and do not establish hardware performance or motion acceptance.
