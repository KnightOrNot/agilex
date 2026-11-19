# Authorization and Constraints

## Workspace and external actions

- Preserve user edits. Obtain authorization for destructive operations, remote changes, releases, outbound messages, paid work, or production actions. Reuse authorization already given for the current scope.
- Do not commit, push, or release without authorization. Earlier one-time exceptions do not carry over. Using a skill, receiving a recommendation, or passing a check grants no authorization; follow the [Git workflow](git.md) for acceptance and branch rules.
- Keep secrets, credentials, local environments, caches, and capture data out of Git. Keep sensitive details out of logs and docs; record redacted identity, results, and evidence locations where needed.
- Report failures honestly. Do not weaken checks or introduce unrelated dependencies, abstractions, or restructuring. Create directories and documents only when they hold useful content.

## Hardware and motion

- Use fake devices, synthetic RGB-D, and local IPC for software tests and CI. Do not access CAN, serial, or cameras during these tests.
- Obtain the relevant authorization for CAN configuration, device access, motion, calibration, and force/torque comparison. See the [testing record](docs/stages/testing.md) for scope and evidence. Permission to configure a host interface does not authorize enabling or moving hardware. A user running a script does not authorize the agent to reproduce the motion.
- Show the target and obtain `yes` before motion. Preserve the browser's unchecked confirmation, backend guard, task and state checks, and duplicate-start protection.
- Motion requires an operator present, a secured arm, a clear workspace, and an available emergency stop. Stop on unexpected displacement, invalid feedback, or jumps. Do not automatically calibrate, subtract offsets, switch control mode, or loosen the arrival tolerance.
- Keep the shared hardware lock across entry points. Do not delete the lock to bypass protection, terminate user-owned services, or clean up anything beyond identified processes this run created.
- Follow the existing JS cleanup policy. Do not automatically reset or disable the arm. Inspect current SDK behavior before using a path other than `read` for read-only work. GELLO initialization via `agilex-controller read` writes torque-off; use only PING/READ for a strictly read-only GELLO probe.
- Force estimates are read-only by default. Closed-loop use requires a design for filtering, saturation, deadband, watchdogs, and force and torque limits. Research formulas alone do not constitute a controller.

## Data and external services

- Treat `data/raw/` as immutable. Do not remove or overwrite it, or edit partial data to look complete. Keep synthetic and operator data separate. `data/lerobot/` is reproducible output and still requires authorization to delete.
- Preserve native Z16, calibration, monotonic clock provenance, and save/discard records. Preview cannot modify captured data.
- Hugging Face uploads must be initiated and authenticated by the user. Do not publish to test an upload. The application may delete only derived output inside the configured root and must protect active sessions. It provides no Hub deletion.
- Remote desktop configuration, exposed ports, and persistent permission changes need their own authorization. A successful SSH or RDP connection is not evidence of robot safety or motion acceptance.
