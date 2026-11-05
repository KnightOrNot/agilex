# CLI reference

English | [简体中文](../../zh/reference/cli.md)

General form:

```bash
uv run agilex-controller [--project-root PATH] [--config FILE] COMMAND [OPTIONS]
```

Common options can follow the subcommand. Editable installations infer their checkout; wheel users should pass `--project-root`. `--config` is relative to the caller's working directory, defaulting to project `config/default.toml`. Every command supports hardware-free `--help`.

## Commands

| Command | Behavior |
| --- | --- |
| `config` | Print effective configuration JSON |
| `read [--gello-port PATH] [--json]` | Initialize physical GELLO, disabling torque, read with project calibration, then close |
| `status [--can-interface IF] [--sdk-project PATH]` | Read arm state using the SDK environment |
| `follow` | Managed preflight, zero/alignment, following and cleanup |
| `record` / `follow-record` | Managed following with episodes and optional automatic conversion |
| `movejs` | Small-step positioning and feedback acceptance through an existing service |
| `convert SESSION OUTPUT` | Offline conversion in the converter environment |

Read/follow/positioning share the application lock. `read` is not a strict read-only audit: driver initialization writes torque disable. For state-preserving checks use only Dynamixel PING/READ.

## Follow and record

| Option | Default / meaning |
| --- | --- |
| `--gello-port PATH` | Stable configured by-id port |
| `--host HOST` / `--hostname HOST` | `127.0.0.1` |
| `--port N` / `--robot-port N` | `6001` |
| `--hz HZ` | `50`, control/raw sample rate |
| `--can-interface IF` | `can0` |
| `--can-bitrate N` | `1000000` |
| `--sdk-project PATH` | SDK checkout |
| `--joint-signs S1 ... S6` | Override follower signs; each ±1 |
| `--max-start-error-rad RAD` | `0.35` |
| `--transition-step-rad RAD` | `0.02`, maximum 0.05 |
| `--max-command-step-rad RAD` | `1.0`, maximum 1.0 |
| `--request-timeout-s SEC` | `2.0`, per RPC |
| `--startup-timeout-s SEC` | `15.0`, service readiness |
| `--camera` / `--no-camera` | Camera disabled in default TOML; enabled by camera wrappers |
| `--camera-depth` / `--no-camera-depth` | Native depth enabled by default |
| `--camera-preview` / `--no-camera-preview` | RGB window, enabled by camera wrappers |
| `--camera-serial SERIAL` | Select device |
| `--camera-width N` / `--camera-height N` / `--camera-fps N` | RGB profile; configure depth in TOML |
| `--camera-png-compress-level N` | Lossless level 0..9; default 0, fastest/larger files, both streams |
| `--yes` | Skip one motion confirmation |
| `--skip-can-setup` | Reuse CAN, still validate SDK feedback |
| `--existing-server` | Skip local CAN/SDK preflight and owned server management |

Managed host addresses must be locally bindable. An existing server requires the explicit flag; this still includes startup zero/alignment and exit zeroing.

Record-only options:

| Option | Default / meaning |
| --- | --- |
| `--raw-data-root PATH` | `data/raw` |
| `--lerobot-data-root PATH` | `data/lerobot` |
| `--converter-project PATH` | `third-party/lerobot-converter` |
| `--task TEXT` | Nonempty session task |
| `--record-queue-size N` | `500` |
| `--dataset-fps FPS` | `30`, offline output only |
| `--start-recording` | Start first episode after alignment |
| `--no-start-recording` | Wait for R |
| `--skip-conversion` | Keep raw only |

R starts, S saves, D discards, P shows state and H help. Single-key controls require a terminal. Ctrl+C/SIGTERM perform cleanup; active unsaved episodes stay partial.

## Movejs

```bash
uv run agilex-controller movejs --joints 0 0 0 0 0 0 --gripper 0.5
```

Requires a running SDK server. Supports host/port aliases, `--request-timeout-s`, six-radian `--joints` (default zeros), `--gripper` (0..1, default current), `--step-rad` (0.02), `--period` (0.02 s) and `--tolerance-deg` (1.0). It checks final feedback and fails if outside tolerance.

This direct positioning command does not start a server or provide managed-follow confirmation/exit zeroing. The browser's configured 1.1° is separate from this CLI default.

## Convert

```bash
uv run agilex-controller convert data/raw/SESSION data/lerobot/DATASET \
  --fps 30 --repo-id local/demo
```

Supports `--converter-project`, `--fps`, `--repo-id`, `--without-velocity`, `--without-ee-pose` and positive finite `--max-camera-skew-ms`. Session/output paths use the caller working directory; the converter project path uses the controller root.

The controller launches the child's `.venv/bin/python` rather than importing its dataset stack, preserving exit codes. No hardware is opened; output must not already exist.

## Browser application

```bash
uv run agilex-data-collection setup [--python 3.12]
uv run agilex-data-collection serve [--simulate] [--port 8000] [--config FILE]
```

Setup synchronizes the independent adapters app environment and needs network. Serve reads `[collection]` from the shared config; physical serve prepares CAN from `[robot]`. Simulation skips all device access and CAN but still persists synthetic data. The port must be 1..65535, default 8000.

The page provides start/sample/save/discard/stop, four previews and the official LeLab browser at `/dataset-browser`, with merge/upload/local delete. Closing the page does not stop the session; use Stop or server Ctrl+C.

## Wrappers and exit codes

| Script | Default behavior |
| --- | --- |
| `scripts/start_gello_follow.sh` | `follow`, camera-free |
| `scripts/start_data_record.sh` | `record`, camera-free |
| `scripts/start_camera_follow.sh` | `follow --camera --camera-preview` |
| `scripts/start_camera_record.sh` | `record --camera --camera-preview` |

User arguments follow wrapper defaults, so `--no-camera-preview` can override them. All wrappers resolve the root environment and shared lock from any working directory. Record uses R/S/D and preserves interrupted partials.

Success, cancellation and clean managed interruption return 0; application/cleanup errors 1; argument syntax 2; interrupted unmanaged operations 130. Conversion failures preserve child status. Control/cleanup errors prevent automatic conversion; saved raw remains available offline.
