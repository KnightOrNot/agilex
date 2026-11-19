# Project Overview

AgileX provides teleoperation and RGB-D data capture for researchers using the PiPER-X six-axis follower, GELLO leader, and RealSense D455F. The CLI and browser applications share hardware configuration and an exclusive hardware lock.

| Entry point | Role | Acceptance criteria |
| --- | --- | --- |
| `agilex-controller` | Following, raw capture, JS positioning, and offline conversion | Cleans up on interruption and error; the converter can read complete captures; partial data stays partial |
| `agilex-data-collection` | Browser following, save/discard, preview, and LeLab management | Exercise the lifecycle and read back data in simulation; verify hardware separately; retain native RGB/Z16, calibration, and time provenance |
| `agx-runtime` | Configurable HAL deployment, teleoperation and sensor-only capture, and raw v3 inspection and replay | Check authority, stream integrity, recording, and replay offline; keep physical acceptance separate |

Current acceptance and open work live in the [testing record](docs/stages/testing.md). See the [v3.3 architecture baseline (Chinese source)](docs/specs/architecture-v3.3.md) for the staged HAL migration.

## Modules and dependency boundaries

| Path | Responsibility |
| --- | --- |
| `src/agx_sim/` | Hardware-free HAL simulation |
| `src/agx_hal/` | Common HAL service, control authorization and watchdogs, and producer episode counters |
| `src/agx_hal_piperx/`, `src/agx_hal_gello/`, `src/agx_hal_realsense/` | Existing driver wrappers run in separate device environments |
| `src/agx_transport/` | Private IPC and codecs shared by runtime and HALs |
| `src/agx_runtime/` | Sessions, device supervision, stream checks, joint mapping, raw v3, and a private command service |
| `third-party/agilex-contract/` | Standalone message types and validation; imported as `agilex_contract` |
| `src/agilex_controller/` | Configuration, SDK client and process management, JS following, and legacy raw lifecycle |
| `src/agilex_data_collection/` | Browser UI, workers, preview, direct LeRobot output, and LeLab integration |
| `config/default.toml` | Shared default configuration; the browser also reads `[collection]` |
| `third-party/agilex-sdk-python/` | CAN, arm control and feedback, and the legacy ZMQ service |
| `third-party/agilex-gello-software/` | GELLO and Dynamixel readings and calibration |
| `third-party/camera-realsense-d455f/` | RGB-D, time mapping, depth units, and calibration; imported as `camera_realsense` |
| `third-party/lerobot-converter/` | Legacy raw validation, time matching, and LeRobot output |
| `third-party/agilex-adapters/` | LeRobot Robot and Teleoperator protocols and owner-private Unix IPC |

CAN stays in the SDK, camera capture in the camera library, and conversion in the converter. The browser application reuses lower-level controller helpers and the hardware lock without invoking the legacy `run_workflow`. Preview encoding and point-cloud processing cannot block the control or recording path. Private IPC has a command watchdog; do not expose pickle over TCP.

## Configuration and data contracts

- Use `config/default.toml` as the single application default. When `[collection].hardware_config` is empty, the browser reuses its hardware tables. Explicit experiment configs retain their existing loading behavior.
- The controller ignores `[collection]`. Submodules receive arguments through their public CLI or API and do not implicitly read the parent TOML. The camera and converter ship their own defaults.
- Pass GELLO calibration through `DynamixelRobotConfig` without editing the library's global port table. Encoder `joint_offsets` and `joint_signs` are separate from `follower_signs`.
- Use uv-managed Python 3.12, separate frozen locks, and separate local virtual environments. The root and GELLO require `>=3.12,<3.13`.
- GELLO uses `agilex_gello_software` and PyPI DynamixelSDK 4.0.5. The current layout requires neither the old `gello.*` namespace nor a nested SDK.
- The adapters' `app` extra uses LeRobot 0.6.0 and LeLab `9b5afaee33baa1d773e499937564f3831d25de22`; the converter uses LeRobot 0.6.1. Preserve nested extra dependencies and the CPU torch/torchvision index. Check real dataset readback when changing this stack.
- Keep browser raw data, legacy raw v1/v2, and runtime raw v3 distinct. Preserve native Z16, depth scale, calibration for the actual camera profile, and monotonic timestamps. See [constraints](constraints.md) for data ownership and deletion rules.
- Browser camera `auto` tries 640×360 at 90 FPS first, then falls back based on observed results. Keep explicit legacy profiles and never switch profiles during recording. Point clouds require rectified intrinsics with zero distortion and do not project RGB texture.
- Preview generations and sequence numbers prevent stale frames from crossing sessions. Reserve one of the two viewer slots before accepting a connection. Preview, capture and dataset FPS are separate; a 30 FPS dataset does not imply 90 FPS capture.
- CLI, browser, and runtime share the 1.5° per-axis default arrival tolerance. Preserve measured P0 residuals and original 1.0°/1.1° criteria. See [ADR 0005](docs/decisions/0005-position-tolerance-baseline.md).

## Scope and non-goals

The P3 candidate is 0.2.4 and remains unreleased. See the [runtime simulation guide](../docs/en/runtime-simulation.md) and [hardware HAL guide](../docs/en/hardware-hal.md). The original CLI and browser hardware paths, calibration, data formats, and six submodule pins remain in use. P3 hardware acceptance and later raw migration, LeRobot export, and browser cutover are tracked separately. Force estimation and precision assembly are [research scope](docs/specs/force-estimation.md); they have not been implemented or accepted. Training, inference, SO101 calibration, and Hub deletion are outside the current application scope. A 404 from `/jobs` is expected.

## Terms

| Term | Chinese | Meaning |
| --- | --- | --- |
| Leader / follower | 主手 / 从臂 | GELLO input / PiPER-X actuator |
| JS positioning | 分步定位 | Small JS targets and feedback checks through the existing SDK |
| Z16 | 原始深度 | Native uint16 range multiplied by the device depth scale to obtain meters |
| Episode | 回合 | A capture span that can be saved or discarded |
| Session | 采集会话 | Lifecycle and configuration shared by one or more episodes |
| Wrench | 末端受力 | Three force and three torque components; simulated only in the current HAL path |

## Sources and open facts

- Read [HABITS.md](../HABITS.md) and [AGENTS.md](../AGENTS.md) for project routing. Implementation facts come from the root source, `config/default.toml`, `pyproject.toml`, `.gitmodules`, and the pinned submodules. The Git remote is `git@github.com:KnightOrNot/agilex.git`; the repository rename did not change the Python distribution or CLI names. See [ADR 0003](docs/decisions/0003-habits-branch-gates.md) for the November 8 transition.
- User documentation: [English](../docs/en/index.md) and [简体中文](../docs/zh/index.md). The [October investigation](docs/reviews/history-2026-10.md), earlier Claude notes, actual tool results, and local test reports inform the historical record. User-supplied research summaries are background, not newly verified findings.
- Pending confirmation: Windows RDP login and graphical preview, complete GELLO gripper endpoints, P3 field acceptance, sustained throughput and timing, and the units, interfaces, frequency, and calibration for force estimation Phase 0.
- The project license is still pending confirmation. The root LICENSE records that status; do not substitute a license without the user's decision.
