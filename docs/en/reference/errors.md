# Troubleshooting

English | [简体中文](../../zh/reference/errors.md)

## Configuration and startup

| Symptom | Action |
| --- | --- |
| Invalid config, dimensions or signs | Inspect effective `config`, supported fields and ±1 sign values before hardware startup |
| Missing/inaccessible GELLO serial | Check by-id identity, target permissions and active dialout membership |
| SDK path/interpreter missing | Initialize pinned submodules and prepare the SDK's independent environment |
| SDK endpoint cannot bind | Stop the conflicting owned workflow normally or explicitly select an existing server; do not attach accidentally |
| RPC timeout/incomplete feedback | Check actual CAN/power/estop state, bitrate, bus traffic and endpoint; do not continue with stale state |
| Startup joint mismatch | Inspect calibration, multi-turn branch and leader/follower position; do not bypass error checks |
| JS positioning failed | Inspect six-axis feedback and residuals; CLI defaults to 1.0°, browser uses its configured 1.1° |

```bash
ip -details -statistics link show can0
uv run agilex-controller status
```

Use status only with configured CAN. GELLO read initializes torque-disable and is not strictly read-only; strict probes must preserve state and send only PING/READ.

## Recording and conversion

R starts, S saves, D discards; without S there is no complete convertible episode. Partial files are intentionally ignored. Raw is authoritative and should not be overwritten or renamed to fake completion. Non-terminal stdin disables single-key controls.

Writer overflow/errors fail visibly. Current fixed-filter lossless PNG defaults to level 0; inspect disk space, CPU, USB and write rate before reducing sampling/profile rates. `--no-camera-preview` can reduce display overhead. Bigger queues do not fix sustained underperformance. Recheck skew requirements whenever rates change.

The converter runs in a separate environment; its output directory must not exist. Install its dataset extra and system FFmpeg/libusb dependencies. Binary import failures require checking the pinned ABI, not only installation success. Conversion ignores partials and preserves raw. Inspect quality_report for frames, timing errors and reuse.

## Browser application

| Symptom | Action |
| --- | --- |
| Setup required | Run browser application setup in addition to root sync |
| Start disabled / POST start 409 | Fill task, confirm physical motion and wait for prior session cleanup |
| Port 8000 in use | Stop the appropriate existing server or choose serve --port 8001 |
| Error during initialization | Inspect page diagnostics and `data/logs/<session>.log`, then resolve device ownership, permissions or CAN |
| Another workflow owns the lock | Stop that workflow normally; do not delete the lock to bypass ownership |
| Startup/exit zero failure | Inspect position_result feedback/residuals and read-only diagnostics; do not relax configured acceptance |
| Unstable fast camera mode | Stop the session and choose slow before restarting |
| Depth/cloud unavailable | Enable depth, start following and verify rectified zero-distortion depth intrinsics |
| Cloud absent | Enable WebGL, refresh and close extra viewers; maximum two preview connections |
| Low sample FPS / max_skew error | Inspect camera/USB/disk/load; keep dataset_fps no higher than control_hz |
| New dataset absent from LeLab | Save at least one episode, verify saved_episodes, stop and refresh |
| Merge disabled | Select two or more local datasets and a legal alphanumeric/dot/underscore/hyphen name |
| Upload failed | Authenticate with HF and check network; publishing is user-triggered |
| Delete rejected | Stop an active owner session; only local copies can be deleted through the app |
| Disabled controls / Couldn't load jobs | Unimplemented recording/training/calibration features are disabled; jobs 404 is expected |

Closing a browser does not stop following. Use Stop or server Ctrl+C and wait for cleanup. If shutdown fails, errors remain visible; the application does not automatically reset, switch modes or disable the arm.

## Camera and matching

- Missing/multiple devices: check USB/udev and specify serial. Use --no-camera for the legacy camera-free workflow.
- Unsupported profile: inspect info --profiles; USB 2 may not sustain requested bandwidth.
- Startup timeout: all enabled streams need fresh global/system-domain frames; do not replace exposure timestamps with receipt times.
- Stalled stream/disconnect/writer failure: the workflow fails and attempts JS cleanup; the active episode is not published. Inspect disk, USB, CPU and actual rate.
- Clock jump/host sampling window: restart a session after diagnosing host time services; existing alignment is invalid.
- Matching error: inspect indexes/completeness; increasing --max-camera-skew-ms relaxes quality rather than removing error.
- Depth readback: specify depth_output_unit="m"; zero means invalid, and the locked default readback is mm.

## Remote startup

| Symptom | Cause and action |
| --- | --- |
| exec: uv: not found | Verify uv in the normal terminal PATH; activating .venv is insufficient |
| Serial exists but is inaccessible | Check target ownership and active dialout membership; refresh login after group changes |
| camera preview failed | Inspect the preview subprocess's original error; on plain SSH use --no-camera-preview |
| Windows RDP 0x204 | Check that the server is enabled, configured and listening, then network/firewall rules; a client error alone does not identify the cause |

`PiPER-X JS target reached` during cleanup reports that positioning target, not successful camera preview or full-session acceptance. See [remote operation](../installation.md).
