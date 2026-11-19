# Physical HAL development and acceptance (P3)

English | [简体中文](../zh/hardware-hal.md)

P3 wraps the existing PiPER-X, GELLO and RealSense drivers in isolated HAL services. Software tests use injected fake backends and real private IPC; **physical acceptance is pending**. The legacy controller and browser keep their existing paths. Run physical commands only on the experiment computer after host checks and operator authorization; configuration loading and help do not access devices.

## Separate device environments

Install from the repository root. The `hal` extra adds protocol dependencies such as contract/msgpack under each frozen lock; `--inexact` preserves existing optional packages. Wrappers temporarily ship in the root wheel. Installing it with `--no-deps` into each device environment avoids pulling other device dependencies into that environment. The runtime never imports device libraries.

```bash
uv sync --frozen
uv sync --project third-party/agilex-sdk-python --frozen --extra hal --inexact
uv sync --project third-party/agilex-gello-software --frozen --extra hal --inexact
uv sync --project third-party/camera-realsense-d455f --frozen --extra hal --inexact
uv pip install --python third-party/agilex-sdk-python/.venv/bin/python --no-deps -e .
uv pip install --python third-party/agilex-gello-software/.venv/bin/python --no-deps -e .
uv pip install --python third-party/camera-realsense-d455f/.venv/bin/python --no-deps -e .
```

Invoke HALs directly with each environment's interpreter afterward. If an exact resync removes the root application, repeat its `uv pip install --no-deps -e .` command. This arrangement precedes P7 package extraction; separate HAL distributions have not been published. Keep the development root and submodule versions consistent rather than mixing old gitlinks with new root code.

```bash
third-party/agilex-sdk-python/.venv/bin/python -m agx_hal_piperx --help
third-party/agilex-gello-software/.venv/bin/python -m agx_hal_gello --help
third-party/camera-realsense-d455f/.venv/bin/python -m agx_hal_realsense --help
```

## Deployment and preparation effects

Copy and review the [example configuration](../../config/runtime-hardware.example.toml). A device `backend` is `sim`, `gello`, `piperx` or `realsense`; `kind` remains the leader/follower/camera/wrench role. Unknown or incompatible settings fail before startup. Relative device `python` paths resolve against the configuration file, while existing endpoints must be absolute. Existing HALs are connected without being started or terminated.

Replace the stable GELLO port and camera serial, then copy verified calibration and mapping. Example values are installation specific. Encoder offsets/signs differ from the runtime's follower mapping; the HAL does not apply that mapping twice. Keep GELLO `hz` at the established control call frequency, normally 50 Hz; smoothing advances per act call and must not change with status polling.

| Phase | PiPER-X | GELLO | RealSense |
| --- | --- | --- | --- |
| DISCOVER / hello | Connect CAN and start SDK feedback threads without motion settings or enable | PING-only probe without register writes | Enumerate the selected camera without configuration or streaming |
| PREPARE | Mark prepared without enabling | Original initialization disables leader torque and retains offset unfolding/smoothing | Original configuration, streaming, warmup and clock qualification; retain actual profile |
| AUTHORIZE | Write motion limits and enable after confirmation | No follower action | No follower action |
| Stop/fault | Revoke and clear pending targets before applying the selected exit policy | Close serial | Stop and restore settings tracked by the original library |

Preparation is not read-only. Status/metadata queries do not add GELLO act calls; sampling follows the HAL cadence. An uncancellable SDK call may still return. The independent watchdog prevents late results from restoring authority, but cannot retract a target already sent to hardware.

## Running and control policy

Complete read-only, preparation and minimal motion checks without cameras before capture. For physical PiPER-X following, `run` requires a terminal, displays `hardware_motion_target`, and waits for typed `yes`. It rejects `--confirm yes` and piped input. The `serve` command does not permit unattended physical following. Sensor-only capture requires no motion confirmation.

```bash
cp config/runtime-hardware.example.toml config/runtime-hardware.local.toml
uv run --frozen agx-runtime run --config config/runtime-hardware.local.toml --seconds 10
uv run --frozen agx-runtime run --config config/runtime-hardware.local.toml --mode sampled --seconds 10
```

The example explicitly selects `piperx_return_zero`: zero in small steps before alignment. At exit, revoke the old lease first. The same session can then obtain limited cleanup authority only if feedback is fresh, all six joints remain enabled, and state and limit checks pass. Cleanup does not rewrite motion limits, enable or disable the arm. New PiPER-X deployments default to `stop_targets`. Arrival tolerance remains the approved 1.5° without additional tolerance experiments.

The example budgets 30 seconds for startup/lease during preparation; ACTIVE command and acknowledgement watchdogs stay at 0.25 seconds. Long driver calls never hold the authority state lock. A separate HAL thread checks deadlines, management calls remain bounded, and status requests cannot renew valid-control deadlines. Invalid feedback, missing required streams and excessive skew retain error-stop behavior.

## Data and evidence limits

PiPER-X retains SDK feedback time, cache age and origin. Missing gripper feedback preserves earlier measured data with its original age. Without any measurement, unknown/command-filled values are invalid rather than fresh feedback. Wall-to-monotonic mapping rejects wall-clock steps.

GELLO preserves the original Agent.act joint sequence (estimated origin) and converts normalized gripper values to meters. Source time temporarily uses private fields in the pinned library, to be reviewed at P7 or an upgrade. Reads spanning a background source update use the older time with uncertainty.

Cameras retain RGB8/Z16 bytes, depth scale, independent sample/receive times and uncertainty. Optional CameraFrameInfo retains SDK time/domain/frame number/clock offset and a calibration digest reference. The raw manifest stores actual profile/calibration in hal_metadata; checking recomputes calibration digests, dimensions and clock mapping. P2 raw without this optional field remains readable, and legacy frames without provenance retain their wire shape. Consumers must upgrade the contract before receiving new provenance fields.

Use the [runtime simulation guide](runtime-simulation.md) for check/replay. Short fake runs do not establish CAN/USB stability, multi-camera 90 FPS throughput or PiPER-X hardware behavior after command loss. P3 minimal motion and P0 cadence comparison, P4 physical recording/throughput/migration and applicable fault injection remain separate acceptance work. Disconnect behavior stays unverified; software stopping does not establish hardware immobility.
