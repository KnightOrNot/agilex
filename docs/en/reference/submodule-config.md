# Submodule configuration

English | [简体中文](../../zh/reference/submodule-config.md)

The root parses its application config and explicitly passes public CLI/API arguments. Children do not implicitly read a parent TOML. SDK drivers/CAN scripts and native GELLO YAML/upstream tools keep their own behavior.

| Child | Scope | Override |
| --- | --- | --- |
| camera-realsense | Capture, outputs, experiments and performance presets | `camera-realsense --config PATH rgbd` |
| agilex-gello-software | Leader port/calibration | Explicit `DynamixelRobotConfig`; standalone CLI parameters |
| agilex-sdk-python | Channel, host, port, hz | Explicit server arguments and standalone `--channel` etc. |
| lerobot-converter | Paths, FPS, features, matching | `lerobot-converter --config PATH INPUT OUTPUT` |
| agilex-adapters | Piperx/gello endpoint, timeout | `PiperXConfig(endpoint=..., timeout_s=...)` / `GelloConfig` |

Camera/converter retain independent `config/default.toml` files. Current main SDK/GELLO/adapters use public CLI/API parameters. Unknown fields, wrong types and nonfinite values fail. Data paths follow each CLI's cwd rules; locating the packaged default itself is cwd-independent.

Camera/converter source default.toml links point to a single repository source and are materialized in wheels. Do not maintain a second copy. Explicit low-level Python arguments remain explicit instead of implicitly injecting CLI defaults into drivers.

## Camera modes

Auto prioritizes 640×360@90, accepting each stream only when measured receipt reaches at least 85% of target. It falls back through 90/60/30, preserving baseline profile dimensions for the final 30 FPS candidate. ColorStream owns candidate order/thresholds. Preserve native Z16, depth scale and final calibration. Switching occurs before first delivery, never midway through recording or by resetting clocks/counters. Startup probing does not validate disk throughput.

The browser selects camera_mode in `[collection]`, default auto. Slow probes lower rates directly; manual uses configured dimensions/FPS. Explicit legacy controller profiles retain their manual semantics. A 90 FPS camera does not automatically change dataset FPS.

See child [camera configuration](../../../third-party/camera-submodule-d455f/docs/reference/config.md) and application [configuration](config.md). Actual physical throughput requires separate validation.
